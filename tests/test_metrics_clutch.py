"""Phase 3 Clutch Rating: hand-computed expected values on synthetic battles."""

from war.metrics.clutch import clutch_rating_by_general
from war.records import Battle


def make_battle(
    general_id,
    outcome,
    own_troops=10_000,
    enemy_troops=10_000,
    resource_backing_tier=3,
):
    """A Battle with only the fields clutch_rating_by_general reads set meaningfully."""
    return Battle(
        battle_id=f"{general_id}-{outcome}-{own_troops}-{enemy_troops}-{resource_backing_tier}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=own_troops,
        enemy_troop_strength=enemy_troops,
        own_casualties=1,
        enemy_casualties=1,
        outcome=outcome,
        decisiveness=None,
        objective_secured=False,
        opponent_general_id=None,
        resource_backing_tier=resource_backing_tier,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def test_outnumbered_battle_counts_as_playing_from_behind():
    battles = [make_battle("alice", "Win", own_troops=5_000, enemy_troops=10_000)]

    stats = clutch_rating_by_general(battles)["alice"]

    assert stats.battles_used == 1
    assert stats.clutch_rating == 1.0


def test_equal_troop_strength_is_not_outnumbered():
    battles = [make_battle("bob", "Win", own_troops=10_000, enemy_troops=10_000)]

    stats = clutch_rating_by_general(battles)["bob"]

    assert stats.battles_used == 0
    assert stats.clutch_rating is None


def test_low_resource_tier_counts_as_playing_from_behind_even_when_not_outnumbered():
    battles = [
        make_battle("carol", "Loss", own_troops=10_000, enemy_troops=10_000, resource_backing_tier=2)
    ]

    stats = clutch_rating_by_general(battles)["carol"]

    assert stats.battles_used == 1
    assert stats.clutch_rating == 0.0


def test_resource_tier_three_is_not_disadvantaged():
    battles = [
        make_battle("dave", "Win", own_troops=10_000, enemy_troops=10_000, resource_backing_tier=3)
    ]

    stats = clutch_rating_by_general(battles)["dave"]

    assert stats.battles_used == 0
    assert stats.clutch_rating is None


def test_clutch_rating_is_mean_outcome_score_over_qualifying_battles_only():
    battles = [
        # not playing from behind -- excluded from the mean
        make_battle("erin", "Loss", own_troops=10_000, enemy_troops=5_000, resource_backing_tier=5),
        # outnumbered
        make_battle("erin", "Win", own_troops=5_000, enemy_troops=10_000),
        # resource-disadvantaged
        make_battle("erin", "Draw", own_troops=10_000, enemy_troops=10_000, resource_backing_tier=1),
        # outnumbered
        make_battle("erin", "Loss", own_troops=1_000, enemy_troops=2_000),
    ]

    stats = clutch_rating_by_general(battles)["erin"]

    # qualifying battles: Win, Draw, Loss -> (1.0 + 0.5 + 0.0) / 3
    assert stats.battles_used == 3
    assert stats.clutch_rating == (1.0 + 0.5 + 0.0) / 3


def test_generals_kept_separate():
    battles = [
        make_battle("alice", "Win", own_troops=5_000, enemy_troops=10_000),
        make_battle("bob", "Loss", own_troops=5_000, enemy_troops=10_000),
    ]

    stats = clutch_rating_by_general(battles)

    assert stats["alice"].clutch_rating == 1.0
    assert stats["bob"].clutch_rating == 0.0


def test_general_with_no_battles_is_absent():
    assert clutch_rating_by_general([]) == {}
