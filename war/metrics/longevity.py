"""Longevity-Adjusted Value: PLAN.md Section 4's "career value normalized for
years active" stat, meant to separate volume compilers (long careers that
accumulate value by attrition) from short, dominant peaks (PLAN.md's own
example: Alexander's decade vs. Eisenhower's).

Design choices, since PLAN.md names the concept but not the exact formula:

* "Career value" reuses the Win/Draw/Loss -> 1.0/0.5/0.0 outcome-score
  mapping `oar.py`/`war_residual.py`/`clutch.py` already use, summed across
  every battle a general commanded — the same "don't re-derive what a
  battle's outcome already answers" reasoning those modules give. A losing
  battle contributes 0, not a penalty, matching how those modules treat Loss.
* "Normalized for longevity" is read as *time*, not battle/campaign count:
  PLAN.md offers "years/campaigns active" as alternatives, but campaign
  count is already `raw_stats.battles_commanded` and every existing rate
  stat (win_rate, avg_force_ratio_faced, ...) already normalizes by battle
  count — a battle-count denominator here would just be a rescaled win
  total, not a new axis. Years is the one thing this metric can uniquely
  add: it penalizes a long career for taking longer to accumulate the same
  value a short, dominant one produced quickly, which is exactly PLAN.md's
  Alexander-vs-Eisenhower framing.
* Career length is `generals.csv`'s `career_end_year - career_start_year +
  1` (inclusive of both end years). Both fields are plain signed ints,
  already astronomical-style with no year-zero offset (see `war/schema.py`'s
  module docstring), so this arithmetic is correct across a BC/AD boundary
  with no special-casing.
* `None` is never produced: every general with at least one row in
  `battles` has a `generals.csv` row (`validate.py` enforces the foreign
  key both ways), and every career is at least one year long, so the
  denominator is never zero. Generals with no rows in `battles` are simply
  absent from the result, same convention as `raw_stats_by_general`.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.records import Battle, General

_OUTCOME_SCORE = {"Win": 1.0, "Draw": 0.5, "Loss": 0.0}


@dataclass(frozen=True)
class LongevityAdjustedValue:
    """One general's career value, normalized by years active."""

    general_id: str
    longevity_adjusted_value: float
    career_value: float
    career_length_years: int


def longevity_adjusted_value_by_general(
    battles: list[Battle], generals: list[General]
) -> dict[str, LongevityAdjustedValue]:
    """Compute Longevity-Adjusted Value per `general_id`.

    Generals with no rows in `battles` are absent from the result, same
    convention as `raw_stats_by_general`. Every general present in
    `battles` must have a matching row in `generals`, true of validated
    data (`validate.py` checks the foreign key).
    """
    by_general: dict[str, list[Battle]] = defaultdict(list)
    for battle in battles:
        by_general[battle.general_id].append(battle)

    career_length_years = {
        g.general_id: g.career_end_year - g.career_start_year + 1 for g in generals
    }

    result = {}
    for general_id, rows in by_general.items():
        career_value = sum(_OUTCOME_SCORE[b.outcome] for b in rows)
        length = career_length_years[general_id]
        result[general_id] = LongevityAdjustedValue(
            general_id=general_id,
            longevity_adjusted_value=career_value / length,
            career_value=career_value,
            career_length_years=length,
        )
    return result
