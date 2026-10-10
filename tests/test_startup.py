import json
import os
import subprocess
import sys
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from deskcat.states import State
from deskcat.window import CatWindow


def test_application_process():
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}
    result = subprocess.run([sys.executable, '-m', 'deskcat', '--smoke-test'],
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {'visible': True, 'state': 'idle', 'width': 240, 'height': 220}


def test_overlay_and_drag(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication.instance() or QApplication([])
    window = CatWindow()
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    window.machine.transition(State.WALK)
    original = window.pos()
    press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(80, 80),
                        QPointF(original + QPoint(80, 80)), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.mousePressEvent(press)
    assert window.machine.state == State.DRAG
    move = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(80, 80),
                       QPointF(original + QPoint(30, 30)), Qt.MouseButton.NoButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.mouseMoveEvent(move)
    assert window.pos() != original
    release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(80, 80),
                          QPointF(window.pos()), Qt.MouseButton.LeftButton,
                          Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    window.mouseReleaseEvent(release)
    assert window.machine.state == State.WALK
    window.close()
