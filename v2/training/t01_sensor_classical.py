from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

SEQ_LEN = 512


def load_npz(path: Path):
    d = np.load(path, allow_pickle=False)
    X = np.asarray(d['X'], dtype=np.float32)
    y = np.asarray(d['y']).astype(str)
    groups = np.asarray(d['groups']).astype(str)
    if X.ndim != 3 or X.shape[-1] != SEQ_LEN:
        raise ValueError(f'expected X[N,C,{SEQ_LEN}], got {X.shape}')
    return X, y, groups


def group_split(groups, seed=2026):
    idx = np.arange(len(groups))
    s1 = GroupShuffleSplit(n_splits=1, train_size=.70, random_state=seed)
    tr, rest = next(s1.split(idx, groups=groups))
    s2 = GroupShuffleSplit(n_splits=1, train_size=.50, random_state=seed + 1)
    va_rel, te_rel = next(s2.split(rest, groups=groups[rest]))
    return tr, rest[va_rel], rest[te_rel]


def safe_corr(a, b):
    if a.size < 4 or b.size < 4 or np.std(a) < 1e-8 or np.std(b) < 1e-8:
        return 0.0
    v = np.corrcoef(a, b)[0, 1]
    return float(v) if np.isfinite(v) else 0.0


def feature_vector(sample):
    row = []
    t = np.linspace(-1.0, 1.0, sample.shape[-1], dtype=np.float32)
    clean = np.nan_to_num(sample, nan=0.0, posinf=0.0, neginf=0.0)
    for ch in clean:
        d = np.diff(ch)
        mu = float(ch.mean())
        sd = float(ch.std() + 1e-8)
        z = (ch - mu) / sd
        q = np.quantile(ch, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
        slope = float(np.dot(ch - mu, t) / (np.dot(t, t) + 1e-8))
        repeated = float(np.mean(np.isclose(d, 0.0, atol=max(1e-6, sd * 1e-4))))
        zero_fraction = float(np.mean(np.isclose(ch, 0.0, atol=max(1e-6, sd * 1e-4))))
        clip_fraction = float(np.mean((ch <= q[0] + 1e-8) | (ch >= q[-1] - 1e-8)))
        fft = np.abs(np.fft.rfft(ch - mu))
        power = fft * fft
        total = float(power.sum() + 1e-12)
        freqs = np.linspace(0.0, 1.0, len(power))
        centroid = float((freqs * power).sum() / total)
        high = float(power[int(.35 * len(power)):].sum() / total)
        row.extend([
            mu, sd, float(ch.min()), float(ch.max()), float(np.ptp(ch)),
            *[float(v) for v in q],
            float(np.median(np.abs(ch - np.median(ch)))),
            float(np.mean(z ** 3)), float(np.mean(z ** 4) - 3.0),
            slope, float(np.mean(np.abs(d))), float(np.std(d)),
            float(np.max(np.abs(d))) if d.size else 0.0,
            repeated, zero_fraction, clip_fraction,
            safe_corr(ch[:-1], ch[1:]),
            safe_corr(ch[:-8], ch[8:]),
            safe_corr(ch[:-32], ch[32:]),
            centroid, high,
        ])

    # Cross-channel synchrony is intentionally explicit: timestamp shifts should not
    # have to be inferred from marginal channel distributions alone.
    for i in range(clean.shape[0]):
        for j in range(i + 1, clean.shape[0]):
            a, b = clean[i], clean[j]
            for lag in (-64, -32, 0, 32, 64):
                if lag < 0:
                    row.append(safe_corr(a[-lag:], b[:lag]))
                elif lag > 0:
                    row.append(safe_corr(a[:-lag], b[lag:]))
                else:
                    row.append(safe_corr(a, b))
    return row


def features(X):
    return np.asarray([feature_vector(s) for s in X], dtype=np.float32)


def metric_pack(y, pred):
    return {
        'macro_f1': float(f1_score(y, pred, average='macro')),
        'balanced_accuracy': float(balanced_accuracy_score(y, pred)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--outdir', type=Path, default=Path('artifacts/t01f1'))
    ap.add_argument('--seed', type=int, default=2026)
    args = ap.parse_args()

    X, y_names, groups = load_npz(args.data)
    tr, va, te = group_split(groups, args.seed)
    F = features(X)
    le = LabelEncoder().fit(y_names)
    y = le.transform(y_names)

    candidates = {
        'extra_trees': ExtraTreesClassifier(
            n_estimators=600, max_features='sqrt', class_weight='balanced',
            n_jobs=-1, random_state=args.seed,
        ),
        'random_forest': RandomForestClassifier(
            n_estimators=500, max_features='sqrt', class_weight='balanced_subsample',
            n_jobs=-1, random_state=args.seed,
        ),
        'hist_gradient_boosting': HistGradientBoostingClassifier(
            max_iter=300, learning_rate=.06, l2_regularization=1.0,
            random_state=args.seed,
        ),
        'logistic': Pipeline([
            ('scale', StandardScaler()),
            ('clf', LogisticRegression(max_iter=4000, class_weight='balanced', C=1.0, random_state=args.seed)),
        ]),
    }

    validation = {}
    for name, model in candidates.items():
        model.fit(F[tr], y[tr])
        pred = model.predict(F[va])
        validation[name] = metric_pack(y[va], pred)
        print(name, validation[name])

    best_name = max(validation, key=lambda n: (validation[n]['macro_f1'], validation[n]['balanced_accuracy']))
    best = candidates[best_name]
    # Final fit can use train+validation only after architecture selection.
    tv = np.concatenate([tr, va])
    best.fit(F[tv], y[tv])
    pred = best.predict(F[te])
    proba = best.predict_proba(F[te]) if hasattr(best, 'predict_proba') else None
    test_metrics = metric_pack(y[te], pred)

    true_names = le.inverse_transform(y[te])
    pred_names = le.inverse_transform(pred)
    report = {
        'run_id': 'FLOWTRUST-V2-T01-F1',
        'task': 'controlled sensor-integrity classification on real UCI physical cycles',
        'data_shape': list(X.shape),
        'feature_count': int(F.shape[1]),
        'split': 'group-disjoint 70/15/15 by physical source cycle; model selection on validation only',
        'classes': le.classes_.tolist(),
        'counts': {'train': int(len(tr)), 'validation': int(len(va)), 'test': int(len(te))},
        'groups': {'total': int(len(np.unique(groups))), 'test': int(len(np.unique(groups[te])))},
        'validation_candidates': validation,
        'selected_model': best_name,
        'test': test_metrics,
        'confusion_matrix': confusion_matrix(y[te], pred, labels=np.arange(len(le.classes_))).tolist(),
        'classification_report': classification_report(true_names, pred_names, output_dict=True, zero_division=0),
        'closed_test_mean_confidence': float(proba.max(1).mean()) if proba is not None else None,
        'gate': 'macro-F1 >= 0.90 and balanced accuracy >= 0.90 on group-disjoint closed test',
        'gate_passed': bool(test_metrics['macro_f1'] >= .90 and test_metrics['balanced_accuracy'] >= .90),
        'note': 'Fault labels are controlled corruptions injected on real physical UCI hydraulic cycles. This is a sensor-integrity benchmark, not cement-process diagnosis.',
    }

    args.outdir.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': best, 'label_encoder': le, 'feature_schema': 't01_sensor_classical_v1'}, args.outdir / 'sensor_integrity_head.joblib')
    np.savez_compressed(args.outdir / 'closed_test_outputs.npz', indices=te, y_true=y[te], y_pred=pred, proba=proba if proba is not None else np.empty((0, 0)))
    (args.outdir / 'metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'selected_model': best_name, **test_metrics, 'gate_passed': report['gate_passed']}, indent=2))


if __name__ == '__main__':
    main()
