"""Tests for scripts/eval_ingest.py's naive numeric parser and scoring logic (A3)."""

import math

from scripts.eval_ingest import (
    extract_for_battle,
    naive_extract_number,
    score_field,
)


def test_plain_number_with_commas():
    assert naive_extract_number("50,000") == 50000


def test_strips_bracketed_citation():
    assert naive_extract_number("35,000[1]") == 35000


def test_k_suffix():
    assert naive_extract_number("3.5k") == 3500


def test_million_suffix():
    assert naive_extract_number("1.2 million") == 1_200_000


def test_approx_marker():
    assert naive_extract_number("c. 20,000") == 20000


def test_range_takes_first_number_only():
    # Documented limitation: the naive baseline is not expected to average ranges.
    assert naive_extract_number("5,700-8,000") == 5700


def test_qualitative_text_returns_none():
    assert naive_extract_number("Heavy") is None
    assert naive_extract_number("Unknown") is None
    assert naive_extract_number("") is None


def test_extra_segment_after_number_is_ignored():
    assert naive_extract_number("40,000\n40+ cannon") == 40000


def test_extract_for_battle_picks_lower_error_orientation():
    # Gold says own=30000, enemy=80000. Infobox lists them combatant1=80000,
    # combatant2=30000 (reversed order) -> should flip to match gold, not take strength1 as own.
    fields = {
        "strength1": "80,000",
        "strength2": "30,000",
        "casualties1": "9,000",
        "casualties2": "2,000",
    }
    result = extract_for_battle(fields, gold_own_strength=30000, gold_enemy_strength=80000)
    assert result["own_troop_strength"] == 30000
    assert result["enemy_troop_strength"] == 80000
    assert result["own_casualties"] == 2000
    assert result["enemy_casualties"] == 9000


def test_extract_for_battle_defaults_forward_when_nothing_comparable():
    fields = {"strength1": "", "strength2": "", "casualties1": "", "casualties2": ""}
    result = extract_for_battle(fields, gold_own_strength=30000, gold_enemy_strength=80000)
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
