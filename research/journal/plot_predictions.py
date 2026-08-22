# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.lines as mlines

# # ==========================================
# # IEEE journal publication style — single-column (3.5 inch)
# # ==========================================
# plt.rcParams.update({
#     'font.family':      'serif',
#     'font.serif':       ['Times New Roman'],
#     'mathtext.fontset': 'stix',
#     'font.size':         8,
#     'axes.labelsize':    8,
#     'xtick.labelsize':   7,
#     'ytick.labelsize':   7,
#     'legend.fontsize':   7,
#     'axes.linewidth':    0.6,
# })

# # ==========================================
# # 데이터 로드
# #   4개 CSV: prediction_results_argus_{c,b,r,e}.csv
# #   공통 컬럼: Window_ID, PDR, Max_Burst, Pred_PDR_cons, Pred_B_cons
# # ==========================================
# dc = pd.read_csv('prediction_results_argus_c.csv')
# db = pd.read_csv('prediction_results_argus_b.csv')
# dr = pd.read_csv('prediction_results_argus_r.csv')
# de = pd.read_csv('prediction_results_argus_e.csv')

# # 모든 CSV의 PDR/Burst 실측값은 동일 → dc 기준 사용
# df_obs = dc[['Window_ID', 'PDR', 'Max_Burst']].copy()
# df_obs['Time_s'] = df_obs['Window_ID'] * 0.1

# # ==========================================
# # 스타일
# # ==========================================
# obs_style  = dict(color='#888888', ls='--', lw=1.8, alpha=0.9, zorder=1)

# colors = {
#     'C': '#9ecae1',
#     'B': '#6baed6',
#     'R': '#3182bd',
#     'E': '#08519c',
# }
# argus_style = {
#     'C': dict(color=colors['C'], ls='-', lw=1.0, zorder=2),
#     'B': dict(color=colors['B'], ls='-', lw=1.0, zorder=3),
#     'R': dict(color=colors['R'], ls='-', lw=1.0, zorder=4),
#     'E': dict(color=colors['E'], ls='-', lw=1.8, zorder=10),  # E만 굵게
# }
# modes = [
#     ('C', dc),
#     ('B', db),
#     ('R', dr),
#     ('E', de),
# ]

# # ==========================================
# # 플롯 생성 함수
# # ==========================================
# def create_plot(mode_pairs, filename, show_legend=False):
#     fig, axes = plt.subplots(2, 1, figsize=(3.5, 3.8))
#     t = df_obs['Time_s']

#     # ── PDR ──────────────────────────────────────────────────────────────
#     axes[0].plot(t, df_obs['PDR'], label='Observed', **obs_style)
#     for key, data in mode_pairs:
#         axes[0].plot(t, data['Pred_PDR_cons'],
#                      label=f'ARGUS-{key}', **argus_style[key])

#     axes[0].set_ylabel(r'PDR ($\widehat{\mathrm{PDR}}$)', fontweight='bold')
#     axes[0].set_ylim(-0.05, 1.1)
#     axes[0].set_yticks([0.0, 0.5, 1.0])
#     axes[0].tick_params(axis='x', labelbottom=False)
#     axes[0].grid(True, ls='--', lw=0.4, alpha=0.7)
#     axes[0].locator_params(axis='x', nbins=6)

#     # ── Burst ─────────────────────────────────────────────────────────────
#     axes[1].plot(t, df_obs['Max_Burst'], label='Observed', **obs_style)
#     for key, data in mode_pairs:
#         axes[1].plot(t, data['Pred_B_cons'],
#                      label=f'ARGUS-{key}', **argus_style[key])

#     axes[1].set_ylabel(r'Burst Length ($\widehat{b}$)', fontweight='bold')
#     axes[1].set_xlabel('Time (s)', fontweight='bold')
#     axes[1].grid(True, ls='--', lw=0.4, alpha=0.7)
#     axes[1].locator_params(axis='x', nbins=6)

