"""
ARGUS simulation script — journal release
===========================================
비교 대상:
  RAW, REP3, REP5                  : 고정 베이스라인
  NAIVE                            : t-1 채널 관측값 → t 예측 (단순 1-lag)
  ARGUS-C/B/R/E                    : EWMA 기반 보수적 예측
  ORACLE                           : t±2 윈도우 5개 중 최악값 (non-causal upper bound)

필요 파일 (같은 디렉토리):
  trace.bin                        : 패킷 수신 이진 트레이스 (packed bits)
  prediction_results_argus_c.csv   : ARGUS-C 예측 결과
  prediction_results_argus_b.csv   : ARGUS-B 예측 결과
  prediction_results_argus_r.csv   : ARGUS-R 예측 결과
  prediction_results_argus_e.csv   : ARGUS-E 예측 결과
  56LUT_3_Balanced.csv             : BSM LUT
  513LUT_3_Balanced.csv            : SDSM LUT
"""

from __future__ import annotations
import os
import random
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ─────────────────────────────────────────────
# 전역 플롯 설정
# IEEE journal two-column format
#   전체 텍스트 폭 ≈ 7.16 in (182 mm)
#   단단 텍스트 폭 ≈ 3.5 in  (89 mm)
#   full-column 2-panel 가로 배치 → figsize=(7.16, 3.2)
# ─────────────────────────────────────────────
plt.rcParams.update({
    'font.family':       'serif',
    'font.serif':        ['Times New Roman', 'Times', 'DejaVu Serif'],
    'mathtext.fontset':  'stix',
    'font.size':         9,
    'axes.labelsize':    10,
    'axes.titlesize':    10,
    'xtick.labelsize':   8,
    'ytick.labelsize':   8,
    'lines.linewidth':   1.5,
    'axes.linewidth':    0.8,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'xtick.major.size':  3.0,
    'ytick.major.size':  3.0,
    'legend.fontsize':   8,
    'pdf.fonttype':      42,   # TrueType embedding
    'ps.fonttype':       42,
})

# ─────────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────────
WINDOW_BITS = 100
ORACLE_HALF = 2

BSM_CONFIG  = dict(lut_csv='56LUT_3_Balanced.csv',  threshold=324, fallback_N=27, period=200, jitter=10, K=8)
SDSM_CONFIG = dict(lut_csv='513LUT_3_Balanced.csv', threshold=312, fallback_N=80, period=500, jitter=25, K=27)

ARGUS_CSVS = {
    'ARGUS-C': 'prediction_results_argus_c.csv',
    'ARGUS-B': 'prediction_results_argus_b.csv',
    'ARGUS-R': 'prediction_results_argus_r.csv',
    'ARGUS-E': 'prediction_results_argus_e.csv',
}

TARGET_MSGS = 100_000
RANDOM_SEED = 42

# ─────────────────────────────────────────────
# 트레이스 로더
# ─────────────────────────────────────────────
def load_trace_bits(path: str) -> np.ndarray:
    if not os.path.exists(path):
        raise FileNotFoundError(f"trace file not found: {path}")
    with open(path, 'rb') as f:
        packed = np.frombuffer(f.read(), dtype=np.uint8)
    return np.unpackbits(packed)


def build_skip_mask(bits: np.ndarray, threshold: int) -> np.ndarray:
    mask = np.zeros(len(bits), dtype=bool)
    count = 0
    for i in range(len(bits)):
        if bits[i] == 0:
            count += 1
        else:
            if count >= threshold:
                mask[i - count: i] = True
            count = 0
    if count >= threshold:
        mask[len(bits) - count:] = True
    return mask


