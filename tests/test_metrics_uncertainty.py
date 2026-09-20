"""Phase 4 Monte Carlo uncertainty: SCOPE.md's verification method for this
phase is explicit -- "test that a High-confidence-only general has a
near-zero interval width; a Low-confidence general has a visibly wider one"
-- plus a few supporting checks on the resampling mechanics themselves.
"""

import numpy as np

from war.metrics.uncertainty import (
    DEFAULT_N_RUNS,
    monte_carlo_uncertainty,
    _resample_battle,
)
from war.records import Battle


def make_battle(
    general_id,
    outcome="Win",
    own_troops=10_000,
    enemy_troops=8_000,
    own_casualties=1_000,
    enemy_casualties=2_000,
    resource_backing_tier=3,
    source_confidence="High",
    battle_id=None,
):
    """A Battle with only the fields the resampling-sensitive metrics read set meaningfully."""
    return Battle(
        battle_id=battle_id or f"{general_id}-{outcome}-{own_troops}-{source_confidence}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=own_troops,
        enemy_troop_strength=enemy_troops,
        own_casualties=own_casualties,
        enemy_casualties=enemy_casualties,
        outcome=outcome,
        decisiveness=None,
        objective_secured=False,
        opponent_general_id=None,
        resource_backing_tier=resource_backing_tier,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence=source_confidence,
        source_citation="test fixture",
        notes=None,
    )


def test_default_n_runs_meets_scope_minimum():
    assert DEFAULT_N_RUNS >= 1000


def test_high_confidence_battle_is_never_perturbed():
    battle = make_battle("alice", source_confidence="High")
    rng = np.random.default_rng(0)

    for _ in range(50):
        assert _resample_battle(battle, rng) == battle


def test_high_confidence_only_general_has_near_zero_interval_width():
    battles = [
        make_battle("alice", "Win", own_troops=10_000, enemy_troops=8_000, source_confidence="High"),
        make_battle("alice", "Loss", own_troops=12_000, enemy_troops=15_000, source_confidence="High"),
    ]

    dist = monte_carlo_uncertainty(battles, n_runs=300, seed=1)["alice"]

    for metric_name, summary in dist.items():
        if summary.runs_used == 0:
            continue
        width = summary.ci_high - summary.ci_low
        assert width == 0.0, f"{metric_name} had nonzero width {width} for an all-High general"
        assert summary.runs_used == 300


def test_low_confidence_general_has_visibly_wider_interval_than_high_confidence_general():
    high_battles = [
        make_battle("bob", "Win", own_troops=10_000, enemy_troops=8_000, source_confidence="High"),
        make_battle("bob", "Loss", own_troops=12_000, enemy_troops=15_000, source_confidence="High"),
    ]
    low_battles = [
        make_battle(
            "carol", "Win", own_troops=10_000, enemy_troops=8_000, source_confidence="Low", battle_id="c1"
        ),
        make_battle(
            "carol", "Loss", own_troops=12_000, enemy_troops=15_000, source_confidence="Low", battle_id="c2"
        ),
    ]

    result = monte_carlo_uncertainty(high_battles + low_battles, n_runs=500, seed=2)
    high_dist = result["bob"]
    low_dist = result["carol"]

    # total_own_troops/avg_force_ratio_faced are general-local (grouped by
    # general_id, never mix in another general's rows), unlike war_residual's
    # deliberately pooled fit -- see uncertainty.py's docstring -- so these
    # are the metrics where "High confidence -> zero width" is guaranteed
    # even with a Low-confidence general resampled in the same batch.
    for metric_name in ("total_own_troops", "avg_force_ratio_faced"):
        high_width = high_dist[metric_name].ci_high - high_dist[metric_name].ci_low
        low_width = low_dist[metric_name].ci_high - low_dist[metric_name].ci_low
        assert high_width == 0.0
        assert low_width > 0.0, f"{metric_name} should have nonzero spread for a Low-confidence general"


def test_resampled_values_stay_within_declared_noise_bounds():
    battle = make_battle(
        "dave", own_troops=10_000, enemy_troops=10_000, own_casualties=1_000,
        enemy_casualties=1_000, source_confidence="Low",
    )
    rng = np.random.default_rng(3)

    for _ in range(2_000):
        resampled = _resample_battle(battle, rng)
        assert 6_000 <= resampled.own_troop_strength <= 14_000
        assert 6_000 <= resampled.enemy_troop_strength <= 14_000
        assert 600 <= resampled.own_casualties <= 1_400
        assert 600 <= resampled.enemy_casualties <= 1_400


def test_troop_strength_floors_at_one_not_zero():
    # own_troop_strength=1 under -40% Low noise would round to 0 without the
    # troop-strength floor documented in the module docstring; that would
    # blow up war_residual's enemy/own division.
    battle = make_battle(
        "erin", own_troops=1, enemy_troops=1, source_confidence="Low",
    )
    rng = np.random.default_rng(4)

    for _ in range(2_000):
        resampled = _resample_battle(battle, rng)
        assert resampled.own_troop_strength >= 1
        assert resampled.enemy_troop_strength >= 1


def test_monte_carlo_uncertainty_runs_without_error_on_extreme_low_confidence_battle():
    battles = [
        make_battle("erin", own_troops=1, enemy_troops=1, source_confidence="Low"),
    ]

    dist = monte_carlo_uncertainty(battles, n_runs=200, seed=5)["erin"]

    assert dist["war_residual"].runs_used == 200


def test_metric_is_none_when_never_defined_across_any_run():
    # own_troops == enemy_troops and resource tier 5 on a High-confidence
    # (never-perturbed) battle never satisfies clutch.py's "playing from
    # behind" condition in any run, so clutch_rating stays None throughout.
    battles = [
        make_battle(
            "frank", "Win", own_troops=10_000, enemy_troops=10_000,
            resource_backing_tier=5, source_confidence="High",
        )
    ]

    dist = monte_carlo_uncertainty(battles, n_runs=100, seed=6)["frank"]

    assert dist["clutch_rating"].mean is None
    assert dist["clutch_rating"].runs_used == 0


def test_generals_kept_separate():
    battles = [
        make_battle("alice", "Win", own_troops=10_000, source_confidence="Low", battle_id="a"),
        make_battle("bob", "Loss", own_troops=5_000, source_confidence="Low", battle_id="b"),
    ]

    result = monte_carlo_uncertainty(battles, n_runs=100, seed=7)

    assert set(result.keys()) == {"alice", "bob"}
    assert result["alice"]["total_own_troops"].mean != result["bob"]["total_own_troops"].mean


def test_general_absent_from_battles_is_absent_from_result():
    assert monte_carlo_uncertainty([], n_runs=10) == {}


def test_deterministic_for_fixed_seed():
    battles = [
        make_battle("alice", "Win", own_troops=10_000, source_confidence="Low"),
    ]

    first = monte_carlo_uncertainty(battles, n_runs=100, seed=42)
    second = monte_carlo_uncertainty(battles, n_runs=100, seed=42)

    assert first["alice"]["total_own_troops"].mean == second["alice"]["total_own_troops"].mean
