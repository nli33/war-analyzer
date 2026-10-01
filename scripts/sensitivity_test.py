#!/usr/bin/env python3
"""A5: how much does the composite ranking move if the gold set's numbers are wrong?

    python scripts/sensitivity_test.py

For each error level in FACTORS (1.5x, 2x, 3x), runs TRIALS trials. Each trial perturbs every
gold battle's own/enemy troop strength and own/enemy casualties by an independent multiplicative
log-normal factor (median 1.0, with the error level as the one-sigma bound: about 68% of samples
land within [1/factor, factor], per `_lognormal_factor`'s docstring), recomputes the composite
ranking (`war.metrics.composite.composite_ranking`) on the perturbed battles against the same
generals, and compares it to the ranking on the unperturbed gold set:

* Spearman rank correlation between baseline and perturbed general order.
* Top-5 overlap: how many of the baseline's top 5 generals are still in the perturbed top 5.

This answers task A5's question directly: composite_ranking's four inputs are
`oar.py` (outcome-only, no strength/casualties), `rate.py`'s decisive_win_rate (uses
`decisiveness`, not strength/casualties), `longevity.py` (outcome-only), and
`war_residual.py` (the only one of the four that reads troop strength, via
`enemy_troop_strength / own_troop_strength` as one of three OLS regressors). So this test mostly
measures how sensitive one of the four composite inputs, at 0.35 weight, is to strength noise;
casualties are perturbed too (for completeness, since a future metric might use them) but do not
feed composite_ranking today and are not expected to move its result.
"""

import argparse
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from war.metrics.composite import composite_ranking  # noqa: E402
from war.records import Battle, General, load_battles, load_generals  # noqa: E402

FACTORS = (1.5, 2.0, 3.0)
TRIALS = 300
TOP_N = 5
_PERTURBED_FIELDS = (
    "own_troop_strength",
    "enemy_troop_strength",
    "own_casualties",
    "enemy_casualties",
)


def _lognormal_factor(rng: np.random.Generator, error_level: float) -> float:
    """Sample one multiplicative perturbation factor.

    `error_level` (e.g. 1.5, 2.0, 3.0) is treated as the one-sigma bound of a log-normal
    distribution centered at 1.0: `exp(Normal(0, ln(error_level)))`. About 68% of samples land
    within `[1/error_level, error_level]`, about 95% within its square — "around 1.5x/2x/3x",
    not a hard cap, matching how `scripts/eval_ingest.py` already describes gold-set agreement
    as a log-error band rather than a clipped range.
    """
    sigma = math.log(error_level)
    return math.exp(rng.normal(0.0, sigma))


def perturb_battles(
    battles: list[Battle], error_level: float, rng: np.random.Generator
) -> list[Battle]:
    """Return a copy of `battles` with each numeric field independently log-normal perturbed.

    Perturbed values are rounded to the nearest int and floored at 1 (schema/metrics assume
    positive troop strength; a perturbed casualty count of 0 is left at 0 only if the original
    was already 0, since some battles do record zero casualties on one side).
    """
    perturbed = []
    for battle in battles:
        changes = {}
        for field in _PERTURBED_FIELDS:
            original = getattr(battle, field)
            factor = _lognormal_factor(rng, error_level)
            scaled = round(original * factor)
            changes[field] = max(scaled, 1) if original > 0 else 0
        perturbed.append(replace(battle, **changes))
    return perturbed


def _ranks_by_general(battles: list[Battle], generals: list[General]) -> dict[str, int]:
    return {entry.general_id: entry.rank for entry in composite_ranking(battles, generals)}


def _top_n(ranks: dict[str, int], n: int) -> set[str]:
    return {gid for gid, rank in ranks.items() if rank <= n}


def spearman_correlation(baseline: dict[str, int], perturbed: dict[str, int]) -> float:
    """Spearman rank correlation between two general_id->rank maps over their common keys.

    Both inputs are already ranks (`composite_ranking`'s own 1..N order), so this is the Pearson
    correlation of those two rank sequences — scipy's `spearmanr` isn't a project dependency
    (requirements.txt), and re-ranking already-ranked data would be a no-op in the no-tie case
    this reaches (composite_score ties are vanishingly unlikely with continuous z-scored inputs).
    """
    common = sorted(set(baseline) & set(perturbed))
    a = np.array([baseline[gid] for gid in common], dtype=float)
    b = np.array([perturbed[gid] for gid in common], dtype=float)
    return float(np.corrcoef(a, b)[0, 1])


def run_sensitivity_test(
    battles: list[Battle],
    generals: list[General],
    factors: tuple[float, ...] = FACTORS,
    trials: int = TRIALS,
    seed: int = 0,
) -> dict:
    baseline_ranks = _ranks_by_general(battles, generals)
    baseline_top = _top_n(baseline_ranks, TOP_N)

    report = {
        "gold_rows": len(battles),
        "gold_generals": len(generals),
        "trials_per_factor": trials,
        "top_n": TOP_N,
        "baseline_top": sorted(baseline_top, key=lambda gid: baseline_ranks[gid]),
        "factors": {},
    }

    rng = np.random.default_rng(seed)
    for factor in factors:
        correlations = []
        overlaps = []
        exact_top_matches = 0
        for _ in range(trials):
            perturbed_battles = perturb_battles(battles, factor, rng)
            perturbed_ranks = _ranks_by_general(perturbed_battles, generals)
            correlations.append(spearman_correlation(baseline_ranks, perturbed_ranks))
            perturbed_top = _top_n(perturbed_ranks, TOP_N)
            overlap = len(baseline_top & perturbed_top)
            overlaps.append(overlap)
            if overlap == TOP_N:
                exact_top_matches += 1

        correlations_arr = np.array(correlations)
        overlaps_arr = np.array(overlaps)
        report["factors"][factor] = {
            "mean_spearman": float(correlations_arr.mean()),
            "min_spearman": float(correlations_arr.min()),
            "p10_spearman": float(np.percentile(correlations_arr, 10)),
            "mean_top5_overlap": float(overlaps_arr.mean()),
            "top5_unchanged_share": exact_top_matches / trials,
        }

    return report


def print_report(report: dict) -> None:
    print(f"gold set: {report['gold_rows']} battles, {report['gold_generals']} generals")
    print(f"trials per error level: {report['trials_per_factor']}")
    print(f"baseline top {report['top_n']}: {', '.join(report['baseline_top'])}")
    print()
    header = (
        f"{'error level':<14}{'mean spearman':<16}{'p10 spearman':<15}"
        f"{'mean top5 overlap':<20}{'top5 unchanged':<15}"
    )
    print(header)
    print("-" * len(header))
    for factor, stats in report["factors"].items():
        row = (
            f"{str(factor) + 'x':<14}"
            f"{stats['mean_spearman']:<16.3f}"
            f"{stats['p10_spearman']:<15.3f}"
            f"{stats['mean_top5_overlap']:<20.2f}"
            f"{stats['top5_unchanged_share']:<15.0%}"
        )
        print(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=TRIALS, help="trials per error level")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed, for reproducibility")
    parser.add_argument("--json", type=Path, default=None, help="also write the report as JSON")
    args = parser.parse_args()

    battles = load_battles()
    generals = load_generals()
    report = run_sensitivity_test(battles, generals, trials=args.trials, seed=args.seed)
    print_report(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
