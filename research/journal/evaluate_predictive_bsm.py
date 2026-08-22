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
            self._build_skip_mask(threshold=324)
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
        if not self.ready: return (27, 0)

        min_pdr = self.pdr_keys[0]
        max_burst = self.burst_keys[-1]

        if current_pdr < min_pdr or current_burst > max_burst:
            return self.lut.get((min_pdr, max_burst), (27, 0))

        mp = self.pdr_keys[-1] if current_pdr >= self.pdr_keys[-1] else \
             self.pdr_keys[np.searchsorted(self.pdr_keys, current_pdr, side="right") - 1]

        mb = self.burst_keys[0] if current_burst <= self.burst_keys[0] else \
             self.burst_keys[np.searchsorted(self.burst_keys, current_burst, side="left")]

        return self.lut.get((mp, mb), (27, 0))

# -----------------------
# 💡 완벽하게 통일된 Metrics 로더
# -----------------------
class ChannelMetrics:
    def __init__(self, csv_path: str):
        self.df = None
        self.ready = False
        if pd is None or not os.path.exists(csv_path):
            print(f"⚠️ 경고: {csv_path} 파일을 찾을 수 없습니다.")
            return
        df = pd.read_csv(csv_path)
        if len(df) > 0:
            self.df = df
            self.df['Oracle_PDR'] = self.df['PDR'].rolling(window=5, center=True, min_periods=1).min()
            self.df['Oracle_Burst'] = self.df['Max_Burst'].rolling(window=5, center=True, min_periods=1).max()
            self.ready = True

    def get_metrics(self, mode: str, trace_idx: int, window_bits: int = 100) -> Tuple[float, float]:
        if not self.ready: return 0.99, 1.0
        win = min(trace_idx // window_bits, len(self.df) - 1)
        row = self.df.iloc[win]

        if mode == "ORACLE":
            return float(row["Oracle_PDR"]), float(row["Oracle_Burst"])

        # 💡 NAIVE든 ARGUS든 시뮬레이터는 묻지도 따지지도 않고 Pred_PDR_cons를 읽는다. (인터페이스 통일)
        return float(row["Pred_PDR_cons"]), float(row["Pred_B_cons"])

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
                 lut_csv="56LUT_3_Balanced.csv", bsm_period_packets=200, jitter=10, K=8,
                 target_bsm_total=100000, silent_boot=False):
        self.trace = TraceState(load_trace_bits(trace_bin))
        self.metrics = ChannelMetrics(channel_metrics_csv)
        self.lut = ErrorControlLUT(lut_csv)
        self.BSM_PERIOD, self.JITTER, self.K, self.target_bsm_total = bsm_period_packets, jitter, K, target_bsm_total

    def run_mode(self, mode: str) -> ModeStats:
        if self.trace.length == 0: return ModeStats(mode, 0, 0, 0, 0, 0.0, 0.0)

        # Predictive 모드인지 확인
        is_predictive = any(x in mode for x in ["ARGUS", "NAIVE", "ORACLE"])

        random.seed(42)
        t = 0
        next_bsm_t = random.randint(self.BSM_PERIOD - self.JITTER, self.BSM_PERIOD + self.JITTER)

        bsm_total = bsm_success = 0
        sum_N = argus_triggers = 0

        argus_active = False
        argus_recv = argus_remaining = argus_next_chunk_t = argus_spacing = 0

        while bsm_total < self.target_bsm_total:
            candidates = [next_bsm_t]
            if is_predictive and argus_active:
                candidates.append(argus_next_chunk_t)
            t = min(candidates)

            if is_predictive and argus_active and t == argus_next_chunk_t:
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
                    if is_predictive: argus_active = False
                    continue

                if is_predictive and argus_active:
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

                elif is_predictive:
                    idx = t % self.trace.length
                    # 💡 get_naive 등 복잡한 거 다 빼고 get_metrics 단일 호출
                    pred_pdr, pred_burst = self.metrics.get_metrics("ORACLE" if mode == "ORACLE" else "PRED", idx)

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
            avg_bytes_val = avg_n_val * 56.0
        else:
            avg_bytes_val = avg_n_val * 7.0

        return ModeStats(mode, bsm_total, bsm_success, bsm_total - bsm_success, cycles, avg_n_val, avg_bytes_val)

