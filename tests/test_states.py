import pytest
from deskcat.states import State, StateMachine


def test_crossfade_and_interruption():
    machine = StateMachine()
    machine.transition(State.WALK)
    machine.update(0.15)
    assert machine.weights[State.IDLE] == pytest.approx(0.5)
    assert machine.weights[State.WALK] == pytest.approx(0.5)
    before = machine.weights.copy()
    machine.transition(State.SLEEP)
    machine.update(0)
    assert machine.weights == before
    machine.update(0.3)
    assert machine.weights[State.SLEEP] == 1
    assert sum(machine.weights.values()) == pytest.approx(1)


@pytest.mark.parametrize('state', list(State))
def test_all_states(state):
    machine = StateMachine()
    machine.transition(state)
    machine.update(0.3)
    assert machine.state == state
    assert machine.weights[state] == 1


def test_stand_up_completes():
    machine = StateMachine()
    machine.transition(State.STAND_UP)
    machine.update(0.8)
    assert machine.state == State.IDLE
