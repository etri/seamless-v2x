from __future__ import annotations
import os
import random
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional
import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

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
            # SDSM 주기가 500이므로, 500 이상의 데드존은 스킵해야 논리적으로 맞습니다.
            self._build_skip_mask(threshold=324)
        else:
            self.skip_mask = np.array([], dtype=bool)

    def _build_skip_mask(self, threshold: int):
        count = 0
        for i in range(self.length):
            if self.bits[i] == 0:
                count += 1
            else:
                if count >= threshold:
                    self.skip_mask[i - count : i] = True
                count = 0

        if count >= threshold:
            self.skip_mask[self.length - count : self.length] = True

    @property
    def length(self) -> int:
        return int(self.bits.size)

    def get_bit(self, t: int) -> int:
        if self.length == 0:
            return 1
        return int(self.bits[t % self.length])


# -----------------------
# LUT (PDR,Burst)->(N,G)
# -----------------------
class ErrorControlLUT:
    def __init__(self, csv_path: str):
        self.lut: Dict[Tuple[float, float], Tuple[int, int]] = {}
        self.pdr_keys: List[float] = []
        self.burst_keys: List[float] = []
        self.ready = False

        if pd is None:
            return
        if not os.path.exists(csv_path):
            return

        df = pd.read_csv(csv_path)
        if len(df) == 0:
            return

        self.pdr_keys = sorted([float(x) for x in df["PDR_Env"].unique()])
        self.burst_keys = sorted([float(x) for x in df["Burst_1_over_r"].unique()])
        for _, r in df.iterrows():
            self.lut[(float(r["PDR_Env"]), float(r["Burst_1_over_r"]))] = (int(r["Action_N"]), int(r["Action_G"]))
        self.ready = True

    def get_optimal_params(self, current_pdr: float, current_burst: float) -> Tuple[int, int]:
        if not self.ready:
            return 0
        if current_burst > 40:
            return (140, 1)

        # 작성자님의 'PDR 내림, Burst 올림' 보수적 접근 유지
        if current_pdr <= self.pdr_keys[0]: mp = self.pdr_keys[0]
        elif current_pdr >= self.pdr_keys[-1]: mp = self.pdr_keys[-1]
        else:
            i = np.searchsorted(self.pdr_keys, current_pdr, side="right")
            mp = self.pdr_keys[i - 1]

        if current_burst <= self.burst_keys[0]: mb = self.burst_keys[0]
        elif current_burst >= self.burst_keys[-1]: mb = self.burst_keys[-1]
        else:
            i = np.searchsorted(self.burst_keys, current_burst, side="left")
            mb = self.burst_keys[i]

        # LUT에 좌표가 없을 경우 크래시 방지용 기본값 추가
        return self.lut.get((mp, mb))


# -----------------------
# Channel metrics
# -----------------------
class ChannelMetrics:
    def __init__(self, csv_path: str):
        self.df = None
        self.ready = False
        if pd is None:
            return
        if not os.path.exists(csv_path):
            return
        df = pd.read_csv(csv_path)
        if len(df) == 0:
            return
        self.df = df
        self.ready = True

    def get_worst_in_neighborhood(self, trace_idx: int, window_bits: int = 100, lookaround: int = 2) -> Tuple[float, float]:
        if not self.ready:
            return 0  # 의도적 종료 장치

        win = trace_idx // window_bits

        # 앞뒤로 lookaround 만큼 윈도우 범위를 잡음 (데이터 범위를 벗어나지 않게 max, min 처리)
        start_win = max(0, win - lookaround)
        end_win = min(len(self.df) - 1, win + lookaround)

        # 해당 범위의 데이터 프레임 슬라이싱
        neighborhood = self.df.iloc[start_win : end_win + 1]

        # [핵심 로직] PDR은 가장 작은(나쁜) 값, Burst는 가장 큰(나쁜) 값 선택
        worst_pdr = float(neighborhood["PDR"].min())
        worst_burst = float(neighborhood["Max_Burst"].max())

        return worst_pdr, worst_burst


