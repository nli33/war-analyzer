"""Scatter: Volume vs. Efficiency, PLAN.md Section 6 deliverable 3's first plot.

PLAN.md's spec: "Volume (battles/troops commanded) vs. Efficiency (win rate or
casualty ratio)" — it names two options for each axis rather than one formula,
so the choice is a judgment call, documented here:

* **Volume = `battles_commanded`** (`raw.py`), not total troops commanded.
  Troop totals span several orders of magnitude across eras in this roster
  (a few thousand for Caesar/Alexander vs. low millions for Zhukov), which
  would force a log axis and compress the very comparison PLAN.md is after
  ("who did more with less"); battles commanded ranges 6-15 across this
  roster's 8 generals, a spread a linear axis reads cleanly.
* **Efficiency = `win_rate`** (`rate.py`), not casualty exchange ratio.
  `casualty_exchange_ratio` is `None` for any general with zero career
  own-casualties (none in this roster, but a real edge case per `rate.py`'s
  own docstring) and is otherwise unbounded, which would need its own log
  axis and skews heavily toward whichever general fought the fewest/most
  lopsided battles. `win_rate` is already bounded to [0, 1], always defined,
  and is literally PLAN.md's own first-listed Efficiency option.

With only 8 points (this run's locked roster, SCOPE.md), every point is
directly labeled by the general's name rather than color-coded by era or
given a legend — a single-series chart needs no legend box (the dataviz
skill's own rule: "a single series needs no legend box, the title names
it"), and coloring 8 individually-identified points by era would just
reproduce identity information the label already carries, at the cost of an
8-hue categorical palette this chart form (`--pairs all`, no fixed adjacency)
cannot validate past 3 slots per the skill's own palette notes. All markers
use the palette's single default sequential/slot-1 hue instead.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend: no display in this sandbox

import matplotlib.pyplot as plt

from war.metrics.raw import raw_stats_by_general
from war.metrics.rate import rate_stats_by_general
from war.records import Battle, General

_MARKER_COLOR = "#2a78d6"  # dataviz skill palette.md categorical slot 1 (light mode)
_SURFACE_COLOR = "#fcfcfb"  # dataviz skill palette.md light chart surface
_TEXT_COLOR = "#0b0b0b"  # dataviz skill palette.md light text-primary


@dataclass(frozen=True)
class VolumeEfficiencyPoint:
    """One general's (Volume, Efficiency) coordinate for this scatter."""

    general_id: str
    display_name: str
    battles_commanded: int
    win_rate: float


def volume_efficiency_points(
    battles: list[Battle], generals: list[General]
) -> list[VolumeEfficiencyPoint]:
    """Compute one (Volume, Efficiency) point per general with battle rows.

    Sorted by `general_id` for deterministic output. Every `general_id`
    present in `battles` has a matching `generals` row on validated data
    (`validate.py` enforces the foreign key), same guarantee `longevity.py`
    relies on.
    """
    raw_stats = raw_stats_by_general(battles)
    rate_stats = rate_stats_by_general(battles)
    display_names = {g.general_id: g.display_name for g in generals}

    return [
        VolumeEfficiencyPoint(
            general_id=general_id,
            display_name=display_names[general_id],
            battles_commanded=raw_stats[general_id].battles_commanded,
            win_rate=rate_stats[general_id].win_rate,
        )
        for general_id in sorted(raw_stats)
    ]


def render_volume_efficiency_figure(
    points: list[VolumeEfficiencyPoint],
) -> matplotlib.figure.Figure:
    """Render the scatter as a matplotlib `Figure`, no file I/O.

    Kept separate from `plot_volume_vs_efficiency` so tests can inspect the
    `Axes` directly (point count, coordinates, labels) without decoding a
    PNG — the verification approach SCOPE.md's Phase 6 note asks for in a
    no-display sandbox.
    """
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=_SURFACE_COLOR)
    ax.set_facecolor(_SURFACE_COLOR)

    xs = [p.battles_commanded for p in points]
    ys = [p.win_rate for p in points]
    ax.scatter(xs, ys, s=64, color=_MARKER_COLOR, zorder=3)
    for p in points:
        ax.annotate(
            p.display_name,
            (p.battles_commanded, p.win_rate),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
            color=_TEXT_COLOR,
        )

    ax.set_xlabel("Volume (battles commanded)", color=_TEXT_COLOR)
    ax.set_ylabel("Efficiency (win rate)", color=_TEXT_COLOR)
    ax.set_title("Volume vs. Efficiency", color=_TEXT_COLOR)
    ax.set_ylim(-0.05, 1.05)
    ax.tick_params(colors=_TEXT_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def plot_volume_vs_efficiency(
    battles: list[Battle], generals: list[General], output_path: Path | str
) -> Path:
    """Compute the points, render the figure, and save it as a PNG.

    Returns the resolved output path. Also writes a same-named `.csv` next
    to the PNG with the exact plotted values, so the chart's correctness can
    be checked from numbers, not just the picture (SCOPE.md Phase 6's note
    for the no-display sandbox).
    """
    points = volume_efficiency_points(battles, generals)
    fig = render_volume_efficiency_figure(points)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    csv_path = output_path.with_suffix(".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["general_id", "display_name", "battles_commanded", "win_rate"])
        for p in points:
            writer.writerow([p.general_id, p.display_name, p.battles_commanded, p.win_rate])

    return output_path
