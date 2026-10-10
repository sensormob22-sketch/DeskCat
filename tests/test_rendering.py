"""Real GLB/Actor/render/readback tests; no mocked Panda3D."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest
from PySide6.QtGui import QColor, QImage, QPainter
from panda3d.core import GeomVertexReader, Thread
from deskcat.rendering.panda import DEFAULT_MODEL, ModelError, PandaRenderer
from deskcat.states import State, StateMachine


@pytest.fixture(scope='module')
def renderer():
    os.environ.setdefault('MESA_SHADER_CACHE_DIR', '/tmp/deskcat-mesa')
    instance = PandaRenderer()
    yield instance
    instance.close()


def effect(renderer, clip):
    return renderer.actor.getPartBundle('modelRoot').getControlEffect(
        renderer.actor.getAnimControl(clip))


def pixels(image):
    return bytes(image.constBits())


def vertices(renderer):
    geom = renderer.actor.find('**/+GeomNode').node().getGeom(0)
    data = geom.getVertexData().animateVertices(True, Thread.getCurrentThread())
    reader = GeomVertexReader(data, 'vertex')
    result = []
    while not reader.isAtEnd():
        result.append(tuple(reader.getData3f()))
    return result


def test_glb_structure_and_reproducibility(tmp_path):
    raw = DEFAULT_MODEL.read_bytes()
    magic, version, size = struct.unpack_from('<III', raw)
    assert magic == 0x46546C67 and version == 2 and size == len(raw)
    length, chunk_type = struct.unpack_from('<II', raw, 12)
    assert chunk_type == 0x4E4F534A
    gltf = json.loads(raw[20:20+length])
    assert gltf['asset']['version'] == '2.0'
    assert len(gltf['skins'][0]['joints']) == 6
    assert {a['name'] for a in gltf['animations']} == {s.value for s in State}
    import runpy
    generator = runpy.run_path(str(DEFAULT_MODEL.parents[2] / 'tools/generate_test_cat.py'))
    output = tmp_path / 'test.glb'
    generator['generate'](output)
    assert output.read_bytes() == raw


def test_alpha_and_qt_composition(renderer):
    image = renderer.frame(.1, StateMachine().weights, 240, 220)
    rgba = pixels(image)
    alphas = rgba[3::4]
    assert image.pixelColor(0,0).alpha() == 0
    assert sum(a == 0 for a in alphas) > 240*220//2
    assert sum(a == 255 for a in alphas) > 500  # actual geometry, not empty frame
    canvas = QImage(240, 220, QImage.Format.Format_RGBA8888)
    canvas.fill(QColor('#ff00ff'))
    painter = QPainter(canvas)
    painter.drawImage(0, 0, image)
    painter.end()
    assert canvas.pixelColor(0,0) == QColor('#ff00ff')
    assert pixels(canvas) != bytes([255,0,255,255]) * (240*220)


def test_skeletal_deformation_and_blend(renderer):
    machine = StateMachine()
    renderer.elapsed = 0
    renderer.frame(0, machine.weights, 240, 220)
    before = vertices(renderer)
    machine.transition(State.WALK)
    machine.update(.15)
    renderer.frame(.5, machine.weights, 240, 220)
    after = vertices(renderer)
    assert any(sum(abs(a-b) for a,b in zip(p,q)) > .01 for p,q in zip(before,after))
    assert effect(renderer, 'idle') == pytest.approx(.5)
    assert effect(renderer, 'walk') == pytest.approx(.5)
    machine.update(.15)
    renderer.frame(.1, machine.weights, 240, 220)
    assert effect(renderer, 'walk') == 1
    assert effect(renderer, 'idle') == 0


@pytest.mark.parametrize('state', list(State))
def test_all_clips_render(renderer, state):
    machine = StateMachine()
    machine.transition(state)
    machine.update(.3)
    image = renderer.frame(.2, machine.weights, 240, 220)
    assert renderer.actor.getAnimControl(state.value).getNumFrames() == 60
    assert effect(renderer, state.value) == 1
    assert any(pixels(image)[3::4])


def test_scale_offset_and_physical_size(renderer):
    machine = StateMachine()
    renderer.elapsed = 0
    original = renderer.frame(0, machine.weights, 240, 220)
    renderer.model_scale = .7
    renderer.offset = (.3,.1)
    moved = renderer.frame(0, machine.weights, 360, 330)
    assert (moved.width(), moved.height()) == (360,330)
    assert renderer.pivot.getScale().x == pytest.approx(.7)
    assert renderer.pivot.getX() == pytest.approx(.3)
    assert pixels(original) != pixels(moved)
    renderer.model_scale, renderer.offset = 1.0, (0,0)


def test_model_errors_preserve_working_renderer(renderer, tmp_path):
    with pytest.raises(ModelError, match='not found'):
        renderer.load(str(tmp_path / 'absent.glb'))
    broken = tmp_path / 'broken.glb'
    broken.write_bytes(b'not a glb')
    with pytest.raises(ModelError, match='Cannot load'):
        renderer.load(str(broken))
    assert any(pixels(renderer.frame(.1, StateMachine().weights, 240,220))[3::4])


@pytest.mark.parametrize('scale', ['1', '1.5'])
def test_3d_application_process(scale):
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_SCALE_FACTOR': scale,
           'MESA_SHADER_CACHE_DIR': '/tmp/deskcat-mesa'}
    result = subprocess.run([sys.executable, '-m', 'deskcat', '--renderer', 'panda', '--smoke-test'],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['visible'] is True
    assert report['dpr'] == float(scale)
    assert report['render_width'] == round(240*float(scale))
    assert report['render_height'] == round(220*float(scale))
    assert report['corner_alpha'] == 0


def test_missing_model_process(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'deskcat', '--renderer', 'panda',
                             '--model', str(tmp_path/'missing.glb'), '--smoke-test'],
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 1
    assert 'Model not found' in result.stderr
    assert 'Traceback' not in result.stderr


def test_3d_window_interactions_process():
    script = r"""
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QKeyEvent
from PySide6.QtWidgets import QApplication
from deskcat.window3d import ThreeDWindow
from deskcat.states import State
app = QApplication([])
w = ThreeDWindow()
w.show()
app.processEvents()
assert w.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
assert w.windowFlags() & Qt.WindowType.FramelessWindowHint
assert w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
assert w.grab().toImage().pixelColor(0,0).alpha() == 0
# No onscreen Panda GraphicsWindow: only an offscreen GraphicsBuffer.
from panda3d.core import GraphicsBuffer
assert isinstance(w.renderer.base.win, GraphicsBuffer)
w.machine.transition(State.WALK)
p = w.pos()
w.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(80,80),
    QPointF(p+QPoint(80,80)), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
    Qt.KeyboardModifier.NoModifier))
