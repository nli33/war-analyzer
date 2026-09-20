"""Phase 3 rate stats: hand-computed expected values on synthetic battles."""

from war.metrics.rate import rate_stats_by_general
from war.records import Battle


def make_battle(
    general_id,
    outcome,
    own_troops,
    enemy_troops,
    own_casualties,
    enemy_casualties,
    objective_secured=False,
):
    """A Battle with only the fields rate_stats_by_general reads set meaningfully."""
    return Battle(
        battle_id=f"{general_id}-{outcome}-{own_troops}-{enemy_troops}-{own_casualties}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=own_troops,
        enemy_troop_strength=enemy_troops,
        own_casualties=own_casualties,
        enemy_casualties=enemy_casualties,
        outcome=outcome,
        decisiveness="Strategic" if objective_secured else None,
        objective_secured=objective_secured,
        opponent_general_id=None,
        resource_backing_tier=3,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def test_win_rate():
    battles = [
        make_battle("alice", "Win", 10_000, 10_000, 500, 2_000, objective_secured=True),
        make_battle("alice", "Loss", 8_000, 8_000, 3_000, 1_000),
        make_battle("alice", "Draw", 5_000, 5_000, 200, 200),
        make_battle("alice", "Win", 5_000, 5_000, 100, 500, objective_secured=False),
    ]

    stats = rate_stats_by_general(battles)["alice"]

    assert stats.win_rate == 2 / 4


def test_casualty_exchange_ratio_uses_career_totals_not_average_of_ratios():
    battles = [
        make_battle("bob", "Win", 10_000, 10_000, 1_000, 4_000, objective_secured=True),
        make_battle("bob", "Loss", 10_000, 10_000, 3_000, 1_000),
    ]

    stats = rate_stats_by_general(battles)["bob"]

    # totals: 5000 enemy : 4000 own -- not the average of 4.0 and 1/3 per-battle
    assert stats.casualty_exchange_ratio == 5_000 / 4_000


def test_casualty_exchange_ratio_none_when_no_own_casualties():
    battles = [make_battle("carol", "Win", 1_000, 1_000, 0, 500, objective_secured=True)]

    stats = rate_stats_by_general(battles)["carol"]

    assert stats.casualty_exchange_ratio is None


def test_avg_force_ratio_faced_is_mean_of_per_battle_ratios():
    battles = [
        make_battle("dave", "Win", 5_000, 10_000, 1, 1, objective_secured=True),
        make_battle("dave", "Win", 10_000, 5_000, 1, 1, objective_secured=True),
    ]

    stats = rate_stats_by_general(battles)["dave"]

    # (10000/5000 + 5000/10000) / 2 = (2.0 + 0.5) / 2 = 1.25
    assert stats.avg_force_ratio_faced == 1.25


def test_decisive_win_rate_only_counts_objective_secured_among_wins():
    battles = [
        make_battle("erin", "Win", 1, 1, 0, 1, objective_secured=True),
        make_battle("erin", "Win", 1, 1, 0, 1, objective_secured=False),
        make_battle("erin", "Loss", 1, 1, 1, 0),
    ]

    stats = rate_stats_by_general(battles)["erin"]

    assert stats.decisive_win_rate == 1 / 2


def test_decisive_win_rate_none_with_no_wins():
    battles = [make_battle("frank", "Loss", 1, 1, 1, 0)]

    stats = rate_stats_by_general(battles)["frank"]

    assert stats.decisive_win_rate is None


def test_generals_kept_separate():
    battles = [
        make_battle("alice", "Win", 1, 1, 0, 1, objective_secured=True),
        make_battle("bob", "Loss", 1, 1, 1, 0),
    ]

    stats = rate_stats_by_general(battles)

    assert stats["alice"].win_rate == 1.0
    assert stats["bob"].win_rate == 0.0


def test_general_with_no_battles_is_absent():
    assert rate_stats_by_general([]) == {}
