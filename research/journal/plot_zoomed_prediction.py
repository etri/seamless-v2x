# # import pandas as pd
# # import numpy as np
# # import matplotlib.pyplot as plt
# # import matplotlib.ticker as ticker

# # # ==========================================
# # # IEEE journal publication style — single-column (3.5 inch)
# # # ==========================================
# # plt.rcParams.update({
# #     'font.family':      'serif',
# #     'font.serif':       ['Times New Roman'],
# #     'mathtext.fontset': 'stix',
# #     'font.size':         8,
# #     'axes.labelsize':    8,
# #     'axes.titleweight': 'bold',
# #     'axes.titlesize':    8,
# #     'xtick.labelsize':   7,
# #     'ytick.labelsize':   7,
# #     'legend.fontsize':   7,
# #     'lines.linewidth':   1.0,
# #     'axes.linewidth':    0.6,
# # })

# # # ── 데이터 ────────────────────────────────────────────────────────────────────
# # df = pd.read_csv('prediction_results_argus_r.csv')
# # df['PDR_naive'] = df['PDR'].shift(1).fillna(df['PDR'].iloc[0])
# # df['B_naive']   = df['Max_Burst'].shift(1).fillna(df['Max_Burst'].iloc[0])
# # df['Time_s']    = df['Window_ID'] * 0.1

# # def seg(wid_s, wid_e):
# #     return df[(df['Window_ID'] >= wid_s) & (df['Window_ID'] <= wid_e)].copy()

# # low  = seg(1486, 1515)   # 148.6 ~ 151.5 s
# # mid  = seg(1093, 1122)   # 109.3 ~ 112.2 s
# # high = seg( 496,  525)   #  49.6 ~  52.5 s

# # max_b = max(
# #     low [['Max_Burst','B_naive','Pred_B_cons']].max().max(),
# #     mid [['Max_Burst','B_naive','Pred_B_cons']].max().max(),
# #     high[['Max_Burst','B_naive','Pred_B_cons']].max().max(),
# # )  # ≈ 52 → y축 0~60, 눈금 0/20/40/60

# # # ── 스타일: 색 + 선 모양 + 마커 (B&W 인쇄 대응) ─────────────────────────────
# # style = {
# #     'Actual':   dict(color='#555555', ls='-',  lw=0.8, marker='',  alpha=0.7),
# #     'Baseline': dict(color='#ff7f0e', ls='--', lw=0.9, marker='',  alpha=0.85),
# #     'Proposed': dict(color='#3182bd', ls='-.', lw=1.0, marker='',  alpha=1.0),
# #     'Fill':     dict(color='#3182bd', alpha=0.15),
# # }

# # # ── x축 헬퍼 ─────────────────────────────────────────────────────────────────
# # def set_xaxis(ax, s, show_label=False):
# #     t0, t1 = s['Time_s'].iloc[0], s['Time_s'].iloc[-1]
# #     ax.set_xlim(t0, t1)
# #     int_ticks = np.arange(int(np.ceil(t0)), int(np.floor(t1)) + 1, 1)
# #     ax.set_xticks(int_ticks)
# #     ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%g'))
# #     if show_label:
# #         ax.set_xlabel('Time (s)', fontweight='bold')

# # # ── 서브플롯 그리기 ───────────────────────────────────────────────────────────
# # def plot_pdr(ax, s, show_legend=False, show_ylabel=True, show_xlabel=False):
# #     t = s['Time_s']
# #     ax.plot(t, s['PDR'],
# #             label='Observed' if show_legend else '', **style['Actual'])
# #     ax.plot(t, s['PDR_naive'],
# #             label='NAIVE'    if show_legend else '', **style['Baseline'])
# #     ax.plot(t, s['Pred_PDR_cons'],
# #             label='ARGUS-R'  if show_legend else '', **style['Proposed'])
# #     ax.fill_between(t, s['Pred_PDR_cons'], s['PDR'],
# #                     where=(s['Pred_PDR_cons'] <= s['PDR']),
# #                     label='Safe Margin' if show_legend else '',
# #                     **style['Fill'])
# #     ax.set_ylim(-0.05, 1.05)
# #     ax.set_yticks([0.0, 0.5, 1.0])
# #     ax.grid(True, ls='--', alpha=0.5, lw=0.4)
# #     set_xaxis(ax, s, show_label=show_xlabel)
# #     if show_ylabel:
# #         ax.set_ylabel(r'PDR ($\widehat{\mathrm{PDR}}$)', fontweight='bold')
# #     else:
# #         ax.tick_params(labelleft=False)

