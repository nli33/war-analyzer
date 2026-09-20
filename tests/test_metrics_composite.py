"""Phase 5 composite ranking: hand-computed expected values on synthetic data,
per SCOPE.md's verification method (same style as the Phase 3 metric tests).
"""

import pytest

from war.config import CompositeWeights
from war.metrics.composite import composite_ranking
from war.records import Battle, General


def make_battle(
    general_id,
    outcome,
    opponent_general_id=None,
    objective_secured=False,
    era="Industrial",
    battle_id=None,
):
    """A Battle with only the fields the four composite inputs read set meaningfully."""
    return Battle(
        battle_id=battle_id or f"{general_id}-{outcome}-{opponent_general_id}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era=era,
        own_troop_strength=10_000,
        enemy_troop_strength=10_000,
        own_casualties=1,
        enemy_casualties=1,
        outcome=outcome,
        decisiveness=None,
        objective_secured=objective_secured,
        opponent_general_id=opponent_general_id,
        resource_backing_tier=3,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def make_general(general_id, era="Industrial", career_start_year=1900, career_end_year=1900):
    return General(
        general_id=general_id,
        display_name=general_id,
        era=era,
        career_start_year=career_start_year,
        career_end_year=career_end_year,
        notes=None,
    )


def test_no_battles_returns_empty_list():
    assert composite_ranking([], []) == []


def test_singleton_era_cohort_gets_zero_z_scores_and_zero_composite_score():
    # alice is the only general in her era: no cohort-mate to compare against,
    # so every z-score (and therefore the composite score) is exactly 0.0,
    # regardless of how good her raw record is.
    battles = [make_battle("alice", "Win", "bob", objective_secured=True, era="WWII")]
    generals = [make_general("alice", era="WWII")]

    result = composite_ranking(battles, generals)

    assert len(result) == 1
    entry = result[0]
    assert entry.general_id == "alice"
    assert entry.oar_z == 0.0
    assert entry.war_residual_z == 0.0
    assert entry.decisiveness_z == 0.0
    assert entry.longevity_z == 0.0
    assert entry.composite_score == 0.0


def _clean_two_general_cohort():
    # alice and bob are the only two generals in Ancient, and both have at
    # least one win (so decisive_win_rate is defined for both, unlike the
    # single-Loss fixtures used elsewhere in this file). alice's record (1
    # Win, decisive) strictly beats bob's (1 Win, non-decisive + 1 Loss) on
    # all four inputs:
    #   * OAR: alice's only result is a win; bob's is a win and a loss, so
    #     his final rating nets lower.
    #   * war_residual: all 3 rows share identical force_ratio/resource/tech,
    #     so pooled OLS degenerates to predicted = mean(actual) = 2/3 for
    #     every row. alice: 1 - 2/3 = +1/3. bob: mean(1 - 2/3, 0 - 2/3) =
    #     mean(+1/3, -2/3) = -1/6.
    #   * decisiveness: alice's win is objective_secured=True (rate 1.0),
    #     bob's is False (rate 0.0).
    #   * longevity: alice's 1-year career banks her 1.0 career value ->
    #     longevity 1.0; bob's 2-year career banks 1.0 (win) + 0 (loss) = 1.0
    #     career value over 2 years -> longevity 0.5.
    # For a 2-member population, z = (x - mean) / std always resolves to
    # exactly +1.0 / -1.0 (mean is the midpoint, std is half the gap)
    # whenever the two values differ, regardless of the input's raw scale --
    # so every one of alice's four z-scores is +1.0 and bob's is -1.0.
    battles = [
        make_battle("alice", "Win", "riven", objective_secured=True, era="Ancient", battle_id="a1"),
        make_battle("bob", "Win", "quill", objective_secured=False, era="Ancient", battle_id="b1"),
        make_battle("bob", "Loss", "worvo", era="Ancient", battle_id="b2"),
    ]
    generals = [
        make_general("alice", era="Ancient", career_start_year=1900, career_end_year=1900),
        make_general("bob", era="Ancient", career_start_year=1900, career_end_year=1901),
    ]
    return battles, generals


def test_two_general_era_cohort_gets_exact_hand_computed_z_scores():
    battles, generals = _clean_two_general_cohort()

    result = composite_ranking(battles, generals)
    by_id = {entry.general_id: entry for entry in result}

    assert by_id["alice"].oar_z == pytest.approx(1.0)
    assert by_id["bob"].oar_z == pytest.approx(-1.0)
    assert by_id["alice"].war_residual_z == pytest.approx(1.0)
    assert by_id["bob"].war_residual_z == pytest.approx(-1.0)
    assert by_id["alice"].decisiveness_z == pytest.approx(1.0)
    assert by_id["bob"].decisiveness_z == pytest.approx(-1.0)
    assert by_id["alice"].longevity_z == pytest.approx(1.0)
    assert by_id["bob"].longevity_z == pytest.approx(-1.0)


def test_composite_score_is_the_configured_weighted_sum_of_z_scores():
    battles, generals = _clean_two_general_cohort()
    weights = CompositeWeights(oar=0.4, war_residual=0.3, decisiveness=0.2, longevity=0.1)

    result = composite_ranking(battles, generals, weights=weights)
    alice = next(entry for entry in result if entry.general_id == "alice")

    # every z-score is exactly +1.0 for alice in this clean two-general cohort
    assert alice.composite_score == pytest.approx(0.4 + 0.3 + 0.2 + 0.1)


def test_ranking_is_sorted_highest_composite_score_first():
    battles, generals = _clean_two_general_cohort()

    result = composite_ranking(battles, generals)

    assert [entry.general_id for entry in result] == ["alice", "bob"]
    assert result[0].rank == 1
    assert result[1].rank == 2
    assert result[0].composite_score > result[1].composite_score


def _winless_loser_cohort():
    # carol has zero wins (so decisive_win_rate is None for her) and dave has
    # one decisive win. dave beats carol cleanly on OAR/war_residual/
    # longevity (z = +1.0 each, by the same 2-member-population math as
    # `_clean_two_general_cohort`), but his decisiveness_z is 0.0: carol's
    # None excludes her from that metric's cohort, leaving dave the sole
    # (singleton) member, which falls back to 0.0 rather than dividing by
    # zero. This gives dave a non-uniform set of z-scores across the four
    # inputs, unlike `_clean_two_general_cohort` where every z is +1.0 --
    # useful for confirming the composite score actually depends on *which*
    # weight is large, not just the weights' total.
    battles = [
        make_battle("carol", "Loss", "dave", era="Medieval", battle_id="c1"),
        make_battle("dave", "Win", "carol", objective_secured=True, era="Medieval", battle_id="d1"),
    ]
    generals = [
        make_general("carol", era="Medieval"),
        make_general("dave", era="Medieval"),
    ]
    return battles, generals


def test_general_with_no_wins_is_ranked_with_zero_decisiveness_z():
    battles, generals = _winless_loser_cohort()

    result = composite_ranking(battles, generals)
    by_id = {entry.general_id: entry for entry in result}

    assert by_id["carol"].decisiveness_z == 0.0
    assert by_id["dave"].decisiveness_z == 0.0
    assert by_id["dave"].oar_z == pytest.approx(1.0)
    assert by_id["dave"].war_residual_z == pytest.approx(1.0)
    assert by_id["dave"].longevity_z == pytest.approx(1.0)


def test_off_roster_opponent_is_excluded_from_the_ranking():
    battles = [make_battle("alice", "Win", "some_unrostered_commander", era="Ancient")]
    generals = [make_general("alice", era="Ancient")]

    result = composite_ranking(battles, generals)

    assert [entry.general_id for entry in result] == ["alice"]


def test_changing_weights_changes_the_composite_score():
    # dave's z-scores are non-uniform (1.0, 1.0, 0.0, 1.0), so shifting all
    # weight onto the one metric that's 0.0 for him (decisiveness) must
    # change his composite score.
    battles, generals = _winless_loser_cohort()

    default_result = composite_ranking(battles, generals)
    dave_default = next(e for e in default_result if e.general_id == "dave").composite_score

    all_decisiveness_weight = CompositeWeights(
        oar=0.0, war_residual=0.0, decisiveness=1.0, longevity=0.0
    )
    alt_result = composite_ranking(battles, generals, weights=all_decisiveness_weight)
    dave_alt = next(e for e in alt_result if e.general_id == "dave").composite_score

    assert dave_default != dave_alt