# ─────────────────────────────────────────────
# LUT 엔진
# ─────────────────────────────────────────────
class LUTEngine:
    def __init__(self, csv_path: str, fallback_N: int, fallback_G: int = 0):
        self.fallback = (fallback_N, fallback_G)
        if not os.path.exists(csv_path):
            print(f"  [warn] LUT not found: {csv_path} -> fallback N={fallback_N}")
            self.pdr_keys = []; self.burst_keys = []; self.lut: Dict = {}
            return
        df = pd.read_csv(csv_path)
        self.pdr_keys   = sorted(df['PDR_Env'].unique().tolist())
        self.burst_keys = sorted(df['Burst_1_over_r'].unique().tolist())
        self.lut = {
            (float(r['PDR_Env']), float(r['Burst_1_over_r'])): (int(r['Action_N']), int(r['Action_G']))
            for _, r in df.iterrows()
        }

    def lookup(self, pdr: float, burst: float, K: int) -> Tuple[int, int]:
        if not self.lut:
            return self.fallback
        if burst > max(self.burst_keys):
            return (64, 2) if K == 8 else (140, 1)
        pdr_q = self.pdr_keys[0]
        for k in self.pdr_keys:
            if k <= pdr:
                pdr_q = k
        burst_q = self.burst_keys[-1]
        for k in self.burst_keys:
            if k >= burst:
                burst_q = k
                break
        return self.lut.get((pdr_q, burst_q), self.fallback)


# ─────────────────────────────────────────────
# 채널 입력 전략
# ─────────────────────────────────────────────
class ChannelInput:
    def __init__(self, mode: str, pred_csv: str = None, truth_csv: str = None):
        self.mode = mode
        if mode == 'NAIVE':
            df = pd.read_csv(truth_csv)
            pdr_truth = df['PDR'].values; burst_truth = df['Max_Burst'].values
            self.pdr_input   = np.concatenate([[0.45], pdr_truth[:-1]])
            self.burst_input = np.concatenate([[40.0], burst_truth[:-1]])
        elif mode == 'ORACLE':
            df = pd.read_csv(truth_csv)
            pdr_truth = df['PDR'].values; burst_truth = df['Max_Burst'].values
            n = len(pdr_truth)
            self.pdr_input = np.zeros(n); self.burst_input = np.zeros(n)
            for t in range(n):
                lo = max(0, t - ORACLE_HALF); hi = min(n, t + ORACLE_HALF + 1)
                self.pdr_input[t]   = pdr_truth[lo:hi].min()
                self.burst_input[t] = burst_truth[lo:hi].max()
        elif mode.startswith('ARGUS'):
            df = pd.read_csv(pred_csv)
            self.pdr_input   = df['Pred_PDR_cons'].values
            self.burst_input = df['Pred_B_cons'].values
        else:
            self.pdr_input = None; self.burst_input = None

    def get(self, win_idx: int) -> Tuple[float, float]:
        idx = min(win_idx, len(self.pdr_input) - 1)
        return float(self.pdr_input[idx]), float(self.burst_input[idx])


# ─────────────────────────────────────────────
# 결과 컨테이너
# ─────────────────────────────────────────────
@dataclass
class SimResult:
    mode: str; total: int; success: int; sum_N: float = 0.0; n_triggers: int = 0

    @property
    def outage_pct(self) -> float:
        return (1.0 - self.success / self.total) * 100.0 if self.total else 100.0


# ─────────────────────────────────────────────
# 시뮬레이터
# ─────────────────────────────────────────────
def simulate(bits, skip_mask, ch_input, lut, mode, K, period, jitter, target) -> SimResult:
    random.seed(RANDOM_SEED)
    N_BITS = len(bits)
    total = success = n_triggers = 0
    sum_N = 0.0
    argus_active = False
    argus_recv = argus_remaining = argus_next_shard_t = argus_spacing = 0
    t = 0
    next_msg_t = random.randint(period - jitter, period + jitter)

    while total < target:
        if mode not in ('RAW', 'REP3', 'REP5') and argus_active:
            t = min(next_msg_t, argus_next_shard_t)
        else:
            t = next_msg_t
        t_mod = t % N_BITS

        if mode not in ('RAW', 'REP3', 'REP5') and argus_active and t == argus_next_shard_t:
            if bits[t_mod] == 1:
                argus_recv += 1
            argus_remaining -= 1
            if argus_remaining == 0:
                total += 1
                if argus_recv >= K: success += 1
                argus_active = False
            else:
                argus_next_shard_t += argus_spacing
            if t != next_msg_t:
                continue

        if t == next_msg_t:
            next_msg_t += random.randint(period - jitter, period + jitter)
            if skip_mask[t_mod]:
                if mode not in ('RAW', 'REP3', 'REP5'): argus_active = False
                continue
            if mode not in ('RAW', 'REP3', 'REP5') and argus_active:
                total += 1
                if argus_recv >= K: success += 1
                argus_active = False

            if mode == 'RAW':
                total += 1
                if bits[t_mod] == 1: success += 1
            elif mode == 'REP3':
                total += 1
                if any(bits[(t + off) % N_BITS] == 1 for off in range(3)): success += 1
            elif mode == 'REP5':
                total += 1
                if any(bits[(t + off) % N_BITS] == 1 for off in range(5)): success += 1
            else:
                win_idx = t_mod // WINDOW_BITS
                pred_pdr, pred_burst = ch_input.get(win_idx)
                N, G = lut.lookup(pred_pdr, pred_burst, K)
                N = max(K, min(255, int(N))); G = max(0, int(G))
                n_triggers += 1; sum_N += N
                argus_active = True
                argus_recv = 1 if bits[t_mod] == 1 else 0
                argus_remaining = N - 1; argus_spacing = G + 1
                if argus_remaining == 0:
                    total += 1
                    if argus_recv >= K: success += 1
                    argus_active = False
                else:
                    argus_next_shard_t = t + argus_spacing

    return SimResult(mode=mode, total=total, success=success, sum_N=sum_N, n_triggers=n_triggers)


