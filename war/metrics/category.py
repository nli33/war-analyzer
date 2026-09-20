"""Category Rankings: PLAN.md Section 6.2.

PLAN.md's spec: "separate ordered lists for: Win Rate, Casualty Efficiency,
Opponent-Adjusted Rating, Clutch Rating, Squander Index, Longevity-Adjusted
Value" — six independent single-stat rankings, unlike `composite.py`'s one
weighted combination. Design choices, since PLAN.md names the six categories
but not the ranking mechanics:

* Each category ranks generals by its own already-computed metric value
  (`rate.py`'s `win_rate`/`casualty_exchange_ratio`, `oar.py`'s `rating`,
  `clutch.py`'s `clutch_rating`, `squander.py`'s `squander_index`,
  `longevity.py`'s `longevity_adjusted_value`) directly — no z-scoring or
  era cohorting, unlike `composite.py`. PLAN.md's era-normalization
  paragraph is scoped to "any cross-era composite"; a single-stat category
  list is not a combination of multiple inputs, so nothing needs a common
  unit to begin with.
* Sort direction is metric-specific: five categories are "higher is
  better" (descending). Squander Index is the one exception — PLAN.md
  defines it as a failure rate ("rate at which tactical wins failed to
  convert"), so a *lower* Squander Index is the better result and that
  category sorts ascending, unlike the other five and unlike every
  z-scored input in `composite.py` (which are all oriented higher-is-
  better already).
* Each category independently excludes generals whose value is `None` for
  that specific metric (`casualty_exchange_ratio` at zero career casualties,
  `clutch_rating`/`squander_index` at zero qualifying battles/labeled wins)
  rather than assigning a placeholder value or dropping that general from
  every other category too — a general can rank in Win Rate while being
  absent from Squander Index. This is the category-ranking analog of
  `composite.py`'s per-metric `None` exclusion, applied per-list instead of
  folded into one combined score.
* "Roster" (the set of generals eligible for any category) is every
  `general_id` that commands at least one row in `battles` --
  `rate_stats_by_general`'s keys, the same battle.general_id-keyed
  convention every Phase 3 metric module already uses. This excludes
  off-roster `opponent_general_id` values from `opponent_adjusted_rating`
  even though `oar_ratings` solves a rating for them too, the same
  off-roster-exclusion `composite.py` documents for the same reason: they
  never command a battle in this dataset, so they are opponents, not ranked
  participants.
"""

from dataclasses import dataclass

from war.metrics.clutch import clutch_rating_by_general
from war.metrics.longevity import longevity_adjusted_value_by_general
from war.metrics.oar import oar_ratings
from war.metrics.rate import rate_stats_by_general
from war.metrics.squander import squander_index_by_general
from war.records import Battle, General


@dataclass(frozen=True)
class CategoryRankEntry:
    """One general's rank and raw metric value within a single category."""

    general_id: str
    rank: int
    value: float


def _ranked(values: dict[str, float], descending: bool) -> list[CategoryRankEntry]:
    ordered = sorted(values.items(), key=lambda item: item[1], reverse=descending)
    return [
        CategoryRankEntry(general_id=general_id, rank=rank, value=value)
        for rank, (general_id, value) in enumerate(ordered, start=1)
    ]


def category_rankings(
    battles: list[Battle], generals: list[General]
) -> dict[str, list[CategoryRankEntry]]:
    """Compute PLAN.md Section 6.2's six category rankings.

    Returns a dict keyed by category name (`win_rate`, `casualty_efficiency`,
    `opponent_adjusted_rating`, `clutch_rating`, `squander_index`,
    `longevity_adjusted_value`), each value a list of `CategoryRankEntry`
    sorted best-first (see this module's docstring for each category's sort
    direction and `None`-exclusion rule). Empty `battles` returns every
    category mapped to an empty list.
    """
    rate_stats = rate_stats_by_general(battles)
    oar = oar_ratings(battles)
    clutch = clutch_rating_by_general(battles)
    squander = squander_index_by_general(battles)
    longevity = longevity_adjusted_value_by_general(battles, generals)

    roster_ids = set(rate_stats)

    return {
        "win_rate": _ranked(
            {gid: rate_stats[gid].win_rate for gid in roster_ids}, descending=True
        ),
        "casualty_efficiency": _ranked(
            {
                gid: rate_stats[gid].casualty_exchange_ratio
                for gid in roster_ids
                if rate_stats[gid].casualty_exchange_ratio is not None
            },
            descending=True,
        ),
        "opponent_adjusted_rating": _ranked(
            {gid: oar[gid].rating for gid in roster_ids}, descending=True
        ),
        "clutch_rating": _ranked(
            {
                gid: clutch[gid].clutch_rating
                for gid in roster_ids
                if clutch[gid].clutch_rating is not None
            },
            descending=True,
        ),
        "squander_index": _ranked(
            {
                gid: squander[gid].squander_index
                for gid in roster_ids
                if squander[gid].squander_index is not None
            },
            descending=False,
        ),
        "longevity_adjusted_value": _ranked(
            {gid: longevity[gid].longevity_adjusted_value for gid in roster_ids},
            descending=True,
        ),
    }
