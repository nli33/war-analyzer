"""Tests for war/battles_dataset.py (C6): assembling data/auto/battles.csv rows."""

from war.battles_dataset import build_battle_rows

_WIKITEXT = """
{{Infobox military conflict
|conflict = Battle of Example
|date = 2 September 31 BC
|result = Decisive Roman victory
|combatant1 = Roman Republic
|combatant2 = Gauls
|commander1 = [[General One]]<br>[[Subordinate One]]
|commander2 = [[General Two]]
|strength1 = 10,000
|strength2 = 6,000
|casualties1 = 500
|casualties2 = 2,000
}}
"""


def test_build_battle_rows_both_sides_on_roster():
    rows = build_battle_rows("Battle of Example", _WIKITEXT, {"general-one", "general-two"})
    assert len(rows) == 2

    mine = next(r for r in rows if r["general_id"] == "general-one")
    assert mine["outcome"] == "Win"
    assert mine["decisiveness"] == "Rout"  # "Decisive ... victory" -> Rout regardless of side
    assert mine["own_troop_strength"] == 10000
    assert mine["enemy_troop_strength"] == 6000
    assert mine["own_casualties"] == 500
    assert mine["enemy_casualties"] == 2000
    assert mine["opponent_general_id"] == "general-two"
    assert mine["date"] == "-0031"
    assert mine["era"] == "Ancient"

    theirs = next(r for r in rows if r["general_id"] == "general-two")
    assert theirs["outcome"] == "Loss"
    assert theirs["own_troop_strength"] == 6000
    assert theirs["enemy_troop_strength"] == 10000


def test_build_battle_rows_only_roster_general_is_written():
    rows = build_battle_rows("Battle of Example", _WIKITEXT, {"general-one"})
    assert [r["general_id"] for r in rows] == ["general-one"]


def test_build_battle_rows_no_roster_match_is_empty():
    assert build_battle_rows("Battle of Example", _WIKITEXT, {"nobody"}) == []


def test_build_battle_rows_no_infobox_is_empty():
    assert build_battle_rows("Not A Battle", "just prose", {"general-one"}) == []


def test_build_battle_rows_no_year_is_dropped():
    wikitext = """
{{Infobox military conflict
|result = French victory
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""
    assert build_battle_rows("Battle of No Date", wikitext, {"general-one"}) == []


def test_build_battle_rows_unresolved_outcome_is_dropped():
    wikitext = """
{{Infobox military conflict
|date = 1800
|result = Ceasefire agreed
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""
    assert build_battle_rows("Battle of No Result", wikitext, {"general-one"}) == []


def test_build_battle_rows_missing_strength_falls_back_to_c5_resolved_value():
    wikitext = """
{{Infobox military conflict
|date = 1800
|result = French victory
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
|strength1 = Unknown
|strength2 = 6,000
}}
"""
    rows = build_battle_rows(
        "Battle of Resolved", wikitext, {"general-one"}, resolved_fields={"strength1": 9000}
    )
    assert rows[0]["own_troop_strength"] == 9000
    assert rows[0]["enemy_troop_strength"] == 6000


def test_build_battle_rows_missing_strength_without_resolution_stays_null():
    wikitext = """
{{Infobox military conflict
|date = 1800
|result = French victory
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
|strength1 = Unknown
|strength2 = 6,000
}}
"""
    rows = build_battle_rows("Battle of Unresolved", wikitext, {"general-one"})
    assert rows[0]["own_troop_strength"] is None
