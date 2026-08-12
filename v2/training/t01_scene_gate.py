from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from transformers import AutoImageProcessor, AutoModel

DEFAULT_MODEL = "facebook/dinov3-vitl16-pretrain-lvd1689m"
VALID_LABELS = {"conveyor_applicable", "industrial_non_conveyor", "non_industrial", "uncertain"}


def expected_calibration_error(y_true, proba, n_bins=10):
    pred = proba.argmax(1)
    conf = proba.max(1)
    correct = (pred == y_true).astype(float)
    ece = 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def load_manifest(path: Path):
    df = pd.read_csv(path)
    required = {"image_path", "label", "group"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Manifest missing columns: {sorted(missing)}")
    bad = sorted(set(df.label) - VALID_LABELS)
    if bad:
        raise ValueError(f"Unsupported labels: {bad}")
    for p in df.image_path:
        if not Path(p).exists():
            raise FileNotFoundError(p)
    return df


def extract_embeddings(df, model_id, batch_size, device, cache_path):
    if cache_path.exists():
        cache = np.load(cache_path, allow_pickle=False)
        if list(cache["image_path"]) == list(df.image_path.astype(str)):
            print(f"Using cached embeddings: {cache_path}")
            return cache["embeddings"]

    processor = AutoImageProcessor.from_pretrained(model_id)
    dtype = torch.bfloat16 if device.startswith("cuda") and torch.cuda.is_bf16_supported() else torch.float32
    model = AutoModel.from_pretrained(model_id, torch_dtype=dtype).to(device).eval()

    chunks = []
    with torch.inference_mode():
        for start in range(0, len(df), batch_size):
            paths = df.image_path.iloc[start:start + batch_size]
            images = [Image.open(p).convert("RGB") for p in paths]
            inputs = processor(images=images, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            outputs = model(**inputs)
            emb = outputs.pooler_output.float().cpu().numpy()
            chunks.append(emb)
            print(f"embedded {min(start + batch_size, len(df))}/{len(df)}")

    embeddings = np.concatenate(chunks, axis=0)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_path, embeddings=embeddings, image_path=df.image_path.astype(str).to_numpy())
    return embeddings


def split_groups(df, seed):
    gss1 = GroupShuffleSplit(n_splits=1, train_size=0.70, random_state=seed)
    train_idx, rest_idx = next(gss1.split(df, groups=df.group))
    rest = df.iloc[rest_idx]
    gss2 = GroupShuffleSplit(n_splits=1, train_size=0.50, random_state=seed + 1)
    val_rel, test_rel = next(gss2.split(rest, groups=rest.group))
    return train_idx, rest_idx[val_rel], rest_idx[test_rel]


def false_conveyor_accept_rate(y_true_names, pred_names):
    neg = np.asarray(y_true_names) != "conveyor_applicable"
    if not neg.any():
        return None
    return float((np.asarray(pred_names)[neg] == "conveyor_applicable").mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True, help="CSV: image_path,label,group[,source,license]")
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t01/vision_scene_gate"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise RuntimeError("T01-A requires a CUDA GPU for the selected 300M DINOv3 ViT-L backbone.")

    df = load_manifest(args.manifest).reset_index(drop=True)
    args.outdir.mkdir(parents=True, exist_ok=True)
    embeddings = extract_embeddings(df, args.model, args.batch_size, device, args.outdir / "embeddings.npz")

    le = LabelEncoder().fit(df.label)
    y = le.transform(df.label)
    tr, va, te = split_groups(df, args.seed)

    # Fit a compact head on frozen 300M foundation embeddings.
    base = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2500, class_weight="balanced", C=1.0, random_state=args.seed)),
    ])
    base.fit(embeddings[tr], y[tr])

    # Calibration uses a group-disjoint validation set. FrozenEstimator prevents
    # accidental refitting of the classifier on calibration data.
    calibrated = CalibratedClassifierCV(estimator=FrozenEstimator(base), method="sigmoid")
    calibrated.fit(embeddings[va], y[va])

    proba = calibrated.predict_proba(embeddings[te])
    pred = calibrated.predict(embeddings[te])
    true_names = le.inverse_transform(y[te])
    pred_names = le.inverse_transform(pred)

    report = {
        "run_id": "FLOWTRUST-V2-T01-A-20260812",
        "model": args.model,
        "backbone_parameters": 300_000_000,
        "head": "logistic_regression_on_frozen_embeddings",
        "calibration": "sigmoid_on_group_disjoint_validation",
        "counts": {"train": int(len(tr)), "validation": int(len(va)), "test": int(len(te))},
        "groups": {
            "train": int(df.group.iloc[tr].nunique()),
            "validation": int(df.group.iloc[va].nunique()),
            "test": int(df.group.iloc[te].nunique()),
        },
        "macro_f1": float(f1_score(y[te], pred, average="macro")),
        "ece": expected_calibration_error(y[te], proba),
        "false_conveyor_accept_rate": false_conveyor_accept_rate(true_names, pred_names),
        "confusion_matrix": confusion_matrix(y[te], pred, labels=np.arange(len(le.classes_))).tolist(),
        "classes": le.classes_.tolist(),
        "classification_report": classification_report(true_names, pred_names, output_dict=True, zero_division=0),
        "gate": "false_conveyor_accept_rate <= 0.02",
    }
    report["gate_passed"] = report["false_conveyor_accept_rate"] is not None and report["false_conveyor_accept_rate"] <= 0.02

    joblib.dump({"classifier": calibrated, "label_encoder": le, "model_id": args.model}, args.outdir / "scene_gate_head.joblib")
    (args.outdir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    df.iloc[te].assign(prediction=pred_names, confidence=proba.max(1)).to_csv(args.outdir / "closed_test_predictions.csv", index=False)
    print(json.dumps({k: report[k] for k in ["macro_f1", "ece", "false_conveyor_accept_rate", "gate_passed"]}, indent=2))


if __name__ == "__main__":
    main()
