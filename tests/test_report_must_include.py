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


def test_classify_not_a_commander_in_any_battle():
    status = classify("x", "X", "x", False, {}, {}, min_battles=2)
    assert not status.in_roster
    assert "not a primary commander" in status.reason


def test_classify_too_few_usable_battles():
    appearances_by_general = {"x": [_appearance("x", "y")]}
    status = classify("x", "X", "x", True, appearances_by_general, {}, min_battles=2)
    assert not status.in_roster
    assert status.usable_appearances == 1
    assert "too few usable-strength battles" in status.reason


def test_classify_in_roster_seed():
    appearances = [_appearance("x", "y"), _appearance("x", "y")]
    appearances_by_general = {"x": appearances}
    roster = {"x": appearances}
    status = classify("x", "X", "x", True, appearances_by_general, roster, min_battles=2)
    assert status.in_roster
    assert "seed" in status.reason


def test_classify_clears_bar_but_not_seed_and_not_kept():
    appearances = [_appearance("x", "y"), _appearance("x", "y")]
    appearances_by_general = {"x": appearances}
    status = classify("x", "X", "x", False, appearances_by_general, {}, min_battles=2)
    assert not status.in_roster
    assert "not seed-listed" in status.reason
