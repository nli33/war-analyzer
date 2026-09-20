"""Composite Power Ranking: PLAN.md Section 6.1.

PLAN.md's spec: a single weighted ordered list combining OAR, WAR-residual,
decisiveness, and longevity, with weights "documented and tunable" — that's
`war/config.py`'s `CompositeWeights`. PLAN.md Section 4's "Era normalization"
paragraph is the other half of the spec that matters here: "All rate stats
are z-scored within era-cohort ... before being combined into any cross-era
composite" — this module is the first (and, so far, only) place that combines
metrics across generals from different eras, so it's where that z-scoring has
to happen; no earlier metric module reads more than one general's era at a
time.

Design choices, since PLAN.md names the four inputs and the era-normalization
rule but not the exact combination mechanics:

* Each of the four inputs (`oar.py`'s `rating`, `war_residual.py`'s
  `war_residual`, `rate.py`'s `decisive_win_rate`, `longevity.py`'s
  `longevity_adjusted_value`) is z-scored **within its own era cohort** —
  each general's `generals.csv` `era` field defines the cohort, using
  **population** standard deviation (`ddof=0`) since a cohort is treated as
  the complete population of this roster's generals in that era, not a
  sample of a larger one. The composite score is then
  `sum(weight_i * z_i)` using `war/config.py`'s `CompositeWeights`, and the
  final ranking is that score sorted descending.
* **Zero-variance cohort convention**: a cohort with only one general (this
  8-general roster has four: Frederick/Napoleon/Grant/Zhukov are each the
  sole representative of Early Modern/Napoleonic/Industrial/WWII) has no
  within-era spread to measure, so `std == 0` and standard z-scoring
  (`(x - mean) / std`) divides by zero. The convention here is `z = 0.0` in
  that case — "no evidence this general is above or below their own era's
  average" is the only honest reading when the era's average *is* that one
  general. This is a real limitation of tonight's locked 8-general/one-per-
  era roster (SCOPE.md), not a bug: it means those four generals' composite
  scores are driven entirely by whichever inputs *do* have cohort-mates
  (none, for a singleton era), i.e. their composite score is exactly 0
  regardless of weights. Flagged here for Phase 7's sanity pass and as a
  reason to prioritize roster expansion (more generals per era) over
  reweighting if the sanity pass finds this suspicious.
* **Missing/`None` inputs**: `rate.py`'s `decisive_win_rate` is `None` for a
  general with zero wins (not reachable in the current 8-general dataset,
  since every roster general has at least one win, but reachable in
  principle and exercised by this module's tests). Such a general is
  excluded from that metric's z-scoring cohort entirely (their `None` can't
  contribute to a mean/std), and their own `z` for that one input defaults
  to `0.0` — same "no evidence either way" reasoning as the zero-variance
  case above, applied per-metric instead of per-cohort.
* **Off-roster opponents**: `oar_ratings` solves ratings for every
  `opponent_general_id` too, not just roster generals (see `oar.py`'s
  docstring). Those participants never appear as a `battle.general_id`, so
  they're absent from `war_residual_by_general`/
  `longevity_adjusted_value_by_general` (both keyed by `battle.general_id`
  only) — intersecting all four inputs' keys before ranking is what keeps
  off-roster opponents out of the composite ranking without a separate
  roster-membership check.
"""

from collections import defaultdict
from dataclasses import dataclass

from war.config import CompositeWeights, DEFAULT_COMPOSITE_WEIGHTS
from war.metrics.longevity import longevity_adjusted_value_by_general
from war.metrics.oar import oar_ratings
from war.metrics.rate import rate_stats_by_general
from war.metrics.war_residual import war_residual_by_general
from war.records import Battle, General


@dataclass(frozen=True)
class CompositeRanking:
    """One general's composite power ranking entry, most-to-least skilled sorted by caller."""

    general_id: str
    rank: int
    composite_score: float
    oar_z: float
    war_residual_z: float
    decisiveness_z: float
    longevity_z: float


def _z_scores_within_era(
    values: dict[str, float], era_by_general: dict[str, str]
) -> dict[str, float]:
    """Z-score `values` (keyed by general_id) within each general's era cohort.

    A cohort with zero population variance (a singleton cohort, or one where
    every member happens to tie) gets `z = 0.0` for every member rather than
    dividing by zero — see this module's docstring.
    """
    by_era: dict[str, list[str]] = defaultdict(list)
    for general_id in values:
        by_era[era_by_general[general_id]].append(general_id)

    z_scores: dict[str, float] = {}
    for general_ids in by_era.values():
        cohort_values = [values[gid] for gid in general_ids]
        mean = sum(cohort_values) / len(cohort_values)
        variance = sum((v - mean) ** 2 for v in cohort_values) / len(cohort_values)
        std = variance**0.5
        for gid in general_ids:
            z_scores[gid] = 0.0 if std == 0 else (values[gid] - mean) / std
    return z_scores


def composite_ranking(
    battles: list[Battle],
    generals: list[General],
    weights: CompositeWeights = DEFAULT_COMPOSITE_WEIGHTS,
) -> list[CompositeRanking]:
    """Compute the composite power ranking, sorted highest-scoring first.

    Only generals with a computable value for at least the OAR/WAR-residual/
    longevity inputs are ranked (every general with any row in `battles` has
    all three, per those metrics' own no-data conventions); a general with no
    wins is still ranked, with `decisiveness_z = 0.0` rather than being
    dropped. Empty `battles` returns an empty list.
    """
    era_by_general = {general.general_id: general.era for general in generals}

    oar = oar_ratings(battles)
    war_residual = war_residual_by_general(battles)
    rate_stats = rate_stats_by_general(battles)
    longevity = longevity_adjusted_value_by_general(battles, generals)

    ranked_ids = set(war_residual) & set(longevity)

    oar_z = _z_scores_within_era(
        {gid: oar[gid].rating for gid in ranked_ids}, era_by_general
    )
    war_residual_z = _z_scores_within_era(
        {gid: war_residual[gid].war_residual for gid in ranked_ids}, era_by_general
    )
    decisiveness_z = _z_scores_within_era(
        {
            gid: rate_stats[gid].decisive_win_rate
            for gid in ranked_ids
            if rate_stats[gid].decisive_win_rate is not None
        },
        era_by_general,
    )
    longevity_z = _z_scores_within_era(
        {gid: longevity[gid].longevity_adjusted_value for gid in ranked_ids}, era_by_general
    )

    scored = []
    for gid in ranked_ids:
        oz = oar_z[gid]
        wz = war_residual_z[gid]
        dz = decisiveness_z.get(gid, 0.0)
        lz = longevity_z[gid]
        composite_score = (
            weights.oar * oz
            + weights.war_residual * wz
            + weights.decisiveness * dz
            + weights.longevity * lz
        )
        scored.append((gid, composite_score, oz, wz, dz, lz))

    scored.sort(key=lambda entry: entry[1], reverse=True)

    return [
        CompositeRanking(
            general_id=gid,
            rank=rank,
            composite_score=composite_score,
            oar_z=oz,
            war_residual_z=wz,
            decisiveness_z=dz,
            longevity_z=lz,
        )
        for rank, (gid, composite_score, oz, wz, dz, lz) in enumerate(scored, start=1)
    ]
