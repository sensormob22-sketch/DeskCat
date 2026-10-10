import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QAction
from PySide6.QtWidgets import QMenu, QApplication
from .states import State
from .rendering.panda import PandaRenderer, DEFAULT_MODEL
from .window import CatWindow


class ThreeDWindow(CatWindow):
    """Keep stage-1 interactions, replace only the drawing with live 3D."""
    def __init__(self, scale=1.0, model=DEFAULT_MODEL, model_scale=1.0, offset=(0.0, 0.0), clip_map=None, diagnostics=None,
                 playback_speed=1.0, forward_heading=0.0):
        super().__init__(scale)
        self.setWindowTitle('DeskCat live 3D prototype')
        self.renderer = None
        self.diagnostics = diagnostics
        self.show_diagnostic_overlay = bool(diagnostics)
        self.render_error = None
        self.frame_interval_ms = 0.0
        try:
            self.renderer = PandaRenderer(model, clip_map=clip_map)
            self.renderer.model_scale = model_scale
            self.renderer.offset = offset
            self.renderer.clock.speed = playback_speed
            self.renderer.forward_heading = forward_heading
            self.renderer.heading = forward_heading
            self._image = self.render_frame(0)
        except Exception:
            self.timer.stop()
            if self.renderer:
                self.renderer.close()
            raise

    def can_move(self):
        if self.renderer is None or self.renderer.clock.paused:
            return False
        target = self.renderer.forward_heading + (180 if self._direction < 0 else 0)
        delta = (target - self.renderer.heading + 180) % 360 - 180
        return abs(delta) < 5

    def render_frame(self, dt):
        dpr = self.devicePixelRatioF()
        self.renderer.direction = self._direction
        image = self.renderer.frame(dt, self.machine.weights,
                                    round(self.width()*dpr), round(self.height()*dpr))
        image.setDevicePixelRatio(dpr)
        return image

    def tick(self):
        previous = self._last
        super().tick()
        self.frame_interval_ms = (self._last - previous)*1000
        try:
            self._image = self.render_frame(min(self._last - previous, .1))
            if self.diagnostics:
                self.diagnostics.sample(self)
        except Exception as exc:
            self.render_error = str(exc)
            print(f'DeskCat rendering failed: {exc}', file=sys.stderr)
            if self.diagnostics:
                self.diagnostics.write('render_error', message=str(exc))
            self.timer.stop()
            self.close()
            QApplication.exit(1)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(0, 0, self._image)
        if self.diagnostics and self.show_diagnostic_overlay:
            p.setPen(QPen(QColor('#ff00ff'), 1))
            p.drawRect(0, 0, self.width()-1, self.height()-1)
            if self.diagnostics.bounds:
                x0,y0,x1,y1 = self.diagnostics.bounds
                dpr = self.devicePixelRatioF()
                p.setPen(QColor('#00ffff'))
                p.drawRect(round(x0/dpr),round(y0/dpr),
                           round((x1-x0)/dpr),round((y1-y0)/dpr))
            p.setPen(QColor('#ffff00'))
            p.drawText(5, 16, f'DPR {self.devicePixelRatioF():.2f} · {self.renderer.last_frame_ms:.1f} ms')
            status = ','.join(self.renderer.unavailable_active)
            p.drawText(5, 32, 'MISSING: '+status if status else self.machine.state.value)
        p.end()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        for state in State:
            if state == State.DRAG:
                continue
            clip = self.renderer.clip_map[state]
            label = state.value + (f' ({clip})' if clip else ' — no clip')
            action = QAction(label, menu)
            action.setEnabled(clip is not None)
            action.triggered.connect(lambda checked=False, s=state: self.machine.transition(s))
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction('Exit', self.close)
        menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.diagnostics:
            self.diagnostics.write('mouse_press', button=int(event.button().value),
                                   state=self.machine.state.value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.diagnostics:
            self.diagnostics.write('mouse_release', state=self.machine.state.value,
                                   position=[self.x(), self.y()])

    def wheelEvent(self, event):
        self.renderer.model_scale = max(.25, min(3, self.renderer.model_scale *
                                                 1.1 ** (event.angleDelta().y()/120)))
        event.accept()

    def keyPressEvent(self, event):
        x,z = self.renderer.offset
        shifts = {Qt.Key.Key_Left: (-.1,0), Qt.Key.Key_Right: (.1,0),
                  Qt.Key.Key_Up: (0,.1), Qt.Key.Key_Down: (0,-.1)}
        if self.diagnostics:
            self.diagnostics.write('key', key=event.key())
        if event.key() == Qt.Key.Key_F7 and self.diagnostics:
            self.show_diagnostic_overlay = not self.show_diagnostic_overlay
        elif event.key() == Qt.Key.Key_F8 and self.diagnostics:
            try:
                self.diagnostics.capture(self)
            except OSError as exc:
                self.diagnostics.write('capture_error', message=str(exc))
        elif event.key() == Qt.Key.Key_Space:
            self.renderer.clock.paused = not self.renderer.clock.paused
        elif event.key() in shifts:
            dx,dz = shifts[event.key()]
            self.renderer.offset = (x+dx,z+dz)
        elif event.key() == Qt.Key.Key_R:
            self.renderer.offset = (0,0)
            self.renderer.model_scale = 1.0
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.timer.stop()
        if self.diagnostics and self.renderer and self.renderer.base:
            self.diagnostics.sample(self, force=True)
        if self.renderer is not None:
            self.renderer.close()
        if self.diagnostics:
            self.diagnostics.close()
        super().closeEvent(event)