def get_overhead(res: SimResult, K: int) -> float:
    if res.mode == 'RAW':  return 1.0
    if res.mode == 'REP3': return 3.0
    if res.mode == 'REP5': return 5.0
    return (res.sum_N / res.n_triggers if res.n_triggers else float(K)) / K


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    bits      = load_trace_bits('trace.bin')
    truth_csv = 'prediction_results_argus_c.csv'
    skip_bsm  = build_skip_mask(bits, BSM_CONFIG['threshold'])
    skip_sdsm = build_skip_mask(bits, SDSM_CONFIG['threshold'])
    lut_bsm   = LUTEngine(BSM_CONFIG['lut_csv'],  BSM_CONFIG['fallback_N'])
    lut_sdsm  = LUTEngine(SDSM_CONFIG['lut_csv'], SDSM_CONFIG['fallback_N'])

    inputs = {'NAIVE': ChannelInput('NAIVE', truth_csv=truth_csv),
              'ORACLE': ChannelInput('ORACLE', truth_csv=truth_csv)}
    for name, csv in ARGUS_CSVS.items():
        inputs[name] = ChannelInput(name, pred_csv=csv)

    ALL_MODES = ['RAW', 'REP3', 'REP5', 'NAIVE'] + list(ARGUS_CSVS.keys()) + ['ORACLE']

    print(f"{'Mode':<12} | {'BSM Outage':>12} {'BSM OH':>8} | {'SDSM Outage':>12} {'SDSM OH':>9}")
    print('-' * 62)

    bsm_res, sdsm_res = {}, {}
    for mode in ALL_MODES:
        ch = inputs.get(mode)
        r_b = simulate(bits, skip_bsm,  ch, lut_bsm,  mode, BSM_CONFIG['K'],  BSM_CONFIG['period'],  BSM_CONFIG['jitter'],  TARGET_MSGS)
        r_s = simulate(bits, skip_sdsm, ch, lut_sdsm, mode, SDSM_CONFIG['K'], SDSM_CONFIG['period'], SDSM_CONFIG['jitter'], TARGET_MSGS)
        bsm_res[mode] = r_b; sdsm_res[mode] = r_s
        print(f"{mode:<12} | {r_b.outage_pct:>11.2f}%  {get_overhead(r_b,8):>7.2f}x | "
              f"{r_s.outage_pct:>11.2f}%  {get_overhead(r_s,27):>8.2f}x")

    _plot(ALL_MODES, bsm_res, sdsm_res)
    print("\n-> 'argus_results.pdf' / 'argus_results.eps' saved")


