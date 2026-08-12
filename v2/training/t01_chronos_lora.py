from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from chronos import Chronos2Pipeline
from chronos.chronos2.preprocess import from_data_frame

DEFAULT_MODEL = "amazon/chronos-2"


def parse_list(text: str):
    return [x.strip() for x in text.split(",") if x.strip()]


def make_test_inputs(df, targets, covariates, prediction_length, id_column, timestamp_column):
    inputs, actuals, ids = [], [], []
    for item_id, g in df.sort_values([id_column, timestamp_column]).groupby(id_column, sort=False):
        if len(g) <= prediction_length:
            continue
        target = g[targets].to_numpy(dtype=np.float32).T
        context_target = target[:, :-prediction_length]
        actual = target[:, -prediction_length:]
        payload = {"target": context_target}
        if covariates:
            payload["past_covariates"] = {
                c: g[c].to_numpy()[:-prediction_length]
                for c in covariates
            }
        inputs.append(payload)
        actuals.append(actual)
        ids.append(str(item_id))
    return inputs, actuals, ids


def mae(a, b):
    return float(np.nanmean(np.abs(np.asarray(a) - np.asarray(b))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="Parquet with split,item_id,timestamp,target/covariate columns")
    ap.add_argument("--targets", required=True, help="Comma-separated target columns, e.g. mass_flow,motor_current,belt_speed")
    ap.add_argument("--covariates", default="", help="Comma-separated past covariates")
    ap.add_argument("--id-column", default="item_id")
    ap.add_argument("--timestamp-column", default="timestamp")
    ap.add_argument("--split-column", default="split")
    ap.add_argument("--prediction-length", type=int, default=16)
    ap.add_argument("--context-length", type=int, default=256)
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t01/chronos_process"))
    args = ap.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("T01-D is configured for CUDA. Do not report Chronos-2 fine-tuning as completed on CPU.")

    targets = parse_list(args.targets)
    covariates = parse_list(args.covariates)
    df = pd.read_parquet(args.data)
    required = {args.id_column, args.timestamp_column, args.split_column, *targets, *covariates}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    split_values = set(df[args.split_column].astype(str))
    if not {"train", "validation", "test"}.issubset(split_values):
        raise ValueError("split column must contain train, validation and test")

    # Guard against the most common leakage: the same item/run appearing in multiple splits.
    split_ids = {
        s: set(df.loc[df[args.split_column] == s, args.id_column].astype(str))
        for s in ["train", "validation", "test"]
    }
    if (split_ids["train"] & split_ids["validation"]) or (split_ids["train"] & split_ids["test"]) or (split_ids["validation"] & split_ids["test"]):
        raise ValueError("Leakage detected: the same item_id/run appears in multiple splits")

    train_df = df[df[args.split_column] == "train"].drop(columns=[args.split_column]).copy()
    val_df = df[df[args.split_column] == "validation"].drop(columns=[args.split_column]).copy()
    test_df = df[df[args.split_column] == "test"].drop(columns=[args.split_column]).copy()

    train_inputs = from_data_frame(
        train_df,
        target_columns=targets,
        prediction_length=args.prediction_length,
        known_covariates_names=covariates or None,
        id_column=args.id_column,
        timestamp_column=args.timestamp_column,
    )
    val_inputs = from_data_frame(
        val_df,
        target_columns=targets,
        prediction_length=args.prediction_length,
        known_covariates_names=covariates or None,
        id_column=args.id_column,
        timestamp_column=args.timestamp_column,
    )

    pipeline = Chronos2Pipeline.from_pretrained(args.model, device_map="cuda")
    finetuned = pipeline.fit(
        inputs=train_inputs,
        validation_inputs=val_inputs,
        prediction_length=args.prediction_length,
        finetune_mode="lora",
        context_length=args.context_length,
        learning_rate=args.lr,
        num_steps=args.steps,
        batch_size=args.batch_size,
        output_dir=args.outdir / "trainer",
        finetuned_ckpt_name="adapter_model",
    )

    test_inputs, actuals, ids = make_test_inputs(
        test_df, targets, covariates, args.prediction_length, args.id_column, args.timestamp_column
    )
    predictions = finetuned.predict(
        test_inputs,
        prediction_length=args.prediction_length,
        batch_size=args.batch_size,
    )
    quantiles = np.asarray(finetuned.quantiles)
    median_idx = int(np.argmin(np.abs(quantiles - 0.5)))

    model_errors, persistence_errors = [], []
    rows = []
    for item_id, pred_tensor, actual, inp in zip(ids, predictions, actuals, test_inputs):
        pred = pred_tensor[:, median_idx, :].float().cpu().numpy()
        persistence = np.repeat(np.asarray(inp["target"])[:, -1:], args.prediction_length, axis=1)
        m_mae = mae(actual, pred)
        p_mae = mae(actual, persistence)
        model_errors.append(m_mae)
        persistence_errors.append(p_mae)
        rows.append({"item_id": item_id, "chronos_mae": m_mae, "persistence_mae": p_mae})

    metrics = {
        "run_id": "FLOWTRUST-V2-T01-D-20260812",
        "model": args.model,
        "foundation_parameters": 120_000_000,
        "finetune_mode": "lora",
        "targets": targets,
        "covariates": covariates,
        "train_items": len(split_ids["train"]),
        "validation_items": len(split_ids["validation"]),
        "test_items": len(ids),
        "chronos_median_mae_mean": float(np.mean(model_errors)),
        "persistence_mae_mean": float(np.mean(persistence_errors)),
        "relative_mae_change_vs_persistence": float(np.mean(model_errors) / max(np.mean(persistence_errors), 1e-12) - 1.0),
        "note": "Forecast residual/anomaly metrics are computed in the downstream evidence stage; this run first verifies time-series adaptation and closed-run generalization."
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.outdir / "closed_test_forecast_metrics.csv", index=False)
    (args.outdir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