#     # ── 범례 ──────────────────────────────────────────────────────────────
#     if show_legend:
#         h_obs = mlines.Line2D([], [], label='Observed',  **obs_style)
#         h_c   = mlines.Line2D([], [], label='ARGUS-C', **argus_style['C'])
#         h_b   = mlines.Line2D([], [], label='ARGUS-B', **argus_style['B'])
#         h_r   = mlines.Line2D([], [], label='ARGUS-R', **argus_style['R'])
#         h_e   = mlines.Line2D([], [], label='ARGUS-E', **argus_style['E'])
#         dummy = mlines.Line2D([], [], color='none', label='')

#         fig.legend(handles=[h_c, h_obs, h_b, h_r, dummy, h_e],
#                    loc='lower center', bbox_to_anchor=(0.5, 0.86),
#                    ncol=3, frameon=False,
#                    columnspacing=1.5, handletextpad=0.4,
#                    prop={'weight': 'bold', 'size': 7})

#         plt.tight_layout(pad=0.5)
#         plt.subplots_adjust(top=0.84, hspace=0.25)
#     else:
#         plt.tight_layout(pad=0.5)
#         plt.subplots_adjust(top=0.95, hspace=0.25)

#     plt.savefig(filename, format='pdf', dpi=600, bbox_inches='tight')
#     plt.close()
#     print(f'-> {filename} 저장 완료')

# # ==========================================
# # 실행: low (C+B), high (R+E)
# # ==========================================
# create_plot([('C', dc), ('B', db)],
#             'estimation_timeseries_low.pdf', show_legend=True)

# create_plot([('R', dr), ('E', de)],
#             'estimation_timeseries_high.pdf', show_legend=False)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

# ==========================================
# Elsevier Publication Style — Single-Column (90 mm = 3.54 inch)
# ==========================================
plt.rcParams.update({
    'font.family':       'serif',
    'font.serif':        ['Times New Roman'],
    'mathtext.fontset':  'stix',
    'font.size':         7.5,    # Elsevier 권장: 7~9pt
    'axes.labelsize':    8,
    'axes.titleweight':  'bold',
    'xtick.labelsize':   7,
    'ytick.labelsize':   7,
    'legend.fontsize':   7,
    'axes.linewidth':    0.6,
    'pdf.fonttype':      42,     # Elsevier 필수: TrueType 폰트 임베딩
    'ps.fonttype':       42,
})

# ==========================================
# 데이터 로드
#   4개 CSV: prediction_results_argus_{c,b,r,e}.csv
#   공통 컬럼: Window_ID, PDR, Max_Burst, Pred_PDR_cons, Pred_B_cons
# ==========================================
# 실제 실행 시 주석 해제하여 사용하세요.
try:
    dc = pd.read_csv('prediction_results_argus_c.csv')
    db = pd.read_csv('prediction_results_argus_b.csv')
    dr = pd.read_csv('prediction_results_argus_r.csv')
    de = pd.read_csv('prediction_results_argus_e.csv')
except FileNotFoundError:
    print("[경고] CSV 파일을 찾을 수 없어 더미 데이터를 사용합니다.")
    # 임시 더미 데이터 (테스트용)
    dc = pd.DataFrame({'Window_ID': range(100), 'PDR': np.random.rand(100), 'Max_Burst': np.random.randint(0, 50, 100), 'Pred_PDR_cons': np.random.rand(100), 'Pred_B_cons': np.random.randint(0, 50, 100)})
    db, dr, de = dc.copy(), dc.copy(), dc.copy()

# 모든 CSV의 PDR/Burst 실측값은 동일 → dc 기준 사용
df_obs = dc[['Window_ID', 'PDR', 'Max_Burst']].copy()
df_obs['Time_s'] = df_obs['Window_ID'] * 0.1

# ==========================================
# 스타일
# ==========================================
# Observed 선은 흑백 인쇄 시에도 명확히 보이도록 alpha를 0.8로 약간 조절
obs_style  = dict(color='#888888', ls='--', lw=1.8, alpha=0.8, zorder=1)

colors = {
    'C': '#9ecae1',
    'B': '#6baed6',
    'R': '#3182bd',
    'E': '#08519c',
}
argus_style = {
    'C': dict(color=colors['C'], ls='-', lw=1.0, zorder=2),
    'B': dict(color=colors['B'], ls='-', lw=1.0, zorder=3),
    'R': dict(color=colors['R'], ls='-', lw=1.0, zorder=4),
    'E': dict(color=colors['E'], ls='-', lw=1.8, zorder=10),  # E만 굵게 강조
}

