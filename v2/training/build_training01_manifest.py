from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_REGISTRY = ROOT / "v2" / "config" / "data_registry.json"
SCALE_REGISTRY = ROOT / "v2" / "config" / "scale_sources.json"
EXPERIMENTS = ROOT / "v2" / "config" / "training_01.json"
OUT = ROOT / "reports" / "t01"


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_text(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def is_training_ready(dataset: dict) -> bool:
    license_text = str(dataset.get("license", "")).lower()
    verified = dataset.get("verified")
    blocked_terms = ("verify", "pending", "non-commercial", "unknown")
    if any(term in license_text for term in blocked_terms):
        return False
    return verified is True or verified in {"repo_verified", "benchmark_repo_verified"}


def main():
    data_registry = read_json(DATA_REGISTRY)
    scale_registry = read_json(SCALE_REGISTRY)
    experiments = read_json(EXPERIMENTS)
    by_id = {d["id"]: d for d in data_registry["datasets"]}

    manifest = {
        "run_id": experiments["run_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_hashes": {
            "data_registry": sha256_text(data_registry),
            "scale_sources": sha256_text(scale_registry),
            "experiments": sha256_text(experiments),
        },
        "experiments": [],
        "blocked_sources": [],
        "bootstrap_notes": {
            "T01-A0": "CoalAD conveyor frames plus COCO hard negatives; bootstrap only, not final industrial validation.",
            "T01-F0": "Real UCI hydraulic sensor cycles with controlled synthetic sensor-integrity corruptions; group split by physical cycle."
        }
    }

    blocked = {}
    for exp in experiments["experiments"]:
        ready, pending = [], []
        for dataset_id in exp.get("datasets", []):
            ds = by_id[dataset_id]
            record = {
                "id": dataset_id,
                "source": ds.get("source"),
                "doi": ds.get("doi"),
                "license": ds.get("license"),
                "verified": ds.get("verified"),
            }
            if is_training_ready(ds):
                ready.append(record)
            else:
                pending.append(record)
                blocked[dataset_id] = record
        manifest["experiments"].append({
            "id": exp["id"],
            "name": exp["name"],
            "model": exp["model"],
            "training_ready_sources": ready,
            "license_or_terms_review_required": pending,
            "gate": exp["gate"],
        })

    manifest["blocked_sources"] = list(blocked.values())
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "data_provenance.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path}")
    for exp in manifest["experiments"]:
        print(f"{exp['id']}: ready={len(exp['training_ready_sources'])}, pending={len(exp['license_or_terms_review_required'])}")
    if manifest["blocked_sources"]:
        print("Blocked/pending sources are excluded until terms are reviewed:")
        for ds in manifest["blocked_sources"]:
            print(f" - {ds['id']}: {ds['license']}")


if __name__ == "__main__":
    main()
