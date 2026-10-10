import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from .rendering.panda import PandaRenderer, DEFAULT_MODEL
from .window import CatWindow


class ThreeDWindow(CatWindow):
    """Keep stage-1 interactions, replace only the drawing with live 3D."""
    def __init__(self, scale=1.0, model=DEFAULT_MODEL, model_scale=1.0, offset=(0.0, 0.0)):
        super().__init__(scale)
        self.setWindowTitle('DeskCat live 3D prototype')
        self.renderer = None
        try:
            self.renderer = PandaRenderer(model)
            self.renderer.model_scale = model_scale
            self.renderer.offset = offset
            self._image = self.render_frame(0)
        except Exception:
            self.timer.stop()
            if self.renderer:
                self.renderer.close()
            raise
        self.render_error = None

    def render_frame(self, dt):
        dpr = self.devicePixelRatioF()
        image = self.renderer.frame(dt, self.machine.weights,
                                    round(self.width()*dpr), round(self.height()*dpr))
        image.setDevicePixelRatio(dpr)
        return image

    def tick(self):
        previous = self._last
        super().tick()
        try:
            self._image = self.render_frame(min(self._last - previous, .1))
        except Exception as exc:
            self.render_error = str(exc)
            print(f'DeskCat rendering failed: {exc}', file=sys.stderr)
            self.timer.stop()
            self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(0, 0, self._image)
        p.end()

    def wheelEvent(self, event):
        self.renderer.model_scale = max(.25, min(3, self.renderer.model_scale *
                                                 1.1 ** (event.angleDelta().y()/120)))
        event.accept()

    def keyPressEvent(self, event):
        x,z = self.renderer.offset
        shifts = {Qt.Key.Key_Left: (-.1,0), Qt.Key.Key_Right: (.1,0),
                  Qt.Key.Key_Up: (0,.1), Qt.Key.Key_Down: (0,-.1)}
        if event.key() in shifts:
            dx,dz = shifts[event.key()]
            self.renderer.offset = (x+dx,z+dz)
        elif event.key() == Qt.Key.Key_R:
            self.renderer.offset = (0,0)
            self.renderer.model_scale = 1.0
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.timer.stop()
        if self.renderer is not None:
            self.renderer.close()
        super().closeEvent(event)
