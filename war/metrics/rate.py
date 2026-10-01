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
* `decisive_win_rate` is, among wins that carry a `decisiveness` label, the
  fraction labeled `Strategic` or `Rout` (per `war/schema.py`'s own
  definition, the two levels that mean the result actually advanced the
  objective or broke the enemy's army, as opposed to `Tactical`/`Pyrrhic`
  wins that didn't convert — `squander.py` makes the identical split for its
  own metric). This schema used to carry a separate hand-judged
  `objective_secured` bool for exactly this question, but it was dropped
  (see PROGRESS.md Phase B): unlike `decisiveness`, which a deterministic
  pipeline can read off the infobox result text, "was the general's stated
  objective achieved" has no such source and would have stayed a manual
  judgment call forever. Wins with no `decisiveness` recorded are excluded
  from both the numerator and denominator, same as `squander.py`'s
  `wins_used` — we cannot judge conversion without the label. `None` when
  the general has no such wins to rate.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.records import Battle

_CONVERTED_LEVELS = {"Strategic", "Rout"}


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
        rated_wins = [b for b in wins if b.decisiveness is not None]
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
                sum(1 for b in rated_wins if b.decisiveness in _CONVERTED_LEVELS)
                / len(rated_wins)
                if rated_wins
                else None
            ),
        )
    return result
