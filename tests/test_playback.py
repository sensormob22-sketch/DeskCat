import pytest
from deskcat.rendering.playback import ClipClock


def test_idle_walk_phase_sync_and_interrupted_transition():
    clock = ClipClock({'idle': 2, 'walk': 1, 'sit': 3})
    clock.update(.6, {'idle': 1})
    assert clock.times['walk'] == 0  # inactive clock doesn't advance globally
    clock.update(0, {'idle': .5, 'walk': .5})
    assert clock.times['walk'] == pytest.approx(.3)
    clock.update(.1, {'idle': .5, 'walk': .5})
    previous = clock.times.copy()
    clock.update(0, {'idle': .4, 'walk': .4, 'sit': .2})
    assert clock.times['idle'] == previous['idle']
    assert clock.times['walk'] == previous['walk']  # no phase reset while visible
    assert clock.times['sit']/3 == pytest.approx(previous['idle']/2)


def test_pause_speed_and_seek():
    clock = ClipClock({'walk': 2})
    clock.speed = .5
    clock.update(1, {'walk': 1})
    assert clock.times['walk'] == .5
    clock.paused = True
    clock.update(1, {'walk': 1})
    assert clock.times['walk'] == .5
    clock.seek('walk', 2.25)
    assert clock.times['walk'] == .25
    clock.paused = False
    clock.update(.5, {'walk': 1})
    assert clock.times['walk'] == .5


def test_empty_and_invalid_clock():
    assert ClipClock({}).update(.2, {}) == {}
    with pytest.raises(ValueError):
        ClipClock({'walk': 0})
    with pytest.raises(ValueError):
        ClipClock({'walk': 2}).update(-1, {'walk': 1})
