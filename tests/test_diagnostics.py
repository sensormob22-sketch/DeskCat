import json
import os
import subprocess
import sys


def test_diagnostic_process_and_startup_error(tmp_path):
    directory = tmp_path/'success'
    env = {**os.environ, 'QT_QPA_PLATFORM':'offscreen',
           'MESA_SHADER_CACHE_DIR':'/tmp/deskcat-mesa'}
    script = '''
import time
from PySide6.QtWidgets import QApplication
from deskcat.diagnostics import Diagnostics
from deskcat.window3d import ThreeDWindow
from deskcat.states import State
app = QApplication([])
d = Diagnostics(DIRECTORY)
w = ThreeDWindow(diagnostics=d)
w.show()
app.processEvents()
d.capture(w)
w.machine.transition(State.WALK)
w._direction = -1
assert not w.can_move()
position = w.pos()
w._last = time.monotonic() - .02
w.tick()
assert w.pos() == position
w.renderer.heading = -180
assert w.can_move()
w._last = time.monotonic() - .03
w.tick()
assert w.x() < position.x()
def fail(*args):
    raise RuntimeError('injected render failure')
w.renderer.frame = fail
assert app.exec() == 1
assert w.render_error == 'injected render failure'
assert w.renderer.base is None
'''.replace('DIRECTORY', repr(str(directory)))
    result = subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for line in (directory/'session.jsonl').read_text().splitlines()]
    frame = next(e for e in events if e['event'] == 'frame')
    assert frame['corner_alpha'] == 0
    assert frame['render_ms'] > 0
    assert frame['alpha_bounds'] is not None
    assert frame['transparent_pixels'] > 0
    assert events[0]['windows_visual_validation'] == 'NOT VERIFIED'
    assert any(e['event']=='render_error' for e in events)
    assert list(directory.glob('frame-*.png'))
    failed = tmp_path/'failed'
    result = subprocess.run([sys.executable,'-m','deskcat','--renderer','panda',
                            '--model',str(tmp_path/'missing.glb'),'--diagnostics',str(failed)],
                           env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 1
    events = [json.loads(line) for line in (failed/'session.jsonl').read_text().splitlines()]
    assert any(e['event']=='startup_error' and 'Model not found' in e['message'] for e in events)
