"""Tests for scripts/report_must_include.py's (E3) pure classification logic."""

from war.roster import BattleAppearance
from scripts.report_must_include import classify, pipeline_general_id_for


def _appearance(general_id, opponent_id, own=10000, enemy=10000):
    return BattleAppearance(
        battle_title="Battle of Somewhere",
        general_id=general_id,
        display_name=general_id,
        opponent_general_id=opponent_id,
        year=1800,
        own_strength=own,
        enemy_strength=enemy,
    )


def test_pipeline_general_id_for_uses_resolver_when_title_is_a_key():
    resolver = {"Napoleon": "napoleon"}
    assert pipeline_general_id_for("Napoleon", resolver) == "napoleon"


def test_pipeline_general_id_for_falls_back_to_raw_slug():
    resolver = {"Someone Else": "someone-else"}
    assert pipeline_general_id_for("Dwight D. Eisenhower", resolver) == "dwight-d-eisenhower"


def test_classify_zero_appearances_falls_back_to_hand_curated():
    # E4: a must-include general with zero pipeline appearances is still forced into the roster
    # and (being gold-set, not Han Xin) falls back to its hand-curated data/generals.csv row.
    status = classify("x", "X", "x", False, {}, {}, min_battles=2)
    assert status.usable_appearances == 0
    assert "falls back to the hand-curated data/generals.csv row" in status.reason


def test_classify_too_few_usable_battles_falls_back_to_hand_curated():
    appearances_by_general = {"x": [_appearance("x", "y")]}
    status = classify("x", "X", "x", True, appearances_by_general, {}, min_battles=2)
    assert status.usable_appearances == 1
    assert "falls back to the hand-curated data/generals.csv row" in status.reason


def test_classify_han_xin_too_thin_has_no_fallback():
    appearances_by_general = {"han-xin": [_appearance("han-xin", "y")]}
    status = classify("han-xin", "Han Xin", "han-xin", False, appearances_by_general, {}, min_battles=2)
    assert status.usable_appearances == 1
    assert "no hand-curated fallback exists for Han Xin" in status.reason


def test_classify_in_roster_seed():
    appearances = [_appearance("x", "y"), _appearance("x", "y")]
    appearances_by_general = {"x": appearances}
    roster = {"x": appearances}
    status = classify("x", "X", "x", True, appearances_by_general, roster, min_battles=2)
    assert status.in_roster
    assert "seed" in status.reason


def test_classify_clears_bar_directly_seed_or_not():
    # E4: clearing the usable-battle bar is sufficient regardless of seed-list membership.
    appearances = [_appearance("x", "y"), _appearance("x", "y")]
    appearances_by_general = {"x": appearances}
    status = classify("x", "X", "x", False, appearances_by_general, {}, min_battles=2)
    assert "in roster" in status.reason
    assert "non-seed" in status.reason
