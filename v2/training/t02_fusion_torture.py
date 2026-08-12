from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from flowtrust_core import CLASSES, FEATURE_NAMES, generate_dataset
from v2.fusion.arbiter import SourceOpinion, fuse_opinions


MODALITIES = {
    "process": [
        "feeder_command_pct", "belt_speed_command_mps", "belt_speed_mps", "speed_ratio",
        "measured_mass_flow_tph", "hopper_level_pct", "hopper_level_rate_pct_min",
        "mass_balance_residual_abs_pct", "flow_cv_60s", "speed_signal_quality",
        "weigh_signal_quality", "level_signal_quality",
    ],
    "electromechanical": [
        "motor_current_a", "motor_load_ratio", "motor_torque_pct", "vibration_mm_s",
        "motor_current_cv_60s", "belt_speed_mps", "speed_ratio", "electrical_signal_quality",
    ],
    "vision": [
        "visual_flow_proxy_tph", "visual_occupancy_pct", "visual_accumulation_pct",
        "visual_spillage_pct", "flow_disagreement_ratio", "camera_quality", "camera_connected",
    ],
}

QUALITY_FEATURES = {
    "process": ["speed_signal_quality", "weigh_signal_quality", "level_signal_quality"],
    "electromechanical": ["electrical_signal_quality", "speed_signal_quality"],
    "vision": ["camera_quality", "camera_connected"],
}


def idx(names):
    return [FEATURE_NAMES.index(n) for n in names]


def quality_for(row: np.ndarray, modality: str) -> float:
    vals = [float(row[FEATURE_NAMES.index(n)]) for n in QUALITY_FEATURES[modality]]
    return float(np.clip(min(vals), 0.0, 1.0))


def fit_heads(Xtr, ytr, seed):
    heads = {}
    for offset, (name, features) in enumerate(MODALITIES.items()):
        model = ExtraTreesClassifier(
            n_estimators=260,
            max_features="sqrt",
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed + offset,
            n_jobs=-1,
        )
        model.fit(Xtr[:, idx(features)], ytr)
        heads[name] = model
    return heads


def proba_dict(model, row, features):
    p = model.predict_proba(row[idx(features)].reshape(1, -1))[0]
    return {c: float(v) for c, v in zip(model.classes_, p)}


def wrong_distribution(true_label: str, rng: np.random.Generator):
    wrong = [c for c in CLASSES if c != true_label]
    chosen = wrong[int(rng.integers(0, len(wrong)))]
    base = {c: 0.002 for c in CLASSES}
    base[chosen] = 0.99
    return base


def evaluate_case(X, y, heads, *, corruption="none", seed=2026):
    rng = np.random.default_rng(seed)
    decisions = []
    for i, (row, truth) in enumerate(zip(X, y)):
        opinions = []
        for m_idx, (name, features) in enumerate(MODALITIES.items()):
            probs = proba_dict(heads[name], row, features)
            q = quality_for(row, name)
            integrity = 1.0

            if corruption == "single_silent" and m_idx == i % 3:
                probs = wrong_distribution(str(truth), rng)
            elif corruption == "single_detected" and m_idx == i % 3:
                probs = wrong_distribution(str(truth), rng)
                integrity = 0.20
            elif corruption == "double_detected" and m_idx in {i % 3, (i + 1) % 3}:
                probs = wrong_distribution(str(truth), rng)
                integrity = 0.20
            elif corruption == "missing_one" and m_idx == i % 3:
                q = 0.0
            elif corruption == "degraded_all":
                q = 0.20
                integrity = 0.20

            opinions.append(SourceOpinion(name=name, probabilities=probs, quality=q, integrity=integrity))

        d = fuse_opinions(opinions, CLASSES)
        decisions.append(d)

    covered = np.asarray([not d.abstained for d in decisions], dtype=bool)
    pred = np.asarray([d.label for d in decisions], dtype=object)
    coverage = float(covered.mean())
    selective_accuracy = float(accuracy_score(y[covered], pred[covered])) if covered.any() else 1.0
    wrong_nonabstain_rate = float(np.mean(covered & (pred != y)))
    abstention_rate = float(1.0 - coverage)
    return {
        "n": int(len(y)),
        "coverage": coverage,
        "abstention_rate": abstention_rate,
        "selective_accuracy": selective_accuracy,
        "wrong_nonabstain_rate": wrong_nonabstain_rate,
        "reason_counts": {reason: sum(d.reason == reason for d in decisions) for reason in sorted(set(d.reason for d in decisions))},
    }


