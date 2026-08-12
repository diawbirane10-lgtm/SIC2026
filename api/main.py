from pathlib import Path
from typing import Dict

import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest, RandomForestClassifier

from flowtrust_core import CLASSES, FEATURE_NAMES, generate_dataset, observability_gate, operator_recommendation, physical_rules

FUSION_VERSION = "t02-v1"
ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
app = FastAPI(title="FLOWTRUST-AFR", version="0.3.0", docs_url=None, redoc_url=None, openapi_url=None)


class Payload(BaseModel):
    features: Dict[str, float]


_cache = {}


def _clip01(x):
    return float(np.clip(float(x), 0.0, 1.0))


def _sigmoid_high(value, threshold, width):
    z = np.clip((float(value) - float(threshold)) / max(float(width), 1e-9), -60, 60)
    return float(1.0 / (1.0 + np.exp(-z)))


def _low(value, threshold, width):
    return 1.0 - _sigmoid_high(value, threshold, width)


def _build_embedded_snapshot():
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
        _cache.update(rf=rf, ood=iso, origin=origin)
    return _cache


def _blank():
    return {label: 0.02 for label in CLASSES}


def _reliabilities(x):
    process = np.mean([_clip01(x.get("weigh_signal_quality", 0)), _clip01(x.get("level_signal_quality", 0))])
    electro = np.mean([_clip01(x.get("speed_signal_quality", 0)), _clip01(x.get("electrical_signal_quality", 0))])
    vision = _clip01(x.get("camera_quality", 0)) if float(x.get("camera_connected", 0)) >= 0.5 else 0.0
    return {"process": float(process), "electromechanical": float(electro), "vision": float(vision)}


def _modality_scores(x):
    flow = float(x.get("measured_mass_flow_tph", 0)); visual = float(x.get("visual_flow_proxy_tph", 0))
    hopper = float(x.get("hopper_level_pct", 0)); hopper_rate = float(x.get("hopper_level_rate_pct_min", 0))
    residual = float(x.get("mass_balance_residual_abs_pct", 0)); flow_cv = float(x.get("flow_cv_60s", 0))
    speed_ratio = float(x.get("speed_ratio", 1)); current = float(x.get("motor_current_a", 0))
    load = float(x.get("motor_load_ratio", 0)); torque = float(x.get("motor_torque_pct", 0))
    vibration = float(x.get("vibration_mm_s", 0)); current_cv = float(x.get("motor_current_cv_60s", 0))
    accumulation = float(x.get("visual_accumulation_pct", 0)); spillage = float(x.get("visual_spillage_pct", 0))
    disagreement = float(x.get("flow_disagreement_ratio", 0))

    p = _blank(); e = _blank(); v = _blank()
    p["normal"] = .55*_low(flow_cv,.14,.035)+.25*_low(residual,12,4)+.20*_low(hopper,82,4)
    p["hopper_bridging"] = .50*_sigmoid_high(hopper,80,4)+.35*_low(flow,42,7)+.15*_low(abs(hopper_rate),1,.4)
    p["unstable_feed"] = .72*_sigmoid_high(flow_cv,.17,.04)+.18*_sigmoid_high(abs(hopper_rate),1.8,.6)+.10*_sigmoid_high(residual,15,5)
    p["conveyor_blockage"] = .50*_low(flow,35,7)+.25*_sigmoid_high(hopper,72,6)+.25*_sigmoid_high(residual,15,5)
    p["weighing_drift"] = .45*_sigmoid_high(residual,18,5)+.30*_low(flow,52,8)+.25*_sigmoid_high(abs(hopper_rate),1.6,.5)
    p["spillage"] = .35*_sigmoid_high(residual,18,5)+.25*_sigmoid_high(abs(hopper_rate),1.6,.5)+.10

    e["normal"] = .40*_sigmoid_high(speed_ratio,.80,.06)+.25*_low(load,.88,.05)+.20*_low(current_cv,.10,.03)+.15*_low(vibration,3.6,.6)
    e["conveyor_blockage"] = .30*_low(speed_ratio,.62,.07)+.25*_sigmoid_high(load,.90,.05)+.15*_sigmoid_high(current,105,8)+.15*_sigmoid_high(torque,92,6)+.15*_sigmoid_high(vibration,4.2,.7)
    e["unstable_feed"] = .45*_sigmoid_high(current_cv,.12,.03)+.30*_sigmoid_high(vibration,3.6,.6)+.15*_sigmoid_high(load,.82,.07)+.10*_sigmoid_high(current,98,8)
    e["hopper_bridging"] = .20*_low(load,.82,.08)+.15*_sigmoid_high(speed_ratio,.82,.06)
    e["weighing_drift"] = .25*_sigmoid_high(speed_ratio,.82,.06)+.20*_low(current_cv,.10,.03)
    e["spillage"] = .20*_sigmoid_high(speed_ratio,.82,.06)+.10*_low(current_cv,.10,.03)

    v["normal"] = .35*_sigmoid_high(visual,48,8)+.30*_low(accumulation,20,6)+.30*_low(spillage,10,4)
    v["spillage"] = .70*_sigmoid_high(spillage,22,6)+.20*_sigmoid_high(disagreement,.16,.05)+.10*_low(accumulation,50,10)
    v["conveyor_blockage"] = .45*_sigmoid_high(accumulation,58,8)+.35*_low(visual,36,7)+.20*_sigmoid_high(disagreement,.12,.05)
    v["hopper_bridging"] = .40*_sigmoid_high(accumulation,30,8)+.35*_low(visual,42,8)+.15*_low(spillage,12,4)
    v["weighing_drift"] = .35*_sigmoid_high(visual,52,8)+.50*_sigmoid_high(disagreement,.18,.05)+.10*_low(spillage,12,4)
    v["unstable_feed"] = .15*_sigmoid_high(disagreement,.10,.04)+.10

    for scores in (p,e,v):
        for label in CLASSES:
            scores[label] = _clip01(scores[label])
    return {"process":p, "electromechanical":e, "vision":v}


