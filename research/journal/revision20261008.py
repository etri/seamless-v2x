"""Reproduce the executed core of the 2026-10-08 ARGUS journal revision.

The release covers the archived predictor, core replay accounting, and fixed-LUT
carrier-spacing comparison. It does not recreate the GE/HMM fitting, bootstrap,
grid-refinement, or codec experiments whose execution artifacts are unavailable.

Archived prediction CSVs store continuous margin bounds rounded to four decimal
places. Published coverage used these bounds; integer burst queries have different
coverage, although rounding them upward leaves the LUT policy unchanged. Both
coverage definitions are reported. Final archived observation rows are retained;
they need not describe the final partial slice of the packed reception trace.

The predictor-generation source for this revision was not recovered. Reconstruction
matches all twelve archived mode/trace CSVs: A uses its full-precision fitted reset
scales; B/C use the same A-derived scales rounded to four/two decimals. This explicit
archival precision rule is not a fitted performance choice. A shared-full-precision
alternative is provided and must not be presented as the archived execution.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import random
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd


MODE_QUANTILES = {"ARGUS-C": 0.50, "ARGUS-B": 0.85, "ARGUS-R": 0.95, "ARGUS-E": 0.99}
MODE_Z = {name: NormalDist().inv_cdf(q) for name, q in MODE_QUANTILES.items()}
SCHEMES = ("RAW", "REP3", "REP5", "NAIVE", *MODE_QUANTILES, "ORACLE")
REFERENCE_SPACING_MS = 1500 / 2600 * 0.5
PDR_NODES = np.array([0.45, 0.55, 0.65, 0.75, 0.85, 0.95])
BURST_NODES = np.array([2, 3, 5, 10, 20, 40])


def load_trace_bits(path: str | Path) -> np.ndarray:
    """Unpack the archived, MSB-first packed binary trace (including packed bits)."""
    return np.unpackbits(np.frombuffer(Path(path).read_bytes(), dtype=np.uint8))


def _bits(bits: np.ndarray) -> np.ndarray:
    values = np.asarray(bits)
    if values.ndim != 1 or not len(values) or not np.isin(values, (0, 1)).all():
        raise ValueError("bits must be a nonempty one-dimensional binary array")
    return values.astype(np.uint8, copy=False)


def window_metrics(bits: np.ndarray, window: int = 100) -> pd.DataFrame:
    """Observe nonoverlapping windows; normalize a final partial window by its size.

    This is the explicit from-bits alternative, not a repair of archived final rows.
    """
    bits = _bits(bits)
    if window < 1:
        raise ValueError("window must be positive")
    rows = []
    for start in range(0, len(bits), window):
        chunk = bits[start : start + window]
        changes = np.diff(np.r_[1, chunk, 1].astype(np.int16))
        starts = np.flatnonzero(changes == -1)
        ends = np.flatnonzero(changes == 1)
        maximum = int((ends - starts).max()) if len(starts) else 0
        rows.append((len(rows) + 1, float(chunk.mean()), maximum))
    return pd.DataFrame(rows, columns=["Window_ID", "PDR", "Max_Burst"])


def _observations(metrics: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    p = metrics["PDR"].to_numpy(dtype=float)
    b = metrics["Max_Burst"].to_numpy(dtype=float)
    if not len(p) or not np.isfinite(p).all() or not np.isfinite(b).all():
        raise ValueError("observations must be nonempty and finite")
    if ((p < 0) | (p > 1) | (b < 0) | (b > 100)).any():
        raise ValueError("observations exceed the [0,1] PDR or [0,100] burst range")
    return p, b


def fit_reset_scales(
    metrics: pd.DataFrame, rolling_window: int = 20, quantile: float = 0.90
) -> tuple[float, float]:
    """Derive the fixed reset scales from Trace-A only (sample std, pandas ddof=1).

    Calibrating on all of A is an in-sample calibration step, not a runtime update.
    Freeze its outputs before producing predictions on any evaluation sequence.
    """
    _observations(metrics)
    if rolling_window < 2 or not 0 <= quantile <= 1:
        raise ValueError("rolling_window must be >=2 and quantile must lie in [0,1]")
    scales = tuple(
        float(metrics[col].rolling(rolling_window).std(ddof=1).quantile(quantile))
        for col in ("PDR", "Max_Burst")
    )
    if not np.isfinite(scales).all():
        raise ValueError("not enough observations to derive reset scales")
    return scales


@dataclass(frozen=True)
class PredictorParameters:
    reset_sigma_p: float
    reset_sigma_b: float
    alpha_deg: float = 0.7
    alpha_rec: float = 0.1
    variance_gain: float = 0.7
    delta_drop: float = 0.15
    warmup: int = 5
    initial_p: float = 0.45
    initial_b: float = 40.0
    initial_var_p: float = 0.01
    initial_var_b: float = 25.0


def execution_parameters(
    reset_scales: tuple[float, float], trace: str,
    calibration_policy: str = "archived_execution",
) -> PredictorParameters:
    """Make the explicit precision handoff reconstructed from archived CSVs.

    All scales originate in the same rolling-20/q90 calculation on A. The archival
    B/C handoff rounds its PDR scale to four and burst scale to two decimals, whereas
    A retains full precision. This rule matches all twelve archived predictor CSVs;
    the unavailable original revision generator is not claimed to have been found.
    """
    if trace not in ("A", "B", "C"):
        raise ValueError("trace must be A, B, or C")
    if calibration_policy not in ("archived_execution", "shared_full_precision"):
        raise ValueError("unknown calibration policy")
    sigma_p, sigma_b = reset_scales
    if calibration_policy == "archived_execution" and trace != "A":
        sigma_p, sigma_b = round(sigma_p, 4), round(sigma_b, 2)
    return PredictorParameters(sigma_p, sigma_b)


def predict_ewma(
    metrics: pd.DataFrame, z: float, params: PredictorParameters
) -> pd.DataFrame:
    """Execute Eqs. 16--19 causally and reproduce archived continuous margin CSVs.

    Row t uses observations strictly before row t. States retain full precision;
    means and continuous bounds are rounded only when exported (four decimals).
    The executed first-five-window cold start forces bounds to (0,100). Column
    Pred_B_query explicitly supplies the integer query of manuscript Eq. 20b.
    """
    p, b = _observations(metrics)
    for gain in (params.alpha_deg, params.alpha_rec, params.variance_gain):
        if not 0 <= gain <= 1:
            raise ValueError("predictor gains must lie in [0,1]")
    if min(params.reset_sigma_p, params.reset_sigma_b, params.initial_var_p,
           params.initial_var_b, params.warmup, z) < 0:
        raise ValueError("scales, variances, warmup, and z must be nonnegative")
    mean_p, mean_b = params.initial_p, params.initial_b
    var_p, var_b = params.initial_var_p, params.initial_var_b
    means = np.empty((len(p), 2))
    variances = np.empty_like(means)
    for t, (observed_p, observed_b) in enumerate(zip(p, b)):
        means[t] = mean_p, mean_b
        variances[t] = var_p, var_b
        residual_p = observed_p - mean_p
        residual_b = observed_b - mean_b
        gain_p = params.alpha_deg if residual_p < 0 else params.alpha_rec
        gain_b = params.alpha_deg if residual_b > 0 else params.alpha_rec
        mean_p += gain_p * residual_p
        mean_b += gain_b * residual_b
        var_p = params.variance_gain * residual_p**2 + (1 - params.variance_gain) * var_p
        var_b = params.variance_gain * residual_b**2 + (1 - params.variance_gain) * var_b
        if residual_p < -params.delta_drop:
            var_p = params.reset_sigma_p**2
            var_b = params.reset_sigma_b**2
    bound_p = np.round(np.clip(means[:, 0] - z * np.sqrt(variances[:, 0]), 0, 1), 4)
    bound_b = np.round(np.clip(means[:, 1] + z * np.sqrt(variances[:, 1]), 0, 100), 4)
    bound_p[:params.warmup] = 0
    bound_b[:params.warmup] = 100
    return pd.DataFrame({
        "Window_ID": np.arange(1, len(p) + 1), "PDR": p, "Max_Burst": b,
        "Pred_PDR_mean": np.round(means[:, 0], 4),
        "Pred_B_mean": np.round(means[:, 1], 4),
        "Pred_PDR_cons": bound_p, "Pred_B_cons": bound_b,
        "Pred_B_query": np.ceil(bound_b).astype(int),
    })


def naive_predictions(metrics: pd.DataFrame) -> pd.DataFrame:
    p, b = _observations(metrics)
    return pd.DataFrame({"Pred_PDR_cons": np.r_[0.45, p[:-1]],
                         "Pred_B_cons": np.r_[40.0, b[:-1]]})


def oracle_predictions(metrics: pd.DataFrame, half_window: int = 2) -> pd.DataFrame:
    """The non-causal same-LUT min/max reference, without cyclic wrapping."""
    p, b = _observations(metrics)
    if half_window < 0:
        raise ValueError("half_window must be nonnegative")
    return pd.DataFrame({
        "Pred_PDR_cons": [p[max(0, t-half_window):t+half_window+1].min() for t in range(len(p))],
        "Pred_B_cons": [b[max(0, t-half_window):t+half_window+1].max() for t in range(len(b))],
    })


def prediction_coverage(
    metrics: pd.DataFrame, predictions: pd.DataFrame, warmup: int = 5,
    integer_query: bool = False,
) -> dict[str, float | int]:
    p, b = _observations(metrics)
    if len(predictions) != len(p) or not 0 <= warmup < len(p):
        raise ValueError("coverage requires aligned rows and at least one evaluated window")
    predicted_p = predictions["Pred_PDR_cons"].to_numpy(dtype=float)
    predicted_b = predictions["Pred_B_cons"].to_numpy(dtype=float)
    if integer_query:
        predicted_b = np.ceil(predicted_b)
    cp = predicted_p[warmup:] <= p[warmup:]
    cb = predicted_b[warmup:] >= b[warmup:]
    return {"evaluated_windows": len(cp), "pdr_coverage_pct": float(cp.mean()*100),
            "burst_coverage_pct": float(cb.mean()*100),
            "joint_coverage_pct": float((cp & cb).mean()*100)}


@dataclass(frozen=True)
class ActionTable:
    pdr_nodes: np.ndarray
    burst_nodes: np.ndarray
    n_grid: np.ndarray
    g_grid: np.ndarray
    K: int

    @classmethod
    def from_csv(cls, path: str | Path, K: int) -> "ActionTable":
        frame = pd.read_csv(path)
        pdr = np.sort(frame.PDR_Env.unique())
        burst = np.sort(frame.Burst_1_over_r.unique())
        grid = frame.set_index(["PDR_Env", "Burst_1_over_r"])
        index = pd.MultiIndex.from_product([pdr, burst])
        if grid.index.has_duplicates or not index.isin(grid.index).all():
            raise ValueError("LUT must contain exactly one action per rectangular grid cell")
        grid = grid.reindex(index)
        n = grid.Action_N.to_numpy(dtype=int).reshape(len(pdr), len(burst))
        g = grid.Action_G.to_numpy(dtype=int).reshape(len(pdr), len(burst))
        if (n < K).any() or (g < 0).any():
            raise ValueError("LUT actions require N>=K and G>=0")
        return cls(pdr, burst, n, g, K)

    def lookup_many(self, pdr: np.ndarray, burst: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p, b = np.broadcast_arrays(np.asarray(pdr, float), np.asarray(burst, float))
        if not np.isfinite(p).all() or not np.isfinite(b).all():
            raise ValueError("LUT queries must be finite")
        pi = np.clip(np.searchsorted(self.pdr_nodes, p, side="right") - 1, 0, len(self.pdr_nodes)-1)
        bi = np.clip(np.searchsorted(self.burst_nodes, b, side="left"), 0, len(self.burst_nodes)-1)
        n, g = self.n_grid[pi, bi], self.g_grid[pi, bi]
        saturation_n, saturation_g = (64, 2) if self.K == 8 else (140, 1)
        saturated = b > self.burst_nodes[-1]
        return np.where(saturated, saturation_n, n), np.where(saturated, saturation_g, g)

    def lookup(self, pdr: float, burst: float) -> tuple[int, int]:
        n, g = self.lookup_many(np.asarray(pdr), np.asarray(burst))
        return int(n), int(g)


@dataclass(frozen=True)
class ReplayConfig:
    profile: str = "BSM"
    K: int = 8
    period: int = 200
    jitter: int = 10
    target_retained: int = 100_000
    mask_threshold: int = 312
    seed: int = 42
    spacing_ms: float = REFERENCE_SPACING_MS
    platform_ms: float = 10.0
    codec_ms: float = 5.0
    deadline_ms: float = 100.0

    @classmethod
    def for_profile(cls, profile: str, **kwargs: Any) -> "ReplayConfig":
        profile = profile.upper()
        if profile == "BSM":
            values = dict(profile=profile, K=8, period=200, jitter=10)
        elif profile == "SDSM":
            values = dict(profile=profile, K=27, period=500, jitter=25)
        else:
            raise ValueError("profile must be BSM or SDSM")
        values.update(kwargs)
        return cls(**values)

    @property
    def deadline_offset(self) -> int:
        if self.spacing_ms <= 0:
            raise ValueError("spacing_ms must be positive")
        return int(np.floor((self.deadline_ms - self.platform_ms - self.codec_ms)
                            / self.spacing_ms + 1e-10))


def build_skip_mask(bits: np.ndarray, threshold: int = 312) -> np.ndarray:
    """Classify starts in complete loss runs; never alter actions or transmissions."""
    bits = _bits(bits)
    if threshold < 1:
        raise ValueError("threshold must be positive")
    mask = np.zeros(len(bits), dtype=bool)
    changes = np.diff(np.r_[1, bits, 1].astype(np.int16))
    starts, ends = np.flatnonzero(changes == -1), np.flatnonzero(changes == 1)
    for start, end in zip(starts, ends):
        if end - start >= threshold:
            mask[start:end] = True
    return mask


def generate_offers(bits: np.ndarray, config: ReplayConfig) -> tuple[np.ndarray, np.ndarray]:
    """Use the same seeded offers for every scheme; stop at target retained starts."""
    bits = _bits(bits)
    if config.target_retained < 1 or config.period <= config.jitter or config.jitter < 0:
        raise ValueError("target must be positive and period must exceed nonnegative jitter")
    mask = build_skip_mask(bits, config.mask_threshold)
    if mask.all():
        raise ValueError("the retrospective mask leaves no retained starts")
    rng = random.Random(config.seed)
    t = rng.randint(config.period-config.jitter, config.period+config.jitter)
    starts, excluded = [], []
    retained = 0
    maximum_offers = max(100_000, config.target_retained*100)
    while retained < config.target_retained:
        excluded_start = bool(mask[t % len(bits)])
        starts.append(t)
        excluded.append(excluded_start)
        retained += not excluded_start
        if len(starts) >= maximum_offers:
            raise ValueError("offer process cannot collect the requested retained starts")
        t += rng.randint(config.period-config.jitter, config.period+config.jitter)
    return np.asarray(starts, dtype=np.int64), np.asarray(excluded, dtype=bool)


def replay(
    bits: np.ndarray, predictions: pd.DataFrame | None, lut: ActionTable | None,
    scheme: str, config: ReplayConfig, offers: tuple[np.ndarray, np.ndarray] | None = None,
    return_events: bool = False,
) -> dict[str, Any]:
    """Count every offer, including masked starts, under the specified timing model.

    Adaptive messages send one distinct shard per selected carrier; recovery counts
    at the K-th correct shard by the deadline, while expenditure counts all selected
    N shards. RAW/REP baselines put a whole message in one carrier, or repeat it in
    3/5 consecutive carriers. Their N=K*copies is source-symbol-equivalent cost,
    not their carrier count. Thus expansion is not identical radio-resource cost.
    Trace losses repeat cyclically; controller sequences restart per trace pass.
    """
    bits = _bits(bits)
    scheme = scheme.upper()
    if scheme not in SCHEMES:
        raise ValueError(f"unknown scheme: {scheme}")
    starts, excluded = generate_offers(bits, config) if offers is None else offers
    starts, excluded = np.asarray(starts, np.int64), np.asarray(excluded, bool)
    if starts.ndim != 1 or excluded.shape != starts.shape or not len(starts) or (starts < 0).any():
        raise ValueError("offers require aligned nonempty starts and excluded flags")
    if scheme in ("RAW", "REP3", "REP5"):
        copies = {"RAW": 1, "REP3": 3, "REP5": 5}[scheme]
        carrier_count = np.full(len(starts), copies, dtype=int)
        n = carrier_count*config.K
        g = np.zeros(len(starts), dtype=int)
        required = 1
    else:
        if predictions is None or lut is None or lut.K != config.K:
            raise ValueError("adaptive replay requires predictions and a matching LUT")
        wi = np.minimum((starts % len(bits))//100, len(predictions)-1)
        n, g = lut.lookup_many(predictions.Pred_PDR_cons.to_numpy()[wi],
                               predictions.Pred_B_cons.to_numpy()[wi])
        carrier_count = n
        required = config.K
    success = np.empty(len(starts), bool)
    last_allowed = config.deadline_offset
    offsets_index = np.arange(int(carrier_count.max()))
    for begin in range(0, len(starts), 4096):
        end = min(begin+4096, len(starts))
        offsets = offsets_index[None, :]*(g[begin:end, None]+1)
        received = bits[(starts[begin:end, None]+offsets) % len(bits)] == 1
        received &= offsets_index[None, :] < carrier_count[begin:end, None]
        received &= offsets <= last_allowed
        success[begin:end] = received.sum(axis=1) >= required
    retained = ~excluded
    retained_count, excluded_count = int(retained.sum()), int(excluded.sum())
    retained_failures = int((retained & ~success).sum())
    excluded_failures = int((excluded & ~success).sum())
    result: dict[str, Any] = {
        "profile": config.profile, "scheme": scheme, "spacing_ms": config.spacing_ms,
        "deadline_offset": last_allowed, "offered": len(starts), "retained": retained_count,
        "excluded": excluded_count, "retained_failures": retained_failures,
        "excluded_failures": excluded_failures,
        "excluded_successes": int((excluded & success).sum()),
        "all_failures": int((~success).sum()),
        "conditional_outage_pct": 100*retained_failures/retained_count if retained_count else None,
        "all_offered_outage_pct": float((~success).mean()*100),
        "retained_expansion": float(n[retained].mean()/config.K) if retained_count else None,
        "all_offered_expansion": float(n.mean()/config.K),
        "mean_offered_carriers": float(carrier_count.mean()),
    }
    if return_events:
        result["events"] = {"starts": starts, "excluded": excluded, "success": success,
                            "N": n, "G": g, "carrier_count": carrier_count}
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_release(
    input_dir: str | Path, output_dir: str | Path, prediction_source: str = "verify",
    spacing: str = "both", target_retained: int = 100_000,
    observation_source: str = "archived",
    profiles: tuple[str, ...] = ("BSM", "SDSM"), prediction_only: bool = False,
    calibration_policy: str = "archived_execution",
) -> dict[str, Any]:
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if prediction_source not in ("generated", "archived", "verify"):
        raise ValueError("prediction_source must be generated, archived, or verify")
    if observation_source not in ("archived", "bits"):
        raise ValueError("observation_source must be archived or bits")
    if not profiles or len(set(profiles)) != len(profiles) or not set(profiles) <= {"BSM", "SDSM"}:
        raise ValueError("profiles must contain BSM and/or SDSM without duplicates")
    if spacing not in ("reference", "0.5", "both"):
        raise ValueError("spacing must be reference, 0.5, or both")
    observations, archives, traces = {}, {}, {}
    inputs = {}
    for trace in ("A", "B", "C"):
        folder = input_dir/trace
        traces[trace] = load_trace_bits(folder/"trace.bin")
        inputs[f"{trace}/trace.bin"] = _sha256(folder/"trace.bin")
        archives[trace] = {}
        for mode in MODE_QUANTILES:
            file = folder/f"prediction_results_{mode.lower().replace('-', '_')}.csv"
            archives[trace][mode] = pd.read_csv(file)
            inputs[f"{trace}/{file.name}"] = _sha256(file)
        archived_metrics = archives[trace]["ARGUS-C"][["PDR", "Max_Burst"]]
        for frame in archives[trace].values():
            if not np.array_equal(frame[["PDR", "Max_Burst"]].to_numpy(), archived_metrics.to_numpy()):
                raise ValueError(f"{trace}: archived predictor modes disagree on observations")
        observations[trace] = (archived_metrics if observation_source == "archived"
                               else window_metrics(traces[trace]))
    reset_p, reset_b = fit_reset_scales(observations["A"])
    parameters = {trace: execution_parameters((reset_p, reset_b), trace, calibration_policy)
                  for trace in ("A", "B", "C")}
    luts = {}
    for profile, K, filename in (("BSM", 8, "56LUT_3_Balanced.csv"),
                                  ("SDSM", 27, "513LUT_3_Balanced.csv")):
        file = input_dir/"lut"/filename
        luts[profile] = ActionTable.from_csv(file, K)
        inputs[f"lut/{filename}"] = _sha256(file)
    coverage_rows, replay_rows, verification_rows, metric_rows = [], [], [], []
    spacings = ([REFERENCE_SPACING_MS, 0.5] if spacing == "both" else
                [REFERENCE_SPACING_MS] if spacing == "reference" else [0.5])
    for trace in ("A", "B", "C"):
        metrics = observations[trace]
        generated = {mode: predict_ewma(metrics, z, parameters[trace]) for mode, z in MODE_Z.items()}
        predictions = {"NAIVE": naive_predictions(metrics), "ORACLE": oracle_predictions(metrics)}
        for mode in MODE_QUANTILES:
            actual, expected = generated[mode], archives[trace][mode]
            comparison = {"trace": trace, "scheme": mode, "rows": len(actual), "match": True}
            for column in ("PDR", "Max_Burst", "Pred_PDR_cons", "Pred_B_cons"):
                difference = np.abs(actual[column].to_numpy()-expected[column].to_numpy())
                comparison[f"{column}_max_abs_error"] = float(difference.max())
                comparison["match"] &= bool(np.allclose(difference, 0, atol=5e-10, rtol=0))
            verification_rows.append(comparison)
            if prediction_source == "verify" and not comparison["match"]:
                raise ValueError(f"generated predictions do not match archived {trace}/{mode}: {comparison}")
            predictions[mode] = expected if prediction_source == "archived" else actual
            prediction_folder = output_dir/"predictions"/trace
            prediction_folder.mkdir(parents=True, exist_ok=True)
            predictions[mode].to_csv(
                prediction_folder/f"prediction_results_{mode.lower().replace('-', '_')}.csv", index=False)
        from_bits = window_metrics(traces[trace])
        archive_truth = archives[trace]["ARGUS-C"][["PDR", "Max_Burst"]]
        difference = from_bits[["PDR", "Max_Burst"]].to_numpy()-archive_truth.to_numpy()
        changed = np.flatnonzero(np.any(np.abs(difference)>5e-10, axis=1))
        metric_rows.append({"trace": trace, "rows": len(from_bits),
                            "different_rows_1based": (changed+1).tolist(),
                            "full_windows_match": bool(np.allclose(difference[:len(traces[trace])//100], 0,
                                                                   atol=5e-10, rtol=0)),
                            "final_from_bits": from_bits.iloc[-1].to_dict(),
                            "final_archived": archive_truth.iloc[-1].to_dict()})
        for mode in ("NAIVE", *MODE_QUANTILES):
            for integer in (False, True):
                coverage_rows.append({"trace": trace, "scheme": mode,
                                      "bound": "integer_query" if integer else "archived_continuous",
                                      **prediction_coverage(metrics, predictions[mode], integer_query=integer)})
        for profile in (() if prediction_only else profiles):
            config = ReplayConfig.for_profile(profile, target_retained=target_retained)
            offers = generate_offers(traces[trace], config)
            for interval in spacings:
                timing = replace(config, spacing_ms=interval)
                for scheme in SCHEMES:
                    replay_rows.append({"trace": trace,
                                        **replay(traces[trace], predictions.get(scheme), luts[profile],
                                                 scheme, timing, offers=offers)})
    output_dir.mkdir(parents=True, exist_ok=True)
    if not prediction_only:
        pd.DataFrame(replay_rows).to_csv(output_dir/"replay.csv", index=False)
    pd.DataFrame(coverage_rows).to_csv(output_dir/"coverage.csv", index=False)
    metadata = {
        "scope": ("core Table V predictor reconstruction and coverage" if prediction_only else
                  "core Tables V-VII and fixed-LUT carrier-spacing subset of Supplementary Table S4"),
        "prediction_source": prediction_source, "observation_source": observation_source,
        "profiles": list(profiles), "prediction_only": prediction_only,
        "calibration_policy": calibration_policy,
        "reset_sigma_p": reset_p, "reset_sigma_b": reset_b, "z": MODE_Z,
        "executed_reset_scales": {trace: {"sigma_p": p.reset_sigma_p, "sigma_b": p.reset_sigma_b}
                                   for trace, p in parameters.items()},
        "prediction_reconstruction": (
            "Original revision generator unavailable; equations plus archival export/precision conventions "
            "were reconstructed and checked against all twelve archived mode/trace CSVs."),
        "replay_prediction_source": "archived" if prediction_source == "archived" else "generated",
        "exported_prediction_source": "generated",
        "input_sha256": inputs,
        "known_execution_details": [
            "Continuous bounds rounded to four decimals reproduce published coverage; integer-query coverage differs.",
            "The first five predictions force margin bounds to (0,100); they are excluded only from coverage.",
            "Archived final observation rows differ from final partial bit windows; archived observations are the default.",
            "The archived A predictor uses full-precision reset scales; B/C use A-derived scales rounded to 4/2 decimals.",
            "RAW/REP use whole-message carriers; expansion is source-symbol-equivalent payload cost, not carrier or radio cost.",
            "Offers and losses are position-indexed; the spacing scenarios are not timestamp-driven field deadline measurements.",
        ],
        "unreproduced_experiments": ["GE/HMM fits", "emission/gain/grid/feedback sensitivity sweeps",
                                     "bootstrap intervals", "codec timing", "device-specific LUT recompilation"],
    }
    documents = [
        ("prediction_metadata.json", {"metadata": metadata, "coverage": coverage_rows}),
        ("prediction_verification.json", verification_rows),
        ("observed_metric_verification.json", metric_rows),
    ]
    if not prediction_only:
        documents.append(("replay.json", {"metadata": metadata, "results": replay_rows}))
    for name, value in documents:
        (output_dir/name).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return {"prediction_matches": all(row["match"] for row in verification_rows),
            "replay_rows": len(replay_rows), "coverage_rows": len(coverage_rows),
            "output_dir": str(output_dir), "reset_scales": [reset_p, reset_b]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent/"revision20261008"
    parser.add_argument("--input-dir", type=Path, default=base/"inputs")
    parser.add_argument("--output-dir", type=Path, default=base/"results")
    parser.add_argument("--prediction-source", choices=("generated", "archived", "verify"), default="verify")
    parser.add_argument("--observation-source", choices=("archived", "bits"), default="archived")
    parser.add_argument("--spacing", choices=("reference", "0.5", "both"), default="both")
    parser.add_argument("--target-retained", type=int, default=100_000)
    parser.add_argument("--profiles", nargs="+", choices=("BSM", "SDSM"), default=["BSM", "SDSM"])
    parser.add_argument("--prediction-only", action="store_true")
    parser.add_argument("--calibration-policy", choices=("archived_execution", "shared_full_precision"),
                        default="archived_execution")
    args = parser.parse_args(argv)
    result = run_release(args.input_dir, args.output_dir, args.prediction_source,
                         args.spacing, args.target_retained, args.observation_source,
                         tuple(args.profiles), args.prediction_only, args.calibration_policy)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
