#!/usr/bin/env python3
"""CLI entry point: renders the Composite Power Ranking + six category
rankings (PLAN.md Section 6 deliverables 1 and 2) to
`output/viz/ranking_tables.html`, plus a `.csv` per table.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.metrics.uncertainty import monte_carlo_uncertainty  # noqa: E402
from war.records import load_battles, load_generals  # noqa: E402
from war.viz.ranking_tables import save_ranking_tables  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output" / "viz" / "ranking_tables.html"

# Fixed seed: this script's output is committed to the repo, so the
# resampled war_residual/clutch_rating confidence intervals must be
# reproducible run to run, not redrawn each time (see uncertainty.py).
MC_SEED = 20260920


def main() -> int:
    battles = load_battles()
    generals = load_generals()
    mc = monte_carlo_uncertainty(battles, seed=MC_SEED)
    output_path = save_ranking_tables(battles, generals, OUTPUT_PATH, mc=mc)
    print(f"wrote {output_path}")
    print(f"wrote {output_path.with_name(output_path.stem + '_composite.csv')}")
    print(f"wrote {output_path.with_name(output_path.stem + '_categories.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
