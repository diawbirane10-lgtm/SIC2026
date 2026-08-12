import numpy as np

from api.main import Payload, diagnose, health
from flowtrust_core import CLASSES, make_synthetic_sample


def test_health_exposes_t02_and_read_only_contract():
    result = health()
    assert result["version"] == "0.3.0"
    assert result["fusion_version"] == "t02-v1"
    assert result["mode"] == "advisory_read_only"
    assert result["automatic_control_allowed"] is False


def test_api_clean_synthetic_decisions_are_safe_and_traceable():
    rng = np.random.default_rng(2026)
    accepted = 0
    wrong_non_abstained = 0

    for label in CLASSES:
        for _ in range(8):
            features = make_synthetic_sample(label, rng)
            result = diagnose(Payload(features=features))

            assert result["automatic_control_allowed"] is False
            if result["fusion"] is not None:
                assert result["fusion"]["version"] == "t02-v1"

            if not result["abstained"]:
                accepted += 1
                wrong_non_abstained += int(result["diagnostic"] != label)
                assert result["fusion"] is not None
                assert len(result["fusion"]["active_modalities"]) >= 2

    assert wrong_non_abstained == 0
    assert accepted >= 24


def test_api_never_forces_diagnosis_when_observability_gate_fails():
    features = make_synthetic_sample("conveyor_blockage", np.random.default_rng(99))
    features["speed_signal_quality"] = 0.10
    features["weigh_signal_quality"] = 0.10

    result = diagnose(Payload(features=features))

    assert result["diagnostic"] == "unknown"
    assert result["abstained"] is True
    assert result["automatic_control_allowed"] is False


def test_api_missing_fraction_over_limit_abstains_before_model():
    features = make_synthetic_sample("normal", np.random.default_rng(100))
    for key in list(features)[:7]:
        features[key] = float("nan")

    result = diagnose(Payload(features=features))

    assert result["diagnostic"] == "unknown"
    assert result["abstained"] is True
    assert result["automatic_control_allowed"] is False
    assert any("Missing fraction" in item for item in result["evidence"])
