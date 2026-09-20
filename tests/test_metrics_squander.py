"""Phase 3 Squander Index: hand-computed expected values on synthetic battles."""

from war.metrics.squander import squander_index_by_general
from war.records import Battle


def make_battle(general_id, outcome, decisiveness, battle_id=None):
    """A Battle with only the fields squander_index_by_general reads set meaningfully."""
    return Battle(
        battle_id=battle_id or f"{general_id}-{outcome}-{decisiveness}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=10_000,
        enemy_troop_strength=10_000,
        own_casualties=1,
        enemy_casualties=1,
        outcome=outcome,
        decisiveness=decisiveness,
        objective_secured=False,
        opponent_general_id=None,
        resource_backing_tier=3,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def test_tactical_win_counts_as_squandered():
    battles = [make_battle("alice", "Win", "Tactical")]

    stats = squander_index_by_general(battles)["alice"]

    assert stats.wins_used == 1
    assert stats.squander_index == 1.0


def test_pyrrhic_win_counts_as_squandered():
    battles = [make_battle("bob", "Win", "Pyrrhic")]

    stats = squander_index_by_general(battles)["bob"]

    assert stats.wins_used == 1
    assert stats.squander_index == 1.0


def test_strategic_win_does_not_count_as_squandered():
    battles = [make_battle("carol", "Win", "Strategic")]

    stats = squander_index_by_general(battles)["carol"]

    assert stats.wins_used == 1
    assert stats.squander_index == 0.0


def test_rout_win_does_not_count_as_squandered():
    battles = [make_battle("dave", "Win", "Rout")]

    stats = squander_index_by_general(battles)["dave"]

    assert stats.wins_used == 1
    assert stats.squander_index == 0.0


def test_losses_and_draws_are_excluded_regardless_of_decisiveness():
    battles = [
        make_battle("erin", "Loss", "Rout", battle_id="erin-loss"),
        make_battle("erin", "Draw", None, battle_id="erin-draw"),
        make_battle("erin", "Win", "Tactical", battle_id="erin-win"),
    ]

    stats = squander_index_by_general(battles)["erin"]

    assert stats.wins_used == 1
    assert stats.squander_index == 1.0


def test_win_with_no_decisiveness_recorded_is_excluded_from_denominator():
    battles = [
        make_battle("frank", "Win", None, battle_id="frank-unlabeled"),
        make_battle("frank", "Win", "Strategic", battle_id="frank-labeled"),
    ]

    stats = squander_index_by_general(battles)["frank"]

    assert stats.wins_used == 1
    assert stats.squander_index == 0.0


def test_mixed_wins_give_fraction_squandered():
    battles = [
        make_battle("grace", "Win", "Tactical", battle_id="grace-1"),
        make_battle("grace", "Win", "Pyrrhic", battle_id="grace-2"),
        make_battle("grace", "Win", "Strategic", battle_id="grace-3"),
        make_battle("grace", "Win", "Rout", battle_id="grace-4"),
    ]

    stats = squander_index_by_general(battles)["grace"]

    assert stats.wins_used == 4
    assert stats.squander_index == 2 / 4


def test_general_with_wins_but_no_decisiveness_labels_gets_none():
    battles = [make_battle("henry", "Win", None)]

    stats = squander_index_by_general(battles)["henry"]

    assert stats.wins_used == 0
    assert stats.squander_index is None


def test_general_with_no_wins_gets_none():
    battles = [make_battle("iris", "Loss", None)]

    stats = squander_index_by_general(battles)["iris"]

    assert stats.wins_used == 0
    assert stats.squander_index is None


def test_general_with_no_battles_is_absent():
    assert squander_index_by_general([]) == {}
