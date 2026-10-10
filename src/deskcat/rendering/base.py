from typing import Mapping, Protocol
from PySide6.QtGui import QImage
from deskcat.states import State


class AnimatedRenderer(Protocol):
    """Future Panda3D backend: RGBA frames in physical pixels.

    Apply weights to Actor joint animations, advance time, render offscreen,
    return an owned QImage (do not retain a borrowed GPU readback buffer).
    """
    def load(self, model_path: str) -> None: ...
    def frame(self, dt: float, weights: Mapping[State, float],
              width: int, height: int) -> QImage: ...
    def close(self) -> None: ...
