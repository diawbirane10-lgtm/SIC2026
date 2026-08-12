from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import torch
from momentfm import MOMENTPipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

MODEL_ID = "AutonLab/MOMENT-1-large"
SEQ_LEN = 512


def load_npz(path: Path):
    d = np.load(path, allow_pickle=False)
    required = {"X", "y", "groups"}
    missing = required - set(d.files)
    if missing:
        raise ValueError(f"NPZ missing arrays: {sorted(missing)}")
    X = np.asarray(d["X"], dtype=np.float32)
    y = np.asarray(d["y"]).astype(str)
    groups = np.asarray(d["groups"]).astype(str)
    if X.ndim != 3 or X.shape[-1] != SEQ_LEN:
        raise ValueError(f"X must have shape [N,C,{SEQ_LEN}], got {X.shape}")
    if not (len(X) == len(y) == len(groups)):
        raise ValueError("X, y and groups lengths differ")
    return X, y, groups


def group_split(groups, seed=2026):
    idx = np.arange(len(groups))
    s1 = GroupShuffleSplit(n_splits=1, train_size=.70, random_state=seed)
    tr, rest = next(s1.split(idx, groups=groups))
    s2 = GroupShuffleSplit(n_splits=1, train_size=.50, random_state=seed + 1)
    va_rel, te_rel = next(s2.split(rest, groups=groups[rest]))
    return tr, rest[va_rel], rest[te_rel]


def extract_embeddings(X, batch_size, device, out_cache: Path):
    if out_cache.exists():
        z = np.load(out_cache, allow_pickle=False)
        if tuple(z["embeddings"].shape[:1]) == (len(X),):
            return z["embeddings"]

    model = MOMENTPipeline.from_pretrained(MODEL_ID, model_kwargs={"task_name": "embedding"})
    model.init()
    model.to(device).eval()
    enc_params = sum(p.numel() for p in model.encoder.parameters())
    if enc_params != 341_231_104:
        print(f"WARNING: upstream encoder parameter count changed: {enc_params:,}")

    chunks = []
    with torch.inference_mode():
        for i in range(0, len(X), batch_size):
            x = torch.from_numpy(X[i:i+batch_size]).to(device)
            output = model(x_enc=x)
            chunks.append(output.embeddings.detach().float().cpu().numpy())
            print(f"embedded {min(i+batch_size,len(X))}/{len(X)}")
    emb = np.concatenate(chunks)
    out_cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_cache, embeddings=emb)
    return emb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="NPZ arrays X[N,C,512], y[N], groups[N]")
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t01/sensor_integrity"))
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("T01-F requires CUDA for the 341M MOMENT-1-large backbone.")
    device = "cuda"
    X, y_names, groups = load_npz(args.data)
    tr, va, te = group_split(groups, args.seed)
    args.outdir.mkdir(parents=True, exist_ok=True)
    emb = extract_embeddings(X, args.batch_size, device, args.outdir / "moment_embeddings.npz")

    le = LabelEncoder().fit(y_names)
    y = le.transform(y_names)
    base = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0, random_state=args.seed)),
    ])
    base.fit(emb[tr], y[tr])
    calibrated = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
    calibrated.fit(emb[va], y[va])
    pred = calibrated.predict(emb[te])
    proba = calibrated.predict_proba(emb[te])

    true_names = le.inverse_transform(y[te])
    pred_names = le.inverse_transform(pred)
    report = {
        "run_id": "FLOWTRUST-V2-T01-F-20260812",
        "foundation": MODEL_ID,
        "foundation_encoder_parameters": 341_231_104,
        "training": "calibrated linear probe on frozen foundation embeddings",
        "split": "group-disjoint 70/15/15",
        "classes": le.classes_.tolist(),
        "counts": {"train": len(tr), "validation": len(va), "test": len(te)},
        "macro_f1": float(f1_score(y[te], pred, average="macro")),
        "balanced_accuracy": float(balanced_accuracy_score(y[te], pred)),
        "confusion_matrix": confusion_matrix(y[te], pred, labels=np.arange(len(le.classes_))).tolist(),
        "classification_report": classification_report(true_names, pred_names, output_dict=True, zero_division=0),
        "closed_test_mean_confidence": float(proba.max(1).mean()),
        "required_fault_labels": ["normal", "stuck_at", "drift", "bias", "spike", "noise_burst", "dropout", "timestamp_shift", "clipping"],
        "note": "Reconstruction anomaly score remains a second independent MOMENT evidence channel; this experiment trains the guided-test fault-type head."
    }
    joblib.dump({"head": calibrated, "label_encoder": le, "foundation": MODEL_ID}, args.outdir / "sensor_fault_head.joblib")
    (args.outdir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(args.outdir / "closed_test_outputs.npz", indices=te, y_true=y[te], y_pred=pred, proba=proba)
    print(json.dumps({"macro_f1": report["macro_f1"], "balanced_accuracy": report["balanced_accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
