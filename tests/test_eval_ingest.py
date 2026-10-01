"""Tests for scripts/eval_ingest.py's real-pipeline scoring logic (C7)."""

import math

from scripts.eval_ingest import extract_for_battle, find_own_side, score_field


def _wikitext(commander1, commander2, strength1="", strength2="", casualties1="", casualties2=""):
    return (
        "{{Infobox military conflict\n"
        f"| commander1 = {commander1}\n"
        f"| commander2 = {commander2}\n"
        f"| strength1 = {strength1}\n"
        f"| strength2 = {strength2}\n"
        f"| casualties1 = {casualties1}\n"
        f"| casualties2 = {casualties2}\n"
        "}}"
    )


def test_find_own_side_matches_commander1():
    wikitext = _wikitext("[[Hannibal]]", "[[Scipio Africanus]]")
    assert find_own_side(wikitext, "hannibal") == "1"


def test_find_own_side_matches_commander2():
    wikitext = _wikitext("[[Hannibal]]", "[[Scipio Africanus]]")
    assert find_own_side(wikitext, "scipio-africanus") == "2"


def test_find_own_side_none_when_general_id_not_present():
    wikitext = _wikitext("[[Hannibal]]", "[[Scipio Africanus]]")
    assert find_own_side(wikitext, "julius-caesar") is None


def test_find_own_side_resolves_gold_id_alias():
    # Gold's hand-chosen id ("hannibal-barca") differs from Wikipedia's own page title
    # ("Hannibal") for the same person; GOLD_ID_ALIASES bridges that naming gap.
    wikitext = _wikitext("[[Hannibal]]", "[[Scipio Africanus]]")
    assert find_own_side(wikitext, "hannibal-barca") == "1"


def test_extract_for_battle_reads_own_side_numbers():
    wikitext = _wikitext(
        "[[Hannibal]]",
        "[[Scipio Africanus]]",
        strength1="40,000",
        strength2="34,000",
        casualties1="5,500",
        casualties2="1,500",
    )
    result = extract_for_battle(wikitext, "scipio-africanus")
    assert result == {
        "own_troop_strength": 34000,
        "enemy_troop_strength": 40000,
        "own_casualties": 1500,
        "enemy_casualties": 5500,
    }


def test_extract_for_battle_no_side_match_returns_all_none():
    wikitext = _wikitext("[[Hannibal]]", "[[Scipio Africanus]]", strength1="40,000")
    result = extract_for_battle(wikitext, "julius-caesar")
    assert result == {
        "own_troop_strength": None,
        "enemy_troop_strength": None,
        "own_casualties": None,
        "enemy_casualties": None,
    }


def test_score_field_coverage_and_buckets():
    # gold=100: extracted 100 (exact), 150 (1.5x), None (missing), 400 (way off)
    pairs = [(100, 100), (100, 150), (100, None), (100, 400)]
    stats = score_field(pairs)
    assert stats["total"] == 4
    assert stats["covered"] == 3
    assert stats["coverage"] == 0.75
    # within 1.5x: 100 and 150 (log(150/100) == log(1.5) exactly) -> 2/3
    assert stats["within_1.5x"] == 2
    assert math.isclose(stats["within_1.5x_share"], 2 / 3)
    # within 3x: 100, 150 -> still not 400 (4x) -> 2/3
    assert stats["within_3.0x"] == 2