def explicit_conflict_test():
    a, b = CLASSES[0], CLASSES[1]
    hi_a = {c: (0.99 if c == a else 0.002) for c in CLASSES}
    hi_b = {c: (0.99 if c == b else 0.002) for c in CLASSES}
    flat = {c: 1.0 / len(CLASSES) for c in CLASSES}
    d = fuse_opinions([
        SourceOpinion("process", hi_a, quality=1.0, integrity=1.0),
        SourceOpinion("electromechanical", hi_b, quality=1.0, integrity=1.0),
        SourceOpinion("vision", flat, quality=0.2, integrity=1.0),
    ], CLASSES)
    return d.to_dict()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("artifacts/t02"))
    ap.add_argument("--samples-per-class", type=int, default=500)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    X, y = generate_dataset(samples_per_class=args.samples_per_class, seed=args.seed)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=.30, random_state=args.seed, stratify=y
    )
    heads = fit_heads(Xtr, ytr, args.seed)

    cases = {
        "clean": evaluate_case(Xte, yte, heads, corruption="none", seed=args.seed),
        "single_source_silent_wrong": evaluate_case(Xte, yte, heads, corruption="single_silent", seed=args.seed + 1),
        "single_source_flagged_bad": evaluate_case(Xte, yte, heads, corruption="single_detected", seed=args.seed + 2),
        "two_sources_flagged_bad": evaluate_case(Xte, yte, heads, corruption="double_detected", seed=args.seed + 3),
        "one_source_missing": evaluate_case(Xte, yte, heads, corruption="missing_one", seed=args.seed + 4),
        "all_sources_degraded": evaluate_case(Xte, yte, heads, corruption="degraded_all", seed=args.seed + 5),
    }
    conflict = explicit_conflict_test()

    gates = {
        "clean_selective_accuracy_ge_0_98": cases["clean"]["selective_accuracy"] >= .98,
        "clean_coverage_ge_0_75": cases["clean"]["coverage"] >= .75,
        "silent_single_wrong_nonabstain_le_0_02": cases["single_source_silent_wrong"]["wrong_nonabstain_rate"] <= .02,
        "flagged_single_wrong_nonabstain_le_0_01": cases["single_source_flagged_bad"]["wrong_nonabstain_rate"] <= .01,
        "flagged_double_abstention_ge_0_98": cases["two_sources_flagged_bad"]["abstention_rate"] >= .98,
        "all_degraded_abstention_eq_1": cases["all_sources_degraded"]["abstention_rate"] == 1.0,
        "explicit_conflict_abstains": bool(conflict["abstained"]),
    }

    report = {
        "run_id": "FLOWTRUST-V2-T02-FUSION",
        "task": "multimodal confidence arbitration and safe abstention torture benchmark",
        "data": {
            "dataset": "FLOWTRUST synthetic SIL generator",
            "samples": int(len(y)),
            "train": int(len(ytr)),
            "closed_test": int(len(yte)),
            "classes": CLASSES,
            "warning": "Synthetic SIL only. This benchmark validates arbitration logic, not SOCOCIM diagnostic performance.",
        },
        "modalities": MODALITIES,
        "cases": cases,
        "explicit_high_confidence_conflict": conflict,
        "gates": gates,
        "all_gates_passed": bool(all(gates.values())),
        "integration_rule": "No automatic control. A failed confidence/consensus gate yields label=unknown and operator verification guidance.",
    }

    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["all_gates_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