# ─────────────────────────────────────────────
# Plot — 1×2 layout for a full-width journal figure
#   IEEE 2-column 전체 폭 = 7.16 in
#   높이 = 3.2 in (compact)
# ─────────────────────────────────────────────
def _plot(modes, bsm_res, sdsm_res):
    x = np.arange(len(modes))

    bsm_out  = [bsm_res[m].outage_pct         for m in modes]
    sdsm_out = [sdsm_res[m].outage_pct        for m in modes]
    bsm_oh   = [get_overhead(bsm_res[m],  8)  for m in modes]
    sdsm_oh  = [get_overhead(sdsm_res[m], 27) for m in modes]
    max_oh   = max(max(bsm_oh), max(sdsm_oh))

    colors = ['#d9d9d9', '#bdbdbd', '#969696',           # RAW REP3 REP5
              '#f0ad4e',                                   # NAIVE
              '#9ecae1', '#6baed6', '#3182bd', '#08519c',  # ARGUS C/B/R/E
              '#8c6bb1']                                   # ORACLE

    fig, axes = plt.subplots(1, 2, figsize=(7.16, 3.2))

    for ax, outages, oh_vals, title in [
        (axes[0], bsm_out,  bsm_oh,  '(a) BSM (56 Bytes)'),
        (axes[1], sdsm_out, sdsm_oh, '(b) SDSM (513 Bytes)'),
    ]:
        bars = ax.bar(x, outages, color=colors, edgecolor='black',
                      linewidth=0.8, alpha=0.85)
        ax.set_ylim(0, 15)
        ax.set_title(title, fontweight='bold', pad=4)
        ax.set_ylabel('Outage Probability (%)', fontweight='bold')

        # 99% target line
        ax.axhline(1.0, color='#e31a1c', linestyle='-.', linewidth=1.2)

        # Target annotation
        ax.text(len(modes) - 0.8, 2.8, 'Target (1%)',
                color='#e31a1c', fontsize=8, fontweight='bold',
                ha='right', va='center')
        ax.annotate('',
                    xy=(len(modes) - 0.5, 1.0),
                    xytext=(len(modes) - 0.5, 2.6),
                    arrowprops=dict(
                        color='#e31a1c', arrowstyle='-|>',
                        linewidth=1.0, shrinkA=0, shrinkB=0))

        # Bar value labels
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.15,
                    f'{h:.2f}%', ha='center', va='bottom',
                    fontweight='bold', fontsize=6.5)

        # Green shading for schemes meeting target
        passed = [i for i, v in enumerate(outages) if v <= 1.0]
        if passed:
            ax.axvspan(passed[0] - 0.5, passed[-1] + 0.5,
                       facecolor='#2ca02c', alpha=0.08, zorder=0)

        # Overhead on twin axis
        ax2 = ax.twinx()
        ax2.plot(x, oh_vals, color='#e31a1c', marker='D',
                 markersize=4.5, linewidth=1.2, linestyle='--')
        ax2.set_ylim(0, max_oh * 1.35)
        ax2.set_ylabel(r'Normalized Overhead ($\times$ Baseline)',
                       fontweight='bold', color='#e31a1c', fontsize=8.5)
        ax2.tick_params(axis='y', labelcolor='#e31a1c')

        ax.set_xticks(x)
        ax.set_xticklabels(modes, rotation=30, ha='right')
        ax.grid(axis='y', linestyle='--', alpha=0.5, linewidth=0.5)

    plt.tight_layout(pad=0.8, w_pad=2.5)
    plt.savefig('argus_results.pdf', format='pdf', dpi=600, bbox_inches='tight')
    plt.savefig('argus_results.eps', format='eps', dpi=600, bbox_inches='tight')


if __name__ == '__main__':
    main()
