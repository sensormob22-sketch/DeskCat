"""Opt-in local JSONL diagnostics. No credentials or process environment dump."""
import json
import platform
from importlib.metadata import version
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import qVersion


class Diagnostics:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.log = (self.directory/'session.jsonl').open('a', encoding='utf-8')
        self.last_sample = 0.0
        self.bounds = None
        self.sequence = 0
        self.write('session', os=platform.platform(), python=platform.python_version(),
                   qt=qVersion(), panda3d=version('panda3d'), gltf=version('panda3d-gltf'),
                   windows_visual_validation='NOT VERIFIED')

    def write(self, event, **fields):
        self.log.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
                                   'event': event, **fields}, ensure_ascii=False)+'\n')
        self.log.flush()

    def sample(self, window, force=False):
        now = time.monotonic()
        if not force and now-self.last_sample < 1:
            return
        self.last_sample = now
        r = window.renderer
        image = window._image
        rgba = bytes(image.constBits())
        alpha = rgba[3::4]
        width, height = image.width(), image.height()
        positions = [i for i,a in enumerate(alpha) if a > 0]
        bounds = None
        if positions:
            xs = [i % width for i in positions]
            ys = [i // width for i in positions]
            bounds = [min(xs),min(ys),max(xs),max(ys)]
        self.bounds = bounds
        screen = window.screen()
        self.write('frame', position=[window.x(),window.y()],
                   logical_size=[window.width(),window.height()], physical_size=[width,height],
                   dpr=window.devicePixelRatioF(), logical_dpi=screen.logicalDotsPerInch(),
                   screen=screen.name(), visible=window.isVisible(), active=window.isActiveWindow(),
                   window_flags=int(window.windowFlags()), direction=window._direction,
                   heading=r.heading, state=window.machine.state.value,
                   weights={s.value:v for s,v in window.machine.weights.items()},
                   clip_map={s.value:c for s,c in r.clip_map.items()},
                   missing_states=r.missing_states, unavailable_active=r.unavailable_active,
                   clip_times=r.clock.times, playback_speed=r.clock.speed, paused=r.clock.paused,
                   driver=r.driver, backend=r.backend, model=r.model_path, model_scale=r.model_scale,
                   model_offset=r.offset, render_ms=r.last_frame_ms,
                   frame_interval_ms=window.frame_interval_ms,
                   transparent_pixels=alpha.count(0), opaque_pixels=alpha.count(255),
                   alpha_bounds=bounds, corner_alpha=image.pixelColor(0,0).alpha(),
                   touches_image_edge=bool(bounds and (bounds[0]==0 or bounds[1]==0 or
                                                       bounds[2]==width-1 or bounds[3]==height-1)),
                   render_error=window.render_error)

    def capture(self, window):
        self.sequence += 1
        name = f'frame-{time.time_ns()}-{self.sequence}.png'
        if not window._image.save(str(self.directory/name)):
            raise OSError('Cannot save diagnostic render capture')
        self.write('capture', file=name, scope='RGBA render only; NOT a desktop screenshot')
        self.sample(window, force=True)

    def close(self):
        if not self.log.closed:
            self.write('closed')
            self.log.close()