# # def plot_burst(ax, s, show_ylabel=True, show_xlabel=False):
# #     t = s['Time_s']
# #     ax.plot(t, s['Max_Burst'],   label='', **style['Actual'])
# #     ax.plot(t, s['B_naive'],     label='', **style['Baseline'])
# #     ax.plot(t, s['Pred_B_cons'], label='', **style['Proposed'])
# #     ax.fill_between(t, s['Max_Burst'], s['Pred_B_cons'],
# #                     where=(s['Pred_B_cons'] >= s['Max_Burst']),
# #                     **style['Fill'])
# #     ax.set_ylim(0, 60)
# #     ax.set_yticks([0, 20, 40, 60])
# #     ax.grid(True, ls='--', alpha=0.5, lw=0.4)
# #     set_xaxis(ax, s, show_label=show_xlabel)
# #     if show_ylabel:
# #         ax.set_ylabel(r'Burst Length ($\widehat{b}$)', fontweight='bold')
# #     else:
# #         ax.tick_params(labelleft=False)

# # # ── 2×2 ──────────────────────────────────────────────────────────────────────
# # fig, axes = plt.subplots(2, 2, figsize=(3.5, 3.2))

# # plot_pdr  (axes[0,0], low,  show_legend=True,  show_ylabel=True,  show_xlabel=False)
# # plot_pdr  (axes[0,1], mid,  show_legend=False, show_ylabel=False, show_xlabel=False)
# # plot_burst(axes[1,0], low,  show_ylabel=True,  show_xlabel=True)
# # plot_pdr  (axes[1,1], high, show_legend=False, show_ylabel=False, show_xlabel=True)

# # # ── (a)(b)(c)(d) 라벨 ────────────────────────────────────────────────────────
# # for ax, lbl in zip(axes.flat, ['(a)', '(b)', '(c)', '(d)']):
# #     ax.text(0.97, 0.96, lbl,
# #             transform=ax.transAxes,
# #             fontsize=7, fontweight='bold',
# #             va='top', ha='right')

# # # ── 범례 ──────────────────────────────────────────────────────────────────────
# # handles, labels = axes[0,0].get_legend_handles_labels()
# # legend = fig.legend(handles, labels,
# #                     loc='lower center', bbox_to_anchor=(0.5, 0.94),
# #                     ncol=4, frameon=False,
# #                     handletextpad=0.2, columnspacing=0.8)
# # for txt in legend.get_texts():
# #     txt.set_weight('bold')

# # plt.tight_layout()
# # plt.subplots_adjust(top=0.88, wspace=0.18, hspace=0.38)
# # plt.savefig('zoomed_prediction_argus_r_final.pdf',
# #             format='pdf', dpi=600, bbox_inches='tight')
# # print('-> 저장 완료')

# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.ticker as ticker

# # ==========================================
# # Elsevier Publication Style — Single-Column (90 mm = 3.54 inch)
# # ==========================================
# plt.rcParams.update({
#     'font.family':       'serif',
#     'font.serif':        ['Times New Roman'],
#     'mathtext.fontset':  'stix',
#     'font.size':         7.5,    # Elsevier 권장: 7~9pt
#     'axes.labelsize':    8,
#     'axes.titleweight':  'bold',
#     'axes.titlesize':    8,
#     'xtick.labelsize':   7,
#     'ytick.labelsize':   7,
#     'legend.fontsize':   7,
#     'lines.linewidth':   1.0,
#     'axes.linewidth':    0.6,
#     'pdf.fonttype':      42,     # Elsevier 필수: TrueType 폰트 임베딩
#     'ps.fonttype':       42,     # (Type 3 폰트 거절 방지)
# })