assert w.machine.state == State.DRAG
w.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(80,80),
    QPointF(p+QPoint(30,30)), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
    Qt.KeyboardModifier.NoModifier))
assert w.pos() != p
w.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(80,80),
    QPointF(w.pos()), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
    Qt.KeyboardModifier.NoModifier))
assert w.machine.state == State.WALK
w.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right,
                         Qt.KeyboardModifier.NoModifier))
assert w.renderer.offset == (.1,0)
w.close()
assert w.renderer.base is None
"""
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen',
                                 'MESA_SHADER_CACHE_DIR': '/tmp/deskcat-mesa'}, timeout=30)
    assert result.returncode == 0, result.stderr


def variant_glb(path, names):
    raw = DEFAULT_MODEL.read_bytes()
    length = struct.unpack_from('<I', raw, 12)[0]
    doc = json.loads(raw[20:20+length])
    animations = doc['animations']
    doc['animations'] = []
    for original, new in names.items():
        animation = next(a for a in animations if a['name'] == original)
        animation['name'] = new
        doc['animations'].append(animation)
    if not doc['animations']:
        del doc['animations']
    encoded = json.dumps(doc).encode()
    encoded += b' ' * (-len(encoded)%4)
    binary_chunk = raw[20+length:]
    body = struct.pack('<II', len(encoded), 0x4E4F534A) + encoded + binary_chunk
    path.write_bytes(struct.pack('<III', 0x46546C67, 2, 12+len(body)) + body)


def test_rig_without_animations(renderer, tmp_path, capsys):
    asset = tmp_path/'rig-only.glb'
    variant_glb(asset, {})
    try:
        renderer.load(asset)
        assert renderer.clips == []
        assert all(c is None for c in renderer.clip_map.values())
        assert set(renderer.missing_states) == {s.value for s in State}
        machine = StateMachine()
        machine.transition(State.WALK)
        machine.update(.3)
        image = renderer.frame(.2, machine.weights, 240,220)
        assert any(pixels(image)[3::4])
        assert renderer.unavailable_active == ['walk']
        assert renderer.clock.times == {}
        assert 'NOT played' in capsys.readouterr().err
    finally:
        renderer.load(DEFAULT_MODEL)


def test_partial_and_explicit_mapping(renderer, tmp_path):
    asset = tmp_path/'partial.glb'
    variant_glb(asset, {'idle': 'Rest', 'walk': 'WalkCycle'})
    try:
        renderer.clip_overrides = {'idle': 'Rest', 'walk': 'WalkCycle'}
        renderer.load(asset)
        assert renderer.clip_map[State.WALK] == 'WalkCycle'
        assert renderer.clip_map[State.GROOM] is None
        machine = StateMachine()
        renderer.frame(.25, machine.weights,240,220)
        machine.transition(State.WALK)
        machine.update(.15)
        renderer.frame(0,machine.weights,240,220)
        assert renderer.clock.times['Rest'] == pytest.approx(.25)
        assert renderer.clock.times['WalkCycle'] == pytest.approx(.25)
        assert effect(renderer,'Rest') == pytest.approx(.5)
        assert effect(renderer,'WalkCycle') == pytest.approx(.5)
        machine.transition(State.GROOM)
        machine.update(.3)
        renderer.frame(0,machine.weights,240,220)
        assert effect(renderer,'WalkCycle') == 0
        assert renderer.unavailable_active == ['groom']
        renderer.clip_overrides = {'walk': 'absent'}
        with pytest.raises(ModelError,match='Mapped clip not found'):
            renderer.load(asset)
        assert renderer.clip_map[State.WALK] == 'WalkCycle'  # failed load is atomic
    finally:
        renderer.clip_overrides = {}
        renderer.load(DEFAULT_MODEL)


def test_direction_turn(renderer):
    try:
        renderer.heading = 0
        renderer.direction = -1
        renderer.frame(.1,StateMachine().weights,240,220)
        assert renderer.heading == pytest.approx(-54)
        renderer.frame(.3,StateMachine().weights,240,220)
        assert abs((renderer.pivot.getH()-180+180)%360-180) < .01
        renderer.direction = 1
        renderer.frame(.4,StateMachine().weights,240,220)
        assert abs(renderer.pivot.getH()) < .01
    finally:
        renderer.direction = 1
        renderer.heading = 0
