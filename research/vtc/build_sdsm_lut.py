import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ==========================================
# [0] 경로 동적 할당
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "513데이터.csv")

# ==========================================
# [1] 공통 환경 파라미터 (Hard/Soft Constraints)
# ==========================================
BASE_CONFIG = {
    "MAX_N": 128.0,                    # N 정규화용 최대값 (513-Byte 기준)
    "LATENCY_DEADLINE": 100.0,         # 지연 시간 정규화용 최대값 (ms)
    "TARGET_PDR": 0.99,                # Hard Constraint: 최소 허용 성공률
    "DESIRED_PDR": 0.999               # Soft Goal: 목표 성공률
}

# ==========================================
# [2] 3가지 최적화 모드 (Weights 튜닝)
# ==========================================
MODES = {
    "1_Overhead_Focused": {
        "W_LATENCY": 2.0,
        "W_OVERHEAD": 2.0,
        "ALPHA_PENALTY": 3.0,
        "TITLE_SUFFIX": "Overhead Focused"
    },
    "2_Latency_Focused": {
        "W_LATENCY": 10.0,
        "W_OVERHEAD": 2.0,
        "ALPHA_PENALTY": 15.0,
        "TITLE_SUFFIX": "Latency Focused"
    },
    "3_Balanced": {
        "W_LATENCY": 10.0,
        "W_OVERHEAD": 6.0,
        "ALPHA_PENALTY": 15.0,
        "TITLE_SUFFIX": "Balanced"
    }
}

# ==========================================
# [3] 최적해 추출 함수 (DataFrame을 직접 받아서 처리)
# ==========================================
def extract_robust_policy(df_raw, mode_name, weights):
    df = df_raw.copy()

    # --- Step 1: 하드 제약 필터링 ---
    feasible_mask = df['Success_Rate_URLLC'] >= BASE_CONFIG["TARGET_PDR"]

    # --- Step 2: 완벽한 정규화 기반 Cost 계산 ---
    norm_latency = df['Expected_Latency'] / BASE_CONFIG["LATENCY_DEADLINE"]
    norm_overhead = df['Action_N'] / BASE_CONFIG["MAX_N"]

    df['Cost'] = (weights["W_LATENCY"] * norm_latency) + (weights["W_OVERHEAD"] * norm_overhead)

    # --- Step 3: PDR 페널티 가산 ---
    max_pdr_gap = BASE_CONFIG["DESIRED_PDR"] - BASE_CONFIG["TARGET_PDR"]
    penalty_mask = df['Success_Rate_URLLC'] < BASE_CONFIG["DESIRED_PDR"]

    normalized_pdr_gap = (BASE_CONFIG["DESIRED_PDR"] - df.loc[penalty_mask, 'Success_Rate_URLLC']) / max_pdr_gap
    df.loc[penalty_mask, 'Cost'] += weights["ALPHA_PENALTY"] * normalized_pdr_gap

    # 하드 제약 탈락자는 Cost 무한대 처리
    df.loc[~feasible_mask, 'Cost'] = float('inf')

    # --- Step 4: 최적해 선정 ---
    idx = df.groupby(['PDR_Env', 'Burst_1_over_r'])['Cost'].idxmin()
    optimal_policy = df.loc[idx].reset_index(drop=True)
    optimal_policy['Is_Feasible'] = optimal_policy['Cost'] != float('inf')

    return optimal_policy

# ==========================================
# [4] 시각화 함수 (SCI/IEEE 논문 출판용 PDF 포맷)
# ==========================================
def plot_robust_heatmaps(df_policy, save_path):
    plot_df = df_policy.copy()
    plot_df.loc[~plot_df['Is_Feasible'], 'Action_N'] = np.nan
    plot_df.loc[~plot_df['Is_Feasible'], 'Action_G'] = np.nan

    pivot_n = plot_df.pivot(index='PDR_Env', columns='Burst_1_over_r', values='Action_N').sort_index(ascending=False)
    pivot_g = plot_df.pivot(index='PDR_Env', columns='Burst_1_over_r', values='Action_G').sort_index(ascending=False)

    # 논문 삽입 시 찌그러지지 않도록 비율(14:5.5) 조정
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    # 🌟 논문용 팁: Suptitle은 과감히 삭제! (LaTeX 캡션으로 대체함)

    # -----------------------------------------------------
    # Heatmap 1: Optimal N (Redundancy)
    # -----------------------------------------------------
    sns.heatmap(pivot_n, annot=True, fmt=".0f", cmap="YlOrRd", ax=axes[0],
                cbar_kws={'label': 'Optimal $N$'}, linewidths=.5,
                annot_kws={"size": 15, "weight": "bold"}, # 칸 안의 글씨 크게!
                mask=pivot_n.isnull())

    axes[0].set_title('Optimal Redundancy ($N$)', fontsize=18, fontweight='bold', pad=15)
    axes[0].set_xlabel('Burst Length ($1/r$)', fontsize=16, fontweight='bold')
    axes[0].set_ylabel('Target PDR', fontsize=16, fontweight='bold')
    axes[0].set_facecolor('lightgray') # Outage 영역
    axes[0].tick_params(axis='both', which='major', labelsize=14)

    # -----------------------------------------------------
    # Heatmap 2: Optimal G (Gap)
    # -----------------------------------------------------
    sns.heatmap(pivot_g, annot=True, fmt=".0f", cmap="YlGnBu", ax=axes[1],
                cbar_kws={'label': 'Optimal $G$'}, linewidths=.5,
                annot_kws={"size": 15, "weight": "bold"},
                mask=pivot_g.isnull())

    axes[1].set_title('Optimal Interleaving Gap ($G$)', fontsize=18, fontweight='bold', pad=15)
    axes[1].set_xlabel('Burst Length ($1/r$)', fontsize=16, fontweight='bold')
    axes[1].set_ylabel('', fontsize=16) # y축 라벨 중복 방지 (깔끔하게 비움)
    axes[1].set_facecolor('lightgray')
    axes[1].tick_params(axis='both', which='major', labelsize=14)

    plt.tight_layout()

    # 🌟 DPI 600의 고해상도 PDF 벡터 이미지로 저장!
    plt.savefig(save_path, dpi=600, bbox_inches='tight', format='pdf')
    plt.close()

# ==========================================
# [5] 메인 실행부 (단일 로드 -> 3번 최적화)
# ==========================================
if __name__ == "__main__":
    print(f"🚀 원본 데이터 로드 중: {CSV_PATH}")
    try:
        raw_df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {CSV_PATH}")
        exit()

    for mode_name, weights in MODES.items():
        print(f"\n======================================")
        print(f"🔍 [Mode] {weights['TITLE_SUFFIX']} 최적화 진행 중...")

        # 1. 정책 추출
        policy_df = extract_robust_policy(raw_df, mode_name, weights)

        # 2. 파일 저장 경로 설정 (확장자를 PDF로 변경!)
        lut_path = os.path.join(BASE_DIR, f"513LUT_{mode_name}.csv")
        pdf_path = os.path.join(BASE_DIR, f"513Heatmap_{mode_name}.pdf") # PNG -> PDF

        # 3. CSV 저장
        policy_df.to_csv(lut_path, index=False)
        print(f"✅ CSV 저장 완료: {lut_path}")

        # 4. 히트맵 시각화 (인자 2개로 축소)
        plot_robust_heatmaps(policy_df, pdf_path)
        print(f"✅ 논문용 PDF 이미지 저장 완료: {pdf_path}")

    print("\n🎉 모든 모드의 최적화 및 논문용 Figure 추출이 완료되었습니다!")
