import pandas as pd
import numpy as np

# ==========================================
# 1. 데이터 로드 및 초기화
# ==========================================
df = pd.read_csv('channel_metrics_pred.csv')
if 'Window_ID' not in df.columns:
    df['Window_ID'] = df.index + 1

df['speed_ms'] = df['speed_kmh'] / 3.6
K, W, sigma_P_min, sigma_B_min = 0.003817, 20, 0.01, 1.0
kappa_P, gamma_B = 3.0, 1.5

# ==========================================
# 2. 통계량 및 마진(Margin) 연산
# ==========================================
df['mu_P'] = df['PDR'].expanding().mean().shift(1).fillna(df['PDR'].iloc[0])
df['mu_B'] = df['Max_Burst'].expanding().mean().shift(1).fillna(df['Max_Burst'].iloc[0])
df['var_P_inf'] = df['PDR'].expanding().var().shift(1).fillna(df['PDR'].var())
df['var_B_inf'] = df['Max_Burst'].expanding().var().shift(1).fillna(df['Max_Burst'].var())
df['var_B_roll'] = df['Max_Burst'].rolling(window=W, min_periods=1).var().shift(1).fillna(df['Max_Burst'].var())

rho = np.maximum(0, 1 - K * (df['speed_ms'] ** 2))
P_mean_t = df['mu_P'] + rho * (df['PDR'] - df['mu_P'])
B_mean_t = df['mu_B'] + rho * (df['Max_Burst'] - df['mu_B'])

var_P_eff_t = df['var_P_inf'] * (1 - rho**2) + kappa_P * (P_mean_t * (1 - P_mean_t)) / 100.0
sigma_P_eff_t = np.maximum(np.sqrt(np.maximum(0, var_P_eff_t)), sigma_P_min)

var_B_eff_t = df['var_B_inf'] * (1 - rho**2) + gamma_B * df['var_B_roll'] + sigma_B_min**2
sigma_B_eff_t = np.sqrt(np.maximum(0, var_B_eff_t))

z_values = [0.00, 0.60, 0.95, 1.99]

# ==========================================
# 3. 파일 포맷 통일하여 8개 CSV 굽기 (Causal Shift 적용)
# ==========================================
for z in z_values:
    # --- (1) ARGUS (Proposed) CSV 생성 ---
    argus_df = pd.DataFrame()
    argus_df['Window_ID'] = df['Window_ID']
    argus_df['PDR'] = df['PDR']
    argus_df['Max_Burst'] = df['Max_Burst']
    argus_df['speed_kmh'] = df['speed_kmh']

    # 💡 칼럼명 'Pred_PDR_cons' 로 고정
    argus_df['Pred_PDR_cons'] = np.round(np.clip(P_mean_t - z * sigma_P_eff_t, 0.0, 1.0), 2).shift(1)
    argus_df['Pred_B_cons'] = np.ceil(np.clip(B_mean_t + z * sigma_B_eff_t, 0.0, 100.0)).shift(1)

    argus_df.loc[:4, 'Pred_PDR_cons'] = 0.0
    argus_df.loc[:4, 'Pred_B_cons'] = 100
    argus_df['Pred_B_cons'] = argus_df['Pred_B_cons'].fillna(100).astype(int)
    argus_df.to_csv(f'prediction_results_z{z:.2f}.csv', index=False)

    # --- (2) NAIVE (Baseline) CSV 생성 ---
    naive_df = pd.DataFrame()
    naive_df['Window_ID'] = df['Window_ID']
    naive_df['PDR'] = df['PDR']
    naive_df['Max_Burst'] = df['Max_Burst']
    naive_df['speed_kmh'] = df['speed_kmh']

    # 💡 [핵심] NAIVE 파일이라도 칼럼명은 똑같이 'Pred_PDR_cons' 사용
    naive_df['Pred_PDR_cons'] = np.round(np.clip(df['PDR'] - z * sigma_P_eff_t, 0.0, 1.0), 2).shift(1)
    naive_df['Pred_B_cons'] = np.ceil(np.clip(df['Max_Burst'] + z * sigma_B_eff_t, 0.0, 100.0)).shift(1)

    naive_df.loc[:4, 'Pred_PDR_cons'] = 0.0
    naive_df.loc[:4, 'Pred_B_cons'] = 100
    naive_df['Pred_B_cons'] = naive_df['Pred_B_cons'].fillna(100).astype(int)
    naive_df.to_csv(f'naiveprediction_results_z{z:.2f}.csv', index=False)

print("✅ 8개의 CSV 파일 생성 완료. 시뮬레이터 구동 준비 끝!")