# ==========================================
# 플롯 생성 함수
# ==========================================
def create_plot(mode_pairs, filename, show_legend=False):
    # 단단 너비 3.54 인치 고정
    fig, axes = plt.subplots(2, 1, figsize=(3.54,2.6))
    t = df_obs['Time_s']

    # ── PDR ──────────────────────────────────────────────────────────────
    axes[0].plot(t, df_obs['PDR'], label='Observed', **obs_style)
    for key, data in mode_pairs:
        axes[0].plot(t, data['Pred_PDR_cons'],
                     label=f'ARGUS-{key}', **argus_style[key])

    axes[0].set_ylabel(r'PDR ($\widehat{\mathrm{PDR}}$)', fontweight='bold')
    axes[0].set_ylim(0.0, 1.05) # -0.05에서 0.0으로 깔끔하게 조정
    axes[0].set_yticks([0.0, 0.5, 1.0])
    axes[0].tick_params(axis='x', labelbottom=False)
    axes[0].grid(True, ls='--', lw=0.4, alpha=0.7)
    axes[0].locator_params(axis='x', nbins=6)

    # ── Burst ─────────────────────────────────────────────────────────────
    axes[1].plot(t, df_obs['Max_Burst'], label='Observed', **obs_style)
    for key, data in mode_pairs:
        axes[1].plot(t, data['Pred_B_cons'],
                     label=f'ARGUS-{key}', **argus_style[key])

    axes[1].set_ylabel(r'Burst Length ($\widehat{b}$)', fontweight='bold')
    axes[1].set_xlabel('Time (s)', fontweight='bold')
    axes[1].grid(True, ls='--', lw=0.4, alpha=0.7)
    axes[1].locator_params(axis='x', nbins=6)

    # ── 범례 (통합) ───────────────────────────────────────────────────────
    if show_legend:
        # 논문 레이아웃을 위해 C, B, R, E 전체 범례를 통일하여 생성
        h_obs = mlines.Line2D([], [], label='Observed',  **obs_style)
        h_c   = mlines.Line2D([], [], label='ARGUS-C', **argus_style['C'])
        h_b   = mlines.Line2D([], [], label='ARGUS-B', **argus_style['B'])
        h_r   = mlines.Line2D([], [], label='ARGUS-R', **argus_style['R'])
        h_e   = mlines.Line2D([], [], label='ARGUS-E', **argus_style['E'])
        dummy = mlines.Line2D([], [], color='none', label='') # 간격 맞춤용 더미

        # 범례 텍스트 굵게 처리 (prop)
        legend = fig.legend(handles=[h_c, h_obs, h_b, h_r, dummy, h_e],
                            loc='lower center', bbox_to_anchor=(0.5, 0.88), # 위치 미세 조정
                            ncol=3, frameon=False,
                            columnspacing=1.5, handletextpad=0.4,
                            prop={'weight': 'bold', 'size': 7})

        plt.tight_layout(pad=0.5)
        plt.subplots_adjust(top=0.84, hspace=0.25)
    else:
        plt.tight_layout(pad=0.5)
        plt.subplots_adjust(top=0.95, hspace=0.25)

    # PDF와 EPS 형식 모두 저장 (Elsevier 필수 요구사항 대응)
    base_name = filename.rsplit('.', 1)[0]
    plt.savefig(f'{base_name}.pdf', format='pdf', dpi=600, bbox_inches='tight')
    plt.savefig(f'{base_name}.eps', format='eps', dpi=600, bbox_inches='tight')
    print(f'-> {base_name}.pdf 및 .eps 저장 완료')
    plt.close()

# ==========================================
# 실행: low (C+B), high (R+E)
# ==========================================
create_plot([('C', dc), ('B', db)], 'estimation_timeseries_low.pdf', show_legend=True)
create_plot([('R', dr), ('E', de)], 'estimation_timeseries_high.pdf', show_legend=False)
