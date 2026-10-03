#!/usr/bin/env python3
"""CLI entry point: renders the Composite Power Ranking + six category
rankings (PLAN.md Section 6 deliverables 1 and 2) to
`output/viz/ranking_tables.html`, plus a `.csv` per table.

Defaults to the hand-curated gold set (`data/*.csv`); pass `--battles`/
`--generals`/`--output` to run the same renderer against `data/auto/` at
scale (PROGRESS.md's D2) without touching the gold set's committed output.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.metrics.uncertainty import monte_carlo_uncertainty  # noqa: E402
from war.records import load_battles, load_generals  # noqa: E402
from war.viz.ranking_tables import (  # noqa: E402
    MIN_BATTLES_FOR_HEADLINE_RANKING,
    save_ranking_tables,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = REPO_ROOT / "output" / "viz" / "ranking_tables.html"

# Fixed seed: this script's output is committed to the repo, so the
# resampled war_residual/clutch_rating confidence intervals must be
# reproducible run to run, not redrawn each time (see uncertainty.py).
MC_SEED = 20260920


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battles", type=Path, default=REPO_ROOT / "data" / "battles.csv")
    parser.add_argument("--generals", type=Path, default=REPO_ROOT / "data" / "generals.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="cap each HTML table at its best N rows (CSVs are never truncated); 0 disables the cap",
    )
    parser.add_argument(
        "--min-battles",
        type=int,
        default=MIN_BATTLES_FOR_HEADLINE_RANKING,
        help="drop generals below this many battles from the HTML tables (CSVs keep everyone); "
        "0 disables the floor",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    top_n = None if args.top_n == 0 else args.top_n

    battles = load_battles(args.battles)
    generals = load_generals(args.generals)
    mc = monte_carlo_uncertainty(battles, seed=MC_SEED)
    output_path = save_ranking_tables(
        battles, generals, args.output, mc=mc, top_n=top_n, min_battles=args.min_battles
    )
    print(f"wrote {output_path}")
    print(f"wrote {output_path.with_name(output_path.stem + '_composite.csv')}")
    print(f"wrote {output_path.with_name(output_path.stem + '_categories.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
