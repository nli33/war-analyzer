"""Phase 3 WAR-residual (expected-outcome regression) tests: known-input/
known-output cases on small synthetic battle sets, per SCOPE.md's
verification method.

Most of these are genuinely hand-computable, unlike OAR's iterative solver:
* When every row shares identical force_ratio/resource_backing_tier/
  tech_era_tier, the design matrix collapses to the all-ones vector, so OLS
  degenerates to "predicted = mean(actual) for every row" — a fraction
  anyone can compute by hand, which is what `test_overperformer_and_...`
  below relies on for its exact expected numbers.
* Ordinary least squares with an intercept column always makes residuals sum
  to exactly zero (`X^T residual = 0`, and the intercept column is the
  all-ones vector) — a standard OLS property, checked directly as an
  invariant rather than re-derived per test.
"""

import pytest

from war.metrics.war_residual import war_residual_by_general
from war.records import Battle


def make_battle(general_id, outcome, force_ratio=1.0, resource=3, tech=3, battle_id=None):
    """A Battle with only the fields war_residual_by_general reads set meaningfully."""
    own = 1000
    return Battle(
        battle_id=battle_id or f"{general_id}-{outcome}-{force_ratio}-{battle_id}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=own,
        enemy_troop_strength=round(own * force_ratio),
        own_casualties=1,
        enemy_casualties=1,
        outcome=outcome,
        decisiveness=None,
        objective_secured=False,
        opponent_general_id=None,
        resource_backing_tier=resource,
        tech_era_tier=tech,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def test_no_battles_returns_empty_dict():
    assert war_residual_by_general([]) == {}


def test_general_with_no_battles_is_absent():
    battles = [make_battle("alice", "Win", battle_id="b1")]
    result = war_residual_by_general(battles)
    assert "bob" not in result


def test_perfect_linear_fit_gives_near_zero_residual():
    # y = 0.25 * force_ratio exactly at force_ratio in {0, 2, 4} -> {Loss, Draw, Win};
    # resource/tech held constant so the only real variation is force_ratio. Since an
    # exact solution exists, lstsq finds it and every residual is ~0.
    battles = [
        make_battle("alice", "Loss", force_ratio=0, battle_id="a1"),
        make_battle("alice", "Draw", force_ratio=2, battle_id="a2"),
        make_battle("alice", "Win", force_ratio=4, battle_id="a3"),
        make_battle("bob", "Loss", force_ratio=0, battle_id="b1"),
        make_battle("bob", "Draw", force_ratio=2, battle_id="b2"),
        make_battle("bob", "Win", force_ratio=4, battle_id="b3"),
    ]

    result = war_residual_by_general(battles)

    assert result["alice"].war_residual == pytest.approx(0.0, abs=1e-6)
    assert result["bob"].war_residual == pytest.approx(0.0, abs=1e-6)


def test_overperformer_and_underperformers_get_exact_hand_computed_residuals():
    # All 8 rows share identical force_ratio/resource/tech, so the design matrix
    # is rank-1 (every row proportional to the all-ones vector) and OLS
    # degenerates to predicted_i = mean(actual) = 1/8 = 0.125 for every row.
    # alice's lone Win (score 1) beats that baseline by 1 - 0.125 = 0.875.
    # bob and carol's Losses (score 0) fall short by 0 - 0.125 = -0.125 each.
    battles = [
        make_battle("alice", "Win", force_ratio=1.5, battle_id="alice-1"),
        make_battle("bob", "Loss", force_ratio=1.5, battle_id="bob-1"),
        make_battle("bob", "Loss", force_ratio=1.5, battle_id="bob-2"),
        make_battle("bob", "Loss", force_ratio=1.5, battle_id="bob-3"),
        make_battle("bob", "Loss", force_ratio=1.5, battle_id="bob-4"),
        make_battle("carol", "Loss", force_ratio=1.5, battle_id="carol-1"),
        make_battle("carol", "Loss", force_ratio=1.5, battle_id="carol-2"),
        make_battle("carol", "Loss", force_ratio=1.5, battle_id="carol-3"),
    ]

    result = war_residual_by_general(battles)

    assert result["alice"].war_residual == pytest.approx(0.875, abs=1e-6)
    assert result["alice"].battles_used == 1
    assert result["bob"].war_residual == pytest.approx(-0.125, abs=1e-6)
    assert result["bob"].battles_used == 4
    assert result["carol"].war_residual == pytest.approx(-0.125, abs=1e-6)
    assert result["carol"].battles_used == 3


def test_residuals_sum_to_zero_across_the_pooled_fit():
    # Standard OLS-with-intercept property: sum of residuals is exactly 0,
    # regardless of how varied the design matrix is.
    battles = [
        make_battle("alice", "Win", force_ratio=0.5, resource=4, tech=2, battle_id="a1"),
        make_battle("alice", "Loss", force_ratio=2.0, resource=2, tech=2, battle_id="a2"),
        make_battle("bob", "Draw", force_ratio=1.0, resource=3, tech=4, battle_id="b1"),
        make_battle("bob", "Win", force_ratio=0.8, resource=5, tech=1, battle_id="b2"),
        make_battle("carol", "Loss", force_ratio=3.0, resource=1, tech=5, battle_id="c1"),
        make_battle("carol", "Win", force_ratio=1.2, resource=3, tech=3, battle_id="c2"),
    ]

    result = war_residual_by_general(battles)

    weighted_sum = sum(r.war_residual * r.battles_used for r in result.values())
    assert weighted_sum == pytest.approx(0.0, abs=1e-6)


def test_battles_used_matches_row_count_per_general():
    battles = [
        make_battle("alice", "Win", battle_id="a1"),
        make_battle("alice", "Loss", battle_id="a2"),
        make_battle("alice", "Draw", battle_id="a3"),
    ]

    result = war_residual_by_general(battles)

    assert result["alice"].battles_used == 3
