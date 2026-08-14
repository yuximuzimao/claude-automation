from scripts.audit_route_atlas_special_mechanisms import detect_risk_signals


def test_provided_item_plus_creature_objective_enters_review_queue():
    raw = {10: {1: {1: {1: 12345}}}, 11: 67890}
    signals = detect_risk_signals(raw, {})
    assert "provided_item_plus_creature_objectives" in signals


def test_plain_creature_objective_does_not_trigger_that_signal():
    raw = {10: {1: {1: {1: 12345}}}, 11: None}
    signals = detect_risk_signals(raw, {})
    assert "provided_item_plus_creature_objectives" not in signals


def test_scripted_classification_is_review_signal():
    profile = {"classification": {"effective_primary": "scripted_transport"}}
    signals = detect_risk_signals({}, profile)
    assert "known_scripted_or_escort_type" in signals
