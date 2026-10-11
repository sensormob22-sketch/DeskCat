"""Seamless offscreen walking across both boundaries, with no direction change."""
import pytest
from deskcat.locomotion import wrap_desktop_x


@pytest.mark.parametrize('left', [0, -1920, 1920])
def test_left_exit_reenters_right_after_entire_cat_leaves(left):
    w=360
    assert wrap_desktop_x(left-w+0.1,left,1920,w)==pytest.approx(left-w+0.1)
    assert wrap_desktop_x(left-w-5,left,1920,w)==pytest.approx(left+1920-5)
    assert wrap_desktop_x(left+1920-5,left,1920,w)==pytest.approx(left+1920-5)


def test_right_exit_reenters_left_after_entire_cat_leaves():
    assert wrap_desktop_x(1920+7,0,1920,360)==pytest.approx(-360+7)
    assert wrap_desktop_x(-360-7,0,1920,360)==pytest.approx(1920-7)


def test_large_overshoot_and_invalid_inputs():
    assert -360 <= wrap_desktop_x(-360-2280*4-10,0,1920,360) <= 1920
    with pytest.raises(ValueError):wrap_desktop_x(0,0,0,360)
