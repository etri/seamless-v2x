import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. IEEE journal publication style (single-column real scale)
# ==========================================
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'mathtext.fontset': 'stix',
    'font.size': 8,
    'axes.labelsize': 8,
    'axes.titleweight': 'bold',
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'lines.linewidth': 1.5,
    'axes.linewidth': 0.6
})

# ==========================================
# 2. 데이터 로드 및 벡터화 연산 준비
# ==========================================
df = pd.read_csv('channel_metrics_pred.csv')
df['speed_ms'] = df['speed_kmh'] / 3.6

K, W, sigma_P_min, sigma_B_min = 0.003817, 20, 0.01, 1.0
df['mu_P'] = df['PDR'].expanding().mean().shift(1).fillna(df['PDR'].iloc[0])
df['mu_B'] = df['Max_Burst'].expanding().mean().shift(1).fillna(df['Max_Burst'].iloc[0])
df['var_P_inf'] = df['PDR'].expanding().var().shift(1).fillna(df['PDR'].var())
df['var_B_inf'] = df['Max_Burst'].expanding().var().shift(1).fillna(df['Max_Burst'].var())
df['var_B_roll'] = df['Max_Burst'].rolling(window=W, min_periods=1).var().shift(1).fillna(df['Max_Burst'].var())

df['Actual_Next_PDR'] = df['PDR'].shift(-1)
df['Actual_Next_B'] = df['Max_Burst'].shift(-1)

kappa_P, gamma_B = 3.0, 1.5

rho = np.maximum(0, 1 - K * (df['speed_ms'] ** 2))
P_mean = df['mu_P'] + rho * (df['PDR'] - df['mu_P'])
B_mean = df['mu_B'] + rho * (df['Max_Burst'] - df['mu_B'])

var_P_eff = df['var_P_inf'] * (1 - rho**2) + kappa_P * (P_mean * (1 - P_mean)) / 100.0
sigma_P_eff = np.maximum(np.sqrt(np.maximum(0, var_P_eff)), sigma_P_min)

var_B_eff = df['var_B_inf'] * (1 - rho**2) + gamma_B * df['var_B_roll'] + sigma_B_min**2
sigma_B_eff = np.sqrt(np.maximum(0, var_B_eff))

eval_mask = (df.index >= 5) & df['Actual_Next_PDR'].notna() & df['Actual_Next_B'].notna()
actual_pdr = df.loc[eval_mask, 'Actual_Next_PDR'].values
actual_b = df.loc[eval_mask, 'Actual_Next_B'].values

p_mean_eval = P_mean[eval_mask].values
sigma_p_eval = sigma_P_eff[eval_mask].values
b_mean_eval = B_mean[eval_mask].values
sigma_b_eval = sigma_B_eff[eval_mask].values

# ==========================================
# 3. Z-score 스윕 및 타겟 Z 탐색
# ==========================================
z_max = 3.0
z_array = np.arange(0.0, z_max + 0.01, 0.01)
pdr_rates, burst_rates = [], []

for z in z_array:
    p_cons = np.clip(p_mean_eval - z * sigma_p_eval, 0.0, 1.0)
    p_cons = np.round(p_cons, 2)
    b_cons = np.ceil(np.clip(b_mean_eval + z * sigma_b_eval, 0.0, 100.0)).astype(int)

    pdr_rates.append((actual_pdr >= p_cons).mean() * 100)
    burst_rates.append((actual_b <= b_cons).mean() * 100)

pdr_rates = np.array(pdr_rates)
burst_rates = np.array(burst_rates)

def find_target_z(target):
    idx = np.where((pdr_rates >= target) & (burst_rates >= target))[0]
    return z_array[idx[0]] if len(idx) > 0 else None

z_targets = {
    0.0: 'ARGUS-C',
    find_target_z(85.0): 'ARGUS-B',
    find_target_z(90.0): 'ARGUS-R',
    find_target_z(95.0): 'ARGUS-E'
}

target_colors = {
    'ARGUS-C': '#9ecae1',
    'ARGUS-B': '#6baed6',
    'ARGUS-R': '#3182bd',
    'ARGUS-E': '#08519c'
}

# ==========================================
# 4. Z값 선정 근거 시각화 (세로 짜부 버전)
# ==========================================
# 💡 [최 교수의 철퇴] 가로 3.5인치 유지, 세로는 2.8 -> 2.2인치로 극단적 압축!
fig, ax = plt.subplots(figsize=(3.5, 2.2))

# 메인 곡선
ax.plot(z_array, pdr_rates, color='#555555', linewidth=1.5, linestyle='-', label=r'PDR Coverage ($\widehat{\mathrm{PDR}}$)', zorder=1)
ax.plot(z_array, burst_rates, color='#555555', linewidth=1.5, linestyle='--', label=r'Burst Coverage ($\widehat{b}$)', zorder=1)

# 타겟 수평선 (85, 90, 95)
for t in [85, 90, 95]:
    ax.axhline(y=t, color='lightgray', linestyle=':', linewidth=1.0, zorder=0)

# 💡 [최 교수의 디테일] 공간이 납작해졌으므로 텍스트 박스의 고도를 재설정 (바닥에 안 끌리게)
y_positions = [63, 74, 63, 74]

for count, (z_val, label) in enumerate(z_targets.items()):
    if z_val is not None:
        c = target_colors[label]

        ax.axvline(x=z_val, color=c, linestyle='-.', linewidth=1.2, alpha=0.9, zorder=4)
        idx = np.where(np.isclose(z_array, z_val))[0][0]
        ax.scatter([z_val, z_val], [pdr_rates[idx], burst_rates[idx]], color=c, zorder=5, s=25, edgecolors='black', linewidths=0.5)

        y_pos = y_positions[count % len(y_positions)]
        ax.text(z_val + 0.03, y_pos, f'{label}\n($z={z_val:.2f}$)',
                 fontsize=6.5, color=c, verticalalignment='center', fontweight='bold',
                 bbox=dict(facecolor='white', alpha=0.9, edgecolor='none', pad=0.1), zorder=6)

ax.set_xlabel('Conservativeness Margin ($z$)', fontweight='bold', labelpad=1) # 💡 축 라벨 밀착
# 💡 [네가 고른 찰떡 라벨 적용]
ax.set_ylabel('Coverage Probability (%)', fontweight='bold', labelpad=1) # 💡 축 라벨 밀착

# 💡 눈금 숫자도 밀착
ax.tick_params(axis='both', which='major', pad=1)

ax.set_xlim(-0.05, z_max) # 💡 좌측 여백 살짝 줄임
ax.set_ylim(60, 102)

# 범례 크기 및 여백 최적화
ax.legend(loc='lower right', frameon=True, facecolor='white', framealpha=0.95, edgecolor='black',
          prop={'weight': 'bold', 'size': 6.5}, borderpad=0.3, labelspacing=0.2)
ax.grid(True, linestyle='--', linewidth=0.4, alpha=0.7)

# 💡 외부 패딩을 0.2로 극한까지 깎음
plt.tight_layout(pad=0.2)
plt.savefig('z_selection_justification_journal.pdf', format='pdf', dpi=600, bbox_inches='tight')
print("-> Journal single-column Z-score sweep figure saved.")
