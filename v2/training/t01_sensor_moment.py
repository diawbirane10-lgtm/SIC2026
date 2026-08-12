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


def statistical_features(X):
    feats = []
    t = np.linspace(-1.0, 1.0, X.shape[-1], dtype=np.float32)
    for sample in X:
        row = []
        for ch in sample:
            finite = np.nan_to_num(ch, nan=0.0, posinf=0.0, neginf=0.0)
            d = np.diff(finite)
            mu = float(finite.mean())
            std = float(finite.std() + 1e-8)
            slope = float(np.dot(finite - mu, t) / (np.dot(t, t) + 1e-8))
            repeated = float(np.mean(np.isclose(d, 0.0, atol=max(1e-6, std * 1e-4))))
            zero_fraction = float(np.mean(np.isclose(finite, 0.0, atol=max(1e-6, std * 1e-4))))
            q01, q99 = np.quantile(finite, [0.01, 0.99])
            clip_fraction = float(np.mean((finite <= q01 + 1e-8) | (finite >= q99 - 1e-8)))
            ac = float(np.corrcoef(finite[:-1], finite[1:])[0, 1]) if std > 1e-7 else 1.0
            if not np.isfinite(ac):
                ac = 0.0
            row.extend([
                mu, std, float(finite.min()), float(finite.max()),
                float(np.ptp(finite)), slope, float(np.std(d)),
                float(np.max(np.abs(d))) if len(d) else 0.0,
                repeated, zero_fraction, clip_fraction, ac,
            ])
        feats.append(row)
    return np.asarray(feats, dtype=np.float32)


def extract_embeddings(X, batch_size, device, out_cache: Path):
    if out_cache.exists():
        z = np.load(out_cache, allow_pickle=False)
        if tuple(z["embeddings"].shape[:1]) == (len(X),):
            return z["embeddings"], int(z.get("encoder_parameters", np.asarray(341_231_104)).item())

    model = MOMENTPipeline.from_pretrained(MODEL_ID, model_kwargs={"task_name": "embedding"})
    model.init()
    model.to(device).eval()
    enc_params = int(sum(p.numel() for p in model.encoder.parameters()))
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
    np.savez_compressed(out_cache, embeddings=emb, encoder_parameters=np.asarray(enc_params, dtype=np.int64))
    return emb, enc_params


def fit_calibrated(X, y, tr, va, seed):
    base = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0, random_state=seed)),
    ])
    base.fit(X[tr], y[tr])
    calibrated = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
    calibrated.fit(X[va], y[va])
    return calibrated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="NPZ arrays X[N,C,512], y[N], groups[N]")
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t01/sensor_integrity"))
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    args = ap.parse_args()

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    print(f"T01-F device={device}")

    X, y_names, groups = load_npz(args.data)
    tr, va, te = group_split(groups, args.seed)
    args.outdir.mkdir(parents=True, exist_ok=True)

    le = LabelEncoder().fit(y_names)
    y = le.transform(y_names)

    stat = statistical_features(X)
    stat_head = fit_calibrated(stat, y, tr, va, args.seed)
    stat_pred = stat_head.predict(stat[te])
    stat_f1 = float(f1_score(y[te], stat_pred, average="macro"))
    stat_bal = float(balanced_accuracy_score(y[te], stat_pred))

    emb, enc_params = extract_embeddings(X, args.batch_size, device, args.outdir / "moment_embeddings.npz")
    moment_head = fit_calibrated(emb, y, tr, va, args.seed)
    pred = moment_head.predict(emb[te])
    proba = moment_head.predict_proba(emb[te])

    true_names = le.inverse_transform(y[te])
    pred_names = le.inverse_transform(pred)
    macro_f1 = float(f1_score(y[te], pred, average="macro"))
    bal_acc = float(balanced_accuracy_score(y[te], pred))
    improvement = macro_f1 - stat_f1

    report = {
        "run_id": "FLOWTRUST-V2-T01-F-20260812",
        "foundation": MODEL_ID,
        "foundation_encoder_parameters": enc_params,
        "device": device,
        "training": "calibrated linear probe on frozen foundation embeddings",
        "split": "group-disjoint 70/15/15 by physical source cycle",
        "classes": le.classes_.tolist(),
        "counts": {"train": int(len(tr)), "validation": int(len(va)), "test": int(len(te))},
        "macro_f1": macro_f1,
        "balanced_accuracy": bal_acc,
        "confusion_matrix": confusion_matrix(y[te], pred, labels=np.arange(len(le.classes_))).tolist(),
        "classification_report": classification_report(true_names, pred_names, output_dict=True, zero_division=0),
        "closed_test_mean_confidence": float(proba.max(1).mean()),
        "statistical_baseline": {
            "description": "logistic classifier on per-channel distribution, slope, derivative, repeated-value, zero/dropout, clipping and autocorrelation features",
            "macro_f1": stat_f1,
            "balanced_accuracy": stat_bal,
        },
        "moment_minus_baseline_macro_f1": improvement,
        "bootstrap_gate": "MOMENT macro-F1 >= statistical baseline macro-F1 and MOMENT balanced accuracy >= baseline balanced accuracy",
        "bootstrap_gate_passed": bool(macro_f1 >= stat_f1 and bal_acc >= stat_bal),
        "required_fault_labels": ["normal", "stuck_at", "drift", "bias", "spike", "noise_burst", "dropout", "timestamp_shift", "clipping"],
        "note": "Fault classes in this bootstrap are controlled sensor corruptions injected on real physical UCI hydraulic cycles; this evaluates sensor-integrity recognition, not cement-process diagnosis."
    }
    joblib.dump({"head": moment_head, "label_encoder": le, "foundation": MODEL_ID}, args.outdir / "sensor_fault_head.joblib")
    joblib.dump({"head": stat_head, "label_encoder": le}, args.outdir / "statistical_baseline_head.joblib")
    (args.outdir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(args.outdir / "closed_test_outputs.npz", indices=te, y_true=y[te], y_pred=pred, proba=proba)
    print(json.dumps({
        "macro_f1": macro_f1,
        "balanced_accuracy": bal_acc,
        "statistical_macro_f1": stat_f1,
        "statistical_balanced_accuracy": stat_bal,
        "bootstrap_gate_passed": report["bootstrap_gate_passed"],
    }, indent=2))


if __name__ == "__main__":
    main()
