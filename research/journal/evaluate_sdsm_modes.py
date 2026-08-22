from __future__ import annotations
import os
import random
from dataclasses import dataclass
from typing import Dict, Tuple, List
import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None
import matplotlib.pyplot as plt

# ==========================================
# 1. IEEE 논문 스타일 전역 설정
# ==========================================
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'mathtext.fontset': 'stix',
    'font.size': 10,
    'axes.labelsize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'lines.linewidth': 1.5,
    'axes.linewidth': 0.8
})

# -----------------------
# Trace loader
# -----------------------
def load_trace_bits(trace_bin_path: str) -> np.ndarray:
    if not os.path.exists(trace_bin_path):
        return np.array([], dtype=np.uint8)
    with open(trace_bin_path, "rb") as f:
        packed = np.frombuffer(f.read(), dtype=np.uint8)
    return np.unpackbits(packed)

@dataclass
class TraceState:
    bits: np.ndarray
    skip_mask: np.ndarray = None

    def __post_init__(self):
        if self.length > 0:
            self.skip_mask = np.zeros(self.length, dtype=bool)
            self._build_skip_mask(threshold=312)
        else:
            self.skip_mask = np.array([], dtype=bool)

    def _build_skip_mask(self, threshold: int):
        count = 0
        for i in range(self.length):
            if self.bits[i] == 0: count += 1
            else:
                if count >= threshold: self.skip_mask[i - count : i] = True
                count = 0
        if count >= threshold: self.skip_mask[self.length - count : self.length] = True

    @property
    def length(self) -> int:
        return int(self.bits.size)

    def get_bit(self, t: int) -> int:
        if self.length == 0: return 1
        return int(self.bits[t % self.length])

# -----------------------
# LUT Loader
# -----------------------
class ErrorControlLUT:
    def __init__(self, csv_path: str):
        self.lut: Dict[Tuple[float, float], Tuple[int, int]] = {}
        self.ready = False
        if pd is None or not os.path.exists(csv_path): return
        df = pd.read_csv(csv_path)
        if len(df) == 0: return

        self.pdr_keys = sorted([float(x) for x in df["PDR_Env"].unique()])
        self.burst_keys = sorted([float(x) for x in df["Burst_1_over_r"].unique()])
        for _, r in df.iterrows():
            self.lut[(float(r["PDR_Env"]), float(r["Burst_1_over_r"]))] = (int(r["Action_N"]), int(r["Action_G"]))
        self.ready = True

    def get_optimal_params(self, current_pdr: float, current_burst: float) -> Tuple[int, int]:
        if not self.ready: return (0, 0)
        if current_burst > 40:
            return (140, 1)

        mp = self.pdr_keys[0] if current_pdr <= self.pdr_keys[0] else \
             self.pdr_keys[-1] if current_pdr >= self.pdr_keys[-1] else \
             self.pdr_keys[np.searchsorted(self.pdr_keys, current_pdr, side="right") - 1]

        mb = self.burst_keys[0] if current_burst <= self.burst_keys[0] else \
             self.burst_keys[-1] if current_burst >= self.burst_keys[-1] else \
             self.burst_keys[np.searchsorted(self.burst_keys, current_burst, side="left")]

        return self.lut.get((mp, mb), (80, 0))

