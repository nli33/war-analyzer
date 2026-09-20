"""Clutch Rating: PLAN.md Section 4's "playing from behind" stat.

PLAN.md's spec: "performance specifically in battles where own force was
outnumbered or resource-disadvantaged." Design choices, since PLAN.md names
the condition but not the exact thresholds or how performance rolls up:

* A battle counts as "playing from behind" if `enemy_troop_strength >
  own_troop_strength` (outnumbered, the same `force_ratio` used by
  `rate.py`'s `avg_force_ratio_faced` and `war_residual.py`, here just
  compared against the break-even point of 1) **or** `resource_backing_tier
  <= 2` (the bottom two rungs of the schema's 1-5 scale). The tier is
  read as an absolute standard — "was this general poorly resourced at the
  time" — rather than relative to the opponent's own backing, since the
  schema only records `resource_backing_tier` for the roster general's own
  side, never the opponent's; there is nothing to compare it against
  per-battle. On the real 83-row dataset, tier <=2 selects 24 rows and
  outnumbered selects 36, so neither condition is vacuous or near-universal.
* Performance is the **mean outcome score** (Win/Draw/Loss -> 1.0/0.5/0.0,
  the same mapping `oar.py`/`war_residual.py` already use) across only the
  qualifying "behind" battles — not a residual against expectation. PLAN.md
  asks for raw performance under adversity, not performance-above-expected
  under adversity; `war_residual.py` already covers the "above expected"
  framing separately, and combining the two ideas into one stat would
  duplicate it.
* `None` when a general has zero qualifying battles, same
  no-data-no-number convention as `rate.py`'s `casualty_exchange_ratio` and
  `decisive_win_rate`.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.records import Battle

_ACTUAL_SCORE = {"Win": 1.0, "Draw": 0.5, "Loss": 0.0}
_RESOURCE_DISADVANTAGED_TIER = 2


def _playing_from_behind(battle: Battle) -> bool:
    return (
        battle.enemy_troop_strength > battle.own_troop_strength
        or battle.resource_backing_tier <= _RESOURCE_DISADVANTAGED_TIER
    )


@dataclass(frozen=True)
class ClutchRating:
    """Mean outcome score for one general, restricted to "playing from behind" battles."""

    general_id: str
    clutch_rating: float | None
    battles_used: int


def clutch_rating_by_general(battles: list[Battle]) -> dict[str, ClutchRating]:
    """Compute Clutch Rating per `general_id`.

    Generals with no rows in `battles` are absent from the result, same
    convention as `raw_stats_by_general`. A general with rows but none of
    them "playing from behind" gets `clutch_rating=None` with
    `battles_used=0`, rather than being dropped entirely.
    """
    by_general: dict[str, list[Battle]] = defaultdict(list)
    for battle in battles:
        by_general[battle.general_id].append(battle)

    result = {}
    for general_id, rows in by_general.items():
        behind_rows = [b for b in rows if _playing_from_behind(b)]
        result[general_id] = ClutchRating(
            general_id=general_id,
            clutch_rating=(
                sum(_ACTUAL_SCORE[b.outcome] for b in behind_rows) / len(behind_rows)
                if behind_rows
                else None
            ),
            battles_used=len(behind_rows),
        )
    return result
