"""Squander Index: PLAN.md Section 4's "brilliant on the field, lost the war" stat.

PLAN.md's spec: "rate at which tactical wins failed to convert into
strategic/political gains." Design choices, since PLAN.md names the concept
but not the exact formula:

* The schema's `decisiveness` enum already exists to answer exactly this
  question per row (see its definition in `war/schema.py`): `Tactical` means
  "won the field, but it bought no lasting strategic gain" and `Pyrrhic`
  means "nominally the winner, but the cost gutted the force" — both are, by
  their own definition, wins that did not convert. `Strategic` ("advanced
  the campaign's actual objective") and `Rout` (the enemy's army broken or
  destroyed) both count as converted. Squander Index is therefore, among a
  general's wins, the fraction labeled `Tactical` or `Pyrrhic` — no separate
  threshold or re-derivation needed, since re-deriving "failed to convert"
  from troop/casualty numbers would just rebuild what the enum already
  records, the same reasoning `rate.py`'s `decisive_win_rate` gives for
  reusing `objective_secured` instead of re-deriving decisiveness.
* `decisiveness` is required by `war/schema.py` for a Win but `validate.py`
  does not actually enforce that conditional requirement (it only checks the
  unconditional `required` flag, which is `False` for this column so Loss/Draw
  rows may leave it empty). A Win row with no `decisiveness` recorded is
  therefore reachable data, not just a hypothetical: such rows are excluded
  from both the numerator and denominator (we cannot judge conversion without
  the label) rather than assumed either way. `wins_used` reports the
  denominator actually used, same transparency `clutch_rating_by_general`
  gives via `battles_used`.
* `None` when a general has zero wins with `decisiveness` recorded, same
  no-data-no-number convention as `rate.py` and `clutch.py`.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.records import Battle

_SQUANDERED_LEVELS = {"Tactical", "Pyrrhic"}


@dataclass(frozen=True)
class SquanderIndex:
    """Fraction of one general's (decisiveness-labeled) wins that failed to convert."""

    general_id: str
    squander_index: float | None
    wins_used: int


def squander_index_by_general(battles: list[Battle]) -> dict[str, SquanderIndex]:
    """Compute Squander Index per `general_id`.

    Generals with no rows in `battles` are absent from the result, same
    convention as `raw_stats_by_general`. A general with wins but none of
    them carrying a `decisiveness` label gets `squander_index=None` with
    `wins_used=0`, rather than being dropped entirely.
    """
    by_general: dict[str, list[Battle]] = defaultdict(list)
    for battle in battles:
        by_general[battle.general_id].append(battle)

    result = {}
    for general_id, rows in by_general.items():
        rated_wins = [
            b for b in rows if b.outcome == "Win" and b.decisiveness is not None
        ]
        squandered = [b for b in rated_wins if b.decisiveness in _SQUANDERED_LEVELS]

        result[general_id] = SquanderIndex(
            general_id=general_id,
            squander_index=(
                len(squandered) / len(rated_wins) if rated_wins else None
            ),
            wins_used=len(rated_wins),
        )
    return result