# # ── 데이터 ────────────────────────────────────────────────────────────────────
# df = pd.read_csv('prediction_results_argus_r.csv')
# df['PDR_naive'] = df['PDR'].shift(1).fillna(df['PDR'].iloc[0])
# df['B_naive']   = df['Max_Burst'].shift(1).fillna(df['Max_Burst'].iloc[0])
# df['Time_s']    = df['Window_ID'] * 0.1

# def seg(wid_s, wid_e):
#     return df[(df['Window_ID'] >= wid_s) & (df['Window_ID'] <= wid_e)].copy()

# low  = seg(1486, 1515)   # 148.6 ~ 151.5 s
# mid  = seg(1093, 1122)   # 109.3 ~ 112.2 s
# high = seg( 496,  525)   #  49.6 ~  52.5 s

# # ── 스타일: 색 + 선 모양 + 마커 (B&W 인쇄 대응) ─────────────────────────────
# style = {
#     'Actual':   dict(color='#555555', ls='-',  lw=0.8, marker='',  alpha=0.7),
#     'Baseline': dict(color='#ff7f0e', ls='--', lw=0.9, marker='',  alpha=0.85),
#     'Proposed': dict(color='#3182bd', ls='-.', lw=1.0, marker='',  alpha=1.0),
#     'Fill':     dict(color='#3182bd', alpha=0.15),
# }

# # ── x축 헬퍼 ─────────────────────────────────────────────────────────────────
# def set_xaxis(ax, s, show_label=False):
#     t0, t1 = s['Time_s'].iloc[0], s['Time_s'].iloc[-1]
#     ax.set_xlim(t0, t1)
#     int_ticks = np.arange(int(np.ceil(t0)), int(np.floor(t1)) + 1, 1)
#     ax.set_xticks(int_ticks)
#     ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%g'))
#     if show_label:
#         ax.set_xlabel('Time (s)', fontweight='bold')

# # ── 서브플롯 그리기 ───────────────────────────────────────────────────────────
# def plot_pdr(ax, s, show_legend=False, show_ylabel=True, show_xlabel=False):
#     t = s['Time_s']
#     ax.plot(t, s['PDR'],
#             label='Observed' if show_legend else '', **style['Actual'])
#     ax.plot(t, s['PDR_naive'],
#             label='NAIVE'    if show_legend else '', **style['Baseline'])
#     ax.plot(t, s['Pred_PDR_cons'],
#             label='ARGUS-R'  if show_legend else '', **style['Proposed'])
#     ax.fill_between(t, s['Pred_PDR_cons'], s['PDR'],
#                     where=(s['Pred_PDR_cons'] <= s['PDR']),
#                     label='Safe Margin' if show_legend else '',
#                     **style['Fill'])
#     ax.set_ylim(-0.05, 1.05)
#     ax.set_yticks([0.0, 0.5, 1.0])
#     ax.grid(True, ls='--', alpha=0.5, lw=0.4)
#     set_xaxis(ax, s, show_label=show_xlabel)
#     if show_ylabel:
#         ax.set_ylabel(r'PDR ($\widehat{\mathrm{PDR}}$)', fontweight='bold')
#     else:
#         ax.tick_params(labelleft=False)

# def plot_burst(ax, s, show_ylabel=True, show_xlabel=False):
#     t = s['Time_s']
#     ax.plot(t, s['Max_Burst'],   label='', **style['Actual'])
#     ax.plot(t, s['B_naive'],     label='', **style['Baseline'])
#     ax.plot(t, s['Pred_B_cons'], label='', **style['Proposed'])
#     ax.fill_between(t, s['Max_Burst'], s['Pred_B_cons'],
#                     where=(s['Pred_B_cons'] >= s['Max_Burst']),
#                     **style['Fill'])
#     ax.set_ylim(0, 60)
#     ax.set_yticks([0, 20, 40, 60])
#     ax.grid(True, ls='--', alpha=0.5, lw=0.4)
#     set_xaxis(ax, s, show_label=show_xlabel)
#     if show_ylabel:
#         ax.set_ylabel(r'Burst Length ($\widehat{b}$)', fontweight='bold')
#     else:
#         ax.tick_params(labelleft=False)

