"""Expected-Outcome Residual ("General WAR"): PLAN.md Section 4's WAR layer.

PLAN.md's spec: "regress battle outcome (or margin of victory/casualty ratio)
against force ratio, resource_backing_tier, and tech_era_tier. The general's
stat is the residual — performance above/below what those inputs alone
predict." Design choices, since PLAN.md names the inputs but not the exact
regression target or how per-battle residuals roll up to a per-general stat:

* The regression target is **battle outcome as a score**, using the same
  Win/Draw/Loss -> 1.0/0.5/0.0 mapping `war/metrics/oar.py` already uses for
  Elo's actual-score term. PLAN.md explicitly offers "battle outcome" as one
  of two valid targets, and it's defined and bounded for every row, unlike
  casualty ratio (undefined when own_casualties is 0, and skewed enough that
  one freak battle could dominate the fit — the same problem `rate.py`'s
  docstring already flags for `casualty_exchange_ratio`).
* Ordinary least squares, `predicted = intercept + b1*force_ratio +
  b2*resource_backing_tier + b3*tech_era_tier`, fit **once across every
  battle in the input, pooled over all generals**. Pooling is what makes the
  fit an "expectation given the inputs" baseline that any individual
  general's performance is compared against, rather than each general being
  graded against their own average (which would make everyone's residual
  trivially ~0).
* `force_ratio` is `enemy_troop_strength / own_troop_strength`, the same
  field `rate.py`'s `avg_force_ratio_faced` uses, with the same
  no-zero-guard precedent (own_troop_strength is never recorded as 0 in this
  dataset).
* **Missing-value policy (PROGRESS.md Phase B3):** both troop-strength
  fields are optional in the schema, but `resource_backing_tier`/
  `tech_era_tier` are not, so a row can only fail to produce a `force_ratio`
  by missing one of its two strength fields. Such rows cannot contribute a
  design-matrix row at all (there is no partial regression input) and are
  dropped from the pooled fit entirely, the "drop the row" policy — a
  general whose every battle is missing a strength figure ends up with zero
  usable rows and is absent from the result, same no-data convention as
  `raw_stats_by_general`.
* The per-general stat is the **mean** residual across that general's
  battles, not the sum — a rate stat, like `avg_force_ratio_faced`, so a
  general with more rows isn't rewarded or punished purely by battle count.
* Fit via `numpy.linalg.lstsq` rather than a hand-rolled normal-equations
  solve — numpy is already a project dependency (requirements.txt) and this
  is exactly the tool for it. `lstsq` also degrades gracefully (minimum-norm
  solution) when a synthetic or real slice of the data leaves the design
  matrix rank-deficient, e.g. resource/tech tiers that happen to be constant
  across every row passed in.
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from war.records import Battle

_ACTUAL_SCORE = {"Win": 1.0, "Draw": 0.5, "Loss": 0.0}


@dataclass(frozen=True)
class WARResidual:
    """Expected-outcome residual for one general: mean actual-minus-predicted score."""

    general_id: str
    war_residual: float
    battles_used: int


def war_residual_by_general(battles: list[Battle]) -> dict[str, WARResidual]:
    """Regress outcome score on force ratio/resource tier/tech tier, return per-general mean residual.

    Generals with no rows in `battles` are absent from the result, same
    convention as `raw_stats_by_general`/`rate_stats_by_general`. The OLS fit
    is pooled across every row that has both strength fields recorded (see
    this module's docstring), so the result depends on the whole usable
    input, not just one general's rows — passing a subset of the dataset
    refits against that subset only.
    """
    usable = [
        battle
        for battle in battles
        if battle.own_troop_strength is not None
        and battle.enemy_troop_strength is not None
    ]
    if not usable:
        return {}

    design = np.array(
        [
            [
                1.0,
                battle.enemy_troop_strength / battle.own_troop_strength,
                battle.resource_backing_tier,
                battle.tech_era_tier,
            ]
            for battle in usable
        ]
    )
    actual = np.array([_ACTUAL_SCORE[battle.outcome] for battle in usable])

    coefficients, *_ = np.linalg.lstsq(design, actual, rcond=None)
    predicted = design @ coefficients
    residuals = actual - predicted

    by_general: dict[str, list[float]] = defaultdict(list)
    for battle, residual in zip(usable, residuals):
        by_general[battle.general_id].append(residual)

    return {
        general_id: WARResidual(
            general_id=general_id,
            war_residual=float(np.mean(values)),
            battles_used=len(values),
        )
        for general_id, values in by_general.items()
    }
