"""Phase 5 config: the composite ranking's weights live in one place (war/config.py)."""

import pytest

from war.config import DEFAULT_COMPOSITE_WEIGHTS, CompositeWeights


def test_default_weights_sum_to_one():
    assert DEFAULT_COMPOSITE_WEIGHTS.is_normalized()


def test_default_weights_cover_all_four_plan_inputs():
    assert DEFAULT_COMPOSITE_WEIGHTS.as_dict().keys() == {
        "oar",
        "war_residual",
        "decisiveness",
        "longevity",
    }


def test_weights_are_overridable():
    custom = CompositeWeights(oar=0.7, war_residual=0.1, decisiveness=0.1, longevity=0.1)
    assert custom != DEFAULT_COMPOSITE_WEIGHTS
    assert custom.oar == 0.7


def test_normalized_rescales_to_sum_one():
    lopsided = CompositeWeights(oar=2.0, war_residual=2.0, decisiveness=1.0, longevity=1.0)
    normalized = lopsided.normalized()
    assert normalized.is_normalized()
    assert normalized.oar == pytest.approx(1 / 3)
    assert normalized.decisiveness == pytest.approx(1 / 6)


def test_normalized_zero_total_raises():
    zero = CompositeWeights(oar=0, war_residual=0, decisiveness=0, longevity=0)
    with pytest.raises(ValueError):
        zero.normalized()


def test_is_normalized_false_when_weights_dont_sum_to_one():
    unnormalized = CompositeWeights(oar=1.0, war_residual=1.0, decisiveness=1.0, longevity=1.0)
    assert not unnormalized.is_normalized()
