"""Tests for planted 4-beat walking on the unchanged four-limb rig."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_calico_walk_trial import (BODY, INDEX, PIVOTS, CYCLE_SECONDS,
                                     STANCE_FRACTION, STRIDE, toe_trajectory,
                                     leg_contact_angles)


def fk_toe(points, angles):
    """Compute the final tip joint from unchanged link lengths and rotations."""
    p = np.asarray(points)[:, :2]
    at = np.array(p[0])
    total = 0.0
    for segment, rotation in enumerate(angles):
        total += rotation
        rest = p[segment + 1] - p[segment]
        c, s = math.cos(total), math.sin(total)
        at += np.array([c * rest[0] - s * rest[1],
                        s * rest[0] + c * rest[1]])
    return at


def test_paws_lock_on_75_percent_stance_and_lift_only_in_swing():
    for limb in ("front", "hind"):
        for side in ("L", "R"):
            points = [PIVOTS[INDEX[f"{limb}_{side}_{j}"]] for j in range(4)]
            p = np.asarray(points)[:, :2]
            for phase in np.linspace(0, 1, 101):
                travel, lift = toe_trajectory(float(phase))
                angles = leg_contact_angles(points, travel, lift)
                actual = fk_toe(points, angles)
                assert np.allclose(actual, p[3] + [travel, lift], atol=2e-6)
                if phase < STANCE_FRACTION:
                    assert lift == 0
                    assert abs(travel - STRIDE * phase / STANCE_FRACTION) < 1e-10
                else:
                    assert lift >= -1e-12


def test_four_phases_only_one_swinging_paw():
    phases = (0, .25, .5, .75)
    for t in np.linspace(.005, CYCLE_SECONDS - .005, 250):
        airborne = [toe_trajectory(float(t) / CYCLE_SECONDS + offset)[1] > 1e-8
                    for offset in phases]
        assert sum(airborne) == 1


def test_stride_and_timing_consistency():
    # A planted toe must move in the local +X direction exactly as fast as
    # the window moves in the screen -X direction after pixel conversion.
    dt = CYCLE_SECONDS * STANCE_FRACTION / 8
    for n in range(8):
        t0 = (n * dt) / CYCLE_SECONDS
        t1 = ((n + 1) * dt) / CYCLE_SECONDS
        x0 = toe_trajectory(t0)[0]
        x1 = toe_trajectory(t1)[0]
        window_travel = STRIDE / (CYCLE_SECONDS * STANCE_FRACTION) * dt
        assert abs((x1 - x0) - window_travel) < 1e-12
