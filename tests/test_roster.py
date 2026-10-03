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
    pipeline_general_id_for,
    seed_general_ids,
    select_roster,
    suspicious_year_rows,
    usable_battle_counts,
    year_from_title,
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


# H1 regression: a date range glued together by a stripped {{ndash}} template used to read as
# "1112 April 1796" / "2122 April 1809" / "9 11 March 1811" before war/scrape.py's fix (the
# splice bug lived in scrape.py; these pin the pipeline's year extraction against what the fixed
# scraper now actually hands it, so a future regression there would surface here too).
def test_extract_year_after_ndash_fix_reads_the_real_year_not_the_spliced_digits():
    assert extract_year("11 12 April 1796") == 1796  # Battle of Montenotte
    assert extract_year("21 22 April 1809") == 1809  # Battle of Eckmühl
    assert extract_year("9 11 March 1811") == 1811  # Battle of Pombal


# --- year_from_title -------------------------------------------------------------------------


def test_year_from_title_parenthetical_year():
    assert year_from_title("Action at Mannheim (1795)") == 1795


def test_year_from_title_parenthetical_bc_year():
    assert year_from_title("Battle of Cartagena (209 BC)") == -209


def test_year_from_title_no_parenthetical_is_none():
    assert year_from_title("Battle of Eckmühl") is None


# --- suspicious_year_rows ---------------------------------------------------------------------


def test_suspicious_year_rows_flags_year_far_from_title():
    appearances = [("napoleon", "Action at Mannheim (1795)", 1112)]
    flagged = suspicious_year_rows(appearances)
    assert len(flagged) == 1
    assert flagged[0]["general_id"] == "napoleon"
    assert "title" in flagged[0]["reason"]


def test_suspicious_year_rows_flags_year_far_from_generals_other_battles():
    appearances = [
        ("napoleon", "Battle of Montenotte", 1796),
        ("napoleon", "Battle of Eckmühl", 2122),
        ("napoleon", "Battle of Waterloo", 1815),
    ]
    flagged = suspicious_year_rows(appearances)
    assert [item["battle_title"] for item in flagged] == ["Battle of Eckmühl"]


def test_suspicious_year_rows_no_flag_for_consistent_career():
    appearances = [
        ("napoleon", "Battle of Montenotte", 1796),
        ("napoleon", "Battle of Waterloo", 1815),
    ]
    assert suspicious_year_rows(appearances) == []


def test_suspicious_year_rows_single_dated_battle_with_no_title_year_is_not_flagged():
    # Nothing to compare against -- must not flag for lack of evidence either way.
    assert suspicious_year_rows([("han-xin", "Battle of Jingxing", 204)]) == []


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


# --- seed_general_ids / pipeline_general_id_for ------------------------------------------------


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


def test_pipeline_general_id_for_uses_resolver_entry():
    assert pipeline_general_id_for("Napoleon", {"Napoleon": "napoleon-merged"}) == "napoleon-merged"


def test_pipeline_general_id_for_falls_back_to_slug():
    assert pipeline_general_id_for("Han Xin", {}) == "han-xin"
    assert pipeline_general_id_for("Napoleon", {"Napoleon": None}) == "napoleon"


# --- usable_battle_counts / select_roster (E4: seedless, must-include forcing) -----------------


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


def test_usable_battle_counts_only_counts_usable_strength_rows():
    appearances = [
        _appearance("alice", "bob"),
        _appearance("alice", "bob", usable=False),
        _appearance("bob", "alice"),
    ]
    assert usable_battle_counts(appearances) == {"alice": 1, "bob": 1}


def test_select_roster_keeps_any_general_at_bar_seed_or_not():
    # E4: no seed_ids parameter any more -- clearing the bar is sufficient regardless of origin.
    appearances = [_appearance("alice", "bob"), _appearance("alice", "bob")]
    roster = select_roster(appearances, min_usable_battles=2)
    assert set(roster) == {"alice"}


def test_select_roster_drops_general_below_bar():
    appearances = [_appearance("alice", "bob")]
    roster = select_roster(appearances, min_usable_battles=2)
    assert roster == {}


def test_select_roster_admits_every_general_who_independently_clears_the_bar():
    # E4 dropped the old "must face an already-kept general" hop: carol/dave clear the bar on
    # their own and are admitted even though alice/bob never appear in the same appearances list.
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
    roster = select_roster(appearances, min_usable_battles=2)
    assert set(roster) == {"alice", "bob", "carol", "dave"}


def test_select_roster_below_bar_strength_rows_are_not_usable():
    appearances = [_appearance("alice", "bob", usable=False), _appearance("alice", "bob", usable=False)]
    roster = select_roster(appearances, min_usable_battles=2)
    assert roster == {}


def test_select_roster_must_include_joins_below_bar():
    appearances = [_appearance("alice", "bob")]  # alice: 1 usable, below a bar of 2
    roster = select_roster(appearances, min_usable_battles=2, must_include_ids=frozenset({"alice"}))
    assert set(roster) == {"alice"}
    assert len(roster["alice"]) == 1


def test_select_roster_must_include_joins_with_zero_appearances():
    appearances = [_appearance("bob", "alice")]
    roster = select_roster(appearances, min_usable_battles=2, must_include_ids=frozenset({"alice"}))
    assert roster["alice"] == []


def test_select_roster_must_include_does_not_suppress_normal_bar_clearing():
    appearances = [_appearance("alice", "bob"), _appearance("alice", "bob")]
    roster = select_roster(appearances, min_usable_battles=2, must_include_ids=frozenset({"someone-else"}))
    assert set(roster) == {"alice", "someone-else"}
    assert roster["someone-else"] == []


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


def test_generals_csv_rows_flags_seed_membership_in_notes():
    roster = {"alice": [_appearance("alice", "bob")], "bob": [_appearance("bob", "alice")]}
    rows = generals_csv_rows(roster, seed_ids=frozenset({"alice"}))
    by_id = {row["general_id"]: row for row in rows}
    assert "seed=true" in by_id["alice"]["notes"]
    assert "seed=false" in by_id["bob"]["notes"]


def test_generals_csv_rows_appends_extra_notes():
    roster = {"alice": [_appearance("alice", "bob")]}
    rows = generals_csv_rows(roster, extra_notes={"alice": "THIN must-include"})
    assert "THIN must-include" in rows[0]["notes"]


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
