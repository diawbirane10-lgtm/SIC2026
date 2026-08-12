from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

from flowtrust_core import CLASSES, make_synthetic_sample, operator_recommendation, physical_rules

TOOL_MAP = {
    "normal": "coherence_test",
    "weighing_drift": "sensor_test",
    "hopper_bridging": "coherence_test",
    "conveyor_blockage": "drive_test",
    "spillage": "camera_test",
    "unstable_feed": "coherence_test",
}

VERIFICATION_STEPS = {
    "normal": [
        "Poursuivre la surveillance des tendances.",
        "Ne déclencher aucune action automatique.",
    ],
    "weighing_drift": [
        "Comparer le débit pesé au proxy visuel et au bilan de trémie.",
        "Contrôler le zéro et la calibration du système de pesage.",
        "Vérifier l'état mécanique du doseur/peseur selon la procédure du site.",
    ],
    "hopper_bridging": [
        "Comparer niveau de trémie, commande doseur et débit aval.",
        "Confirmer visuellement la continuité du flux à la sortie de trémie.",
        "Demander une inspection terrain selon les règles de sécurité du site.",
    ],
    "conveyor_blockage": [
        "Comparer vitesse commandée et vitesse réelle.",
        "Examiner courant, couple et vibration de l'entraînement.",
        "Vérifier les alarmes variateur et l'accumulation matière avant toute intervention.",
    ],
    "spillage": [
        "Inspecter la zone de transfert par la branche vision.",
        "Comparer débit pesé, flux visuel utile et évolution du stock.",
        "Demander une vérification terrain de la zone de déversement.",
    ],
    "unstable_feed": [
        "Analyser la variabilité du débit et du courant sur plusieurs fenêtres.",
        "Comparer la consigne doseur à la réponse réelle.",
        "Vérifier la régularité d'alimentation et la qualité matière avec l'opérateur.",
    ],
}

DISPLAY = {
    "normal": "alimentation stable",
    "weighing_drift": "dérive de pesage probable",
    "hopper_bridging": "pontage de trémie probable",
    "conveyor_blockage": "bourrage convoyeur probable",
    "spillage": "déversement probable",
    "unstable_feed": "alimentation instable",
}

KEY_EVIDENCE = [
    "measured_mass_flow_tph",
    "visual_flow_proxy_tph",
    "flow_disagreement_ratio",
    "belt_speed_command_mps",
    "belt_speed_mps",
    "speed_ratio",
    "hopper_level_pct",
    "hopper_level_rate_pct_min",
    "motor_current_a",
    "motor_load_ratio",
    "motor_torque_pct",
    "vibration_mm_s",
    "flow_cv_60s",
    "motor_current_cv_60s",
    "visual_accumulation_pct",
    "visual_spillage_pct",
    "camera_quality",
]


def round_value(v):
    return round(float(v), 4)


def make_output(label: str, evidence: list[str], tool: str, steps: list[str]) -> str:
    why = " ".join(evidence[:3]) if evidence else "Les sources disponibles restent globalement cohérentes."
    return (
        f"Diagnostic analytique reçu : {DISPLAY[label]}. "
        f"Pourquoi : {why} "
        f"Test guidé recommandé : {tool}. "
        "Vérifications : " + " ".join(f"{i+1}) {step}" for i, step in enumerate(steps)) + " "
        "FLOWTRUST reste en lecture seule : la décision et toute intervention restent sous la responsabilité de l'opérateur et des procédures du site."
    )


def build_row(label: str, rng: np.random.Generator, rng_py: random.Random):
    x = make_synthetic_sample(label, rng)
    rules = physical_rules(x)
    tool = TOOL_MAP[label]
    steps = list(VERIFICATION_STEPS[label])
    rng_py.shuffle(steps)
    # Keep the technical sequence deterministic for safety-critical labels where order matters.
    if label in {"conveyor_blockage", "hopper_bridging"}:
        steps = VERIFICATION_STEPS[label]
    payload = {
        "mode": "advisory_read_only",
        "diagnostic_engine": label,
        "evidence": {k: round_value(x[k]) for k in KEY_EVIDENCE},
        "physics_evidence": rules,
        "available_tools": ["sensor_test", "camera_test", "drive_test", "coherence_test", "observability_test"],
        "request": rng_py.choice([
            "Explique le diagnostic et indique le prochain test utile.",
            "Que dois-je vérifier maintenant et pourquoi ?",
            "Aide-moi à comprendre les preuves et propose une vérification non intrusive.",
            "Quel test guidé lancer ensuite ?",
        ]),
    }
    return {"input": payload, "output": make_output(label, rules, tool, steps)}


def make_unknown_row(rng_py: random.Random):
    failure = rng_py.choice(["camera_and_weigh_missing", "desynchronized_sources", "two_bad_instruments", "out_of_domain_scene"])
    payload = {
        "mode": "advisory_read_only",
        "diagnostic_engine": "unknown",
        "abstained": True,
        "observability_failure": failure,
        "available_tools": ["sensor_test", "camera_test", "drive_test", "coherence_test", "observability_test"],
        "request": rng_py.choice([
            "Peux-tu conclure ?",
            "Quel est le défaut ?",
            "Que dois-je faire ensuite ?",
            "Explique pourquoi FLOWTRUST s'abstient.",
        ]),
    }
    output = (
        "FLOWTRUST ne doit pas conclure avec les preuves actuelles. "
        f"Cause d'abstention : {failure}. "
        "Lancer d'abord observability_test, puis tester ou rétablir la source signalée. "
        "Aucune valeur manquante ne doit être inventée et aucune commande machine n'est autorisée."
    )
    return {"input": payload, "output": output}


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("data/t01/operator_sft"))
    ap.add_argument("--per-class", type=int, default=1800)
    ap.add_argument("--unknown", type=int, default=1800)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    rng_py = random.Random(args.seed)
    rows = []
    for label in CLASSES:
        rows.extend(build_row(label, rng, rng_py) for _ in range(args.per_class))
    rows.extend(make_unknown_row(rng_py) for _ in range(args.unknown))
    rng_py.shuffle(rows)

    n = len(rows)
    n_train = int(n * 0.80)
    n_val = int(n * 0.10)
    train = rows[:n_train]
    val = rows[n_train:n_train+n_val]
    test = rows[n_train+n_val:]
    write_jsonl(args.outdir / "train.jsonl", train)
    write_jsonl(args.outdir / "validation.jsonl", val)
    write_jsonl(args.outdir / "closed_test.jsonl", test)

    meta = {
        "run_id": "FLOWTRUST-V2-T01-E-DATA-20260812",
        "seed": args.seed,
        "generator": "flowtrust_core physical synthetic truth + deterministic safety policy",
        "rows": {"train": len(train), "validation": len(val), "closed_test": len(test), "total": n},
        "warning": "This corpus teaches evidence-grounded behavior and tool selection. External maintenance corpora are used through RAG/domain adaptation separately; they are not treated as plant truth."
    }
    (args.outdir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
