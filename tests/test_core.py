import numpy as np

from flowtrust_core import (
    CLASSES,
    FEATURE_NAMES,
    generate_dataset,
    observability_gate,
    operator_recommendation,
    physical_rules,
)


def _base():
    x = {k: 1.0 for k in FEATURE_NAMES}
    x.update({
        "speed_signal_quality": 0.99,
        "weigh_signal_quality": 0.99,
        "level_signal_quality": 0.99,
        "electrical_signal_quality": 0.99,
        "camera_quality": 0.99,
        "camera_connected": 1.0,
        "speed_ratio": 1.0,
        "motor_load_ratio": 0.7,
        "hopper_level_pct": 60.0,
        "measured_mass_flow_tph": 70.0,
        "flow_disagreement_ratio": 0.03,
        "visual_spillage_pct": 1.0,
        "flow_cv_60s": 0.04,
        "motor_current_cv_60s": 0.04,
    })
    return x


def test_dataset_is_reproducible_and_complete():
    x1, y1 = generate_dataset(samples_per_class=4, seed=2026)
    x2, y2 = generate_dataset(samples_per_class=4, seed=2026)
    assert x1.shape == (len(CLASSES) * 4, len(FEATURE_NAMES))
    assert np.array_equal(x1, x2)
    assert np.array_equal(y1, y2)
    assert set(y1) == set(CLASSES)


def test_observability_allows_good_sources():
    ok, evidence = observability_gate(_base())
    assert ok is True
    assert evidence == []


def test_observability_abstains_with_two_bad_instrument_sources():
    x = _base()
    x["speed_signal_quality"] = 0.1
    x["weigh_signal_quality"] = 0.1
    ok, evidence = observability_gate(x)
    assert ok is False
    assert evidence


def test_physical_rule_flags_blockage_signature():
    x = _base()
    x["speed_ratio"] = 0.3
    x["motor_load_ratio"] = 1.05
    evidence = physical_rules(x)
    assert any("bourrage" in item.lower() for item in evidence)


def test_physical_rule_flags_hopper_bridging_signature():
    x = _base()
    x["hopper_level_pct"] = 90.0
    x["measured_mass_flow_tph"] = 25.0
    evidence = physical_rules(x)
    assert any("pontage" in item.lower() for item in evidence)


def test_unknown_recommendation_never_commands_automatic_action():
    text = operator_recommendation("unknown").lower()
    assert "ne pas conclure" in text
    assert "verification" in text