class ChannelMetrics:
    def __init__(self, csv_path: str):
        self.df = None
        self.ready = False
        if pd is None or not os.path.exists(csv_path): return
        df = pd.read_csv(csv_path)
        if len(df) > 0:
            self.df = df
            self.df['Oracle_PDR'] = self.df['PDR'].rolling(window=5, center=True, min_periods=1).min()
            self.df['Oracle_Burst'] = self.df['Max_Burst'].rolling(window=5, center=True, min_periods=1).max()
            self.ready = True

    def get_predicted(self, trace_idx: int, window_bits: int = 100) -> Tuple[float, float]:
        if not self.ready: return 0.99, 1.0
        win = min(trace_idx // window_bits, len(self.df) - 1)
        return float(self.df.iloc[win]["Pred_PDR_cons"]), float(self.df.iloc[win]["Pred_B_cons"])

    def get_naive(self, trace_idx: int, window_bits: int = 100) -> Tuple[float, float]:
        if not self.ready: return 0.99, 1.0
        win = min(trace_idx // window_bits, len(self.df) - 1)
        return float(self.df.iloc[win]["PDR"]), float(self.df.iloc[win]["Max_Burst"])

    def get_oracle(self, trace_idx: int, window_bits: int = 100) -> Tuple[float, float]:
        if not self.ready: return 0.99, 1.0
        win = min(trace_idx // window_bits, len(self.df) - 1)
        return float(self.df.iloc[win]["Oracle_PDR"]), float(self.df.iloc[win]["Oracle_Burst"])

# -----------------------
# Results Stats
# -----------------------
@dataclass
class ModeStats:
    mode: str
    bsm_total: int
    bsm_success: int
    bsm_fail: int
    trace_cycles_done: int
    avg_N: float = 0.0
    avg_bytes: float = 0.0

    @property
    def pdr(self) -> float:
        return (self.bsm_success / self.bsm_total) if self.bsm_total else 0.0

# -----------------------
# Event-driven simulator
# -----------------------
class SenderSimEventDriven:
    def __init__(self, trace_bin="trace.bin", channel_metrics_csv="prediction_results_z0.00.csv",
                 lut_csv="513LUT_3_Balanced.csv", bsm_period_packets=500, jitter=25, K=27,
                 target_bsm_total=100000, silent_boot=False):
        self.trace = TraceState(load_trace_bits(trace_bin))
        self.metrics = ChannelMetrics(channel_metrics_csv)
        self.lut = ErrorControlLUT(lut_csv)
        self.BSM_PERIOD, self.JITTER, self.K, self.target_bsm_total = bsm_period_packets, jitter, K, target_bsm_total

    def run_mode(self, mode: str) -> ModeStats:
        if self.trace.length == 0: return ModeStats(mode, 0, 0, 0, 0, 0.0, 0.0)

        random.seed(42)
        t = 0
        next_bsm_t = random.randint(self.BSM_PERIOD - self.JITTER, self.BSM_PERIOD + self.JITTER)

        bsm_total = bsm_success = 0
        sum_N = argus_triggers = 0

        argus_active = False
        argus_recv = argus_remaining = argus_next_chunk_t = argus_spacing = 0

        while bsm_total < self.target_bsm_total:
            candidates = [next_bsm_t]
            if mode in ["ARGUS", "NAIVE", "ORACLE"] and argus_active:
                candidates.append(argus_next_chunk_t)
            t = min(candidates)

            if mode in ["ARGUS", "NAIVE", "ORACLE"] and argus_active and t == argus_next_chunk_t:
                if self.trace.get_bit(t) == 1: argus_recv += 1
                argus_remaining -= 1
                if argus_remaining == 0:
                    bsm_total += 1
                    if argus_recv >= self.K: bsm_success += 1
                    argus_active = False
                else: argus_next_chunk_t += argus_spacing

            if t == next_bsm_t:
                if self.trace.skip_mask[t % self.trace.length]:
                    next_bsm_t += random.randint(self.BSM_PERIOD - self.JITTER, self.BSM_PERIOD + self.JITTER)
                    if mode in ["ARGUS", "NAIVE", "ORACLE"]: argus_active = False
                    continue

                if mode in ["ARGUS", "NAIVE", "ORACLE"] and argus_active:
                    bsm_total += 1
                    if argus_recv >= self.K: bsm_success += 1
                    argus_active = False

                next_bsm_t += random.randint(self.BSM_PERIOD - self.JITTER, self.BSM_PERIOD + self.JITTER)

                if mode == "RAW":
                    bsm_total += 1
                    if self.trace.get_bit(t) == 1: bsm_success += 1

                elif mode == "REP3":
                    bsm_total += 1
                    if any(self.trace.get_bit(t + offset) == 1 for offset in range(3)): bsm_success += 1

                elif mode == "REP5":
                    bsm_total += 1
                    if any(self.trace.get_bit(t + offset) == 1 for offset in range(5)): bsm_success += 1

                elif mode in ["ARGUS", "NAIVE", "ORACLE"]:
                    idx = t % self.trace.length
                    if mode == "ARGUS": pred_pdr, pred_burst = self.metrics.get_predicted(idx)
                    elif mode == "NAIVE": pred_pdr, pred_burst = self.metrics.get_naive(idx)
                    elif mode == "ORACLE": pred_pdr, pred_burst = self.metrics.get_oracle(idx)

                    N, G = self.lut.get_optimal_params(pred_pdr, pred_burst)
                    N, G = max(self.K, min(255, int(N))), max(0, int(G))

                    argus_triggers += 1
                    sum_N += N

                    argus_active, argus_recv, argus_remaining, argus_spacing = True, (1 if self.trace.get_bit(t)==1 else 0), N-1, G+1

                    if argus_remaining == 0:
                        bsm_total += 1
                        if argus_recv >= self.K: bsm_success += 1
                        argus_active = False
                    else: argus_next_chunk_t = t + argus_spacing

        cycles = t // self.trace.length if self.trace.length else 0

        if mode == "RAW": avg_n_val = 1.0
        elif mode == "REP3": avg_n_val = 3.0
        elif mode == "REP5": avg_n_val = 5.0
        else: avg_n_val = (sum_N / argus_triggers) if argus_triggers > 0 else 0.0

        if mode in ["RAW", "REP3", "REP5"]:
            avg_bytes_val = avg_n_val * 513.0
        else:
            avg_bytes_val = avg_n_val * 19.0

        return ModeStats(mode, bsm_total, bsm_success, bsm_total - bsm_success, cycles, avg_n_val, avg_bytes_val)

def main():
    trace_bin = "trace.bin"
    lut_csv = "513LUT_3_Balanced.csv"

    metrics_csvs = ["prediction_results_z0.00.csv", "prediction_results_z0.60.csv",
                    "prediction_results_z0.95.csv", "prediction_results_z1.99.csv"]
    all_results = []

    print("\n[ Phase 1: Running Baselines, NAIVE, and Theoretical Upper Bound (513 Bytes) ]")
    sim_base = SenderSimEventDriven(trace_bin=trace_bin, channel_metrics_csv=metrics_csvs[0],
                                    lut_csv=lut_csv, bsm_period_packets=500, jitter=25, K=27,
                                    target_bsm_total=100000, silent_boot=True)

    for m in ["RAW", "REP3", "REP5", "NAIVE"]:
        all_results.append(sim_base.run_mode(m))

    for csv_file in metrics_csvs:
        z_val = csv_file.split('_')[-1].replace('.csv', '')
        sim_argus = SenderSimEventDriven(trace_bin=trace_bin, channel_metrics_csv=csv_file,
                                         lut_csv=lut_csv, bsm_period_packets=500, jitter=25, K=27,
                                         target_bsm_total=100000, silent_boot=True)
        res = sim_argus.run_mode("ARGUS")
        res.mode = f"ARGUS_z{z_val}" if "z" not in z_val else f"ARGUS_{z_val}"
        all_results.append(res)

    res_oracle = sim_base.run_mode("ORACLE")
    res_oracle.mode = "Upper Bound\n(Oracle)"
    all_results.append(res_oracle)

    print("\n" + "="*95)
    print(f" {'MODE':<20s} | {'Total':<8s} | {'Success':<8s} | {'PDR (%)':<8s} | {'Avg N':<8s} | {'Avg Bytes':<10s}")
    print("-" * 95)
    for r in all_results:
        print(f" {r.mode.replace(chr(10), ' '):<20s} | {r.bsm_total:<8d} | {r.bsm_success:<8d} | {100*r.pdr:>6.2f}% | {r.avg_N:>8.2f} | {r.avg_bytes:>7.2f} B")
    print("="*95)

    # ==========================================
    # 4. 이중 축(Dual-Axis) 바 & 라인 차트 생성
    # ==========================================
    print("\n[ PDF 이중 축 그래프 생성 중... ]")
    names = [r.mode for r in all_results]
    pdrs = [r.pdr * 100 for r in all_results]
    avg_bytes_list = [r.avg_bytes for r in all_results]

    colors = ['#cccccc', '#aaaaaa', '#777777', '#ffb347',
              'black', '#d62728', '#1f77b4', '#2ca02c', '#9467bd']

    fig, ax1 = plt.subplots(figsize=(12, 6))

    bars = ax1.bar(names, pdrs, color=colors, edgecolor='black', linewidth=1.2, alpha=0.85, label='PDR (Reliability)')
    ax1.set_ylim(85, 101)
    ax1.set_ylabel('Packet Delivery Ratio (PDR) %', fontweight='bold', fontsize=11)

    # 💡 [변경] 퍼센트 텍스트를 막대 바깥(위)이 아니라 막대 안쪽 상단으로 이동
    for i, bar in enumerate(bars):
        yval = bar.get_height()
        # 막대 색상이 밝은 회색 계열(처음 3개)이면 글씨를 검정색으로, 나머지는 흰색으로
        text_color = 'black' if i < 3 else 'white'
        ax1.text(bar.get_x() + bar.get_width()/2, yval - 1.3, # -1.0 만큼 아래로 내려 막대 안으로
                 f"{yval:.2f}%", ha='center', va='top', fontweight='bold', fontsize=10, color=text_color, zorder=10)

    ax1.axhline(y=99.0, color='#17becf', linestyle='-.', linewidth=2.5, zorder=1)
    ax1.text(-0.35, 98.4, '99% Reliability Target', color='#17becf', fontweight='bold', fontsize=10, ha='left', va='bottom')

    ax1.axvspan(5.5, 8.5, facecolor='#17becf', alpha=0.1, zorder=0)

    ax2 = ax1.twinx()
    line = ax2.plot(names, avg_bytes_list, color='#e31a1c', marker='D', markersize=8, linewidth=2.5,
                    linestyle='--', label='Average Payload Size (Bytes)')

    max_b = max(avg_bytes_list)
    ax2.set_ylim(0, max_b * 1.3)
    ax2.set_ylabel('Average Payload Size (Bytes)', fontweight='bold', fontsize=11, color='#e31a1c')
    ax2.tick_params(axis='y', labelcolor='#e31a1c')

    ax1.set_xticks(range(len(names)))
    ax1.set_xticklabels(names, rotation=20, ha='right')
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

    plt.tight_layout()
    plt.savefig("pdr_bytes_cost_dual_axis_sdsm.pdf", format='pdf', dpi=600)
    print("-> 'pdr_bytes_cost_dual_axis_sdsm.pdf' 저장 완료!\n")

if __name__ == "__main__":
    main()