# # ── 2×2 배치 (너비 3.54 인치) ────────────────────────────────────────────────
# fig, axes = plt.subplots(2, 2, figsize=(3.54, 3.2))

# plot_pdr  (axes[0,0], low,  show_legend=True,  show_ylabel=True,  show_xlabel=False)
# plot_pdr  (axes[0,1], mid,  show_legend=False, show_ylabel=False, show_xlabel=False)
# plot_burst(axes[1,0], low,  show_ylabel=True,  show_xlabel=True)
# plot_pdr  (axes[1,1], high, show_legend=False, show_ylabel=False, show_xlabel=True)

# # ── (a)(b)(c)(d) 라벨 ────────────────────────────────────────────────────────
# for ax, lbl in zip(axes.flat, ['(a)', '(b)', '(c)', '(d)']):
#     ax.text(0.97, 0.96, lbl,
#             transform=ax.transAxes,
#             fontsize=7.5, fontweight='bold',
#             va='top', ha='right')

# # ── 범례 ──────────────────────────────────────────────────────────────────────
# handles, labels = axes[0,0].get_legend_handles_labels()
# legend = fig.legend(handles, labels,
#                     loc='lower center', bbox_to_anchor=(0.5, 0.94),
#                     ncol=4, frameon=False,
#                     handletextpad=0.2, columnspacing=0.8)
# for txt in legend.get_texts():
#     txt.set_weight('bold')

# plt.tight_layout()
# plt.subplots_adjust(top=0.88, wspace=0.18, hspace=0.38)

# # Elsevier의 경우 EPS나 고해상도 PDF 선호 (TrueType 임베딩 필수)
# plt.savefig('zoomed_prediction_argus_r_elsevier.pdf',
#             format='pdf', dpi=600, bbox_inches='tight')
# plt.savefig('zoomed_prediction_argus_r_elsevier.eps',
#             format='eps', dpi=600, bbox_inches='tight')
# print('-> 저장 완료')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ==========================================
# IEEE journal — single-column figure (3.5 in = 89 mm)
# \begin{figure}[!t]
#   \includegraphics[width=\columnwidth]{...}
# ==========================================
plt.rcParams.update({
    'font.family':       'serif',
    'font.serif':        ['Times New Roman', 'Times', 'DejaVu Serif'],
    'mathtext.fontset':  'stix',
    'font.size':         8,
    'axes.labelsize':    8,
    'axes.titleweight':  'bold',
    'axes.titlesize':    8,
    'xtick.labelsize':   7,
    'ytick.labelsize':   7,
    'legend.fontsize':   7,
    'lines.linewidth':   1.0,
    'axes.linewidth':    0.6,
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'xtick.major.size':  2.5,
    'ytick.major.size':  2.5,
    'pdf.fonttype':      42,
    'ps.fonttype':       42,
})

# ── 데이터 ──
df = pd.read_csv('prediction_results_argus_r.csv')
df['PDR_naive'] = df['PDR'].shift(1).fillna(df['PDR'].iloc[0])
df['B_naive']   = df['Max_Burst'].shift(1).fillna(df['Max_Burst'].iloc[0])
df['Time_s']    = df['Window_ID'] * 0.1

def seg(wid_s, wid_e):
    return df[(df['Window_ID'] >= wid_s) & (df['Window_ID'] <= wid_e)].copy()

low  = seg(1486, 1515)
mid  = seg(1093, 1122)
high = seg( 496,  525)

