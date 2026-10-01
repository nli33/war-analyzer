"""Tests for scripts/sensitivity_test.py's perturbation and comparison helpers (A5)."""

import math
from dataclasses import replace

import numpy as np

from scripts.sensitivity_test import (
    _lognormal_factor,
    _top_n,
    perturb_battles,
    spearman_correlation,
)
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
    objective_secured=True,
    opponent_general_id="g2",
    resource_backing_tier=2,
    tech_era_tier=1,
    political_constraint_flag=False,
    source_confidence="High",
    source_citation="test",
    notes=None,
)


def test_lognormal_factor_at_error_level_one_is_always_one():
    # error_level=1.0 -> sigma=ln(1)=0 -> Normal(0, 0) is always 0 -> exp(0) == 1.0.
    rng = np.random.default_rng(0)
    for _ in range(10):
        assert _lognormal_factor(rng, 1.0) == 1.0


def test_perturb_battles_at_error_level_one_is_a_no_op():
    rng = np.random.default_rng(0)
    [perturbed] = perturb_battles([_BASE_BATTLE], error_level=1.0, rng=rng)
    assert perturbed == _BASE_BATTLE


def test_perturb_battles_leaves_zero_casualties_at_zero():
    # enemy_casualties=0 on _BASE_BATTLE: any factor times 0 is still 0, not floored up to 1.
    rng = np.random.default_rng(0)
    [perturbed] = perturb_battles([_BASE_BATTLE], error_level=3.0, rng=rng)
    assert perturbed.enemy_casualties == 0


def test_perturb_battles_floors_nonzero_fields_at_one():
    tiny = replace(_BASE_BATTLE, own_casualties=1)
    rng = np.random.default_rng(0)
    for _ in range(50):
        [perturbed] = perturb_battles([tiny], error_level=3.0, rng=rng)
        assert perturbed.own_casualties >= 1


def test_perturb_battles_only_touches_perturbed_numeric_fields():
    rng = np.random.default_rng(0)
    [perturbed] = perturb_battles([_BASE_BATTLE], error_level=2.0, rng=rng)
    assert perturbed.battle_id == _BASE_BATTLE.battle_id
    assert perturbed.outcome == _BASE_BATTLE.outcome
    assert perturbed.resource_backing_tier == _BASE_BATTLE.resource_backing_tier


def test_spearman_correlation_perfect_agreement():
    ranks = {"a": 1, "b": 2, "c": 3, "d": 4}
    assert spearman_correlation(ranks, dict(ranks)) == 1.0


def test_spearman_correlation_perfect_reversal():
    baseline = {"a": 1, "b": 2, "c": 3, "d": 4}
    reversed_ranks = {"a": 4, "b": 3, "c": 2, "d": 1}
    assert spearman_correlation(baseline, reversed_ranks) == -1.0


def test_spearman_correlation_only_uses_common_keys():
    baseline = {"a": 1, "b": 2, "c": 3, "d": 4}
    perturbed = {"a": 1, "b": 2, "c": 3, "extra": 99}
    # Common keys a,b,c agree exactly -> perfect correlation, "d"/"extra" ignored.
    assert math.isclose(spearman_correlation(baseline, perturbed), 1.0)


def test_top_n_selects_ranks_at_or_below_n():
    ranks = {"a": 1, "b": 2, "c": 3, "d": 4}
    assert _top_n(ranks, 2) == {"a", "b"}
