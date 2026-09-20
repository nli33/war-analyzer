"""Phase 3 Longevity-Adjusted Value: hand-computed expected values on synthetic data."""

from war.metrics.longevity import longevity_adjusted_value_by_general
from war.records import Battle, General


def make_battle(general_id, outcome, battle_id=None):
    """A Battle with only the fields longevity_adjusted_value_by_general reads set meaningfully."""
    return Battle(
        battle_id=battle_id or f"{general_id}-{outcome}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=10_000,
        enemy_troop_strength=10_000,
        own_casualties=1,
        enemy_casualties=1,
        outcome=outcome,
        decisiveness=None,
        objective_secured=False,
        opponent_general_id=None,
        resource_backing_tier=3,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def make_general(general_id, career_start_year, career_end_year):
    return General(
        general_id=general_id,
        display_name=general_id,
        era="Industrial",
        career_start_year=career_start_year,
        career_end_year=career_end_year,
        notes=None,
    )


def test_single_win_single_year_career():
    battles = [make_battle("alice", "Win")]
    generals = [make_general("alice", 1900, 1900)]

    stats = longevity_adjusted_value_by_general(battles, generals)["alice"]

    assert stats.career_value == 1.0
    assert stats.career_length_years == 1
    assert stats.longevity_adjusted_value == 1.0


def test_wins_draws_and_losses_sum_to_career_value():
    battles = [
        make_battle("bob", "Win", battle_id="bob-1"),
        make_battle("bob", "Draw", battle_id="bob-2"),
        make_battle("bob", "Loss", battle_id="bob-3"),
    ]
    generals = [make_general("bob", 1900, 1901)]

    stats = longevity_adjusted_value_by_general(battles, generals)["bob"]

    assert stats.career_value == 1.5
    assert stats.career_length_years == 2
    assert stats.longevity_adjusted_value == 0.75


def test_short_dominant_peak_beats_long_volume_career():
    # Same total career value (4 wins), but carol's career is a third as long.
    carol_battles = [make_battle("carol", "Win", battle_id=f"carol-{i}") for i in range(4)]
    dave_battles = [make_battle("dave", "Win", battle_id=f"dave-{i}") for i in range(4)]
    generals = [
        make_general("carol", 1900, 1902),
        make_general("dave", 1900, 1908),
    ]

    stats = longevity_adjusted_value_by_general(carol_battles + dave_battles, generals)

    assert stats["carol"].career_value == stats["dave"].career_value == 4.0
    assert stats["carol"].longevity_adjusted_value > stats["dave"].longevity_adjusted_value


def test_career_span_crosses_bc_ad_boundary_with_no_year_zero():
    # Astronomical year numbering: -0002 (2 BC), -0001 (1 BC), 0000, 0001, 0002 -> 5 years.
    battles = [make_battle("erin", "Win")]
    generals = [make_general("erin", -2, 2)]

    stats = longevity_adjusted_value_by_general(battles, generals)["erin"]

    assert stats.career_length_years == 5
    assert stats.longevity_adjusted_value == 1.0 / 5


def test_general_with_no_battles_is_absent():
    generals = [make_general("frank", 1900, 1910)]
    assert longevity_adjusted_value_by_general([], generals) == {}
