from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Tuple

import numpy as np

from flowtrust_core import CLASSES

FUSION_VERSION = "t02-v1"
MODALITIES = ("process", "electromechanical", "vision")


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _high(value: float, threshold: float, width: float) -> float:
    width = max(float(width), 1e-9)
    z = np.clip((float(value) - float(threshold)) / width, -60.0, 60.0)
    return float(1.0 / (1.0 + np.exp(-z)))


def _low(value: float, threshold: float, width: float) -> float:
    return 1.0 - _high(value, threshold, width)


def _mean_quality(x: Mapping[str, float], keys: Iterable[str]) -> float:
    values = [_clip01(_finite(x.get(key, 0.0))) for key in keys]
    return float(np.mean(values)) if values else 0.0


def _completeness(x: Mapping[str, float], keys: Iterable[str]) -> float:
    keys = list(keys)
    if not keys:
        return 0.0
    present = 0
    for key in keys:
        try:
            value = float(x.get(key, np.nan))
        except (TypeError, ValueError):
            value = np.nan
        present += int(np.isfinite(value))
    return present / len(keys)


def _source_reliabilities(x: Mapping[str, float]) -> Dict[str, float]:
    process_fields = (
        "measured_mass_flow_tph",
        "hopper_level_pct",
        "hopper_level_rate_pct_min",
        "mass_balance_residual_abs_pct",
        "flow_cv_60s",
    )
    electro_fields = (
        "speed_ratio",
        "motor_current_a",
        "motor_load_ratio",
        "motor_torque_pct",
        "vibration_mm_s",
        "motor_current_cv_60s",
    )
    vision_fields = (
        "visual_flow_proxy_tph",
        "visual_accumulation_pct",
        "visual_spillage_pct",
    )

    process = _mean_quality(x, ("weigh_signal_quality", "level_signal_quality"))
    process *= _completeness(x, process_fields)

    electromechanical = _mean_quality(x, ("speed_signal_quality", "electrical_signal_quality"))
    electromechanical *= _completeness(x, electro_fields)

    camera_connected = 1.0 if _finite(x.get("camera_connected", 0.0)) >= 0.5 else 0.0
    vision = _clip01(_finite(x.get("camera_quality", 0.0))) * camera_connected
    vision *= _completeness(x, vision_fields)

    return {
        "process": _clip01(process),
        "electromechanical": _clip01(electromechanical),
        "vision": _clip01(vision),
    }


def _blank_scores() -> Dict[str, float]:
    return {label: 0.02 for label in CLASSES}


