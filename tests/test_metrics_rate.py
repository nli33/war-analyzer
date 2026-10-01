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
    decisiveness=None,
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
        decisiveness=decisiveness,
        opponent_general_id=None,
        resource_backing_tier=3,
        tech_era_tier=3,
        source_citation="test fixture",
        notes=None,
    )


def test_win_rate():
    battles = [
        make_battle("alice", "Win", 10_000, 10_000, 500, 2_000, decisiveness="Strategic"),
        make_battle("alice", "Loss", 8_000, 8_000, 3_000, 1_000),
        make_battle("alice", "Draw", 5_000, 5_000, 200, 200),
        make_battle("alice", "Win", 5_000, 5_000, 100, 500, decisiveness="Tactical"),
    ]

    stats = rate_stats_by_general(battles)["alice"]

    assert stats.win_rate == 2 / 4


def test_casualty_exchange_ratio_uses_career_totals_not_average_of_ratios():
    battles = [
        make_battle("bob", "Win", 10_000, 10_000, 1_000, 4_000, decisiveness="Strategic"),
        make_battle("bob", "Loss", 10_000, 10_000, 3_000, 1_000),
    ]

    stats = rate_stats_by_general(battles)["bob"]

    # totals: 5000 enemy : 4000 own -- not the average of 4.0 and 1/3 per-battle
    assert stats.casualty_exchange_ratio == 5_000 / 4_000


def test_casualty_exchange_ratio_none_when_no_own_casualties():
    battles = [make_battle("carol", "Win", 1_000, 1_000, 0, 500, decisiveness="Strategic")]

    stats = rate_stats_by_general(battles)["carol"]

    assert stats.casualty_exchange_ratio is None


def test_avg_force_ratio_faced_is_mean_of_per_battle_ratios():
    battles = [
        make_battle("dave", "Win", 5_000, 10_000, 1, 1, decisiveness="Strategic"),
        make_battle("dave", "Win", 10_000, 5_000, 1, 1, decisiveness="Strategic"),
    ]

    stats = rate_stats_by_general(battles)["dave"]

    # (10000/5000 + 5000/10000) / 2 = (2.0 + 0.5) / 2 = 1.25
    assert stats.avg_force_ratio_faced == 1.25


def test_decisive_win_rate_only_counts_strategic_or_rout_among_rated_wins():
    battles = [
        make_battle("erin", "Win", 1, 1, 0, 1, decisiveness="Strategic"),
        make_battle("erin", "Win", 1, 1, 0, 1, decisiveness="Tactical"),
        make_battle("erin", "Loss", 1, 1, 1, 0),
    ]

    stats = rate_stats_by_general(battles)["erin"]

    assert stats.decisive_win_rate == 1 / 2


def test_decisive_win_rate_excludes_wins_without_a_decisiveness_label():
    battles = [
        make_battle("gail", "Win", 1, 1, 0, 1, decisiveness="Strategic"),
        make_battle("gail", "Win", 1, 1, 0, 1),  # no decisiveness recorded
    ]

    stats = rate_stats_by_general(battles)["gail"]

    # the unlabeled win is excluded from both numerator and denominator, not
    # counted as "not decisive" -- same convention as squander.py's wins_used.
    assert stats.decisive_win_rate == 1.0


def test_decisive_win_rate_none_with_no_wins():
    battles = [make_battle("frank", "Loss", 1, 1, 1, 0)]

    stats = rate_stats_by_general(battles)["frank"]

    assert stats.decisive_win_rate is None


def test_avg_force_ratio_faced_skips_rows_missing_either_strength_field():
    battles = [
        make_battle("hank", "Win", 5_000, 10_000, 1, 1, decisiveness="Strategic"),
        make_battle("hank", "Loss", None, 10_000, 1, 1),  # own strength missing
        make_battle("hank", "Loss", 10_000, None, 1, 1),  # enemy strength missing
    ]

    stats = rate_stats_by_general(battles)["hank"]

    # only the first row has both sides recorded, so the average is just its ratio
    assert stats.avg_force_ratio_faced == 2.0


def test_avg_force_ratio_faced_none_when_no_row_has_both_strengths():
    battles = [make_battle("ivy", "Win", None, 10_000, 1, 1, decisiveness="Strategic")]

    stats = rate_stats_by_general(battles)["ivy"]

    assert stats.avg_force_ratio_faced is None


def test_casualty_exchange_ratio_sums_only_rows_with_that_sides_casualties():
    battles = [
        make_battle("jill", "Win", 1, 1, 1_000, None, decisiveness="Strategic"),
        make_battle("jill", "Loss", 1, 1, None, 4_000),
    ]

    stats = rate_stats_by_general(battles)["jill"]

    # own total: 1000 (second row's own_casualties missing, skipped)
    # enemy total: 4000 (first row's enemy_casualties missing, skipped)
    assert stats.casualty_exchange_ratio == 4_000 / 1_000


def test_casualty_exchange_ratio_none_when_one_side_never_recorded():
    # own_casualties present and nonzero on both rows, enemy_casualties missing
    # on every row -- not "zero enemy casualties," genuinely never recorded.
    battles = [
        make_battle("kate", "Win", 1, 1, 500, None, decisiveness="Strategic"),
        make_battle("kate", "Loss", 1, 1, 1_000, None),
    ]

    stats = rate_stats_by_general(battles)["kate"]

    assert stats.casualty_exchange_ratio is None


def test_generals_kept_separate():
    battles = [
        make_battle("alice", "Win", 1, 1, 0, 1, decisiveness="Strategic"),
        make_battle("bob", "Loss", 1, 1, 1, 0),
    ]

    stats = rate_stats_by_general(battles)

    assert stats["alice"].win_rate == 1.0
    assert stats["bob"].win_rate == 0.0


def test_general_with_no_battles_is_absent():
    assert rate_stats_by_general([]) == {}