# -----------------------
# Results
# -----------------------
@dataclass
class ModeStats:
    mode: str
    sdsm_total: int
    sdsm_success: int
    sdsm_fail: int
    trace_cycles_done: int

    @property
    def pdr(self) -> float:
        return (self.sdsm_success / self.sdsm_total) if self.sdsm_total else 0.0


# -----------------------
# Event-driven simulator
# -----------------------
class SenderSimEventDriven:
    def __init__(self,
                 trace_bin="trace.bin",
                 channel_metrics_csv="channel_metrics.csv",
                 lut_csv="513LUT_3_Balanced.csv",
                 sdsm_period_packets=500,
                 jitter=20,
                 K=27,
                 target_packets=100000,
                 progress_every=1000,
                 silent_boot=False):
        self.trace_path = trace_bin
        self.metrics_path = channel_metrics_csv
        self.lut_path = lut_csv

        self.trace = TraceState(load_trace_bits(trace_bin))
        self.metrics = ChannelMetrics(channel_metrics_csv)
        self.lut = ErrorControlLUT(lut_csv)

        self.SDSM_PERIOD = int(sdsm_period_packets)
        self.JITTER = int(jitter)
        self.K = int(K)
        self.target_packets = int(target_packets)
        self.progress_every = int(progress_every)

        if not silent_boot:
            self._print_boot()

    def _print_boot(self):
        print("=== SenderSim (SDSM Mode, Target: 10,000 Packets) ===")
        print(f"trace bits: {self.trace.length}")
        if self.trace.length > 0:
            one_ratio = float(self.trace.bits.mean())
            skip_ratio = float(self.trace.skip_mask.mean())
            print(f"trace 1-ratio: {one_ratio*100:.2f}% | skip mask: {skip_ratio*100:.2f}%")
        print(f"SDSM period: {self.SDSM_PERIOD} ± {self.JITTER} | RS K={self.K}")
        print(f"Stop condition: SDSM count == {self.target_packets}")
        print("==============================================================\n")

    def run_mode(self, mode: str) -> ModeStats:

        if self.trace.length == 0:
            print(f"[{mode}] ERROR: trace is empty -> can't simulate drops.")
            return ModeStats(mode, 0, 0, 0, 0)

        t = 0
        next_sdsm_t = random.randint(self.SDSM_PERIOD - self.JITTER, self.SDSM_PERIOD + self.JITTER)

        sdsm_total = 0
        sdsm_success = 0

        argus_active = False
        argus_recv = 0
        argus_remaining = 0
        argus_next_chunk_t = 0
        argus_spacing = 0

        def progress(tag: str = ""):
            print(f"[{mode}] SDSM={sdsm_total}/{self.target_packets} succ={sdsm_success} "
                  f"fail={sdsm_total-sdsm_success} {tag}")

        # 타겟 패킷 수(10000개)를 채울 때까지 무한 루프
        while sdsm_total < self.target_packets:
            candidates = [next_sdsm_t]
            if mode == "ARGUS" and argus_active:
                candidates.append(argus_next_chunk_t)

            t = min(candidates)

            # 1. ARGUS 청크 전송 처리
            if mode == "ARGUS" and argus_active and t == argus_next_chunk_t:
                bit = self.trace.get_bit(t)
                if bit == 1:
                    argus_recv += 1
                argus_remaining -= 1

                if argus_remaining == 0:
                    sdsm_total += 1
                    if argus_recv >= self.K:
                        sdsm_success += 1
                    argus_active = False

                    if sdsm_total % self.progress_every == 0:
                        progress()
                else:
                    argus_next_chunk_t += argus_spacing

            # 2. 새로운 SDSM 발생 타이밍
            if t == next_sdsm_t:
                if self.trace.skip_mask[t % self.trace.length]:
                    next_sdsm_t += random.randint(self.SDSM_PERIOD - self.JITTER, self.SDSM_PERIOD + self.JITTER)
                    if mode == "ARGUS" and argus_active:
                        argus_active = False
                    continue

                if mode == "ARGUS" and argus_active:
                    sdsm_total += 1
                    if argus_recv >= self.K:
                        sdsm_success += 1
                    argus_active = False

                    if sdsm_total % self.progress_every == 0:
                        progress("(Early Cutoff Success!)" if argus_recv >= self.K else "(Early Cutoff Fail)")

                next_sdsm_t += random.randint(self.SDSM_PERIOD - self.JITTER, self.SDSM_PERIOD + self.JITTER)

                if mode == "RAW":
                    ok = (self.trace.get_bit(t) == 1)
                    sdsm_total += 1
                    sdsm_success += 1 if ok else 0

                elif mode == "REP3":
                    ok = False
                    for offset in range(3):
                        if self.trace.get_bit(t + offset) == 1:
                            ok = True
                    sdsm_total += 1
                    sdsm_success += 1 if ok else 0

                elif mode == "REP5":
                    ok = False
                    for offset in range(5):
                        if self.trace.get_bit(t + offset) == 1:
                            ok = True
                    sdsm_total += 1
                    sdsm_success += 1 if ok else 0

                elif mode == "ARGUS":
                    worst_pdr, worst_burst = self.metrics.get_worst_in_neighborhood(t % self.trace.length, window_bits=100, lookaround=2)
                    N, G = self.lut.get_optimal_params(worst_pdr, worst_burst)

                    N = max(self.K, min(255, int(N)))
                    G = max(0, int(G))

                    argus_active = True
                    argus_recv = 0
                    argus_remaining = N
                    argus_spacing = G + 1

                    bit = self.trace.get_bit(t)
                    if bit == 1:
                        argus_recv += 1
                    argus_remaining -= 1

                    if argus_remaining == 0:
                        sdsm_total += 1
                        if argus_recv >= self.K:
                            sdsm_success += 1
                        argus_active = False

                        if sdsm_total % self.progress_every == 0:
                            progress()
                    else:
                        argus_next_chunk_t = t + argus_spacing

                if mode != "ARGUS" and sdsm_total > 0 and sdsm_total % self.progress_every == 0:
                    progress()

        final_cycles = t // self.trace.length

        return ModeStats(
            mode=mode,
            sdsm_total=sdsm_total,
            sdsm_success=sdsm_success,
            sdsm_fail=sdsm_total - sdsm_success,
            trace_cycles_done=final_cycles,
        )