def _modality_scores(x: Mapping[str, float]) -> Dict[str, Dict[str, float]]:
    flow = _finite(x.get("measured_mass_flow_tph"))
    hopper = _finite(x.get("hopper_level_pct"))
    hopper_rate = _finite(x.get("hopper_level_rate_pct_min"))
    residual = _finite(x.get("mass_balance_residual_abs_pct"))
    flow_cv = _finite(x.get("flow_cv_60s"))

    speed_ratio = _finite(x.get("speed_ratio"), 1.0)
    motor_load = _finite(x.get("motor_load_ratio"))
    current = _finite(x.get("motor_current_a"))
    torque = _finite(x.get("motor_torque_pct"))
    vibration = _finite(x.get("vibration_mm_s"))
    current_cv = _finite(x.get("motor_current_cv_60s"))

    visual_flow = _finite(x.get("visual_flow_proxy_tph"))
    accumulation = _finite(x.get("visual_accumulation_pct"))
    spillage = _finite(x.get("visual_spillage_pct"))
    disagreement = _finite(x.get("flow_disagreement_ratio"))

    process = _blank_scores()
    process["normal"] = (
        0.55 * _low(flow_cv, 0.14, 0.035)
        + 0.25 * _low(residual, 12.0, 4.0)
        + 0.20 * (1.0 - _high(hopper, 82.0, 4.0))
    )
    process["hopper_bridging"] = (
        0.50 * _high(hopper, 80.0, 4.0)
        + 0.35 * _low(flow, 42.0, 7.0)
        + 0.15 * _low(abs(hopper_rate), 1.0, 0.4)
    )
    process["unstable_feed"] = (
        0.72 * _high(flow_cv, 0.17, 0.04)
        + 0.18 * _high(abs(hopper_rate), 1.8, 0.6)
        + 0.10 * _high(residual, 15.0, 5.0)
    )
    process["conveyor_blockage"] = (
        0.50 * _low(flow, 35.0, 7.0)
        + 0.25 * _high(hopper, 72.0, 6.0)
        + 0.25 * _high(residual, 15.0, 5.0)
    )
    process["weighing_drift"] = (
        0.45 * _high(residual, 18.0, 5.0)
        + 0.30 * _low(flow, 52.0, 8.0)
        + 0.25 * _high(abs(hopper_rate), 1.6, 0.5)
    )
    process["spillage"] = (
        0.35 * _high(residual, 18.0, 5.0)
        + 0.25 * _high(abs(hopper_rate), 1.6, 0.5)
        + 0.10
    )

    electromechanical = _blank_scores()
    electromechanical["normal"] = (
        0.40 * _high(speed_ratio, 0.80, 0.06)
        + 0.25 * _low(motor_load, 0.88, 0.05)
        + 0.20 * _low(current_cv, 0.10, 0.03)
        + 0.15 * _low(vibration, 3.6, 0.6)
    )
    electromechanical["conveyor_blockage"] = (
        0.30 * _low(speed_ratio, 0.62, 0.07)
        + 0.25 * _high(motor_load, 0.90, 0.05)
        + 0.15 * _high(current, 105.0, 8.0)
        + 0.15 * _high(torque, 92.0, 6.0)
        + 0.15 * _high(vibration, 4.2, 0.7)
    )
    electromechanical["unstable_feed"] = (
        0.45 * _high(current_cv, 0.12, 0.03)
        + 0.30 * _high(vibration, 3.6, 0.6)
        + 0.15 * _high(motor_load, 0.82, 0.07)
        + 0.10 * _high(current, 98.0, 8.0)
    )
    # These classes are intentionally weak in the electromechanical channel.
    # A healthy motor does not invalidate spillage or a weighing problem.
    electromechanical["hopper_bridging"] = 0.20 * _low(motor_load, 0.82, 0.08) + 0.15 * _high(speed_ratio, 0.82, 0.06)
    electromechanical["weighing_drift"] = 0.25 * _high(speed_ratio, 0.82, 0.06) + 0.20 * _low(current_cv, 0.10, 0.03)
    electromechanical["spillage"] = 0.20 * _high(speed_ratio, 0.82, 0.06) + 0.10 * _low(current_cv, 0.10, 0.03)

    vision = _blank_scores()
    vision["normal"] = (
        0.35 * _high(visual_flow, 48.0, 8.0)
        + 0.30 * _low(accumulation, 20.0, 6.0)
        + 0.30 * _low(spillage, 10.0, 4.0)
    )
    vision["spillage"] = (
        0.70 * _high(spillage, 22.0, 6.0)
        + 0.20 * _high(disagreement, 0.16, 0.05)
        + 0.10 * _low(accumulation, 50.0, 10.0)
    )
    vision["conveyor_blockage"] = (
        0.45 * _high(accumulation, 58.0, 8.0)
        + 0.35 * _low(visual_flow, 36.0, 7.0)
        + 0.20 * _high(disagreement, 0.12, 0.05)
    )
    vision["hopper_bridging"] = (
        0.40 * _high(accumulation, 30.0, 8.0)
        + 0.35 * _low(visual_flow, 42.0, 8.0)
        + 0.15 * _low(spillage, 12.0, 4.0)
    )
    vision["weighing_drift"] = (
        0.35 * _high(visual_flow, 52.0, 8.0)
        + 0.50 * _high(disagreement, 0.18, 0.05)
        + 0.10 * _low(spillage, 12.0, 4.0)
    )
    # No temporal visual-CV feature exists yet, therefore this channel remains weak.
    vision["unstable_feed"] = 0.15 * _high(disagreement, 0.10, 0.04) + 0.10

    for scores in (process, electromechanical, vision):
        for label in CLASSES:
            scores[label] = _clip01(scores[label])

    return {
        "process": process,
        "electromechanical": electromechanical,
        "vision": vision,
    }


