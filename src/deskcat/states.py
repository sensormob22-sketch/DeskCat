"""Renderer-independent state and crossfade weights."""
from enum import Enum


class State(str, Enum):
    IDLE = "idle"
    WALK = "walk"
    SIT = "sit"
    STAND_UP = "stand_up"
    GROOM = "groom"
    SLEEP = "sleep"
    DRAG = "drag"


class StateMachine:
    def __init__(self, fade_seconds: float = 0.3):
        if fade_seconds <= 0:
            raise ValueError("fade_seconds must be positive")
        self.state = State.IDLE
        self.fade_seconds = fade_seconds
        self.weights = {state: float(state == State.IDLE) for state in State}
        self._source = self.weights.copy()
        self._elapsed = fade_seconds
        self._age = 0.0

    def transition(self, target: State):
        target = State(target)
        if target == self.state:
            return
        self._source = self.weights.copy()
        self.state = target
        self._elapsed = self._age = 0.0

    def update(self, dt: float):
        if dt < 0:
            raise ValueError("dt must be nonnegative")
        self._age += dt
        if self.state == State.STAND_UP and self._age >= 0.8:
            self.transition(State.IDLE)
        self._elapsed += dt
        t = min(1.0, self._elapsed / self.fade_seconds)
        t = t * t * (3 - 2 * t)
        self.weights = {
            state: self._source[state] * (1 - t) + float(state == self.state) * t
            for state in State
        }
