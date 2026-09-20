"""Monte Carlo uncertainty bands: SCOPE.md Phase 4 / PLAN.md Section 5.

PLAN.md's spec: "For Low-confidence battles, sample troop/casualty figures
from a plausible range (Monte Carlo) rather than using a single point
estimate; run the full pipeline N times to produce a distribution of each
general's rating." Design choices, since PLAN.md names the mechanism but not
the exact noise model or which of Phase 3's metrics to re-run:

* Every battle's `source_confidence` sets a per-run multiplicative noise
  half-width applied independently to each of the four numeric fields
  (own/enemy troop strength, own/enemy casualties): High = 0 (the recorded
  figure is trusted as-is, so a High-confidence-only general's distribution
  collapses to a single repeated point -- the exact property SCOPE.md's
  Phase 4 test asks for), Medium = 10% (matches the scale of real
  cross-source disagreement logged in Phase 2 for 18th/19th-century muster
  rolls, e.g. Mollwitz's 16,000-23,000 range), Low = 40% (matches the wider
  ancient/medieval/contested-modern disagreements logged in Phase 2, e.g.
  Operation Mars' ~55% Krivosheev/Glantz gap or the Genghis/Saladin
  order-of-magnitude placeholder figures). Each run draws its factor
  uniformly from `[1 - half_width, 1 + half_width]`, independently per field
  per battle, so own troop strength and enemy casualties on the same row are
  not forced to move together.
* Resampled troop-strength fields are floored at 1, not the schema's
  `min_value=0` -- `rate.py` and `war_residual.py` both divide by
  `own_troop_strength` and document that it's never recorded as 0 in this
  dataset; a resample must preserve that invariant or those metrics would
  raise `ZeroDivisionError` mid-run. Casualty fields are floored at 0, the
  schema's actual minimum, since a resampled-down-to-zero casualty count is
  a legitimate value (the schema already allows it).
* Only metrics whose formula actually reads the resampled fields are
  re-run per iteration: `raw.py`'s three troop/casualty totals, `rate.py`'s
  `casualty_exchange_ratio`/`avg_force_ratio_faced`, `war_residual.py`'s
  `war_residual` (force_ratio is a regression input), and `clutch.py`'s
  `clutch_rating` (the outnumbered condition reads troop strength, so which
  battles even qualify as "playing from behind" can change run to run).
  `win_rate`, `decisive_win_rate`, OAR, Squander Index, and
  Longevity-Adjusted Value are deliberately excluded: every one of them is a
  function of `outcome`, `objective_secured`, `decisiveness`, or career
  years, none of which this resampling touches, so re-running them N times
  would just reproduce the same point estimate N times -- a degenerate,
  not-actually-uncertain "distribution".
* A metric value that's legitimately `None` for a given run (e.g.
  `casualty_exchange_ratio` when resampled own-casualties net to exactly 0
  career-wide, or `clutch_rating` when resampling happens to move every one
  of a general's battles out of the "playing from behind" condition for that
  run) is excluded from that general/metric's sample rather than counted as
  0 or crashing the run. If every run comes back `None`, the summary itself
  is `None` with `runs_used=0`, the same no-data convention every Phase 3
  metric already uses.
* The interval is the empirical 5th/95th percentile across the N resampled
  runs (a 90% interval, per SCOPE.md), not a parametric fit -- nothing here
  is assumed Gaussian, and empirical percentiles degrade gracefully to a
  single repeated point when noise is 0.
* `war_residual` is the one metric here that is *not* purely general-local:
  `war_residual_by_general` fits its regression pooled across every battle
  passed in, so resampling another general's Low-confidence rows shifts the
  fitted coefficients and can widen a High-confidence general's own
  war_residual interval too. That's a faithful re-run of "the full
  pipeline" each iteration (PLAN.md's own phrasing), not a bug -- but it
  does mean the "High-confidence general -> zero width" property only holds
  metric-by-metric for the general-local metrics (the raw/rate totals and
  clutch_rating), not for war_residual when it's resampled alongside other,
  less-certain generals.
"""

from collections import defaultdict
from dataclasses import dataclass, replace

import numpy as np

from war.metrics.clutch import clutch_rating_by_general
from war.metrics.raw import raw_stats_by_general
from war.metrics.rate import rate_stats_by_general
from war.metrics.war_residual import war_residual_by_general
from war.records import Battle

