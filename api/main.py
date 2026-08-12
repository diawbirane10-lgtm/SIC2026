from pathlib import Path
from typing import Dict

import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest, RandomForestClassifier

from flowtrust_core import FEATURE_NAMES, generate_dataset, observability_gate, operator_recommendation, physical_rules
from fusion_trust import FUSION_VERSION, fuse_multimodal_evidence

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
app = FastAPI(title="FLOWTRUST-AFR", version="0.3.0", docs_url=None, redoc_url=None, openapi_url=None)


class Payload(BaseModel):
    features: Dict[str, float]


_cache = {}


def _build_embedded_snapshot():
    """Build a compact deterministic SIL snapshot when binary artifacts are absent.

    This keeps the Vercel demo self-contained. It is a public/SIL demonstrator
    snapshot, not a model trained on SOCOCIM plant data.
    """
    X, y = generate_dataset(samples_per_class=360, seed=2026)
    rf = RandomForestClassifier(
        n_estimators=140,
        max_depth=14,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=2026,
        n_jobs=-1,
    ).fit(X, y)
    iso = IsolationForest(
        n_estimators=120,
        contamination=0.04,
        random_state=2026,
        n_jobs=-1,
    ).fit(X)
    return rf, iso, "embedded_sil_snapshot"


def load_models():
    if _cache:
        return _cache

    rf_path = MODELS / "afr_rf_diagnostic_v1.joblib"
    ood_path = MODELS / "afr_isolation_known_domain_v1.joblib"
    if rf_path.exists() and ood_path.exists():
        _cache["rf"] = joblib.load(rf_path)["model"]
        _cache["ood"] = joblib.load(ood_path)["model"]
        _cache["origin"] = "versioned_joblib"
    else:
        rf, iso, origin = _build_embedded_snapshot()
        _cache["rf"] = rf
        _cache["ood"] = iso
        _cache["origin"] = origin
    return _cache


def _safe_unknown(evidence, confidence=0.0, fusion=None):
    return {
        "diagnostic": "unknown",
        "confidence": float(confidence),
        "abstained": True,
        "evidence": list(evidence),
        "recommendation": operator_recommendation("unknown"),
        "fusion": fusion,
        "fusion_version": FUSION_VERSION,
        "automatic_control_allowed": False,
    }


@app.get("/api/health")
def health():
    models = load_models()
    return {
        "status": "ok",
        "version": "0.3.0",
        "mode": "advisory_read_only",
        "automatic_control_allowed": False,
        "model_id": "flowtrust-t02-v1",
        "fusion_version": FUSION_VERSION,
        "model_origin": models["origin"],
        "training_strategy": "hybrid_traced_sil_public_auxiliary",
    }


@app.post("/api/diagnose")
def diagnose(payload: Payload):
    x = payload.features
    ok, gate_evidence = observability_gate(x)
    vector = np.asarray([[float(x.get(feature, np.nan)) for feature in FEATURE_NAMES]], dtype=float)
    missing = float(np.isnan(vector).mean())

    if missing > 0.20 or not ok:
        return _safe_unknown(gate_evidence + [f"Missing fraction={missing:.1%}"])

    if np.isnan(vector).any():
        vector = np.nan_to_num(vector, nan=0.0)

    models = load_models()
    rf = models["rf"]
    iso = models["ood"]

    if iso.predict(vector)[0] < 0:
        return _safe_unknown(["Point hors enveloppe connue selon IsolationForest."])

    probability_vector = rf.predict_proba(vector)[0]
    model_probabilities = {
        str(label): float(probability)
        for label, probability in zip(rf.classes_, probability_vector)
    }

    fusion = fuse_multimodal_evidence(x, model_probabilities)
    evidence = physical_rules(x)

    if fusion["abstained"]:
        evidence.extend(fusion["abstention_reasons"])
        return _safe_unknown(evidence, confidence=fusion["confidence"], fusion=fusion)

    label = str(fusion["diagnostic"])
    modality_summary = []
    for name, details in fusion["modalities"].items():
        if details["active"]:
            modality_summary.append(
                f"{name}: vote={details['vote']}, support={details['strength']:.2f}, fiabilite={details['reliability']:.2f}"
            )
    evidence.extend(modality_summary)

    return {
        "diagnostic": label,
        "confidence": float(fusion["confidence"]),
        "abstained": False,
        "evidence": evidence,
        "recommendation": operator_recommendation(label),
        "fusion": fusion,
        "fusion_version": FUSION_VERSION,
        "model_origin": models["origin"],
        "automatic_control_allowed": False,
    }
