"""Raw / counting stats: PLAN.md Section 4, career totals.

PLAN.md lists "battles commanded" and "campaigns commanded" as separate
counts, but PLAN.md Section 1 defines the atomic unit of this whole project
as "individual battle/campaign commanded" — one row is a battle *or* a
campaign, never both — so the two counts are always identical. We only
expose `battles_commanded` rather than duplicating it under a second name.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.records import Battle


@dataclass(frozen=True)
class RawStats:
    """Career counting stats for one general."""

    general_id: str
    battles_commanded: int
    wins: int
    losses: int
    draws: int
    total_own_troops: int
    total_enemy_casualties_inflicted: int
    total_own_casualties_taken: int


def raw_stats_by_general(battles: list[Battle]) -> dict[str, RawStats]:
    """Roll up career counting stats per `general_id`.

    Generals with no rows in `battles` are simply absent from the result
    (there is nothing to count), rather than appearing with all-zero stats.
    """
    by_general: dict[str, list[Battle]] = defaultdict(list)
    for battle in battles:
        by_general[battle.general_id].append(battle)

    result = {}
    for general_id, rows in by_general.items():
        result[general_id] = RawStats(
            general_id=general_id,
            battles_commanded=len(rows),
            wins=sum(1 for b in rows if b.outcome == "Win"),
            losses=sum(1 for b in rows if b.outcome == "Loss"),
            draws=sum(1 for b in rows if b.outcome == "Draw"),
            total_own_troops=sum(b.own_troop_strength for b in rows),
            total_enemy_casualties_inflicted=sum(b.enemy_casualties for b in rows),
            total_own_casualties_taken=sum(b.own_casualties for b in rows),
        )
    return result
