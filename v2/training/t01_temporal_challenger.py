from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def load_matrix(path: Path):
    return np.loadtxt(path, dtype=np.float32)


def group_split(groups, seed=2026):
    idx = np.arange(len(groups))
    s1 = GroupShuffleSplit(n_splits=1, train_size=.70, random_state=seed)
    tr, rest = next(s1.split(idx, groups=groups))
    s2 = GroupShuffleSplit(n_splits=1, train_size=.50, random_state=seed + 1)
    va_rel, te_rel = next(s2.split(rest, groups=groups[rest]))
    return tr, rest[va_rel], rest[te_rel]


def build_windows(root: Path, max_cycles: int, context: int, horizon: int, windows_per_cycle: int):
    ps1 = load_matrix(root / 'PS1.txt')
    ps2 = load_matrix(root / 'PS2.txt')
    eps = load_matrix(root / 'EPS1.txt')
    profile = load_matrix(root / 'profile.txt')
    if not (len(ps1) == len(ps2) == len(eps) == len(profile)):
        raise RuntimeError('UCI channel cycle counts differ')
    stable = np.flatnonzero(profile[:, 4] == 0)
    if len(stable) > max_cycles:
        stable = stable[np.linspace(0, len(stable)-1, max_cycles).round().astype(int)]

    X, Y, groups = [], [], []
    total = context + horizon
    for cycle in stable:
        raw = np.stack([ps1[cycle], ps2[cycle], eps[cycle]], axis=0).astype(np.float32)
        max_start = raw.shape[1] - total
        if max_start < 0:
            continue
        starts = np.linspace(0, max_start, windows_per_cycle + 2).round().astype(int)[1:-1]
        for start in starts:
            block = raw[:, start:start+total]
            ctx = block[:, :context]
            fut = block[:, context:]
            mu = ctx.mean(axis=1, keepdims=True)
            scale = ctx.std(axis=1, keepdims=True)
            scale = np.maximum(scale, np.maximum(np.mean(np.abs(ctx), axis=1, keepdims=True) * .01, 1e-6))
            ctx_z = (ctx - mu) / scale
            fut_z = (fut - mu) / scale
            # Flatten raw context plus first differences; the latter make local dynamics explicit.
            feat = np.concatenate([ctx_z.reshape(-1), np.diff(ctx_z, axis=1).reshape(-1)])
            X.append(feat.astype(np.float32))
            Y.append(fut_z.reshape(-1).astype(np.float32))
            groups.append(f'uci_cycle_{int(cycle):04d}')
    return np.stack(X), np.stack(Y), np.asarray(groups)


def score(y_true, y_pred):
    return float(mean_absolute_error(y_true, y_pred))


def persistence_from_features(X, channels, context, horizon):
    ctx_flat = X[:, :channels * context].reshape(-1, channels, context)
    last = ctx_flat[:, :, -1]
    return np.repeat(last[:, :, None], horizon, axis=2).reshape(len(X), -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--outdir', type=Path, default=Path('artifacts/t01d1'))
    ap.add_argument('--max-cycles', type=int, default=240)
    ap.add_argument('--windows-per-cycle', type=int, default=8)
    ap.add_argument('--context', type=int, default=64)
    ap.add_argument('--horizon', type=int, default=16)
    ap.add_argument('--seed', type=int, default=2026)
    args = ap.parse_args()

    for name in ['PS1.txt', 'PS2.txt', 'EPS1.txt', 'profile.txt']:
        if not (args.root / name).exists():
            raise FileNotFoundError(args.root / name)

    X, Y, groups = build_windows(args.root, args.max_cycles, args.context, args.horizon, args.windows_per_cycle)
    tr, va, te = group_split(groups, args.seed)
    persistence = persistence_from_features(X, 3, args.context, args.horizon)

    candidates = {
        'ridge': Pipeline([
            ('scale', StandardScaler()),
            ('model', Ridge(alpha=10.0)),
        ]),
        'extra_trees': ExtraTreesRegressor(
            n_estimators=300, max_features=.7, min_samples_leaf=2,
            n_jobs=-1, random_state=args.seed,
        ),
        'random_forest': RandomForestRegressor(
            n_estimators=250, max_features=.7, min_samples_leaf=2,
            n_jobs=-1, random_state=args.seed,
        ),
    }

    validation = {}
    for name, model in candidates.items():
        model.fit(X[tr], Y[tr])
        pred = model.predict(X[va])
        validation[name] = {
            'mae': score(Y[va], pred),
            'persistence_mae': score(Y[va], persistence[va]),
        }
        validation[name]['relative_vs_persistence'] = validation[name]['mae'] / max(validation[name]['persistence_mae'], 1e-12) - 1.0
        print(name, validation[name])

    best_name = min(validation, key=lambda n: validation[n]['mae'])
    best = candidates[best_name]
    tv = np.concatenate([tr, va])
    best.fit(X[tv], Y[tv])
    pred = best.predict(X[te])
    model_mae = score(Y[te], pred)
    persistence_mae = score(Y[te], persistence[te])
    relative = model_mae / max(persistence_mae, 1e-12) - 1.0
    gate = bool(model_mae <= .95 * persistence_mae)

    report = {
        'run_id': 'FLOWTRUST-V2-T01-D1',
        'task': 'multichannel short-horizon forecast on real stable UCI physical cycles',
        'source': 'UCI Condition monitoring of hydraulic systems, ID 447, CC BY 4.0',
        'doi': '10.24432/C5CW21',
        'channels': ['PS1_pressure', 'PS2_pressure', 'EPS1_motor_power'],
        'context_length': args.context,
        'prediction_length': args.horizon,
        'windows_per_cycle': args.windows_per_cycle,
        'data_shape': {'X': list(X.shape), 'Y': list(Y.shape)},
        'groups': {'total': int(len(np.unique(groups))), 'test': int(len(np.unique(groups[te])))},
        'split': 'group-disjoint 70/15/15 by physical source cycle; model selection on validation only',
        'validation_candidates': validation,
        'selected_model': best_name,
        'test_model_mae': model_mae,
        'test_persistence_mae': persistence_mae,
        'relative_error_vs_persistence': relative,
        'gate': 'closed-test normalized MAE <= 95% of persistence normalized MAE',
        'gate_passed': gate,
        'note': 'This is an off-domain temporal competence benchmark on a physical hydraulic rig; it is not a cement-plant performance claim.',
    }

    args.outdir.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': best, 'context': args.context, 'horizon': args.horizon, 'channels': report['channels']}, args.outdir / 'temporal_head.joblib')
    np.savez_compressed(args.outdir / 'closed_test_outputs.npz', indices=te, y_true=Y[te], y_pred=pred, persistence=persistence[te], groups=groups[te])
    (args.outdir / 'metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'selected_model': best_name, 'model_mae': model_mae, 'persistence_mae': persistence_mae, 'relative_error_vs_persistence': relative, 'gate_passed': gate}, indent=2))


if __name__ == '__main__':
    main()
