"""
ARGUS Figure 1 — Window-level extractor with LUT cell mapping

For each non-overlapping W=100 window, computes:
  - pdr_hat, b_hat                  : raw window statistics
  - pdr_cell, b_cell                : LUT cell after quantization (Eq. 13),
                                      or 'SAT' if the window falls outside the
                                      LUT grid on the worst-case side and
                                      the saturation policy is invoked.
  - region                          : 'grid' | 'sat_worst'

Quantization rules (Section IV-C, Eq. 13):
  Idx_PDR = floor_Q(PDR_hat)        downward to PDR grid
  Idx_b   = ceil_Q (b_hat)          upward   to b   grid
The PDR grid is {0.45, 0.55, ..., 0.95}.
The b   grid is {2, 3, 5, 10, 20, 40}.

Worst-case saturation (Section IV-C, sat_worst):
  PDR_hat < 0.45  OR  b_hat > 40    → fallback to pi_sat ({64,2} for BSM, {128,1} for SDSM)

Best-case boundary (PDR_hat > 0.95, or b_hat < 2) is NOT a saturation event:
the quantization rules clamp these windows into the lightest grid cell
(PDR=0.95, b=2). They are reported as normal 'grid' windows.

Usage:
    python extract_windows.py trace.bin                  # writes trace_windows.csv
    python extract_windows.py trace.bin out.csv          # custom output path

Or simply run without arguments — falls back to 'trace.bin' in cwd.
"""

import os
import sys
import csv
from collections import Counter

# ----- Configuration (matches the paper) -----
W = 100
PDR_GRID = [0.45, 0.55, 0.65, 0.75, 0.85, 0.95]    # Eq. (11)
B_GRID   = [2, 3, 5, 10, 20, 40]                   # Eq. (11)
# ----------------------------------------------


def iter_bits(file_path):
    """Yield each bit of the file, MSB-first per byte. 1 = success, 0 = loss."""
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                return
            for byte in chunk:
                for i in range(7, -1, -1):
                    yield (byte >> i) & 1


def windowize(bits, W):
    """
    Walk the bit stream in non-overlapping windows of length W.
    Emit (pdr_hat, b_hat) where b_hat = longest 0-run inside the window.
    Trailing partial window (< W bits) is discarded.
    """
    n_succ = 0
    cur_run = 0
    max_run = 0
    seen = 0
    for b in bits:
        if b == 1:
            n_succ += 1
            if cur_run > max_run:
                max_run = cur_run
            cur_run = 0
        else:
            cur_run += 1
        seen += 1
        if seen == W:
            if cur_run > max_run:
                max_run = cur_run
            yield (n_succ / W, max_run)
            n_succ = 0
            cur_run = 0
            max_run = 0
            seen = 0


def quantize_pdr(p):
    """
    floor_Q(p) into PDR_GRID.
      p < 0.45               -> 'SAT'  (sat_worst, lower bound)
      p >= 0.95              -> 0.95   (clamp upward, NOT saturation)
      else                   -> largest grid value <= p
    """
    if p < PDR_GRID[0]:
        return "SAT"
    if p >= PDR_GRID[-1]:
        return PDR_GRID[-1]
    chosen = PDR_GRID[0]
    for g in PDR_GRID:
        if g <= p:
            chosen = g
        else:
            break
    return chosen


def quantize_b(b):
    """
    ceil_Q(b) into B_GRID.
      b > 40                 -> 'SAT'  (sat_worst, upper bound)
      b <= 2                 -> 2      (clamp downward, NOT saturation)
      else                   -> smallest grid value >= b
    """
    if b > B_GRID[-1]:
        return "SAT"
    if b <= B_GRID[0]:
        return B_GRID[0]
    for g in B_GRID:
        if g >= b:
            return g
    return "SAT"


def cell_of(pdr, b):
    """Return (pdr_cell, b_cell, region) for a window."""
    pc = quantize_pdr(pdr)
    bc = quantize_b(b)
    region = "sat_worst" if (pc == "SAT" or bc == "SAT") else "grid"
    return pc, bc, region


def summarize(rows, label=""):
    n = len(rows)
    if n == 0:
        print("No complete windows extracted.")
        return

    pdrs = [r["pdr_hat"] for r in rows]
    bs   = [r["b_hat"]   for r in rows]

    n_grid = sum(1 for r in rows if r["region"] == "grid")
    n_sat  = sum(1 for r in rows if r["region"] == "sat_worst")

    print("=" * 78)
    if label:
        print(f"Trace: {label}")
    print(f"Windows extracted (W={W}, non-overlapping): {n:,}")
    print("-" * 78)
    print(f"PDR_hat   min/mean/max : {min(pdrs):.3f} / {sum(pdrs)/n:.3f} / {max(pdrs):.3f}")
    print(f"b_hat     min/mean/max : {min(bs)} / {sum(bs)/n:.2f} / {max(bs)}")
    print("-" * 78)
    print(f"Region:  grid       (LUT cell)            : {n_grid:>6,}  ({n_grid/n*100:6.2f}%)")
    print(f"         sat_worst  (pi_sat fallback)     : {n_sat :>6,}  ({n_sat /n*100:6.2f}%)")
    print("-" * 78)

    # ---- LUT cell occupancy table ----
    cell_count = Counter()
    for r in rows:
        cell_count[(r["pdr_cell"], r["b_cell"])] += 1

    pdr_axis = list(reversed(PDR_GRID)) + ["SAT"]   # PDR high (good) on top
    b_axis   = list(B_GRID) + ["SAT"]               # b low (good) on left

    print("LUT cell occupancy (count and % of all windows):")
    print()
    header = "PDR \\ b   |" + "".join(f" {str(bc):>7}" for bc in b_axis) + "  |  row %"
    print(header)
    print("-" * len(header))
    for pc in pdr_axis:
        row_total = 0
        cells = []
        for bc in b_axis:
            c = cell_count.get((pc, bc), 0)
            row_total += c
            cells.append(c)
        line = f"{str(pc):>9} |"
        for c in cells:
            if c == 0:
                line += f" {'.':>7}"
            else:
                line += f" {c:>7,}"
        line += f"  | {row_total/n*100:6.2f}%"
        print(line)
    print("-" * len(header))
    col_line = "    col % |"
    for bc in b_axis:
        col_total = sum(cell_count.get((pc, bc), 0) for pc in pdr_axis)
        col_line += f" {col_total/n*100:6.2f}%"
    col_line += "  |"
    print(col_line)
    print("=" * 78)


def main(in_path, out_path=None):
    if not os.path.isfile(in_path):
        print(f"File not found: {in_path}")
        sys.exit(1)

    if out_path is None:
        base, _ = os.path.splitext(in_path)
        out_path = f"{base}_windows.csv"

    rows = []
    for idx, (pdr, b) in enumerate(windowize(iter_bits(in_path), W)):
        pc, bc, region = cell_of(pdr, b)
        rows.append({
            "window_idx": idx,
            "pdr_hat":    pdr,
            "b_hat":      b,
            "pdr_cell":   pc,
            "b_cell":     bc,
            "region":     region,
        })

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["window_idx", "pdr_hat", "b_hat", "pdr_cell", "b_cell", "region"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows):,} rows to: {out_path}\n")
    summarize(rows, label=os.path.basename(in_path))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        main("trace.bin")
    else:
        main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)