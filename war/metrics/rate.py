"""Rate / per-battle stats: PLAN.md Section 4.

Design choices, since PLAN.md names the four stats but not their exact
formulas:

* `casualty_exchange_ratio` is enemy:own casualties computed from **career
  totals** (sum of enemy casualties over sum of own casualties), not an
  average of each battle's own ratio. Averaging per-battle ratios would let a
  single tiny skirmish with a freak ratio dominate the stat as much as a
  battle with 100x the casualties; totals weight every casualty equally,
  which matches how career batting-average-style stats are usually built.
  Undefined (`None`) when the general took zero career casualties, rather
  than raising or returning `inf` — the schema allows `own_casualties=0`.
* `avg_force_ratio_faced` is the mean, across battles, of
  `enemy_troop_strength / own_troop_strength` for that battle — this one
  *is* a per-battle average, because it's about how outnumbered the general
  was in a typical fight, not a career-wide troop total. >1 means typically
  outnumbered; <1 means typically had the numbers.
* `decisive_win_rate` is, among wins only, the fraction with
  `objective_secured=true` — reusing the schema's existing bool rather than
  re-deriving "decisive" from the `decisiveness` enum, since that field is
  literally defined as "was the stated objective achieved". `None` when the
  general has no wins to rate.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.records import Battle


@dataclass(frozen=True)
class RateStats:
    """Per-battle rate stats for one general."""

    general_id: str
    win_rate: float
    casualty_exchange_ratio: float | None
    avg_force_ratio_faced: float
    decisive_win_rate: float | None


def rate_stats_by_general(battles: list[Battle]) -> dict[str, RateStats]:
    """Compute per-battle rate stats per `general_id`.

    Generals with no rows in `battles` are simply absent from the result,
    same convention as `raw_stats_by_general`.
    """
    by_general: dict[str, list[Battle]] = defaultdict(list)
    for battle in battles:
        by_general[battle.general_id].append(battle)

    result = {}
    for general_id, rows in by_general.items():
        wins = [b for b in rows if b.outcome == "Win"]
        total_own_casualties = sum(b.own_casualties for b in rows)
        total_enemy_casualties = sum(b.enemy_casualties for b in rows)

        result[general_id] = RateStats(
            general_id=general_id,
            win_rate=len(wins) / len(rows),
            casualty_exchange_ratio=(
                total_enemy_casualties / total_own_casualties
                if total_own_casualties > 0
                else None
            ),
            avg_force_ratio_faced=(
                sum(b.enemy_troop_strength / b.own_troop_strength for b in rows) / len(rows)
            ),
            decisive_win_rate=(
                sum(1 for b in wins if b.objective_secured) / len(wins) if wins else None
            ),
        )
    return result
