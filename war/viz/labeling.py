"""Shared "label only the extremes" rule for the three Section 6 scatter plots.

At the locked 8-general roster (SCOPE.md's original scope), every plotted
point got a text label — 8 names fit a chart without overlapping. Once the
roster scales to the auto-ingested hundreds of generals (PROGRESS.md's D2),
labeling every point the same way turns the chart into unreadable overlapping
text. The fix is one deterministic rule shared by all three scatter modules
(`volume_efficiency.py`, `tactical_strategic.py`, `oar_resource_backing.py`):
plot every point, but only draw a text label for whichever point(s) sit at
the min or max of either axis — the "most", "least", "best", "worst" that a
reader actually wants named on a scatter plot, not every point in the middle
of the cloud. At most 4 points get labeled (fewer with ties or with under 4
total points), so this reduces to "label everything" at the original 8-point
scale without a separate code path.
"""

from typing import Callable, TypeVar

T = TypeVar("T")


def extreme_labels(
    points: list[T], x_of: Callable[[T], float], y_of: Callable[[T], float]
) -> list[T]:
    """Return the subset of `points` sitting at the min or max of either axis.

    >>> extreme_labels([(1, 1), (2, 5), (3, 3), (4, 9)], lambda p: p[0], lambda p: p[1])
    [(1, 1), (4, 9)]
    """
    if not points:
        return []
    xs = [x_of(p) for p in points]
    ys = [y_of(p) for p in points]
    extreme_indices: set[int] = set()
    for values in (xs, ys):
        lo, hi = min(values), max(values)
        extreme_indices.update(i for i, v in enumerate(values) if v in (lo, hi))
    return [p for i, p in enumerate(points) if i in extreme_indices]
