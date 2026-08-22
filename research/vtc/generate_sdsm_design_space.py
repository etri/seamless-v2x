import numpy as np
import pandas as pd
import itertools
import multiprocessing as mp
import time
from tqdm import tqdm
import os

# ==========================================
# [1] 시뮬레이션 하이퍼파라미터 세팅
# ==========================================
K_REQUIRED = 27        # 원본 심볼 수 (19Byte * 27개 = 513Byte)
ITERATIONS = 100000    # 각 조합당 독립 시행 횟수 (10만 번)

# V2X 물리 계층 하드 제약 조건
BASE_DELAY_MS = 15.0
T_TX_MS = (1500.0 / 2600.0) * 0.5   # 약 0.288 ms
DEADLINE_MS = 100.0                 # 데드라인 (이후 도착은 쓰레기)
MAX_INDEX_DIFF = 294                # 수신 버퍼 제약

# State (환경 변수) - 이전 턴의 세밀한 튜닝값 유지
PDR_LIST = np.round(np.arange(0.45, 0.96, 0.1), 2).tolist() # [0.45, ..., 0.95]
BURST_LIST = [2, 3, 5, 10, 20, 40]                          # 세밀하게 쪼갠 r 값

# Action (전략 변수)
N_LIST = list(range(40, 129, 1))                            # 40 ~ 128
G_LIST = [0, 1, 2]                                    # G 확장 (Burst 방어용)

# ==========================================
# [2] Gilbert-Elliot 채널 파라미터 계산기
# ==========================================
def get_ge_params(pdr_target, burst_len):
    loss_prob_good = 0.01
    loss_prob_bad = 0.80
    p_bg = 1.0 / burst_len

    target_plr = 1.0 - pdr_target

    if target_plr <= loss_prob_good: p_gb = 0.0
    elif target_plr >= loss_prob_bad: p_gb = 1.0
    else:
        target_p_bad = (target_plr - loss_prob_good) / (loss_prob_bad - loss_prob_good)
        p_gb = (target_p_bad * p_bg) / (1.0 - target_p_bad)

    return p_gb, p_bg, loss_prob_good, loss_prob_bad

# ==========================================
# [3] 고속 벡터화 시뮬레이션 엔진 (Memory Safe)
# ==========================================
def simulate_case(args):
    pdr_target, burst_len, N, G = args
    p_gb, p_bg, loss_prob_good, loss_prob_bad = get_ge_params(pdr_target, burst_len)

    span = (N - 1) * (G + 1) + 1

    # ---------------------------------------------------------
    # 🛡️ 메모리 방어 1단계: float32 다운캐스팅
    # N이 128로 커져도 ITERATIONS가 10만이므로 메모리 매우 쾌적!
    # ---------------------------------------------------------
    transitions = np.random.rand(ITERATIONS, span).astype(np.float32)
    drops = np.random.rand(ITERATIONS, span).astype(np.float32)
    states = np.zeros((ITERATIONS, span), dtype=np.int8)

    steady_bad_prob = p_gb / (p_gb + p_bg) if (p_gb + p_bg) > 0 else 0
    states[:, 0] = (np.random.rand(ITERATIONS) < steady_bad_prob).astype(np.int8)

    for t in range(1, span):
        prev_state = states[:, t-1]
        to_bad = (prev_state == 0) & (transitions[:, t] < p_gb)
        to_good = (prev_state == 1) & (transitions[:, t] < p_bg)
        states[:, t] = prev_state
        states[to_bad, t] = 1
        states[to_good, t] = 0

    drop_probs = np.where(states == 1, loss_prob_bad, loss_prob_good)
    is_lost = drops < drop_probs  # bool 배열 생성

    # ---------------------------------------------------------
    # 🛡️ 메모리 방어 2단계: 다 쓴 거대 배열 즉시 파기
    # ---------------------------------------------------------
    del transitions
    del drops
    del states
    del drop_probs

    tx_indices = np.arange(0, span, G + 1)
    tx_success = ~is_lost[:, tx_indices]

    del is_lost # 원본 is_lost 파기

    # ---------------------------------------------------------
    # [핵심 로직] 조기 종료(Early Termination) 및 하드 제약 검사
    # K=27 을 기준으로 판별
    # ---------------------------------------------------------
    cumulative_success = np.cumsum(tx_success, axis=1)

    is_overall_success = cumulative_success[:, -1] >= K_REQUIRED

    kth_idx = np.argmax(cumulative_success == K_REQUIRED, axis=1)
    actual_kth_tx_index = tx_indices[kth_idx]

    first_idx = np.argmax(cumulative_success == 1, axis=1)
    actual_first_tx_index = tx_indices[first_idx]

    kth_latency_ms = BASE_DELAY_MS + (actual_kth_tx_index * T_TX_MS)
    index_diff = actual_kth_tx_index - actual_first_tx_index

    # ⭐ V2X 엄격한 하드 제약 판별
    is_urllc_success = is_overall_success & \
                       (kth_latency_ms <= DEADLINE_MS) & \
                       (index_diff <= MAX_INDEX_DIFF)

    urllc_success_rate = np.mean(is_urllc_success)

    if np.any(is_urllc_success):
        expected_latency = np.mean(kth_latency_ms[is_urllc_success])
    else:
        expected_latency = 100.0

    return {
        'PDR_Env': pdr_target,
        'Burst_1_over_r': burst_len,
        'Action_N': N,
        'Action_G': G,
        'Success_Rate_URLLC': urllc_success_rate,
        'Expected_Latency': expected_latency,
        'Coding_Rate': K_REQUIRED / N
    }

# ==========================================
# [4] 멀티프로세싱 실행기 (CPU 버닝)
# ==========================================
if __name__ == '__main__':
    print("🔥 ARGUS High-Resolution Offline Simulator (513-Byte URLLC Edition) 🔥")

    tasks = list(itertools.product(PDR_LIST, BURST_LIST, N_LIST, G_LIST))
    print(f"총 조합 수: {len(PDR_LIST)} x {len(BURST_LIST)} x {len(N_LIST)} x {len(G_LIST)} = {len(tasks)} Cases")

    start_time = time.time()

    # ---------------------------------------------------------
    # N이 커졌지만 ITERATIONS가 1/5이므로 메모리에 여유가 생겼습니다.
    # 코어를 8개까지 늘려 연산 속도를 확보합니다.
    # ---------------------------------------------------------
    cpu_cores = 8
    print(f"🚀 M3 Pro 메모리 최적화 모드: {cpu_cores} Core 가동 시작!")

    results = []
    with mp.Pool(processes=cpu_cores) as pool:
        for res in tqdm(pool.imap_unordered(simulate_case, tasks), total=len(tasks), desc="Simulating"):
            results.append(res)

    df_results = pd.DataFrame(results)
    df_results.sort_values(by=['PDR_Env', 'Burst_1_over_r', 'Action_N', 'Action_G'], inplace=True)

    csv_filename = "513데이터.csv"
    df_results.to_csv(csv_filename, index=False)

    elapsed_time = time.time() - start_time
    print(f"✅ 시뮬레이션 완료! 총 소요 시간: {elapsed_time/60:.2f} 분")
    print(f"💾 완벽한 513-Byte 물리 데이터가 '{csv_filename}'에 저장되었습니다.")