def _cross_source_support(x: Mapping[str, float]) -> Dict[str, float]:
    flow = _finite(x.get("measured_mass_flow_tph"))
    visual_flow = _finite(x.get("visual_flow_proxy_tph"))
    disagreement = _finite(x.get("flow_disagreement_ratio"))
    spillage = _finite(x.get("visual_spillage_pct"))
    accumulation = _finite(x.get("visual_accumulation_pct"))
    speed_ratio = _finite(x.get("speed_ratio"), 1.0)
    motor_load = _finite(x.get("motor_load_ratio"))
    hopper = _finite(x.get("hopper_level_pct"))
    flow_cv = _finite(x.get("flow_cv_60s"))
    current_cv = _finite(x.get("motor_current_cv_60s"))

    support = {label: 0.0 for label in CLASSES}
    support["weighing_drift"] = (
        0.45
        * _high(disagreement, 0.20, 0.05)
        * _high(visual_flow, 50.0, 8.0)
        * _low(flow, 55.0, 8.0)
    )
    support["spillage"] = 0.40 * _high(disagreement, 0.16, 0.05) * _high(spillage, 20.0, 5.0)
    support["conveyor_blockage"] = (
        0.35 * _low(speed_ratio, 0.60, 0.08) * _high(accumulation, 50.0, 10.0) * _high(motor_load, 0.88, 0.06)
    )
    support["hopper_bridging"] = 0.30 * _high(hopper, 80.0, 5.0) * _low(flow, 40.0, 8.0) * _low(visual_flow, 45.0, 8.0)
    support["unstable_feed"] = 0.25 * _high(flow_cv, 0.17, 0.04) * _high(current_cv, 0.12, 0.03)
    return support


def _normalise_model_probabilities(model_probabilities: Mapping[str, float] | None) -> Dict[str, float]:
    if not model_probabilities:
        return {label: 0.0 for label in CLASSES}
    values = {label: max(_finite(model_probabilities.get(label, 0.0)), 0.0) for label in CLASSES}
    total = sum(values.values())
    if total <= 0.0:
        return {label: 0.0 for label in CLASSES}
    return {label: values[label] / total for label in CLASSES}


def _top(scores: Mapping[str, float]) -> Tuple[str, float, str, float]:
    ordered = sorted(CLASSES, key=lambda label: float(scores.get(label, 0.0)), reverse=True)
    first, second = ordered[0], ordered[1]
    return first, float(scores[first]), second, float(scores[second])


