"""Single source of truth for the composite power ranking's weights.

PLAN.md Section 6.1 names four inputs to the composite ranking (OAR,
WAR-residual, decisiveness, longevity) but not their relative weights.
SCOPE.md Phase 5 requires those weights to live in "one config location, not
hardcoded inline" — this module is that location, so a re-weighting run
(SCOPE.md's own Phase 5 verification: "changing a weight and re-running
produces a different order") is a one-line edit here, not a change to
whatever composite-ranking code ends up consuming these weights.

Judgment calls, since PLAN.md doesn't specify a formula:

* "decisiveness" maps to `rate.py`'s `decisive_win_rate` — the fraction of
  wins with `objective_secured=true`. It's the one existing metric that is
  literally named for this PLAN.md concept, same reuse-over-re-derive
  reasoning `rate.py` itself gives for not re-deriving "decisive" from the
  `decisiveness` enum a second time.
* "longevity" maps to `longevity.py`'s `longevity_adjusted_value`, not raw
  career value — the whole point of that metric is already "career value
  normalized for years active," which is what PLAN.md asks the composite
  ranking to reward.
* Default weights are an even-ish split (OAR and WAR-residual weighted
  equal and highest, since both are already opponent/context-adjusted
  "true skill" estimates; decisiveness and longevity weighted equal and
  lower, since each captures one narrower slice of career shape) rather
  than an equal 25/25/25/25 split — a placeholder judgment call to be
  revisited by Phase 7's sanity pass, not a claim of a historically
  validated weighting. Documented here, not derived from data.
* Weights are not required to sum to 1.0 by this module — `is_normalized`
  and `normalized` let a caller check/fix that, but a caller combining raw
  (non-z-scored) metric values may deliberately want un-normalized weights.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CompositeWeights:
    """Weights for the four composite power ranking inputs.

    Field names match the metric each weight applies to:
    `oar` -> `oar.py`'s `oar_ratings`, `war_residual` ->
    `war_residual.py`'s `war_residual_by_general`, `decisiveness` ->
    `rate.py`'s `decisive_win_rate`, `longevity` ->
    `longevity.py`'s `longevity_adjusted_value`.
    """

    oar: float = 0.35
    war_residual: float = 0.35
    decisiveness: float = 0.15
    longevity: float = 0.15

    def as_dict(self) -> dict[str, float]:
        return {
            "oar": self.oar,
            "war_residual": self.war_residual,
            "decisiveness": self.decisiveness,
            "longevity": self.longevity,
        }

    def total(self) -> float:
        return sum(self.as_dict().values())

    def is_normalized(self, tolerance: float = 1e-9) -> bool:
        return abs(self.total() - 1.0) <= tolerance

    def normalized(self) -> "CompositeWeights":
        """Return an equivalent `CompositeWeights` rescaled to sum to 1.0.

        Raises `ValueError` on an all-zero weight set, since there is no
        scale factor that turns a zero total into 1.0.
        """
        total = self.total()
        if total == 0:
            raise ValueError("cannot normalize a CompositeWeights with a zero total")
        return replace(
            self,
            **{key: value / total for key, value in self.as_dict().items()},
        )


DEFAULT_COMPOSITE_WEIGHTS = CompositeWeights()
