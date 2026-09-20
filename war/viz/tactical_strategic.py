"""Scatter: Tactical vs. Strategic rating, PLAN.md Section 6 deliverable 3's second plot.

PLAN.md names the *purpose* of this plot ("identifies 'brilliant tactician /
poor strategist' outliers") but not a formula for either axis, so the mapping
onto existing metrics is a judgment call, documented here:

* **Tactical rating = `win_rate`** (`rate.py`) — the fraction of battles a
  general actually won, independent of what came of the win. This is the
  "brilliant tactician" half: raw skill at winning the field on the day.
* **Strategic rating = `decisive_win_rate`** (`rate.py`) — PLAN.md Section 4
  literally defines this stat as "wins converted to strategic gain vs.
  tactical-only," which *is* the second axis PLAN.md asks for here. Reusing
  it avoids inventing a second, competing definition of "strategic" (e.g.
  re-deriving it from `decisiveness` the way `squander.py` does for a
  different stat) when PLAN.md already named this one for exactly this
  purpose.
* Both axes are bounded to `[0, 1]`, so unlike `volume_efficiency.py` this
  plot needs no log axis or ratio handling.
* `decisive_win_rate` is `None` for a general with zero wins (`rate.py`) —
  there is nothing to rate "strategic conversion" of. Such generals are
  excluded from this plot's points, the same no-data-no-point convention
  `squander.py`/`clutch.py` use for their own None cases. Not reachable on
  this roster's 8 generals (every one has at least one win), but handled for
  future roster expansion (SCOPE.md).

The "brilliant tactician / poor strategist" outlier PLAN.md names reads as
bottom-right on this plot: high tactical rating (wins fights) paired with low
strategic rating (rarely turns wins into lasting gains) — the Squander Index
pattern (`squander.py`) visualized as a 2D outlier rather than a single
number.

Point styling/labeling follows `volume_efficiency.py`'s reasoning: 8 points,
each directly labeled by name, single palette hue, no legend.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend: no display in this sandbox

import matplotlib.pyplot as plt

from war.metrics.rate import rate_stats_by_general
from war.records import Battle, General

_MARKER_COLOR = "#2a78d6"  # dataviz skill palette.md categorical slot 1 (light mode)
_SURFACE_COLOR = "#fcfcfb"  # dataviz skill palette.md light chart surface
_TEXT_COLOR = "#0b0b0b"  # dataviz skill palette.md light text-primary


@dataclass(frozen=True)
class TacticalStrategicPoint:
    """One general's (Tactical rating, Strategic rating) coordinate for this scatter."""

    general_id: str
    display_name: str
    tactical_rating: float
    strategic_rating: float


def tactical_strategic_points(
    battles: list[Battle], generals: list[General]
) -> list[TacticalStrategicPoint]:
    """Compute one (Tactical rating, Strategic rating) point per general with a rateable win.

    Sorted by `general_id` for deterministic output. Generals with no wins
    (`decisive_win_rate is None` in `rate.py`) are excluded, since strategic
    conversion cannot be rated with no wins to convert.
    """
    rate_stats = rate_stats_by_general(battles)
    display_names = {g.general_id: g.display_name for g in generals}

    return [
        TacticalStrategicPoint(
            general_id=general_id,
            display_name=display_names[general_id],
            tactical_rating=stats.win_rate,
            strategic_rating=stats.decisive_win_rate,
        )
        for general_id, stats in sorted(rate_stats.items())
        if stats.decisive_win_rate is not None
    ]


def render_tactical_strategic_figure(
    points: list[TacticalStrategicPoint],
) -> matplotlib.figure.Figure:
    """Render the scatter as a matplotlib `Figure`, no file I/O.

    Kept separate from `plot_tactical_vs_strategic` so tests can inspect the
    `Axes` directly (point count, coordinates, labels) without decoding a
    PNG — the verification approach SCOPE.md's Phase 6 note asks for in a
    no-display sandbox.
    """
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=_SURFACE_COLOR)
    ax.set_facecolor(_SURFACE_COLOR)

    xs = [p.tactical_rating for p in points]
    ys = [p.strategic_rating for p in points]
    ax.scatter(xs, ys, s=64, color=_MARKER_COLOR, zorder=3)
    for p in points:
        ax.annotate(
            p.display_name,
            (p.tactical_rating, p.strategic_rating),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
            color=_TEXT_COLOR,
        )

    ax.set_xlabel("Tactical rating (win rate)", color=_TEXT_COLOR)
    ax.set_ylabel("Strategic rating (decisive win rate)", color=_TEXT_COLOR)
    ax.set_title("Tactical vs. Strategic Rating", color=_TEXT_COLOR)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.tick_params(colors=_TEXT_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def plot_tactical_vs_strategic(
    battles: list[Battle], generals: list[General], output_path: Path | str
) -> Path:
    """Compute the points, render the figure, and save it as a PNG.

    Returns the resolved output path. Also writes a same-named `.csv` next
    to the PNG with the exact plotted values, so the chart's correctness can
    be checked from numbers, not just the picture (SCOPE.md Phase 6's note
    for the no-display sandbox).
    """
    points = tactical_strategic_points(battles, generals)
    fig = render_tactical_strategic_figure(points)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    csv_path = output_path.with_suffix(".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["general_id", "display_name", "tactical_rating", "strategic_rating"])
        for p in points:
            writer.writerow([p.general_id, p.display_name, p.tactical_rating, p.strategic_rating])

    return output_path
