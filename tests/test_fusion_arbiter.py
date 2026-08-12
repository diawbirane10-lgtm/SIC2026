from v2.fusion.arbiter import SourceOpinion, fuse_opinions


CLASSES = ["a", "b", "c"]


def p(label, confidence=.95):
    rest = (1.0 - confidence) / (len(CLASSES) - 1)
    return {c: confidence if c == label else rest for c in CLASSES}


def test_two_sources_agree_decision_is_allowed():
    d = fuse_opinions([
        SourceOpinion("process", p("a"), quality=.95, integrity=.95),
        SourceOpinion("electrical", p("a", .90), quality=.90, integrity=.95),
        SourceOpinion("vision", p("b", .70), quality=.70, integrity=.90),
    ], CLASSES)
    assert not d.abstained
    assert d.label == "a"


def test_two_high_confidence_sources_conflict_abstains():
    d = fuse_opinions([
        SourceOpinion("process", p("a", .99), quality=1.0, integrity=1.0),
        SourceOpinion("electrical", p("b", .99), quality=1.0, integrity=1.0),
        SourceOpinion("vision", p("c", .50), quality=.2, integrity=1.0),
    ], CLASSES)
    assert d.abstained
    assert d.label == "unknown"
    assert d.reason == "high_confidence_cross_modal_conflict"


def test_low_integrity_sources_are_excluded_and_force_abstention():
    d = fuse_opinions([
        SourceOpinion("process", p("a"), quality=.95, integrity=.2),
        SourceOpinion("electrical", p("a"), quality=.95, integrity=.2),
        SourceOpinion("vision", p("a"), quality=.95, integrity=.95),
    ], CLASSES)
    assert d.abstained
    assert d.reason == "insufficient_independent_sources"


def test_one_flagged_bad_source_cannot_override_two_good_sources():
    d = fuse_opinions([
        SourceOpinion("process", p("a", .92), quality=.95, integrity=.95),
        SourceOpinion("electrical", p("a", .91), quality=.95, integrity=.95),
        SourceOpinion("vision", p("b", .999), quality=1.0, integrity=.1),
    ], CLASSES)
    assert not d.abstained
    assert d.label == "a"