def _fuse(x, rf_probs):
    reliabilities = _reliabilities(x)
    scores = _modality_scores(x)
    active = [name for name, rel in reliabilities.items() if rel >= .35]
    details = {}
    for name, sc in scores.items():
        vote = max(sc, key=sc.get)
        details[name] = {"reliability":reliabilities[name], "active":name in active, "vote":vote, "strength":float(sc[vote])}

    if len(active) < 2:
        return {"version":FUSION_VERSION,"diagnostic":"unknown","confidence":0.0,"abstained":True,"abstention_reasons":["Moins de deux modalités indépendantes sont suffisamment fiables."],"active_modalities":active,"modalities":details,"fused_scores":{label:0.0 for label in CLASSES},"consensus":0.0,"margin":0.0}

    total_rel = sum(reliabilities[n] for n in active)
    fused = {label:0.0 for label in CLASSES}
    for label in CLASSES:
        modality_part = sum(reliabilities[n]*scores[n][label] for n in active)/max(total_rel,1e-9)
        fused[label] = .78*modality_part + .22*float(rf_probs.get(label,0.0))
    total = sum(fused.values()) or 1.0
    fused = {k:v/total for k,v in fused.items()}
    ordered = sorted(CLASSES,key=lambda k:fused[k],reverse=True)
    candidate, runner = ordered[0], ordered[1]
    margin = fused[candidate]-fused[runner]
    supporting = [n for n in active if details[n]["vote"] == candidate and details[n]["strength"] >= .30]
    consensus = sum(reliabilities[n] for n in supporting)/max(total_rel,1e-9)
    strong_votes = [details[n]["vote"] for n in active if details[n]["strength"] >= .45]
    contradiction = len(set(strong_votes)) == len(strong_votes) and len(strong_votes) >= 3
    reasons=[]
    if fused[candidate] < .38: reasons.append("Support fusionné insuffisant.")
    if margin < .055: reasons.append("Marge trop faible entre les deux hypothèses principales.")
    if candidate != "normal" and consensus < .34: reasons.append("Le défaut n'est pas soutenu par assez de modalités indépendantes.")
    if contradiction: reasons.append("Contradiction forte entre les modalités actives.")
    abstained = bool(reasons)
    confidence = 0.0 if abstained else _clip01(.62*fused[candidate]+.38*consensus)
    return {"version":FUSION_VERSION,"diagnostic":"unknown" if abstained else candidate,"candidate":candidate,"confidence":confidence,"abstained":abstained,"abstention_reasons":reasons,"active_modalities":active,"modalities":details,"fused_scores":fused,"consensus":consensus,"margin":margin}


def _safe_unknown(evidence, confidence=0.0, fusion=None):
    return {"diagnostic":"unknown","confidence":float(confidence),"abstained":True,"evidence":list(evidence),"recommendation":operator_recommendation("unknown"),"fusion":fusion,"fusion_version":FUSION_VERSION,"automatic_control_allowed":False}


@app.get("/api/health")
def health():
    models = load_models()
    return {"status":"ok","version":"0.3.0","mode":"advisory_read_only","automatic_control_allowed":False,"model_id":"flowtrust-t02-v1","fusion_version":FUSION_VERSION,"model_origin":models["origin"],"training_strategy":"hybrid_traced_sil_public_auxiliary"}


@app.post("/api/diagnose")
def diagnose(payload: Payload):
    x = payload.features
    ok, gate_evidence = observability_gate(x)
    vector = np.asarray([[float(x.get(feature,np.nan)) for feature in FEATURE_NAMES]],dtype=float)
    missing = float(np.isnan(vector).mean())
    if missing > .20 or not ok:
        return _safe_unknown(gate_evidence+[f"Missing fraction={missing:.1%}"])
    if np.isnan(vector).any():
        vector = np.nan_to_num(vector,nan=0.0)

    models = load_models(); rf=models["rf"]; iso=models["ood"]
    if iso.predict(vector)[0] < 0:
        return _safe_unknown(["Point hors enveloppe connue selon IsolationForest."])

    probs = rf.predict_proba(vector)[0]
    rf_probs = {str(label):float(p) for label,p in zip(rf.classes_,probs)}
    fusion = _fuse(x,rf_probs)
    evidence = physical_rules(x)
    if fusion["abstained"]:
        evidence.extend(fusion["abstention_reasons"])
        return _safe_unknown(evidence,confidence=fusion["confidence"],fusion=fusion)

    label = str(fusion["diagnostic"])
    for name,details in fusion["modalities"].items():
        if details["active"]:
            evidence.append(f"{name}: vote={details['vote']}, support={details['strength']:.2f}, fiabilite={details['reliability']:.2f}")
    if not evidence:
        evidence.append("Aucune incohérence physique majeure détectée dans la fenêtre courante.")
    return {"diagnostic":label,"confidence":float(fusion["confidence"]),"abstained":False,"evidence":evidence,"recommendation":operator_recommendation(label),"fusion":fusion,"fusion_version":FUSION_VERSION,"model_origin":models["origin"],"automatic_control_allowed":False}
