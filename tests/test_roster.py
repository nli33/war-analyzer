"""Tests for war/roster.py (C4b): year extraction, side-aware battle appearances, and roster
selection. Real-page block reuses data/raw/eval_ingest_cache.json like test_commanders.py /
test_infobox_numbers.py do, skipped if that cache isn't present on disk.
"""

import json
from pathlib import Path

import pytest

from war.roster import (
    BattleAppearance,
    battle_appearances,
    extract_year,
    generals_csv_rows,
    seed_general_ids,
    select_roster,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_CACHE = REPO_ROOT / "data" / "raw" / "eval_ingest_cache.json"


# --- extract_year --------------------------------------------------------------------------


def test_extract_year_day_month_year_ignores_day_number():
    assert extract_year("18 June 1815") == 1815


def test_extract_year_bc_marker():
    assert extract_year("9 August 48 BC") == -48


def test_extract_year_bce_dotted():
    assert extract_year("100 B.C.E.") == -100


def test_extract_year_range_takes_first():
    assert extract_year("1861-1865") == 1861


def test_extract_year_century_only_is_none():
    assert extract_year("4th century BC") is None


def test_extract_year_empty_is_none():
    assert extract_year("") is None
    assert extract_year(None) is None


# --- battle_appearances ----------------------------------------------------------------------

_SYNTHETIC_WIKITEXT = """
{{Infobox military conflict
|conflict = Battle of Example
|date = 2 September 31 BC
|result = Decisive victory for Side One
|commander1 = [[General One]]<br>[[Subordinate One]]
|commander2 = [[General Two]]
|strength1 = 10,000
|strength2 = 6,000
}}
"""


def test_battle_appearances_both_sides_identifiable():
    appearances = battle_appearances("Battle of Example", _SYNTHETIC_WIKITEXT)
    assert len(appearances) == 2

    mine = next(a for a in appearances if a.general_id == "general-one")
    assert mine.opponent_general_id == "general-two"
    assert mine.own_strength == 10000
    assert mine.enemy_strength == 6000
    assert mine.year == -31
    assert mine.has_usable_strength

    theirs = next(a for a in appearances if a.general_id == "general-two")
    assert theirs.opponent_general_id == "general-one"
    assert theirs.own_strength == 6000
    assert theirs.enemy_strength == 10000
    assert theirs.has_usable_strength


def test_battle_appearances_no_infobox_is_empty():
    assert battle_appearances("Not A Battle Page", "just some prose, no infobox") == []


def test_battle_appearances_forwards_identity_resolver():
    resolver = {"General One": "canonical-general"}
    appearances = battle_appearances("Battle of Example", _SYNTHETIC_WIKITEXT, resolver)
    assert {a.general_id for a in appearances} >= {"canonical-general"}


def test_battle_appearances_missing_strength_is_not_usable():
    wikitext = """
{{Infobox military conflict
|date = 1800
|commander1 = [[General One]]
|commander2 = [[General Two]]
|strength1 = Unknown
|strength2 = 6,000
}}
"""
    appearances = battle_appearances("Battle of Example Two", wikitext)
    mine = next(a for a in appearances if a.general_id == "general-one")
    assert mine.own_strength is None
    assert not mine.has_usable_strength


# --- seed_general_ids / select_roster --------------------------------------------------------


def test_seed_general_ids_slugs_titles():
    assert seed_general_ids(["Napoleon", "Julius Caesar"]) == {"napoleon", "julius-caesar"}


def test_seed_general_ids_uses_identity_resolver_when_given():
    resolver = {"Napoleon I": "napoleon"}
    assert seed_general_ids(["Napoleon I", "Julius Caesar"], resolver) == {
        "napoleon",
        "julius-caesar",
    }


def test_seed_general_ids_falls_back_to_slug_when_resolver_has_no_entry_or_resolves_to_none():
    resolver = {"Napoleon I": None}
    assert seed_general_ids(["Napoleon I", "Unseen Title"], resolver) == {
        "napoleon-i",
        "unseen-title",
    }


def _appearance(general_id, opponent_id, usable=True, year=1800):
    return BattleAppearance(
        battle_title=f"Battle for {general_id}",
        general_id=general_id,
        display_name=general_id,
        opponent_general_id=opponent_id,
        year=year,
        own_strength=10000 if usable else None,
        enemy_strength=8000 if usable else None,
    )


def test_select_roster_keeps_seed_general_at_bar():
    appearances = [_appearance("alice", "bob"), _appearance("alice", "bob")]
    roster = select_roster(appearances, seed_ids={"alice"}, min_usable_battles=2)
    assert set(roster) == {"alice"}


def test_select_roster_drops_seed_general_below_bar():
    appearances = [_appearance("alice", "bob")]
    roster = select_roster(appearances, seed_ids={"alice"}, min_usable_battles=2)
    assert roster == {}


def test_select_roster_admits_unlisted_opponent_who_clears_bar():
    # bob isn't a seed general but fights alice (kept) twice with usable strength both times;
    # a real scan emits bob's own-perspective appearances alongside alice's from the same two
    # battle pages (battle_appearances returns both identifiable sides together).
    appearances = [
        _appearance("alice", "bob"),
        _appearance("bob", "alice"),
        _appearance("alice", "bob"),
        _appearance("bob", "alice"),
    ]
    roster = select_roster(appearances, seed_ids={"alice"}, min_usable_battles=2)
    assert set(roster) == {"alice", "bob"}


def test_select_roster_does_not_admit_unrelated_general_never_facing_a_kept_one():
    appearances = [
        _appearance("alice", "bob"),
        _appearance("bob", "alice"),
        _appearance("alice", "bob"),
        _appearance("bob", "alice"),
        _appearance("carol", "dave"),
        _appearance("dave", "carol"),
        _appearance("carol", "dave"),
        _appearance("dave", "carol"),
    ]
    # carol/dave never fight a kept general (alice/bob's opponents), so neither seed-eligible
    # nor opponent-eligible even though carol clears the usable-battle bar on her own.
    roster = select_roster(appearances, seed_ids={"alice"}, min_usable_battles=2)
    assert set(roster) == {"alice", "bob"}


def test_select_roster_below_bar_strength_rows_are_not_usable():
    appearances = [_appearance("alice", "bob", usable=False), _appearance("alice", "bob", usable=False)]
    roster = select_roster(appearances, seed_ids={"alice"}, min_usable_battles=2)
    assert roster == {}


# --- generals_csv_rows ------------------------------------------------------------------------


def test_generals_csv_rows_derives_era_and_career_years():
    roster = {
        "alice": [
            _appearance("alice", "bob", year=1796),
            _appearance("alice", "bob", year=1812),
            _appearance("alice", "bob", year=1815),
        ]
    }
    rows = generals_csv_rows(roster)
    assert len(rows) == 1
    row = rows[0]
    assert row["general_id"] == "alice"
    assert row["career_start_year"] == 1796
    assert row["career_end_year"] == 1815
    assert row["era"] == "Napoleonic"
    assert "3 usable-strength battle" in row["notes"]


def test_generals_csv_rows_drops_general_with_no_dateable_battle():
    roster = {"alice": [_appearance("alice", "bob", year=None)]}
    assert generals_csv_rows(roster) == []


# --- real page integration -------------------------------------------------------------------


@pytest.mark.skipif(not EVAL_CACHE.exists(), reason="requires data/raw/eval_ingest_cache.json")
def test_real_wikipedia_page_pharsalus():
    cache = json.loads(EVAL_CACHE.read_text(encoding="utf-8"))
    appearances = battle_appearances("Battle of Pharsalus", cache["Battle of Pharsalus"])
    by_general = {a.general_id: a for a in appearances}
    assert "julius-caesar" in by_general
    caesar = by_general["julius-caesar"]
    assert caesar.opponent_general_id == "pompey"
    assert caesar.own_strength == 23000
    assert caesar.year == -48
