from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from chronos import Chronos2Pipeline

MODEL_ID = "amazon/chronos-2"


def load_matrix(path: Path) -> np.ndarray:
    return np.loadtxt(path, dtype=np.float32)


def channel_normalized_mae(actual: np.ndarray, predicted: np.ndarray, context: np.ndarray) -> float:
    scales = np.std(context, axis=1)
    scales = np.maximum(scales, np.maximum(np.mean(np.abs(context), axis=1) * 0.01, 1e-6))
    mae_per_channel = np.mean(np.abs(actual - predicted), axis=1)
    return float(np.mean(mae_per_channel / scales))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t01d_zero_shot"))
    ap.add_argument("--context", type=int, default=256)
    ap.add_argument("--prediction-length", type=int, default=32)
    ap.add_argument("--max-cycles", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    for name in ["PS1.txt", "PS2.txt", "EPS1.txt", "profile.txt"]:
        if not (args.root / name).exists():
            raise FileNotFoundError(args.root / name)

    ps1 = load_matrix(args.root / "PS1.txt")
    ps2 = load_matrix(args.root / "PS2.txt")
    eps = load_matrix(args.root / "EPS1.txt")
    profile = load_matrix(args.root / "profile.txt")
    stable = np.flatnonzero(profile[:, 4] == 0)
    if len(stable) > args.max_cycles:
        selected = stable[np.linspace(0, len(stable)-1, args.max_cycles).round().astype(int)]
    else:
        selected = stable

    total = args.context + args.prediction_length
    rng = np.random.default_rng(args.seed)
    contexts, actuals, cycle_ids = [], [], []
    for cycle in selected:
        channels = np.stack([ps1[cycle], ps2[cycle], eps[cycle]], axis=0)
        if channels.shape[1] < total:
            continue
        start = int(rng.integers(0, channels.shape[1] - total + 1))
        window = channels[:, start:start+total]
        contexts.append(window[:, :args.context])
        actuals.append(window[:, args.context:])
        cycle_ids.append(int(cycle))

    if not contexts:
        raise RuntimeError("No usable stable UCI cycles")

    inputs = [{"target": torch.from_numpy(x.astype(np.float32))} for x in contexts]
    pipeline = Chronos2Pipeline.from_pretrained(MODEL_ID, device_map="cpu")
    model_parameters = int(sum(p.numel() for p in pipeline.model.parameters()))
    print(f"Loaded {MODEL_ID}: {model_parameters:,} parameters")

    outputs = pipeline.predict(inputs, prediction_length=args.prediction_length, batch_size=args.batch_size)
    quantiles = np.asarray(pipeline.quantiles, dtype=float)
    median_idx = int(np.argmin(np.abs(quantiles - 0.5)))
    q10_idx = int(np.argmin(np.abs(quantiles - 0.1)))
    q90_idx = int(np.argmin(np.abs(quantiles - 0.9)))

    chronos_err, persistence_err, coverages, rows = [], [], [], []
    for cycle, context, actual, out in zip(cycle_ids, contexts, actuals, outputs):
        pred = out[:, median_idx, :].float().cpu().numpy()
        q10 = out[:, q10_idx, :].float().cpu().numpy()
        q90 = out[:, q90_idx, :].float().cpu().numpy()
        persistence = np.repeat(context[:, -1:], args.prediction_length, axis=1)
        ce = channel_normalized_mae(actual, pred, context)
        pe = channel_normalized_mae(actual, persistence, context)
        coverage = float(np.mean((actual >= q10) & (actual <= q90)))
        chronos_err.append(ce)
        persistence_err.append(pe)
        coverages.append(coverage)
        rows.append({"cycle": cycle, "chronos_nmae": ce, "persistence_nmae": pe, "q10_q90_coverage": coverage})

    chronos_mean = float(np.mean(chronos_err))
    persistence_mean = float(np.mean(persistence_err))
    relative = float(chronos_mean / max(persistence_mean, 1e-12) - 1.0)
    gate_passed = bool(chronos_mean <= 0.95 * persistence_mean)

    metrics = {
        "run_id": "FLOWTRUST-V2-T01-D0-20260812",
        "model": MODEL_ID,
        "model_parameters": model_parameters,
        "mode": "zero_shot_multivariate_cpu",
        "source": "UCI Condition monitoring of hydraulic systems, ID 447",
        "doi": "10.24432/C5CW21",
        "channels": ["PS1_pressure", "PS2_pressure", "EPS1_motor_power"],
        "stable_physical_cycles": cycle_ids,
        "context_length": args.context,
        "prediction_length": args.prediction_length,
        "chronos_normalized_mae_mean": chronos_mean,
        "persistence_normalized_mae_mean": persistence_mean,
        "relative_error_vs_persistence": relative,
        "mean_q10_q90_coverage": float(np.mean(coverages)),
        "bootstrap_gate": "Chronos-2 zero-shot normalized MAE <= 95% of persistence normalized MAE",
        "bootstrap_gate_passed": gate_passed,
        "note": "This bootstrap tests whether the 120M temporal foundation adds forecast value on real physical trajectories before any LoRA adaptation; it is not a cement-plant performance claim.",
        "per_cycle": rows,
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({
        "model_parameters": model_parameters,
        "chronos_normalized_mae_mean": chronos_mean,
        "persistence_normalized_mae_mean": persistence_mean,
        "relative_error_vs_persistence": relative,
        "bootstrap_gate_passed": gate_passed,
    }, indent=2))


if __name__ == "__main__":
    main()