def main():
    trace_bin = "trace.bin"
    metrics_csv = "channel_metrics.csv"

    lut_files = [
        ("ARGUS_Overhead", "513LUT_1_Overhead_Focused.csv"),
        ("ARGUS_Latency",  "513LUT_2_Latency_Focused.csv"),
        ("ARGUS_Balanced", "513LUT_3_Balanced.csv")
    ]

    all_results = []

    print("\n[ Phase 1: Running Baselines (RAW, REP3, REP5) ]")
    sim_base = SenderSimEventDriven(
        trace_bin=trace_bin,
        channel_metrics_csv=metrics_csv,
        lut_csv=lut_files[0][1],
        sdsm_period_packets=500, jitter=20, K=27,
        target_packets=100000, progress_every=2500, silent_boot=False
    )

    for m in ["RAW", "REP3", "REP5"]:
        print(f"\n--- RUN {m} ---")
        all_results.append(sim_base.run_mode(m))

    print("\n[ Phase 2: Running ARGUS 3 Modes ]")
    for argus_name, lut_file in lut_files:
        print(f"\n--- RUN {argus_name} ({lut_file}) ---")
        sim_argus = SenderSimEventDriven(
            trace_bin=trace_bin,
            channel_metrics_csv=metrics_csv,
            lut_csv=lut_file,
            sdsm_period_packets=500, jitter=20, K=27,
            target_packets=100000, progress_every=2500, silent_boot=True
        )
        res = sim_argus.run_mode("ARGUS")
        res.mode = argus_name
        all_results.append(res)

    print("\n" + "="*80)
    print(" SUMMARY OF ALL MODES (10,000 SDSMs) ")
    print("="*80)
    for r in all_results:
        print(f"{r.mode:15s} | SDSM total={r.sdsm_total:6d} success={r.sdsm_success:6d} "
              f"fail={r.sdsm_fail:6d} | PDR={100*r.pdr:6.2f}%")
    print("="*80)

if __name__ == "__main__":
    main()