"""Tests for scripts/ablation_harness.py's pure comparison helpers (H3)."""

from dataclasses import replace

from scripts.ablation_harness import (
    Variant,
    _largest_tie_group_size,
    _min_battles_variant,
    _shrunk_decisive_win_rate,
    _vs_baseline_spearman,
)
from war.metrics.composite import CompositeRanking
from war.records import Battle

_BASE_BATTLE = Battle(
    battle_id="b1",
    general_id="g1",
    battle_name="Test Battle",
    date="100-01-01",
    era="Ancient",
    own_troop_strength=10_000,
    enemy_troop_strength=20_000,
    own_casualties=1_000,
    enemy_casualties=0,
    outcome="Win",
    decisiveness="Strategic",
    opponent_general_id="g2",
    resource_backing_tier=2,
    tech_era_tier=1,
    source_citation="test",
    notes=None,
)


def test_shrunk_decisive_win_rate_pulls_small_samples_toward_half():
    # g1: 2 rated wins, both converted -> raw rate 1.0, shrunk toward 0.5 by pseudo_count=5.
    battles = [
        _BASE_BATTLE,
        replace(_BASE_BATTLE, battle_id="b2", decisiveness="Rout"),
    ]
    result = _shrunk_decisive_win_rate(battles, ranked_ids={"g1"}, pseudo_count=5)
    assert result["g1"] == (2 + 2.5) / (2 + 5)


def test_shrunk_decisive_win_rate_defined_at_the_prior_for_zero_data():
    # g1 has no rows at all here but is still a ranked_id -- unlike decisive_win_rate (None),
    # the shrunk version must return exactly the 0.5 prior, not skip the general.
    result = _shrunk_decisive_win_rate([], ranked_ids={"g1"}, pseudo_count=5)
    assert result == {"g1": 0.5}


def test_shrunk_decisive_win_rate_ignores_unlabeled_wins_and_non_ranked_ids():
    battles = [
        replace(_BASE_BATTLE, decisiveness=None),  # unlabeled win: not counted as rated
        replace(_BASE_BATTLE, battle_id="b2", general_id="other", decisiveness="Rout"),
    ]
    result = _shrunk_decisive_win_rate(battles, ranked_ids={"g1"}, pseudo_count=5)
    # g1's only row is unlabeled -> 0 rated wins -> prior; "other" isn't in ranked_ids -> absent.
    assert result == {"g1": 0.5}


def test_min_battles_variant_filters_without_renumbering_rank():
    baseline_ranking = [
        CompositeRanking("g1", 1, 2.0, 0.0, 0.0, 0.0, 0.0),
        CompositeRanking("g2", 2, 1.0, 0.0, 0.0, 0.0, 0.0),
        CompositeRanking("g3", 3, 0.5, 0.0, 0.0, 0.0, 0.0),
    ]
    battle_counts = {"g1": 10, "g2": 2, "g3": 8}

    variant = _min_battles_variant("floor5", "min battles >= 5", 5, baseline_ranking, battle_counts)

    assert variant.rank_by_id == {"g1": 1, "g3": 3}
    assert variant.score_by_id == {"g1": 2.0, "g3": 0.5}


def test_vs_baseline_spearman_perfect_agreement_on_common_generals():
    baseline = Variant("baseline", "baseline", {"g1": 1, "g2": 2, "g3": 3}, {})
    same_order = Variant("v", "v", {"g1": 1, "g2": 2}, {})

    assert _vs_baseline_spearman(same_order, baseline) == 1.0


def test_vs_baseline_spearman_reversed_order_is_negative():
    baseline = Variant("baseline", "baseline", {"g1": 1, "g2": 2, "g3": 3}, {})
    reversed_order = Variant("v", "v", {"g1": 3, "g2": 2, "g3": 1}, {})

    assert _vs_baseline_spearman(reversed_order, baseline) == -1.0


def test_largest_tie_group_size_counts_the_biggest_shared_score():
    scores = {"g1": 0.0, "g2": 0.0, "g3": 0.0, "g4": 1.5}
    assert _largest_tie_group_size(scores) == 3


def test_largest_tie_group_size_is_one_when_every_score_is_distinct():
    scores = {"g1": 0.1, "g2": 0.2, "g3": 0.3}
    assert _largest_tie_group_size(scores) == 1


def test_largest_tie_group_size_of_empty_scores_is_zero():
    assert _largest_tie_group_size({}) == 0