def fuse_multimodal_evidence(
    x: Mapping[str, float],
    model_probabilities: Mapping[str, float] | None = None,
) -> Dict[str, object]:
    """Fuse process, electromechanical and vision evidence with fail-safe abstention.

    T02 deliberately separates source reliability from diagnostic support.  A source
    with poor quality or incomplete inputs contributes less or is excluded.  The RF
    output, when supplied, is a supporting prior and never bypasses contradiction,
    observability or support gates.
    """

    reliabilities = _source_reliabilities(x)
    scores = _modality_scores(x)
    active = [name for name in MODALITIES if reliabilities[name] >= 0.35]
    reasons: List[str] = []

    modality_details: Dict[str, Dict[str, object]] = {}
    for name in MODALITIES:
        vote, strength, _, _ = _top(scores[name])
        modality_details[name] = {
            "reliability": round(reliabilities[name], 6),
            "active": name in active,
            "vote": vote,
            "strength": round(strength, 6),
            "scores": {label: round(scores[name][label], 6) for label in CLASSES},
        }

    if len(active) < 2:
        reasons.append("Moins de deux modalites independantes sont suffisamment fiables.")
        return {
            "version": FUSION_VERSION,
            "diagnostic": "unknown",
            "candidate": "unknown",
            "confidence": 0.0,
            "agreement": 0.0,
            "margin": 0.0,
            "abstained": True,
            "abstention_reasons": reasons,
            "active_modalities": active,
            "modalities": modality_details,
            "fused_scores": {label: 0.0 for label in CLASSES},
            "model_top": None,
            "model_confidence": 0.0,
        }

    total_reliability = sum(reliabilities[name] for name in active)
    heuristic = {
        label: sum(reliabilities[name] * scores[name][label] for name in active) / total_reliability
        for label in CLASSES
    }
    cross_support = _cross_source_support(x)
    heuristic = {label: _clip01(heuristic[label] + cross_support[label]) for label in CLASSES}

    model = _normalise_model_probabilities(model_probabilities)
    has_model = any(value > 0.0 for value in model.values())
    if has_model:
        # The interpretable modalities remain the majority contribution.
        fused = {label: 0.58 * heuristic[label] + 0.42 * model[label] for label in CLASSES}
    else:
        fused = dict(heuristic)

    candidate, confidence, second, second_score = _top(fused)
    margin = confidence - second_score
    agreement = sum(reliabilities[name] * scores[name][candidate] for name in active) / total_reliability

    expected = {
        "conveyor_blockage": {"process", "electromechanical", "vision"},
        "hopper_bridging": {"process", "vision"},
        "spillage": {"vision"},
        "unstable_feed": {"process", "electromechanical"},
        "weighing_drift": {"process", "vision"},
        "normal": {"process", "electromechanical", "vision"},
    }[candidate]
    expected_active = [name for name in active if name in expected]
    supporting = [name for name in expected_active if scores[name][candidate] >= 0.48]

    if candidate == "spillage":
        support_ok = "vision" in supporting and scores["vision"][candidate] >= 0.62
    elif expected_active:
        support_weight = sum(reliabilities[name] for name in supporting)
        expected_weight = sum(reliabilities[name] for name in expected_active)
        support_ok = support_weight >= 0.42 * expected_weight
    else:
        support_ok = False

    if not support_ok:
        reasons.append("Le candidat n'est pas suffisamment soutenu par les modalites pertinentes.")

    # Only a materially stronger opposing anomaly is considered a contradiction.
    # This avoids treating an unaffected motor as proof against a visually detected spill.
    opposing: List[Tuple[str, str, float, float]] = []
    for name in active:
        vote, strength, _, _ = _top(scores[name])
        candidate_strength = scores[name][candidate]
        if (
            vote != "normal"
            and vote != candidate
            and strength >= 0.68
            and strength - candidate_strength >= 0.18
        ):
            opposing.append((name, vote, strength, candidate_strength))
    if len(opposing) >= 2 or len({item[1] for item in opposing}) >= 2:
        reasons.append("Des modalites fiables portent des diagnostics anormaux contradictoires.")

    heuristic_top, heuristic_confidence, _, _ = _top(heuristic)
    model_top = None
    model_confidence = 0.0
    if has_model:
        model_top, model_confidence, _, _ = _top(model)
        if (
            model_top != heuristic_top
            and model_confidence >= 0.78
            and heuristic_confidence >= 0.78
            and heuristic[heuristic_top] - heuristic.get(model_top, 0.0) >= 0.22
        ):
            reasons.append("Le modele statistique et les evidences physiques fiables se contredisent fortement.")

    disagreement = _finite(x.get("flow_disagreement_ratio"))
    if (
        disagreement > 0.38
        and candidate not in {"weighing_drift", "spillage", "conveyor_blockage"}
        and _finite(x.get("weigh_signal_quality")) >= 0.60
        and _finite(x.get("camera_quality")) >= 0.60
        and _finite(x.get("camera_connected")) >= 0.5
    ):
        reasons.append("Desaccord debit/vision eleve sans mecanisme explicatif coherent.")

    if confidence < 0.52:
        reasons.append("Confiance fusionnee insuffisante.")
    if margin < 0.10:
        reasons.append("Marge insuffisante entre les deux diagnostics les plus probables.")

    abstained = bool(reasons)
    diagnostic = "unknown" if abstained else candidate

    return {
        "version": FUSION_VERSION,
        "diagnostic": diagnostic,
        "candidate": candidate,
        "confidence": round(float(confidence), 6),
        "agreement": round(float(agreement), 6),
        "margin": round(float(margin), 6),
        "abstained": abstained,
        "abstention_reasons": reasons,
        "active_modalities": active,
        "modalities": modality_details,
        "fused_scores": {label: round(float(fused[label]), 6) for label in CLASSES},
        "model_top": model_top,
        "model_confidence": round(float(model_confidence), 6),
    }
