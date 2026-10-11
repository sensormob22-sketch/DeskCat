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
                 playback_speed=1.0, forward_heading=0.0, walk_speed=0.0):
        super().__init__(scale)
        self.setWindowTitle('DeskCat live 3D prototype')
        self.renderer = None
        # Wheel zoom must expand the transparent Qt surface, not only the 3D
        # mesh inside a permanently fixed 240x220 viewport.
        self._zoom_reference_size = (self.width(), self.height())
        self._zoom_reference_model_scale = model_scale
        self.walk_speed_override = walk_speed
        self.walk_speed_px = walk_speed or 28.0
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
        # Model's toe/stance contract takes precedence unless an explicit speed
        # override was requested. Recompute after zoom and playback speed edits.
        if self.renderer is not None and self.walk_speed_override == 0:
            matched = self.renderer.matched_walk_speed(self.height())
            if matched is not None:
                self.walk_speed_px = matched
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

    def zoom_to(self, target_scale):
        """Enlarge the Qt alpha viewport with the cat; retain screen containment.

        Keep pixels-per-world-unit constant by enlarging the orthographic film
        with the window. This avoids the old cropped-cat zoom behaviour and
        does not fake a zoom by shrinking the model back to its former size.
        """
        if self.renderer is None:
            return
        base_width, base_height = self._zoom_reference_size
        base_scale = self._zoom_reference_model_scale
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        # Leave usable desktop space around the overlay. On smaller displays
        # limit actual cat scale rather than crop a larger animal.
        max_width = max(1, int(available.width() * .88))
        max_height = max(1, int(available.height() * .82))
        maximum = min(3.0, base_scale * max_width / base_width,
                      base_scale * max_height / base_height)
        minimum = min(.25, maximum)
        scale = max(minimum, min(float(target_scale), maximum))
        ratio = scale / base_scale
        width = max(1, min(max_width, round(base_width * ratio)))
        height = max(1, min(max_height, round(base_height * ratio)))

        # Hold the original bottom/centre anchor in desktop coordinates, so
        # zooming does not teleport the paws to a different floor or monitor.
        center_x = self.x() + self.width() / 2.0
        bottom_y = self.y() + self.height()
        self.renderer.model_scale = scale
        self.renderer.viewport_height_scale = height / base_height
        self.renderer.camera_height_scale = ratio
        self.setFixedSize(width, height)
        x = round(center_x - width / 2.0)
        y = round(bottom_y - height)
        x = max(available.left(), min(x, available.left() + available.width() - width))
        y = max(available.top(), min(y, available.top() + available.height() - height))
        self.move(x, y)
        self._x = float(self.x())
        # Render at the new physical DPR resolution straight away: otherwise
        # Qt may briefly scale the old, cropped frame during a wheel event.
        self._image = self.render_frame(0)
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self.zoom_to(self.renderer.model_scale * 1.1 ** (delta / 120))
        event.accept()

    def keyPressEvent(self, event):
        x,z = self.renderer.offset
        shifts = {Qt.Key.Key_Left: (-.1,0), Qt.Key.Key_Right: (.1,0),
                  Qt.Key.Key_Up: (0,.1), Qt.Key.Key_Down: (0,-.1)}
        if self.diagnostics:
            self.diagnostics.write('key', key=event.key())
        if event.key() == Qt.Key.Key_W:
            self.machine.transition(State.IDLE if self.machine.state == State.WALK else State.WALK)
        elif event.key() == Qt.Key.Key_F7 and self.diagnostics:
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
            self.zoom_to(self._zoom_reference_model_scale)
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
