# Causal AL-FEC core replay: 2026-10-08 revision

This release makes the core results of the October 8 ARGUS TVT revision executable. The predictor and replay were reconstructed from the archived inputs and checked against the manuscript on October 12, 2026. They use **PDR and maximum loss-run length**, not vehicle speed.

The current entry point is [`revision20261008.py`](./revision20261008.py). It uses one fixed-parameter asymmetric EWMA, one-window causal input, the archived Balanced LUT, and a **312-carrier-position evaluation mask for both BSM and SDSM**. The mask selects a reporting subset; it never suppresses offered messages, changes actions, or filters transmissions.

## Run

Python 3.10 or newer is required.

```bash
cd research/journal
python -m pip install -r requirements.txt
python revision20261008.py --prediction-source verify --spacing both
python -m unittest discover -s tests -v
```

The paths are resolved relative to the script, so the main command also works from the repository root:

```bash
python research/journal/revision20261008.py --prediction-source verify --spacing both
```

`verify` regenerates the predictions and fails if they differ from the archived prediction inputs. `generated` uses regenerated predictions without requiring archived agreement; `archived` replays the supplied prediction CSVs. Calibration derives the reset scales from Trace-A only. The default `--calibration-policy archived_execution` retains full precision for A and transfers the derived values rounded to four PDR decimals and two burst decimals for B/C, reproducing the archived CSVs. Fitting uses all of A and is an offline, in-sample step, not an online causal operation. No B/C observations select the reset scales. `shared_full_precision` exposes the alternative and does not exactly match B/C archives.

Useful options:

```bash
python generate_predictions.py                         # predictions and coverage only
python evaluate_bsm_modes.py                           # BSM replay
python evaluate_sdsm_modes.py                          # SDSM replay
python compare_predictors.py                          # both profiles and spacing scenarios
python revision20261008.py --observation-source bits --prediction-source generated --output-dir /tmp/argus-from-bits
python revision20261008.py --calibration-policy shared_full_precision --prediction-source generated --output-dir /tmp/argus-shared-precision
```

