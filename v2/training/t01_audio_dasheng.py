from __future__ import annotations

import argparse
import json
from pathlib import Path

import dasheng
import joblib
import librosa
import numpy as np
import pandas as pd
import torch
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

SAMPLE_RATE = 16000
MODEL_PARAMS = 600_000_000


def read_manifest(path: Path):
    df = pd.read_csv(path)
    required = {"audio_path", "label", "group"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"manifest missing: {sorted(missing)}")
    for p in df.audio_path:
        if not Path(p).exists():
            raise FileNotFoundError(p)
    return df.reset_index(drop=True)


def group_split(df, seed):
    idx = np.arange(len(df))
    s1 = GroupShuffleSplit(n_splits=1, train_size=.70, random_state=seed)
    tr, rest = next(s1.split(idx, groups=df.group))
    s2 = GroupShuffleSplit(n_splits=1, train_size=.50, random_state=seed + 1)
    va_rel, te_rel = next(s2.split(rest, groups=df.group.iloc[rest]))
    return tr, rest[va_rel], rest[te_rel]


def load_audio(path: str, seconds: float):
    y, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    n = int(seconds * SAMPLE_RATE)
    if len(y) < n:
        y = np.pad(y, (0, n - len(y)))
    elif len(y) > n:
        # Center crop is deterministic; later runs may add training-only random crops.
        start = (len(y) - n) // 2
        y = y[start:start+n]
    peak = np.max(np.abs(y)) + 1e-8
    return (y / peak).astype(np.float32)


def embed(df, batch_size, seconds, device, cache_path):
    if cache_path.exists():
        z = np.load(cache_path, allow_pickle=False)
        if len(z["embeddings"]) == len(df):
            return z["embeddings"]

    model = dasheng.dasheng_06B().to(device).eval()
    chunks = []
    with torch.inference_mode():
        for i in range(0, len(df), batch_size):
            audio = np.stack([load_audio(p, seconds) for p in df.audio_path.iloc[i:i+batch_size]])
            x = torch.from_numpy(audio).to(device)
            feats = model(x)
            # Dasheng may return sequence features; aggregate only after preserving
            # the full backbone representation for each example.
            if feats.ndim == 3:
                feats = feats.mean(dim=1)
            chunks.append(feats.detach().float().cpu().numpy())
            print(f"embedded {min(i+batch_size,len(df))}/{len(df)}")
    emb = np.concatenate(chunks)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_path, embeddings=emb)
    return emb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True, help="CSV audio_path,label,group[,speed,load,noise_domain]")
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t01/conveyor_audio"))
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("T01-C requires CUDA for Dasheng-0.6B.")
    df = read_manifest(args.manifest)
    args.outdir.mkdir(parents=True, exist_ok=True)
    emb = embed(df, args.batch_size, args.seconds, "cuda", args.outdir / "dasheng_embeddings.npz")
    tr, va, te = group_split(df, args.seed)

    le = LabelEncoder().fit(df.label.astype(str))
    y = le.transform(df.label.astype(str))
    base = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0, random_state=args.seed)),
    ])
    base.fit(emb[tr], y[tr])
    clf = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
    clf.fit(emb[va], y[va])
    pred = clf.predict(emb[te])
    proba = clf.predict_proba(emb[te])
    true_names = le.inverse_transform(y[te])
    pred_names = le.inverse_transform(pred)

    report = {
        "run_id": "FLOWTRUST-V2-T01-C-20260812",
        "foundation": "Dasheng-0.6B",
        "foundation_parameters": MODEL_PARAMS,
        "foundation_pretraining": "272k hours general audio",
        "training": "calibrated linear fault head on frozen embeddings",
        "split": "group-disjoint 70/15/15",
        "classes": le.classes_.tolist(),
        "macro_f1": float(f1_score(y[te], pred, average="macro")),
        "balanced_accuracy": float(balanced_accuracy_score(y[te], pred)),
        "mean_confidence": float(proba.max(1).mean()),
        "confusion_matrix": confusion_matrix(y[te], pred, labels=np.arange(len(le.classes_))).tolist(),
        "classification_report": classification_report(true_names, pred_names, output_dict=True, zero_division=0),
        "note": "Training 01 starts with a frozen 600M encoder. Partial backbone fine-tuning is allowed only if it improves leave-condition-out results, not because more trainable parameters look better."
    }
    joblib.dump({"head": clf, "label_encoder": le, "foundation": "Dasheng-0.6B"}, args.outdir / "fault_head.joblib")
    (args.outdir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    df.iloc[te].assign(prediction=pred_names, confidence=proba.max(1)).to_csv(args.outdir / "closed_test_predictions.csv", index=False)
    print(json.dumps({"macro_f1": report["macro_f1"], "balanced_accuracy": report["balanced_accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