def main():
    trace_bin = "trace.bin"
    lut_csv = "56LUT_3_Balanced.csv"

    # 💡 [핵심 복구] ARGUS용 4개, NAIVE용 4개 CSV 파일 분리 (네가 로컬에 구워놓은 8개 파일)
    z_str_list = ["0.00", "0.60", "0.95", "1.99"]
    argus_csvs = [f"prediction_results_z{z}.csv" for z in z_str_list]
    naive_csvs = [f"naiveprediction_results_z{z}.csv" for z in z_str_list]

    all_results = []

    print("\n[ Phase 1: Running Baselines and Oracle ]")
    # Base (RAW, REP3, REP5)
    sim_base = SenderSimEventDriven(trace_bin=trace_bin, channel_metrics_csv=argus_csvs[0],
                                    lut_csv=lut_csv, target_bsm_total=100000, silent_boot=True)
    for m in ["RAW", "REP3", "REP5"]:
        all_results.append(sim_base.run_mode(m))

    print("[ Phase 2: Running NAIVE (4 Margins) ]")
    for idx, csv_file in enumerate(naive_csvs):
        sim_naive = SenderSimEventDriven(trace_bin=trace_bin, channel_metrics_csv=csv_file,
                                         lut_csv=lut_csv, target_bsm_total=100000, silent_boot=True)
        z_val = z_str_list[idx]
        mode_name = "NAIVE" if z_val == "0.00" else f"NAIVE_z{z_val}"
        res = sim_naive.run_mode(mode_name)
        res.mode = mode_name
        all_results.append(res)

    print("[ Phase 3: Running ARGUS (4 Margins) ]")
    for idx, csv_file in enumerate(argus_csvs):
        sim_argus = SenderSimEventDriven(trace_bin=trace_bin, channel_metrics_csv=csv_file,
                                         lut_csv=lut_csv, target_bsm_total=100000, silent_boot=True)
        z_val = z_str_list[idx]
        mode_name = "ARGUS" if z_val == "0.00" else f"ARGUS_z{z_val}"
        res = sim_argus.run_mode(mode_name)
        res.mode = mode_name
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

    # 색상 매핑 (총 12개 바)
    colors = [
        '#d9d9d9', '#bdbdbd', '#969696',  # RAW, REP3, REP5
        '#fdd0a2', '#fdae6b', '#fd8d3c', '#e6550d',  # NAIVE 4개 (Oranges)
        '#c6dbef', '#9ecae1', '#4292c6', '#084594',  # ARGUS 4개 (Blues)
        '#807dba'   # Oracle
    ]

    fig, ax1 = plt.subplots(figsize=(14, 6))

    bars = ax1.bar(names, pdrs, color=colors, edgecolor='black', linewidth=1.2, alpha=0.85, label='PDR (Reliability)')
    ax1.set_ylim(85, 101)
    ax1.set_ylabel('Packet Delivery Ratio (PDR) %', fontweight='bold', fontsize=12)

    for i, bar in enumerate(bars):
        yval = bar.get_height()
        text_color = 'black' if yval > 90 else 'white' # 대비 조절
        ax1.text(bar.get_x() + bar.get_width()/2, yval - 0.5,
                 f"{yval:.2f}%", ha='center', va='top', fontweight='bold', fontsize=10, color=text_color, rotation=90)

    ax1.axhline(y=99.0, color='#17becf', linestyle='-.', linewidth=2.5)
    ax1.text(-0.35, 98.4, '99% Reliability Target', color='#17becf', fontweight='bold', fontsize=10, ha='left', va='bottom')

    # 💡 99% 달성 구간 하이라이트 배경 (수동 조정 필요)
    ax1.axvspan(6.5, 10.5, facecolor='#17becf', alpha=0.1, zorder=0)

    ax2 = ax1.twinx()
    line = ax2.plot(names, avg_bytes_list, color='#e31a1c', marker='D', markersize=8, linewidth=2.5,
                    linestyle='--', label='Average Payload Size (Bytes)')

    max_b = max(avg_bytes_list)
    ax2.set_ylim(0, max_b * 1.3)
    ax2.set_ylabel('Average Payload Size (Bytes)', fontweight='bold', fontsize=12, color='#e31a1c')
    ax2.tick_params(axis='y', labelcolor='#e31a1c')

    ax1.set_xticks(range(len(names)))
    ax1.set_xticklabels(names, rotation=35, ha='right', fontsize=10)
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

    plt.tight_layout()
    plt.savefig("pdr_bytes_cost_dual_axis_bsm.pdf", format='pdf', dpi=600)
    print("-> 'pdr_bytes_cost_dual_axis_bsm.pdf' 저장 완료!\n")

if __name__ == "__main__":
    main()