"""Opponent-Adjusted Rating (OAR): PLAN.md Section 4's Elo-style iterative rating.

PLAN.md's spec: "ratings for all generals are solved simultaneously/
iteratively until convergent" — beating a highly-rated opponent boosts a
rating more than beating a weak one. Design choices, since PLAN.md names the
approach but not the exact update rule:

* Standard Elo expected-score formula, `1 / (1 + 10**((opp - own) / 400))`,
  with `Win`/`Draw`/`Loss` mapped to actual scores `1.0`/`0.5`/`0.0`.
* Each epoch is a **synchronous batch update**: every battle's rating delta
  is computed from ratings frozen at the start of the epoch, then all deltas
  are summed and applied at once. This makes the result independent of the
  order battles happen to appear in `data/battles.csv`, matching "solved
  simultaneously" rather than a chess-clock-style running update.
* Every delta is applied symmetrically (winner +x, loser -x), so the sum of
  all ratings is conserved every epoch — a zero-sum property, same as
  standard Elo, and a cheap invariant to check in tests.
* **Decaying step size** (`k_factor * decay**epoch`): a general with a
  perfect record in this dataset (e.g. Alexander the Great — every row a
  Win) has no losses to balance the expected-score math, so a constant-K
  iterative Elo update never reaches a fixed point for that general; the
  rating gap keeps growing (logarithmically) forever. Decaying the step
  size guarantees the *sum* of all future deltas is bounded (a geometric
  series), so the solver always converges to a finite rating even for an
  undefeated or winless general, at the cost of the final number being a
  step-size-dependent approximation rather than a "true" fixed point for
  those edge cases. Well-mixed records (most of the roster) converge to the
  same fixed point regardless of decay, well before decay would matter.
* Battles with no `opponent_general_id` (a handful of multi-faction sieges
  and battles against an unnamed force) are skipped for rating purposes —
  Elo needs an opponent to compare against. They still count toward
  raw/rate stats elsewhere, just not here.
* `opponent_general_id` values with no row in `generals.csv` (most of them —
  this dataset only curates the roster's own side) are still included as
  full participants in the rating graph, starting from the same base rating
  as everyone else, per the project's existing "off-roster opponents get a
  default rating in the OAR solver" decision (see PROGRESS.md notes) rather
  than requiring 50+ extra curated opponent rows.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.records import Battle

_ACTUAL_SCORE = {"Win": 1.0, "Draw": 0.5, "Loss": 0.0}


@dataclass(frozen=True)
class OARRating:
    """Solved Elo-style rating for one participant (roster general or opponent)."""

    general_id: str
    rating: float
    battles_rated: int


def oar_ratings(
    battles: list[Battle],
    k_factor: float = 32.0,
    base_rating: float = 1500.0,
    decay: float = 0.9,
    tolerance: float = 1e-6,
    max_epochs: int = 2000,
) -> dict[str, OARRating]:
    """Solve Elo-style Opponent-Adjusted Ratings for every participant.

    Participants are every `general_id` plus every non-empty
    `opponent_general_id` appearing in `battles`. A participant who never
    appears in a battle with a recorded opponent keeps `base_rating`
    untouched.
    """
    participants: set[str] = set()
    rated_battles: list[Battle] = []
    for battle in battles:
        participants.add(battle.general_id)
        if battle.opponent_general_id:
            participants.add(battle.opponent_general_id)
            rated_battles.append(battle)

    ratings = {pid: base_rating for pid in participants}

    battles_rated: dict[str, int] = defaultdict(int)
    for battle in rated_battles:
        battles_rated[battle.general_id] += 1
        battles_rated[battle.opponent_general_id] += 1

    for epoch in range(1, max_epochs + 1):
        k_epoch = k_factor * (decay**epoch)
        deltas: dict[str, float] = defaultdict(float)
        for battle in rated_battles:
            own_rating = ratings[battle.general_id]
            opp_rating = ratings[battle.opponent_general_id]
            expected = 1.0 / (1.0 + 10 ** ((opp_rating - own_rating) / 400.0))
            actual = _ACTUAL_SCORE[battle.outcome]
            change = k_epoch * (actual - expected)
            deltas[battle.general_id] += change
            deltas[battle.opponent_general_id] -= change

        max_delta = max((abs(d) for d in deltas.values()), default=0.0)
        for pid, delta in deltas.items():
            ratings[pid] += delta
        if max_delta < tolerance:
            break

    return {
        pid: OARRating(
            general_id=pid,
            rating=ratings[pid],
            battles_rated=battles_rated.get(pid, 0),
        )
        for pid in participants
    }