# ── 스타일 ──
style = {
    'Actual':   dict(color='#555555', ls='-',  lw=0.8, marker='', alpha=0.7),
    'Baseline': dict(color='#ff7f0e', ls='--', lw=0.9, marker='', alpha=0.85),
    'Proposed': dict(color='#3182bd', ls='-.', lw=1.0, marker='', alpha=1.0),
}

# ── x축 헬퍼 ──
def set_xaxis(ax, s, show_label=False):
    t0, t1 = s['Time_s'].iloc[0], s['Time_s'].iloc[-1]
    ax.set_xlim(t0, t1)
    int_ticks = np.arange(int(np.ceil(t0)), int(np.floor(t1)) + 1, 1)
    ax.set_xticks(int_ticks)
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%g'))
    if show_label:
        ax.set_xlabel('Time (s)', fontweight='bold')

# ── 서브플롯 ──
def plot_pdr(ax, s, show_legend=False, show_ylabel=True, show_xlabel=False):
    t = s['Time_s']
    ax.plot(t, s['PDR'],
            label='Observed' if show_legend else '', **style['Actual'])
    ax.plot(t, s['PDR_naive'],
            label='NAIVE'    if show_legend else '', **style['Baseline'])
    ax.plot(t, s['Pred_PDR_cons'],
            label='ARGUS-R'  if show_legend else '', **style['Proposed'])
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks([0.0, 0.5, 1.0])
    ax.grid(True, ls='--', alpha=0.5, lw=0.4)
    set_xaxis(ax, s, show_label=show_xlabel)
    if show_ylabel:
        ax.set_ylabel(r'PDR ($\widehat{\mathrm{PDR}}$)', fontweight='bold')
    else:
        ax.tick_params(labelleft=False)

def plot_burst(ax, s, show_ylabel=True, show_xlabel=False):
    t = s['Time_s']
    ax.plot(t, s['Max_Burst'],   **style['Actual'])
    ax.plot(t, s['B_naive'],     **style['Baseline'])
    ax.plot(t, s['Pred_B_cons'], **style['Proposed'])
    ax.set_ylim(0, 60)
    ax.set_yticks([0, 20, 40, 60])
    ax.grid(True, ls='--', alpha=0.5, lw=0.4)
    set_xaxis(ax, s, show_label=show_xlabel)
    if show_ylabel:
        ax.set_ylabel(r'Burst Length ($\widehat{b}$)', fontweight='bold')
    else:
        ax.tick_params(labelleft=False)

# ── 2×2 (columnwidth = 3.5 in, half-page ≈ 3.2 in height) ──
fig, axes = plt.subplots(2, 2, figsize=(3.5, 3.2))

plot_pdr  (axes[0,0], low,  show_legend=True,  show_ylabel=True,  show_xlabel=False)
plot_pdr  (axes[0,1], mid,  show_legend=False, show_ylabel=False, show_xlabel=False)
plot_burst(axes[1,0], low,  show_ylabel=True,  show_xlabel=True)
plot_pdr  (axes[1,1], high, show_legend=False, show_ylabel=False, show_xlabel=True)

# ── (a)(b)(c)(d) 라벨 ──
for ax, lbl in zip(axes.flat, ['(a)', '(b)', '(c)', '(d)']):
    ax.text(0.97, 0.96, lbl,
            transform=ax.transAxes,
            fontsize=7, fontweight='bold',
            va='top', ha='right')

# ── 범례 (상단 중앙) ──
handles, labels = axes[0,0].get_legend_handles_labels()
legend = fig.legend(handles, labels,
                    loc='lower center', bbox_to_anchor=(0.5, 0.94),
                    ncol=3, frameon=False,
                    handletextpad=0.2, columnspacing=0.8)
for txt in legend.get_texts():
    txt.set_weight('bold')

plt.tight_layout()
plt.subplots_adjust(top=0.88, wspace=0.18, hspace=0.38)

plt.savefig('zoomed_prediction.pdf', format='pdf', dpi=600, bbox_inches='tight')
plt.savefig('zoomed_prediction.eps', format='eps', dpi=600, bbox_inches='tight')
print('-> saved: zoomed_prediction.pdf / .eps')