"""
ARGUS Simulation Script
=======================
비교 대상:
  RAW, REP3, REP5                  : 고정 베이스라인
  NAIVE                            : t-1 채널 관측값 → t 예측 (단순 1-lag)
  ARGUS-C/B/R/E                    : EWMA 기반 보수적 예측 (z=0.00/0.60/0.99/1.65)
  ORACLE                           : t±2 윈도우 5개 중 최악값 (non-causal upper bound)

실행 방법:
  python argus_sim.py

필요 파일 (같은 디렉토리):
  trace.bin                        : 패킷 수신 이진 트레이스 (packed bits)
  prediction_results_argus_c.csv   : ARGUS-C 예측 결과 (z=0.00)
  prediction_results_argus_b.csv   : ARGUS-B 예측 결과 (z=0.60)
  prediction_results_argus_r.csv   : ARGUS-R 예측 결과 (z=0.99)
  prediction_results_argus_e.csv   : ARGUS-E 예측 결과 (z=1.65)
  56LUT_3_Balanced.csv             : BSM LUT  (컬럼: PDR_Env, Burst_1_over_r, Action_N, Action_G)
  513LUT_3_Balanced.csv            : SDSM LUT (동일 형식)
"""
#
# from __future__ import annotations
# import os
# import random
# from dataclasses import dataclass
# from typing import Dict, Tuple
#
# import numpy as np
# import pandas as pd
# import matplotlib
# matplotlib.use('Agg')
# import matplotlib.pyplot as plt
#
# # ─────────────────────────────────────────────
# # 전역 플롯 설정
# # Elsevier Vehicular Communications 단단(single-column) 포맷
# #   단단 텍스트 폭 ≈ 90 mm = 3.54 in
# #   2-panel 세로 배치 → figsize=(3.54, 5.0)
# # ─────────────────────────────────────────────
# plt.rcParams.update({
#     'font.family':       'serif',
#     'font.serif':        ['Times New Roman'],
#     'mathtext.fontset':  'stix',
#     'font.size':         7,
#     'axes.labelsize':    8,
#     'axes.titlesize':    8,
#     'xtick.labelsize':   6.5,
#     'ytick.labelsize':   7,
#     'lines.linewidth':   1.0,
#     'axes.linewidth':    0.7,
#     'xtick.major.width': 0.7,
#     'ytick.major.width': 0.7,
#     'legend.fontsize':   6.5,
#     'pdf.fonttype':      42,   # TrueType 임베딩 (Elsevier 필수)
#     'ps.fonttype':       42,
# })
#
# # ─────────────────────────────────────────────
# # 설정값
# # ─────────────────────────────────────────────
# WINDOW_BITS = 100
# ORACLE_HALF = 2
#
# BSM_CONFIG  = dict(lut_csv='56LUT_3_Balanced.csv',  threshold=324, fallback_N=27, period=200, jitter=10, K=8)
# SDSM_CONFIG = dict(lut_csv='513LUT_3_Balanced.csv', threshold=312, fallback_N=80, period=500, jitter=25, K=27)
#
# ARGUS_CSVS = {
#     'ARGUS-C': 'prediction_results_argus_c.csv',
#     'ARGUS-B': 'prediction_results_argus_b.csv',
#     'ARGUS-R': 'prediction_results_argus_r.csv',
#     'ARGUS-E': 'prediction_results_argus_e.csv',
# }
#
# TARGET_MSGS = 100_000
# RANDOM_SEED = 42
#
# # ─────────────────────────────────────────────
# # 트레이스 로더
# # ─────────────────────────────────────────────
# def load_trace_bits(path: str) -> np.ndarray:
#     if not os.path.exists(path):
#         raise FileNotFoundError(f"trace file not found: {path}")
#     with open(path, 'rb') as f:
#         packed = np.frombuffer(f.read(), dtype=np.uint8)
#     return np.unpackbits(packed)
#
#
# def build_skip_mask(bits: np.ndarray, threshold: int) -> np.ndarray:
#     mask = np.zeros(len(bits), dtype=bool)
#     count = 0
#     for i in range(len(bits)):
#         if bits[i] == 0:
#             count += 1
#         else:
#             if count >= threshold:
#                 mask[i - count: i] = True
#             count = 0
#     if count >= threshold:
#         mask[len(bits) - count:] = True
#     return mask
#
#
# # ─────────────────────────────────────────────
# # LUT 엔진
# # ─────────────────────────────────────────────
# class LUTEngine:
#     def __init__(self, csv_path: str, fallback_N: int, fallback_G: int = 0):
#         self.fallback = (fallback_N, fallback_G)
#         if not os.path.exists(csv_path):
#             print(f"  [경고] LUT 파일 없음: {csv_path} → fallback N={fallback_N} 사용")
#             self.pdr_keys = []; self.burst_keys = []; self.lut: Dict = {}
#             return
#         df = pd.read_csv(csv_path)
#         self.pdr_keys   = sorted(df['PDR_Env'].unique().tolist())
#         self.burst_keys = sorted(df['Burst_1_over_r'].unique().tolist())
#         self.lut = {
#             (float(r['PDR_Env']), float(r['Burst_1_over_r'])): (int(r['Action_N']), int(r['Action_G']))
#             for _, r in df.iterrows()
#         }
#
#     def lookup(self, pdr: float, burst: float, K: int) -> Tuple[int, int]:
#         if not self.lut:
#             return self.fallback
#         if burst > max(self.burst_keys):
#             return (64, 2) if K == 8 else (140, 1)
#         pdr_q = self.pdr_keys[0]
#         for k in self.pdr_keys:
#             if k <= pdr:
#                 pdr_q = k
#         burst_q = self.burst_keys[-1]
#         for k in self.burst_keys:
#             if k >= burst:
#                 burst_q = k
#                 break
#         return self.lut.get((pdr_q, burst_q), self.fallback)
#
#
# # ─────────────────────────────────────────────
# # 채널 입력 전략
# # ─────────────────────────────────────────────
# class ChannelInput:
#     def __init__(self, mode: str, pred_csv: str = None, truth_csv: str = None):
#         self.mode = mode
#         if mode == 'NAIVE':
#             df = pd.read_csv(truth_csv)
#             pdr_truth = df['PDR'].values; burst_truth = df['Max_Burst'].values
#             self.pdr_input   = np.concatenate([[0.45], pdr_truth[:-1]])
#             self.burst_input = np.concatenate([[40.0], burst_truth[:-1]])
#         elif mode == 'ORACLE':
#             df = pd.read_csv(truth_csv)
#             pdr_truth = df['PDR'].values; burst_truth = df['Max_Burst'].values
#             n = len(pdr_truth)
#             self.pdr_input = np.zeros(n); self.burst_input = np.zeros(n)
#             for t in range(n):
#                 lo = max(0, t - ORACLE_HALF); hi = min(n, t + ORACLE_HALF + 1)
#                 self.pdr_input[t]   = pdr_truth[lo:hi].min()
#                 self.burst_input[t] = burst_truth[lo:hi].max()
#         elif mode.startswith('ARGUS'):
#             df = pd.read_csv(pred_csv)
#             self.pdr_input   = df['Pred_PDR_cons'].values
#             self.burst_input = df['Pred_B_cons'].values
#         else:
#             self.pdr_input = None; self.burst_input = None
#
#     def get(self, win_idx: int) -> Tuple[float, float]:
#         idx = min(win_idx, len(self.pdr_input) - 1)
#         return float(self.pdr_input[idx]), float(self.burst_input[idx])
#
#
# # ─────────────────────────────────────────────
# # 결과 컨테이너
# # ─────────────────────────────────────────────
# @dataclass
# class SimResult:
#     mode: str; total: int; success: int; sum_N: float = 0.0; n_triggers: int = 0
#
#     @property
#     def outage_pct(self) -> float:
#         return (1.0 - self.success / self.total) * 100.0 if self.total else 100.0
#
#
# # ─────────────────────────────────────────────
# # 시뮬레이터
# # ─────────────────────────────────────────────
# def simulate(bits, skip_mask, ch_input, lut, mode, K, period, jitter, target) -> SimResult:
#     random.seed(RANDOM_SEED)
#     N_BITS = len(bits)
#     total = success = n_triggers = 0
#     sum_N = 0.0
#     argus_active = False
#     argus_recv = argus_remaining = argus_next_shard_t = argus_spacing = 0
#     t = 0
#     next_msg_t = random.randint(period - jitter, period + jitter)
#
#     while total < target:
#         if mode not in ('RAW', 'REP3', 'REP5') and argus_active:
#             t = min(next_msg_t, argus_next_shard_t)
#         else:
#             t = next_msg_t
#         t_mod = t % N_BITS
#
#         if mode not in ('RAW', 'REP3', 'REP5') and argus_active and t == argus_next_shard_t:
#             if bits[t_mod] == 1:
#                 argus_recv += 1
#             argus_remaining -= 1
#             if argus_remaining == 0:
#                 total += 1
#                 if argus_recv >= K: success += 1
#                 argus_active = False
#             else:
#                 argus_next_shard_t += argus_spacing
#             if t != next_msg_t:
#                 continue
#
#         if t == next_msg_t:
#             next_msg_t += random.randint(period - jitter, period + jitter)
#             if skip_mask[t_mod]:
#                 if mode not in ('RAW', 'REP3', 'REP5'): argus_active = False
#                 continue
#             if mode not in ('RAW', 'REP3', 'REP5') and argus_active:
#                 total += 1
#                 if argus_recv >= K: success += 1
#                 argus_active = False
#
#             if mode == 'RAW':
#                 total += 1
#                 if bits[t_mod] == 1: success += 1
#             elif mode == 'REP3':
#                 total += 1
#                 if any(bits[(t + off) % N_BITS] == 1 for off in range(3)): success += 1
#             elif mode == 'REP5':
#                 total += 1
#                 if any(bits[(t + off) % N_BITS] == 1 for off in range(5)): success += 1
#             else:
#                 win_idx = t_mod // WINDOW_BITS
#                 pred_pdr, pred_burst = ch_input.get(win_idx)
#                 N, G = lut.lookup(pred_pdr, pred_burst, K)
#                 N = max(K, min(255, int(N))); G = max(0, int(G))
#                 n_triggers += 1; sum_N += N
#                 argus_active = True
#                 argus_recv = 1 if bits[t_mod] == 1 else 0
#                 argus_remaining = N - 1; argus_spacing = G + 1
#                 if argus_remaining == 0:
#                     total += 1
#                     if argus_recv >= K: success += 1
#                     argus_active = False
#                 else:
#                     argus_next_shard_t = t + argus_spacing
#
#     return SimResult(mode=mode, total=total, success=success, sum_N=sum_N, n_triggers=n_triggers)
#
#
# def get_overhead(res: SimResult, K: int) -> float:
#     if res.mode == 'RAW':  return 1.0
#     if res.mode == 'REP3': return 3.0
#     if res.mode == 'REP5': return 5.0
#     return (res.sum_N / res.n_triggers if res.n_triggers else float(K)) / K
#
#
# # ─────────────────────────────────────────────
# # 메인
# # ─────────────────────────────────────────────
# def main():
#     bits      = load_trace_bits('trace.bin')
#     truth_csv = 'prediction_results_argus_c.csv'
#     skip_bsm  = build_skip_mask(bits, BSM_CONFIG['threshold'])
#     skip_sdsm = build_skip_mask(bits, SDSM_CONFIG['threshold'])
#     lut_bsm   = LUTEngine(BSM_CONFIG['lut_csv'],  BSM_CONFIG['fallback_N'])
#     lut_sdsm  = LUTEngine(SDSM_CONFIG['lut_csv'], SDSM_CONFIG['fallback_N'])
#
#     inputs = {'NAIVE': ChannelInput('NAIVE', truth_csv=truth_csv),
#               'ORACLE': ChannelInput('ORACLE', truth_csv=truth_csv)}
#     for name, csv in ARGUS_CSVS.items():
#         inputs[name] = ChannelInput(name, pred_csv=csv)
#
#     ALL_MODES = ['RAW', 'REP3', 'REP5', 'NAIVE'] + list(ARGUS_CSVS.keys()) + ['ORACLE']
#
#     print(f"{'Mode':<12} | {'BSM Outage':>12} {'BSM OH':>8} | {'SDSM Outage':>12} {'SDSM OH':>9}")
#     print('-' * 62)
#
#     bsm_res, sdsm_res = {}, {}
#     for mode in ALL_MODES:
#         ch = inputs.get(mode)
#         r_b  = simulate(bits, skip_bsm,  ch, lut_bsm,  mode, BSM_CONFIG['K'],  BSM_CONFIG['period'],  BSM_CONFIG['jitter'],  TARGET_MSGS)
#         r_s  = simulate(bits, skip_sdsm, ch, lut_sdsm, mode, SDSM_CONFIG['K'], SDSM_CONFIG['period'], SDSM_CONFIG['jitter'], TARGET_MSGS)
#         bsm_res[mode] = r_b; sdsm_res[mode] = r_s
#         print(f"{mode:<12} | {r_b.outage_pct:>11.2f}%  {get_overhead(r_b,8):>7.2f}x | "
#               f"{r_s.outage_pct:>11.2f}%  {get_overhead(r_s,27):>8.2f}x")
#
#     _plot(ALL_MODES, bsm_res, sdsm_res)
#     print("\n→ 'argus_results.pdf' / 'argus_results.eps' 저장 완료")
#
#
# # ─────────────────────────────────────────────
# # 플롯 — 2×1 세로 배치 (단단 포맷)
# # ─────────────────────────────────────────────
# def _plot(modes, bsm_res, sdsm_res):
#     x = np.arange(len(modes))
#
#     bsm_out  = [bsm_res[m].outage_pct         for m in modes]
#     sdsm_out = [sdsm_res[m].outage_pct        for m in modes]
#     bsm_oh   = [get_overhead(bsm_res[m],  8)  for m in modes]
#     sdsm_oh  = [get_overhead(sdsm_res[m], 27) for m in modes]
#     max_oh   = max(max(bsm_oh), max(sdsm_oh))
#
#     colors = ['#d9d9d9', '#bdbdbd', '#969696',           # RAW REP3 REP5
#               '#f0ad4e',                                   # NAIVE
#               '#9ecae1', '#6baed6', '#3182bd', '#08519c',  # ARGUS C/B/R/E
#               '#8c6bb1']                                   # ORACLE
#
#     # 단단 폭 3.54 in, 2-panel 세로 → 높이 5.0 in
#     fig, axes = plt.subplots(2, 1, figsize=(3.54, 5.0))
#
#     for ax, outages, oh_vals, title in [
#         (axes[0], bsm_out,  bsm_oh,  '(a) BSM (56 Bytes)'),
#         (axes[1], sdsm_out, sdsm_oh, '(b) SDSM (513 Bytes)'),
#     ]:
#         bars = ax.bar(x, outages, color=colors, edgecolor='black',
#                       linewidth=0.6, alpha=0.85)
#         ax.set_ylim(0, 15)
#         ax.set_title(title, fontweight='bold', pad=3)
#         ax.set_ylabel('Outage Probability (%)', fontweight='bold')
#         ax.axhline(1.0, color='#e31a1c', linestyle='-.', linewidth=1.0)
#
#         target_y = 1.0
#         text_height = 2.5 # 텍스트가 떠 있을 높이
#
#         # 1. 'Target (1%)' 글씨: 화살표보다 약간 왼쪽(0.8)에 배치하고 오른쪽 정렬(ha='right')
#         ax.text(len(modes) - 0.6, 2.7, 'Target (1%)',
#                 color='#e31a1c', fontsize=6, fontweight='bold',
#                 ha='right', va='center')
#
#         # 2. 화살표: 글씨의 오른쪽 끝(0.5) 지점에서 수직으로 떨어뜨림
#         ax.annotate('',
#                     xy=(len(modes) - 0.5, 1.0),      # 화살촉 (Target line)
#                     xytext=(len(modes) - 0.5, 2.5),  # 화살표 시작점 (글씨 높이와 맞춤)
#                     arrowprops=dict(
#                         color='#e31a1c',
#                         arrowstyle='-|>',
#                         linewidth=0.9,
#                         shrinkA=0,  # 몸통이 잘리지 않도록 0 설정
#                         shrinkB=0   # 몸통이 잘리지 않도록 0 설정
#                     ))
#         for bar in bars:
#             h = bar.get_height()
#             ax.text(bar.get_x() + bar.get_width() / 2, h + 0.1,
#                     f'{h:.2f}%', ha='center', va='bottom',
#                     fontweight='bold', fontsize=4.5, rotation=0)
#
#         passed = [i for i, v in enumerate(outages) if v <= 1.0]
#         if passed:
#             ax.axvspan(passed[0] - 0.5, passed[-1] + 0.5,
#                        facecolor='#2ca02c', alpha=0.08, zorder=0)
#
#         ax2 = ax.twinx()
#         ax2.plot(x, oh_vals, color='#e31a1c', marker='D',
#                  markersize=3.5, linewidth=0.9, linestyle='--')
#         ax2.set_ylim(0, max_oh * 1.35)
#         ax2.set_ylabel(r'Norm. Overhead ($\times$Baseline)',
#                        fontweight='bold', color='#e31a1c', fontsize=6.5)
#         ax2.tick_params(axis='y', labelcolor='#e31a1c', labelsize=6.5)
#
#         ax.set_xticks(x)
#         ax.set_xticklabels(modes, rotation=35, ha='right', fontsize=6)
#         ax.grid(axis='y', linestyle='--', alpha=0.5, linewidth=0.5)
#         ax.tick_params(axis='both', which='major', length=2.5, width=0.7)
#
#     plt.tight_layout(pad=0.6, h_pad=1.8)
#     plt.savefig('argus_results.pdf', format='pdf', dpi=600, bbox_inches='tight')
#     plt.savefig('argus_results.eps', format='eps', dpi=600, bbox_inches='tight')
#
#
# if __name__ == '__main__':
#     main()
