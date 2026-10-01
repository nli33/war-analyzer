#!/usr/bin/env python3
"""CLI entry point: renders the Volume vs. Efficiency scatter (PLAN.md Section 6)
to `output/viz/volume_vs_efficiency.png` (plus a `.csv` of the plotted values).

Defaults to the hand-curated gold set (`data/*.csv`); pass `--battles`/
`--generals`/`--output` to run the same renderer against `data/auto/` at
scale (PROGRESS.md's D2) without touching the gold set's committed output.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.records import load_battles, load_generals  # noqa: E402
from war.viz.volume_efficiency import plot_volume_vs_efficiency  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = REPO_ROOT / "output" / "viz" / "volume_vs_efficiency.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battles", type=Path, default=REPO_ROOT / "data" / "battles.csv")
    parser.add_argument("--generals", type=Path, default=REPO_ROOT / "data" / "generals.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    battles = load_battles(args.battles)
    generals = load_generals(args.generals)
    output_path = plot_volume_vs_efficiency(battles, generals, args.output)
    print(f"wrote {output_path}")
    print(f"wrote {output_path.with_suffix('.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
