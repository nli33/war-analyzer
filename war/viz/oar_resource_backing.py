"""Scatter: Opponent-Adjusted Rating vs. Resource Backing, PLAN.md Section 6
deliverable 3's third plot.

PLAN.md's spec: this plot "identifies over/underperformance relative to what
they were given" — a general with a high rating despite thin backing is
over-performing; a general with a low rating despite heavy backing is
under-performing. PLAN.md names the two axes directly (unlike the other two
scatters, which each offered a choice of formula), but one of them still
needs a judgment call to turn into a per-general number:

* **Opponent-Adjusted Rating = `oar_ratings(battles)[gid].rating`** (`oar.py`)
  — already a per-general number, reused as-is. Only roster generals are
  plotted (every `battle.general_id`), even though `oar_ratings` also solves
  ratings for off-roster `opponent_general_id`s — same roster-only convention
  `composite.py` uses for the same reason (this is a ranking of the roster,
  not of every name that ever opposed it).
* **Resource Backing = mean `resource_backing_tier` across a general's own
  battles.** `resource_backing_tier` (schema) is recorded **per battle**, not
  per general — `war_residual.py` and `clutch.py` already read it at that
  granularity — so a single per-general axis value needs an aggregation no
  existing metric module computes yet. The mean is used rather than the
  final/latest value or the max, on the same reasoning `longevity.py` uses
  "average across the career" elsewhere: a career-spanning scatter point
  should represent the whole career's typical material position, not just
  where it ended up (e.g. Frederick's tier drops from 3 to 1 across the Seven
  Years' War per PROGRESS.md's notes; Napoleon's rises from 2 to 5 and back to
  1). This aggregation is small enough (one `sum/len` per general) that it is
  computed directly in this module rather than added to `rate.py`, since no
  other metric needs a general-level resource-backing figure.

Unlike `volume_efficiency.py`/`tactical_strategic.py`, neither axis here is
bounded to a known range: OAR ratings are open-ended Elo-style numbers
centered on `oar.py`'s `base_rating` (1500), and mean resource-backing tier
is bounded to the schema's `[1, 5]` range only because the underlying field
is, so the y-axis (not the x-axis) gets a fixed `[0.5, 5.5]` limit for
readability, the same "pad a known bounded range" treatment
`tactical_strategic.py` gives its own `[0, 1]`-bounded axes.

Point styling/labeling follows `volume_efficiency.py`'s reasoning: 8 points,
each directly labeled by name, single palette hue, no legend.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend: no display in this sandbox

import matplotlib.pyplot as plt

from war.metrics.oar import oar_ratings
from war.records import Battle, General

_MARKER_COLOR = "#2a78d6"  # dataviz skill palette.md categorical slot 1 (light mode)
_SURFACE_COLOR = "#fcfcfb"  # dataviz skill palette.md light chart surface
_TEXT_COLOR = "#0b0b0b"  # dataviz skill palette.md light text-primary


@dataclass(frozen=True)
class OARResourceBackingPoint:
    """One general's (Opponent-Adjusted Rating, Resource Backing) coordinate."""

    general_id: str
    display_name: str
    oar_rating: float
    avg_resource_backing_tier: float


def oar_resource_backing_points(
    battles: list[Battle], generals: list[General]
) -> list[OARResourceBackingPoint]:
    """Compute one (OAR, mean resource-backing tier) point per roster general.

    Sorted by `general_id` for deterministic output. Every `general_id`
    present in `battles` has a matching `generals` row on validated data
    (`validate.py` enforces the foreign key), same guarantee
    `volume_efficiency.py`/`tactical_strategic.py` rely on.
    """
    oar = oar_ratings(battles)
    display_names = {g.general_id: g.display_name for g in generals}

    tiers_by_general: dict[str, list[int]] = {}
    for battle in battles:
        tiers_by_general.setdefault(battle.general_id, []).append(battle.resource_backing_tier)

    return [
        OARResourceBackingPoint(
            general_id=general_id,
            display_name=display_names[general_id],
            oar_rating=oar[general_id].rating,
            avg_resource_backing_tier=sum(tiers) / len(tiers),
        )
        for general_id, tiers in sorted(tiers_by_general.items())
    ]


def render_oar_resource_backing_figure(
    points: list[OARResourceBackingPoint],
) -> matplotlib.figure.Figure:
    """Render the scatter as a matplotlib `Figure`, no file I/O.

    Kept separate from `plot_oar_vs_resource_backing` so tests can inspect
    the `Axes` directly (point count, coordinates, labels) without decoding a
    PNG — the verification approach SCOPE.md's Phase 6 note asks for in a
    no-display sandbox.
    """
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=_SURFACE_COLOR)
    ax.set_facecolor(_SURFACE_COLOR)

    xs = [p.oar_rating for p in points]
    ys = [p.avg_resource_backing_tier for p in points]
    ax.scatter(xs, ys, s=64, color=_MARKER_COLOR, zorder=3)
    for p in points:
        ax.annotate(
            p.display_name,
            (p.oar_rating, p.avg_resource_backing_tier),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
            color=_TEXT_COLOR,
        )

    ax.set_xlabel("Opponent-Adjusted Rating (Elo-style)", color=_TEXT_COLOR)
    ax.set_ylabel("Resource Backing (mean tier, 1-5)", color=_TEXT_COLOR)
    ax.set_title("Opponent-Adjusted Rating vs. Resource Backing", color=_TEXT_COLOR)
    ax.set_ylim(0.5, 5.5)
    ax.tick_params(colors=_TEXT_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def plot_oar_vs_resource_backing(
    battles: list[Battle], generals: list[General], output_path: Path | str
) -> Path:
    """Compute the points, render the figure, and save it as a PNG.

    Returns the resolved output path. Also writes a same-named `.csv` next
    to the PNG with the exact plotted values, so the chart's correctness can
    be checked from numbers, not just the picture (SCOPE.md Phase 6's note
    for the no-display sandbox).
    """
    points = oar_resource_backing_points(battles, generals)
    fig = render_oar_resource_backing_figure(points)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    csv_path = output_path.with_suffix(".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["general_id", "display_name", "oar_rating", "avg_resource_backing_tier"])
        for p in points:
            writer.writerow(
                [p.general_id, p.display_name, p.oar_rating, p.avg_resource_backing_tier]
            )

    return output_path