DEFAULT_N_RUNS = 1000

_NOISE_HALF_WIDTH = {"High": 0.0, "Medium": 0.10, "Low": 0.40}

# field -> floor applied to a resampled value (see module docstring for why
# troop strength floors at 1 rather than the schema's own min_value=0).
_FIELD_FLOORS = {
    "own_troop_strength": 1,
    "enemy_troop_strength": 1,
    "own_casualties": 0,
    "enemy_casualties": 0,
}

# metric name -> (stat family to recompute each run, attribute to read off it)
_METRIC_SOURCES = (
    ("total_own_troops", raw_stats_by_general, "total_own_troops"),
    ("total_enemy_casualties_inflicted", raw_stats_by_general, "total_enemy_casualties_inflicted"),
    ("total_own_casualties_taken", raw_stats_by_general, "total_own_casualties_taken"),
    ("casualty_exchange_ratio", rate_stats_by_general, "casualty_exchange_ratio"),
    ("avg_force_ratio_faced", rate_stats_by_general, "avg_force_ratio_faced"),
    ("war_residual", war_residual_by_general, "war_residual"),
    ("clutch_rating", clutch_rating_by_general, "clutch_rating"),
)
_COMPUTE_FNS = {fn for _, fn, _ in _METRIC_SOURCES}


@dataclass(frozen=True)
class MetricDistribution:
    """Monte Carlo summary for one (general, metric) pair across N runs.

    `mean`/`ci_low`/`ci_high` are `None`, with `runs_used=0`, when the
    underlying metric was `None` in every run (no qualifying data), same
    no-data convention as the Phase 3 metric it wraps.
    """

    general_id: str
    metric: str
    mean: float | None
    ci_low: float | None  # empirical 5th percentile
    ci_high: float | None  # empirical 95th percentile
    runs_used: int


def _resample_battle(battle: Battle, rng: np.random.Generator) -> Battle:
    half_width = _NOISE_HALF_WIDTH[battle.source_confidence]
    if half_width == 0.0:
        return battle
    updates = {}
    for field, floor in _FIELD_FLOORS.items():
        factor = 1.0 + rng.uniform(-half_width, half_width)
        updates[field] = max(floor, round(getattr(battle, field) * factor))
    return replace(battle, **updates)


def monte_carlo_uncertainty(
    battles: list[Battle],
    n_runs: int = DEFAULT_N_RUNS,
    seed: int | None = None,
) -> dict[str, dict[str, MetricDistribution]]:
    """Resample-and-recompute the resampling-sensitive metrics `n_runs` times.

    Returns `result[general_id][metric_name]`. A general absent from
    `battles` is absent from the result, matching every Phase 3 metric's
    convention. Deterministic for a fixed `seed`; omit it for a fresh draw
    each call.
    """
    rng = np.random.default_rng(seed)
    samples: dict[tuple[str, str], list[float]] = defaultdict(list)

    for _ in range(n_runs):
        resampled = [_resample_battle(b, rng) for b in battles]
        computed = {fn: fn(resampled) for fn in _COMPUTE_FNS}
        for metric_name, fn, attr in _METRIC_SOURCES:
            for general_id, stat in computed[fn].items():
                value = getattr(stat, attr)
                if value is not None:
                    samples[(general_id, metric_name)].append(value)

    general_ids = {battle.general_id for battle in battles}
    result: dict[str, dict[str, MetricDistribution]] = {
        general_id: {} for general_id in general_ids
    }
    for general_id in general_ids:
        for metric_name, _fn, _attr in _METRIC_SOURCES:
            values = samples.get((general_id, metric_name), [])
            if values:
                arr = np.array(values)
                result[general_id][metric_name] = MetricDistribution(
                    general_id=general_id,
                    metric=metric_name,
                    mean=float(np.mean(arr)),
                    ci_low=float(np.percentile(arr, 5)),
                    ci_high=float(np.percentile(arr, 95)),
                    runs_used=len(values),
                )
            else:
                result[general_id][metric_name] = MetricDistribution(
                    general_id=general_id,
                    metric=metric_name,
                    mean=None,
                    ci_low=None,
                    ci_high=None,
                    runs_used=0,
                )
    return result
