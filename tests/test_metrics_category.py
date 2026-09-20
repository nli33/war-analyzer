"""Phase 5 category rankings: hand-computed expected values on synthetic
data, per SCOPE.md's verification method (same style as the Phase 3 metric
tests and test_metrics_composite.py).
"""

from war.metrics.category import category_rankings
from war.records import Battle, General


def make_battle(
    general_id,
    outcome,
    battle_id,
    opponent_general_id=None,
    decisiveness=None,
    objective_secured=False,
    own_troop_strength=10_000,
    enemy_troop_strength=10_000,
    own_casualties=100,
    enemy_casualties=100,
    resource_backing_tier=3,
    era="Industrial",
):
    return Battle(
        battle_id=battle_id,
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era=era,
        own_troop_strength=own_troop_strength,
        enemy_troop_strength=enemy_troop_strength,
        own_casualties=own_casualties,
        enemy_casualties=enemy_casualties,
        outcome=outcome,
        decisiveness=decisiveness,
        objective_secured=objective_secured,
        opponent_general_id=opponent_general_id,
        resource_backing_tier=resource_backing_tier,
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


CATEGORY_KEYS = {
    "win_rate",
    "casualty_efficiency",
    "opponent_adjusted_rating",
    "clutch_rating",
    "squander_index",
    "longevity_adjusted_value",
}


def test_no_battles_returns_every_category_as_empty_list():
    result = category_rankings([], [])

    assert set(result) == CATEGORY_KEYS
    assert all(entries == [] for entries in result.values())


def test_win_rate_ranks_descending_with_ranks_starting_at_one():
    battles = [
        make_battle("alice", "Win", "a1"),
        make_battle("alice", "Win", "a2"),
        make_battle("bob", "Win", "b1"),
        make_battle("bob", "Loss", "b2"),
    ]
    generals = [make_general("alice"), make_general("bob")]

    result = category_rankings(battles, generals)
    entries = result["win_rate"]

    assert [e.general_id for e in entries] == ["alice", "bob"]
    assert entries[0].rank == 1 and entries[0].value == 1.0
    assert entries[1].rank == 2 and entries[1].value == 0.5


def test_casualty_efficiency_excludes_general_with_zero_career_casualties():
    battles = [
        make_battle("alice", "Win", "a1", own_casualties=0, enemy_casualties=500),
        make_battle("bob", "Win", "b1", own_casualties=10, enemy_casualties=20),
    ]
    generals = [make_general("alice"), make_general("bob")]

    result = category_rankings(battles, generals)
    entries = result["casualty_efficiency"]

    assert [e.general_id for e in entries] == ["bob"]
    assert entries[0].value == 2.0


def test_opponent_adjusted_rating_excludes_off_roster_opponent():
    # "casca" only ever appears as an opponent, never as a commanding
    # general_id, so she is not part of the roster even though oar_ratings
    # solves a rating for her too (see oar.py's docstring).
    battles = [make_battle("alice", "Win", "a1", opponent_general_id="casca")]
    generals = [make_general("alice")]

    result = category_rankings(battles, generals)
    entries = result["opponent_adjusted_rating"]

    assert [e.general_id for e in entries] == ["alice"]


def test_clutch_rating_excludes_general_with_no_qualifying_battles():
    battles = [
        # alice is outnumbered (enemy > own): qualifies as "playing from behind".
        make_battle(
            "alice", "Win", "a1", own_troop_strength=10_000, enemy_troop_strength=20_000
        ),
        # bob is never outnumbered and never resource-disadvantaged: no
        # qualifying battle, so clutch_rating is None and he's excluded.
        make_battle(
            "bob",
            "Win",
            "b1",
            own_troop_strength=10_000,
            enemy_troop_strength=5_000,
            resource_backing_tier=3,
        ),
    ]
    generals = [make_general("alice"), make_general("bob")]

    result = category_rankings(battles, generals)
    entries = result["clutch_rating"]

    assert [e.general_id for e in entries] == ["alice"]
    assert entries[0].value == 1.0


def test_squander_index_sorts_ascending_lower_is_better_and_excludes_unlabeled_wins():
    battles = [
        # alice's win converted (Strategic): squander_index 0.0, the "best" result.
        make_battle("alice", "Win", "a1", decisiveness="Strategic", objective_secured=True),
        # bob's win did not convert (Tactical): squander_index 1.0, the "worst" result.
        make_battle("bob", "Win", "b1", decisiveness="Tactical", objective_secured=False),
        # carol's win has no decisiveness label at all: excluded, wins_used=0.
        make_battle("carol", "Win", "c1", decisiveness=None),
    ]
    generals = [make_general("alice"), make_general("bob"), make_general("carol")]

    result = category_rankings(battles, generals)
    entries = result["squander_index"]

    assert [e.general_id for e in entries] == ["alice", "bob"]
    assert entries[0].value == 0.0
    assert entries[1].value == 1.0


def test_longevity_adjusted_value_present_for_every_roster_general():
    battles = [
        make_battle("alice", "Win", "a1"),
        make_battle("bob", "Loss", "b1"),
    ]
    generals = [
        make_general("alice", career_start_year=1900, career_end_year=1900),
        make_general("bob", career_start_year=1900, career_end_year=1901),
    ]

    result = category_rankings(battles, generals)
    entries = {e.general_id: e for e in result["longevity_adjusted_value"]}

    assert set(entries) == {"alice", "bob"}
    assert entries["alice"].value == 1.0
    assert entries["bob"].value == 0.0
