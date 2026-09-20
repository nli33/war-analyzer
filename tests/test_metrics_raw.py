"""Phase 3 raw/counting stats: hand-computed expected values on synthetic battles."""

from war.metrics.raw import raw_stats_by_general
from war.records import Battle


def make_battle(general_id, outcome, own_troops, own_casualties, enemy_casualties):
    """A Battle with only the fields raw_stats_by_general reads set meaningfully."""
    return Battle(
        battle_id=f"{general_id}-{outcome}-{own_troops}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=own_troops,
        enemy_troop_strength=own_troops,
        own_casualties=own_casualties,
        enemy_casualties=enemy_casualties,
        outcome=outcome,
        decisiveness="Tactical" if outcome == "Win" else None,
        objective_secured=outcome == "Win",
        opponent_general_id=None,
        resource_backing_tier=3,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def test_single_general_totals():
    battles = [
        make_battle("alice", "Win", own_troops=10_000, own_casualties=500, enemy_casualties=2_000),
        make_battle("alice", "Loss", own_troops=8_000, own_casualties=3_000, enemy_casualties=1_000),
        make_battle("alice", "Draw", own_troops=5_000, own_casualties=200, enemy_casualties=200),
    ]

    stats = raw_stats_by_general(battles)["alice"]

    assert stats.battles_commanded == 3
    assert stats.wins == 1
    assert stats.losses == 1
    assert stats.draws == 1
    assert stats.total_own_troops == 10_000 + 8_000 + 5_000
    assert stats.total_enemy_casualties_inflicted == 2_000 + 1_000 + 200
    assert stats.total_own_casualties_taken == 500 + 3_000 + 200


def test_generals_are_kept_separate():
    battles = [
        make_battle("alice", "Win", own_troops=10_000, own_casualties=100, enemy_casualties=1_000),
        make_battle("bob", "Win", own_troops=1_000, own_casualties=10, enemy_casualties=50),
        make_battle("bob", "Win", own_troops=2_000, own_casualties=20, enemy_casualties=60),
    ]

    stats = raw_stats_by_general(battles)

    assert stats["alice"].battles_commanded == 1
    assert stats["bob"].battles_commanded == 2
    assert stats["bob"].total_own_troops == 3_000
    assert stats["bob"].wins == 2


def test_general_with_no_battles_is_absent():
    stats = raw_stats_by_general([])
    assert stats == {}


def test_all_outcome_kinds_counted_independently():
    battles = [
        make_battle("carol", "Win", 1, 0, 0),
        make_battle("carol", "Win", 1, 0, 0),
        make_battle("carol", "Loss", 1, 0, 0),
        make_battle("carol", "Draw", 1, 0, 0),
    ]

    stats = raw_stats_by_general(battles)["carol"]

    assert (stats.wins, stats.losses, stats.draws) == (2, 1, 1)
    assert stats.wins + stats.losses + stats.draws == stats.battles_commanded
