from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

FAULTS = [
    "normal",
    "stuck_at",
    "drift",
    "bias",
    "spike",
    "noise_burst",
    "dropout",
    "timestamp_shift",
    "clipping",
]
SEQ_LEN = 512


def load_matrix(path: Path) -> np.ndarray:
    return np.loadtxt(path, dtype=np.float32)


def robust_normalize_cycle(x: np.ndarray) -> np.ndarray:
    med = np.median(x, axis=1, keepdims=True)
    mad = np.median(np.abs(x - med), axis=1, keepdims=True)
    scale = np.maximum(1.4826 * mad, np.std(x, axis=1, keepdims=True) * 0.25)
    scale = np.maximum(scale, 1e-4)
    return (x - med) / scale


def inject_fault(base: np.ndarray, fault: str, rng: np.random.Generator) -> np.ndarray:
    x = base.copy()
    if fault == "normal":
        return x
    c = int(rng.integers(0, x.shape[0]))
    s = int(rng.integers(96, 192))
    e = int(rng.integers(320, 448))
    if e <= s + 32:
        e = min(SEQ_LEN, s + 96)

    if fault == "stuck_at":
        x[c, s:e] = x[c, s]
    elif fault == "drift":
        amp = float(rng.uniform(1.0, 2.5)) * (1 if rng.random() > 0.5 else -1)
        x[c, s:] += np.linspace(0.0, amp, SEQ_LEN - s, dtype=np.float32)
    elif fault == "bias":
        amp = float(rng.uniform(0.8, 1.8)) * (1 if rng.random() > 0.5 else -1)
        x[c, s:e] += amp
    elif fault == "spike":
        n = int(rng.integers(3, 9))
        idx = rng.choice(np.arange(s, e), size=n, replace=False)
        x[c, idx] += rng.normal(0.0, 5.0, size=n).astype(np.float32)
    elif fault == "noise_burst":
        x[c, s:e] += rng.normal(0.0, 1.8, size=e-s).astype(np.float32)
    elif fault == "dropout":
        x[c, s:e] = 0.0
    elif fault == "timestamp_shift":
        shift = int(rng.integers(24, 80))
        x[c] = np.roll(x[c], shift)
        x[c, :shift] = x[c, shift]
    elif fault == "clipping":
        lo, hi = np.quantile(x[c], [0.2, 0.8])
        x[c, s:e] = np.clip(x[c, s:e], lo, hi)
    else:
        raise ValueError(fault)
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True, help="Extracted UCI hydraulic dataset directory")
    ap.add_argument("--out", type=Path, default=Path("data/manifests/t01f_uci_sensor_faults.npz"))
    ap.add_argument("--max-cycles", type=int, default=54)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    required = ["PS1.txt", "PS2.txt", "EPS1.txt", "profile.txt"]
    for name in required:
        if not (args.root / name).exists():
            raise FileNotFoundError(args.root / name)

    print("Loading real UCI hydraulic channels...")
    ps1 = load_matrix(args.root / "PS1.txt")
    ps2 = load_matrix(args.root / "PS2.txt")
    eps = load_matrix(args.root / "EPS1.txt")
    profile = load_matrix(args.root / "profile.txt")
    if not (len(ps1) == len(ps2) == len(eps) == len(profile)):
        raise RuntimeError("Channel/profile cycle counts differ")

    # UCI profile column 5: stable flag, 0 = stable, 1 = conditions may not be stationary yet.
    stable = np.flatnonzero(profile[:, 4] == 0)
    if len(stable) < args.max_cycles:
        selected = stable
    else:
        # Spread selections across the experiment timeline to avoid a narrow operating slice.
        idx = np.linspace(0, len(stable) - 1, args.max_cycles).round().astype(int)
        selected = stable[idx]

    rng = np.random.default_rng(args.seed)
    X, y, groups, source_cycles = [], [], [], []
    for cycle in selected:
        raw = np.stack([ps1[cycle], ps2[cycle], eps[cycle]], axis=0)
        raw = robust_normalize_cycle(raw)
        max_start = raw.shape[1] - SEQ_LEN
        start = int(rng.integers(0, max_start + 1))
        base = raw[:, start:start + SEQ_LEN].astype(np.float32)
        for fault in FAULTS:
            local_rng = np.random.default_rng(args.seed + int(cycle) * 101 + FAULTS.index(fault) * 10007)
            X.append(inject_fault(base, fault, local_rng))
            y.append(fault)
            groups.append(f"uci_cycle_{int(cycle):04d}")
            source_cycles.append(int(cycle))

    X = np.stack(X).astype(np.float32)
    y = np.asarray(y)
    groups = np.asarray(groups)
    source_cycles = np.asarray(source_cycles, dtype=np.int32)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        X=X,
        y=y,
        groups=groups,
        source_cycles=source_cycles,
        channels=np.asarray(["PS1_pressure", "PS2_pressure", "EPS1_motor_power"]),
        source=np.asarray("UCI Condition monitoring of hydraulic systems, ID 447, CC BY 4.0"),
        doi=np.asarray("10.24432/C5CW21"),
        seed=np.asarray(args.seed, dtype=np.int64),
    )
    print(f"wrote={args.out} X={X.shape} groups={len(np.unique(groups))}")
    unique, counts = np.unique(y, return_counts=True)
    print(dict(zip(unique.tolist(), counts.tolist())))


if __name__ == "__main__":
    main()