Partial wrappers use distinct output folders (`predictions_only`, `results_bsm`, `results_sdsm`, `mode_coverage`) and preserve the complete `results` replay. Prediction-only execution does not overwrite an existing replay CSV/JSON. `select_margin.py` now reports the fixed reference modes and their coverage; it does not tune z. The old speed-conditioned implementation is preserved in [commit 8400a6e](https://github.com/etri/seamless-v2x/tree/8400a6e184286d73697f3eb5bd67bf7c6939d474/research/journal). The two `plot_*.py` files and PDFs in `results/` are historical visualizations from that snapshot, not revision reproductions. Current numerical outputs are in `revision20261008/results/`.

## Published inputs and outputs

[`revision20261008/inputs/`](./revision20261008/inputs) contains A/B/C packed binary receptions, four archived prediction CSVs per trace, and two Balanced LUTs. Prediction files expose only PDR, maximum run, and margin bounds; raw device/host logs, location metadata, paper files, and private paths are not republished. [`input_manifest.json`](./revision20261008/input_manifest.json) records the input hashes.

The default output directory contains:

- `replay.csv` / `replay.json`: every scheme/profile/trace, with offered/excluded/retained counts, excluded successes and failures, conditional and all-offered outage, and selected-symbol expansion.
- `coverage.csv`: same-window coverage after five warm-up windows, for both continuous archived bounds and integer burst queries.
- `predictions/`: regenerated causal prediction CSVs.
- `prediction_verification.json`: agreement of regenerated and archived inputs.
- `observed_metric_verification.json`: comparison of archived observations with metrics recomputed from packed bits.

The release reproduces **Table V coverage and Tables VI/VII point estimates/accounting**, plus the **reference and uniform 0.5-ms fixed-LUT, 10+5-ms columns of Supplementary Table S4**. The regression test expectations come from the manuscript, not from the implementation under test.

**Not reproduced here:** paired-bootstrap intervals, GE/HMM fitting and emission sensitivity, gain/grid/feedback sweeps, device-specific LUT recompilation, and host codec timing. The original execution artifacts for those additional analyses were not located for this release. Historical VTC design-space code remains available in `research/vtc`; its original evaluation mask is intentionally not rewritten as a journal-revision result.

## Replay contract

- BSM uses K=8, period 200 carrier positions and jitter ±10; SDSM uses K=27, period 500 and jitter ±25. These are position-indexed workloads, not measured 10-Hz/2-Hz message processes.
- A/B are segments from the same measurement campaign. C is the archived counter-union stress input, not an independent chronological drive.
- The loss sequence is replayed cyclically. Seed 42 generates one shared offered-start list per trace/profile, stopping after 100,000 retained starts. Excluded starts are still evaluated for all-offered metrics. Repeated offers are not independent field samples.
- The causal inputs use only earlier observation windows. Oracle is the non-causal ±2-window min/max reference within the same LUT family, not an optimality bound.
- The reference interval is `(1500/2600)*0.5 ms`; the sensitivity interval is 0.5 ms. Recovery requires the K-th correct symbol within the 100-ms budget after 10-ms platform and 5-ms codec design terms. These are modeled timelines, not measured end-to-end latency.
- RS coding is modeled by correct-symbol counts. No byte codec, radio scheduler, feedback transport, or integrated HIL deadline is executed by this replay.
- RAW/REP3/REP5 convey one complete message per carrier, with replicas on consecutive positions. ARGUS conveys one RS symbol per selected carrier. **Mean selected N/K is source-symbol-equivalent protection-payload expansion**, includes all selected coded symbols, and includes both successes and failures. It is neither carrier occupancy, measured post-decoding transmissions, header-inclusive bytes, nor on-air resource cost. The whole-message and fixed-field packing assumptions differ.

## Executed details and manuscript discrepancies

These details are explicit to preserve the archived computation rather than silently changing its results:

1. Mode labels use full-precision Gaussian quantiles for 0.50/0.85/0.95/0.99. The predictor keeps full-precision internal states and exports continuous margin bounds rounded to four decimal places. The first five output bounds are forced to `(0,100)` and are omitted only from coverage.
2. **Table V uses the continuous archived burst bound.** Manuscript Eq. (20b) writes an integer ceiling. The LUT rounds upward to a burst-grid node, so ceiling the bound does not change policy actions on these integer grid nodes, but it changes prediction coverage. Both coverage definitions are exported; the paper should distinguish them.
3. Archive matching requires a calibration transfer precision rule: A uses the full Trace-A rolling-20 q90 scales, whereas B/C use the same derived scales rounded to four PDR decimals and two burst decimals. This was reconstructed by exact agreement with all 12 archived prediction files; it is disclosed rather than described as bit-identical constants across traces. A shared-full-precision alternative is available.
4. Archived final observation rows are retained by default. They differ from observations of the last partial slice of the packed bits. All complete 100-position windows are checked separately. `--observation-source bits` exposes the alternative without treating it as a reproduction of the archived table.
5. All-offered outage is primary for comparisons; conditional outage is a transparent subset diagnostic. A same-LUT reference, excluded-start mask, or saturation choice is not a computed lower bound on all application-layer failures.

## 한글 안내

2026-10-08 TVT 리비전의 **핵심 예측·성능 회계**를 재현하는 공개 코드입니다. 기존 공개 입력을 확인해 2026-10-12에 복원·검증했으며, 차량 속도를 쓰는 이전 예측기 대신 PDR/최대 손실 run에 대한 인과적 비대칭 EWMA를 실행합니다. BSM/SDSM 모두 312-position 평가 mask를 사용하고, 제외된 메시지도 전송·복구 결과를 계산합니다.

위 실행 명령으로 표 V의 coverage, 표 VI/VII의 건수·점추정 성능·N/K, 보충 표 S4의 reference/0.5-ms 고정 LUT 조건을 확인할 수 있습니다. GE/HMM·추가 민감도·bootstrap CI·codec 측정까지 전체 논문을 재현하는 패키지는 아닙니다. 실행하지 않는 분석을 검증 완료했다고 표시하지 않습니다.

표 V는 보관된 연속 burst bound로 계산됐고 논문 식 (20b)는 정수 ceiling을 표시합니다. 정책은 같지만 coverage가 다르므로 두 결과를 나란히 공개합니다. A에서 산출한 reset scale이 A에는 전체 정밀도, B/C에는 4자리·2자리로 전달된 차이도 보관된 CSV 일치에 근거한 재구성 규칙으로 명시합니다. 마지막 불완전 관측 구간의 원 입력과 bits 재계산 차이도 기록합니다. N/K는 정규화된 보호 payload 사용량이며 실제 무선 비용·carrier 점유·end-to-end latency 보장이 아닙니다.
