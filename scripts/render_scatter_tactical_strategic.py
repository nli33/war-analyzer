#!/usr/bin/env python3
"""CLI entry point: renders the Tactical vs. Strategic scatter (PLAN.md Section 6)
to `output/viz/tactical_vs_strategic.png` (plus a `.csv` of the plotted values).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.records import load_battles, load_generals  # noqa: E402
from war.viz.tactical_strategic import plot_tactical_vs_strategic  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output" / "viz" / "tactical_vs_strategic.png"


def main() -> int:
    battles = load_battles()
    generals = load_generals()
    output_path = plot_tactical_vs_strategic(battles, generals, OUTPUT_PATH)
    print(f"wrote {output_path}")
    print(f"wrote {output_path.with_suffix('.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
