import numpy as np

from flowtrust_core import CLASSES, make_synthetic_sample
from fusion_trust import FUSION_VERSION, fuse_multimodal_evidence


def _model_prior(label: str, confidence: float = 0.94):
    remainder = (1.0 - confidence) / (len(CLASSES) - 1)
    return {name: (confidence if name == label else remainder) for name in CLASSES}


def _sample(label: str, seed: int = 2026):
    return make_synthetic_sample(label, np.random.default_rng(seed))


def test_t02_clean_synthetic_has_zero_wrong_non_abstained_decisions():
    rng = np.random.default_rng(2026)
    wrong_non_abstained = 0
    accepted = 0
    total = 0

    for label in CLASSES:
        for _ in range(64):
            x = make_synthetic_sample(label, rng)
            decision = fuse_multimodal_evidence(x, _model_prior(label))
            total += 1
            if not decision["abstained"]:
                accepted += 1
                wrong_non_abstained += int(decision["diagnostic"] != label)

    assert wrong_non_abstained == 0
    assert accepted / total >= 0.70


def test_t02_survives_loss_of_one_modality_when_two_independent_sources_agree():
    x = _sample("conveyor_blockage", seed=11)
    x["camera_connected"] = 0.0
    x["camera_quality"] = 0.0

    decision = fuse_multimodal_evidence(x, _model_prior("conveyor_blockage"))

    assert decision["diagnostic"] == "conveyor_blockage"
    assert decision["abstained"] is False
    assert decision["active_modalities"] == ["process", "electromechanical"]


def test_t02_two_degraded_modalities_force_safe_abstention():
    x = _sample("conveyor_blockage", seed=12)
    x["weigh_signal_quality"] = 0.10
    x["level_signal_quality"] = 0.10
    x["camera_connected"] = 0.0
    x["camera_quality"] = 0.0

    decision = fuse_multimodal_evidence(x, _model_prior("conveyor_blockage"))

    assert decision["diagnostic"] == "unknown"
    assert decision["abstained"] is True
    assert len(decision["active_modalities"]) < 2
    assert any("deux modalites" in reason.lower() for reason in decision["abstention_reasons"])


def test_t02_strong_model_vs_physics_conflict_forces_abstention():
    x = _sample("conveyor_blockage", seed=13)

    decision = fuse_multimodal_evidence(x, _model_prior("spillage"))

    assert decision["diagnostic"] == "unknown"
    assert decision["abstained"] is True
    assert any("modele statistique" in reason.lower() for reason in decision["abstention_reasons"])


def test_t02_two_independent_abnormal_votes_in_conflict_force_abstention():
    x = _sample("normal", seed=14)

    # Electromechanical channel: strong blockage signature.
    x.update({
        "speed_ratio": 0.30,
        "motor_load_ratio": 1.08,
        "motor_current_a": 132.0,
        "motor_torque_pct": 112.0,
        "vibration_mm_s": 6.8,
        "motor_current_cv_60s": 0.04,
    })
    # Vision channel: strong spillage signature without accumulation.
    x.update({
        "visual_spillage_pct": 58.0,
        "visual_accumulation_pct": 3.0,
        "visual_flow_proxy_tph": 44.0,
        "flow_disagreement_ratio": 0.40,
    })

    decision = fuse_multimodal_evidence(x, _model_prior("normal"))

    assert decision["diagnostic"] == "unknown"
    assert decision["abstained"] is True
    assert any("contradictoires" in reason.lower() for reason in decision["abstention_reasons"])


def test_t02_unexplained_weigh_vs_vision_disagreement_abstains():
    x = _sample("normal", seed=15)
    x["visual_flow_proxy_tph"] = 15.0
    x["flow_disagreement_ratio"] = abs(x["measured_mass_flow_tph"] - 15.0) / 15.0
    x["visual_accumulation_pct"] = 3.0
    x["visual_spillage_pct"] = 1.0

    decision = fuse_multimodal_evidence(x, _model_prior("normal"))

    assert decision["diagnostic"] == "unknown"
    assert decision["abstained"] is True
    assert any("desaccord debit/vision" in reason.lower() for reason in decision["abstention_reasons"])


def test_t02_result_is_traceable_for_hmi_and_audit_log():
    decision = fuse_multimodal_evidence(_sample("spillage", seed=16), _model_prior("spillage"))

    assert decision["version"] == FUSION_VERSION
    assert set(decision["modalities"]) == {"process", "electromechanical", "vision"}
    assert set(decision["fused_scores"]) == set(CLASSES)
    for modality in decision["modalities"].values():
        assert 0.0 <= modality["reliability"] <= 1.0
        assert "vote" in modality
        assert "strength" in modality
