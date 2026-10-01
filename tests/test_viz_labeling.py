"""`extreme_labels` (PROGRESS.md D2): the shared "label only the extremes"
rule all three Section 6 scatter modules use once the roster scales past a
handful of generals.
"""

from war.viz.labeling import extreme_labels


def test_empty_points_returns_empty():
    assert extreme_labels([], lambda p: p, lambda p: p) == []


def test_single_point_is_its_own_extreme():
    assert extreme_labels([(1, 1)], lambda p: p[0], lambda p: p[1]) == [(1, 1)]


def test_middle_points_excluded():
    points = [(1, 1), (2, 5), (3, 3), (4, 9)]

    result = extreme_labels(points, lambda p: p[0], lambda p: p[1])

    # (2, 5) and (3, 3) are neither the min/max x nor the min/max y
    assert result == [(1, 1), (4, 9)]


def test_tied_extremes_all_included():
    points = [(1, 1), (1, 9), (5, 5)]

    result = extreme_labels(points, lambda p: p[0], lambda p: p[1])

    # both x=1 points tie for min-x; (5, 5) is max x and also max y
    assert set(result) == {(1, 1), (1, 9), (5, 5)}


def test_preserves_input_order():
    points = [(4, 9), (1, 1), (3, 3)]

    result = extreme_labels(points, lambda p: p[0], lambda p: p[1])

    assert result == [(4, 9), (1, 1)]
