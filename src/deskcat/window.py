import math
import time
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QApplication, QMenu, QWidget
from .states import State, StateMachine


class CatWindow(QWidget):
    """Transparent desktop overlay with a deliberately non-3D placeholder."""
    def __init__(self, scale: float = 1.0):
        super().__init__()
        self.setWindowTitle("DeskCat prototype")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(round(240 * scale), round(220 * scale))
        self.machine = StateMachine()
        self._drag_offset = None
        self._resume = State.IDLE
        self._x = 0.0
        self._direction = 1
        self._phase = 0.0
        self._last = time.monotonic()
        screen = QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.right() - self.width(), area.bottom() - self.height())
        self._x = float(self.x())
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    def tick(self):
        now = time.monotonic()
        dt = min(now - self._last, 0.1)
        self._last = now
        self.machine.update(dt)
        self._phase += dt
        if self.machine.state == State.WALK:
            area = self.screen().availableGeometry()
            self._x += self._direction * 75 * dt
            left, right = area.left(), area.right() + 1 - self.width()
            if self._x < left or self._x > right:
                self._direction *= -1
                self._x = max(left, min(right, self._x))
            self.move(round(self._x), self.y())
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / 240, self.height() / 220)
        w = self.machine.weights
        pose = w[State.SIT] * 12 + w[State.SLEEP] * 35
        bob = math.sin(self._phase * 9) * 3 * w[State.WALK]
        p.translate(0, pose + bob)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#8c8075"))
        p.drawEllipse(60, 85, 125, 83)
        p.drawEllipse(158, 85, 48, 27)
        p.setBrush(QColor("#b8aaa0"))
        p.drawEllipse(48, 45, 85, 78)
        p.drawPolygon(QPolygonF([QPointF(51, 62), QPointF(55, 25), QPointF(78, 48)]))
        p.drawPolygon(QPolygonF([QPointF(102, 48), QPointF(129, 25), QPointF(130, 69)]))
        p.drawEllipse(70, 145, 25, 32)
        p.drawEllipse(140, 145, 25, 32)
        p.setBrush(QColor("#263a26"))
        eye_height = max(2, round(10 * (1 - w[State.SLEEP])))
        p.drawEllipse(65, 76, 10, eye_height)
        p.drawEllipse(105, 76, 10, eye_height)
        p.setBrush(QColor("#dd9c9c"))
        p.drawEllipse(86, 94, 9, 6)
        p.resetTransform()
        p.setPen(QColor("#d0d0d0"))
        p.drawText(8, self.height() - 8, f"prototype · {self.machine.state.value}")
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._resume = self.machine.state
            self.machine.transition(State.DRAG)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            point = event.globalPosition().toPoint() - self._drag_offset
            screen = QApplication.screenAt(event.globalPosition().toPoint()) or self.screen()
            area = screen.availableGeometry()
            point.setX(max(area.left(), min(point.x(), area.right() + 1 - self.width())))
            point.setY(max(area.top(), min(point.y(), area.bottom() + 1 - self.height())))
            self.move(point)
            self._x = float(self.x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.machine.transition(self._resume)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        for state in State:
            if state != State.DRAG:
                action = QAction(state.value, menu)
                action.triggered.connect(lambda checked=False, s=state: self.machine.transition(s))
                menu.addAction(action)
        menu.addSeparator()
        menu.addAction("Exit", self.close)
        menu.exec(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
