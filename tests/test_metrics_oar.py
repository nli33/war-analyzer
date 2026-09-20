"""Phase 3 OAR (iterative Elo) solver: known-input/known-output cases on
synthetic battle sets, per SCOPE.md's verification method.

Elo iteration doesn't reduce to a one-line hand-computable fraction the way
the rate stats do, so these tests check the properties `war/metrics/oar.py`'s
docstring claims for the solver instead of one pinned magic number:
zero-sum conservation, monotonic direction, the core "beating a higher-rated
opponent earns more" comparison, and the no-opponent / off-roster edge cases.
"""

from war.metrics.oar import oar_ratings
from war.records import Battle


def make_battle(general_id, outcome, opponent_general_id, battle_id=None):
    """A Battle with only the fields oar_ratings reads set meaningfully."""
    return Battle(
        battle_id=battle_id or f"{general_id}-vs-{opponent_general_id}-{outcome}",
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
        opponent_general_id=opponent_general_id,
        resource_backing_tier=3,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def test_winner_rating_rises_and_loser_rating_falls():
    battles = [make_battle("alice", "Win", "bob")]

    ratings = oar_ratings(battles, base_rating=1500.0)

    assert ratings["alice"].rating > 1500.0
    assert ratings["bob"].rating < 1500.0


def test_ratings_are_zero_sum_across_a_single_matchup():
    battles = [make_battle("alice", "Win", "bob")]

    ratings = oar_ratings(battles, base_rating=1500.0)

    # every delta is applied +x/-x, so the pair's combined rating is conserved
    assert ratings["alice"].rating + ratings["bob"].rating == 1500.0 + 1500.0


def test_equal_and_opposite_records_end_up_equally_rated():
    # alice and bob split two battles evenly, symmetric record -> equal ratings
    battles = [
        make_battle("alice", "Win", "bob", battle_id="b1"),
        make_battle("alice", "Loss", "bob", battle_id="b2"),
    ]

    ratings = oar_ratings(battles, base_rating=1500.0)

    assert ratings["alice"].rating == ratings["bob"].rating == 1500.0


def test_beating_a_higher_rated_opponent_earns_more_than_beating_an_average_one():
    # "champ" earns an above-base rating by beating a separate general first,
    # then alice beats champ; compare against a separate world where alice
    # instead beats an average (never-played, base-rated) opponent.
    champ_pedigree = [make_battle("champ", "Win", "some_other_general")]
    champ_rating = oar_ratings(champ_pedigree, base_rating=1500.0)["champ"].rating
    assert champ_rating > 1500.0

    beats_champ = champ_pedigree + [make_battle("alice", "Win", "champ", battle_id="alice-champ")]
    beats_average = [make_battle("alice", "Win", "bob", battle_id="alice-bob")]

    gain_vs_champ = oar_ratings(beats_champ, base_rating=1500.0)["alice"].rating - 1500.0
    gain_vs_average = oar_ratings(beats_average, base_rating=1500.0)["alice"].rating - 1500.0

    assert gain_vs_champ > gain_vs_average


def test_battle_with_no_opponent_recorded_is_skipped_and_keeps_base_rating():
    battles = [make_battle("alice", "Win", None)]

    ratings = oar_ratings(battles, base_rating=1500.0)

    assert ratings["alice"].rating == 1500.0
    assert ratings["alice"].battles_rated == 0


def test_off_roster_opponent_is_included_with_a_default_rating():
    battles = [make_battle("alice", "Win", "some_unrostered_commander")]

    ratings = oar_ratings(battles, base_rating=1500.0)

    assert "some_unrostered_commander" in ratings
    assert ratings["some_unrostered_commander"].rating < 1500.0


def test_battles_rated_counts_only_battles_with_a_recorded_opponent():
    battles = [
        make_battle("alice", "Win", "bob", battle_id="b1"),
        make_battle("alice", "Win", None, battle_id="b2"),
    ]

    ratings = oar_ratings(battles, base_rating=1500.0)

    assert ratings["alice"].battles_rated == 1
    assert ratings["bob"].battles_rated == 1


def test_solver_is_deterministic():
    battles = [
        make_battle("alice", "Win", "bob", battle_id="b1"),
        make_battle("bob", "Win", "alice", battle_id="b2"),
        make_battle("alice", "Win", "carol", battle_id="b3"),
    ]

    first = oar_ratings(battles)
    second = oar_ratings(battles)

    assert first == second


def test_general_with_no_battles_is_absent():
    assert oar_ratings([]) == {}
