import argparse
import json
import math
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .window import CatWindow


def main(argv=None):
    parser = argparse.ArgumentParser(description="DeskCat transparent desktop prototype")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--smoke-test", action="store_true",
                        help="show window, run event loop, report and exit after 250 ms")
    parser.add_argument('--renderer', choices=('qt', 'panda'), default='qt')
    parser.add_argument('--start-walking', action='store_true', help='start the animated cat walking immediately')
    parser.add_argument('--walk-speed', type=float, default=28.0, help='desktop walking speed in logical pixels per second')
    parser.add_argument('--model', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'assets/3d/test_cat.glb')
    parser.add_argument('--model-scale', type=float, default=1.0)
    parser.add_argument('--model-x', type=float, default=0.0)
    parser.add_argument('--model-z', type=float, default=0.0)
    parser.add_argument('--position', type=int, nargs=2, metavar=('X', 'Y'))
    parser.add_argument('--benchmark', type=int, metavar='FRAMES')
    parser.add_argument('--clips', type=Path, help='JSON state -> actual clip name (or null)')
    parser.add_argument('--diagnostics', type=Path, metavar='DIRECTORY')
    parser.add_argument('--playback-speed', type=float, default=1.0)
    parser.add_argument('--forward-heading', type=float, default=0.0,
                        help='Heading offset in degrees that makes model face screen-right')
    args = parser.parse_args(argv)
    if not 0.5 <= args.scale <= 3:
        parser.error("--scale must be between 0.5 and 3")
    if not 0.25 <= args.model_scale <= 3:
        parser.error('--model-scale must be between 0.25 and 3')
    if not math.isfinite(args.walk_speed) or not 1 <= args.walk_speed <= 150:
        parser.error('--walk-speed must be between 1 and 150 logical pixels/second')
    if args.start_walking and args.renderer != 'panda':
        parser.error('--start-walking requires --renderer panda')
    if args.benchmark is not None and args.benchmark < 10:
        parser.error('--benchmark requires at least 10 frames')
    if not math.isfinite(args.playback_speed) or args.playback_speed < 0:
        parser.error('--playback-speed must be finite and nonnegative')
    if not all(math.isfinite(v) for v in (args.model_x, args.model_z, args.forward_heading)):
        parser.error('Model position and heading must be finite')
    if args.diagnostics and (args.renderer != 'panda' or args.benchmark is not None):
        parser.error('--diagnostics requires --renderer panda and no --benchmark')
    diagnostics = None
    try:
        if args.diagnostics:
            from .diagnostics import Diagnostics
            diagnostics = Diagnostics(args.diagnostics)
        clip_map = None
        if args.clips:
            clip_map = json.loads(args.clips.read_text(encoding='utf-8'))
            if not isinstance(clip_map, dict) or any(not isinstance(k, str) or
                    (v is not None and not isinstance(v, str)) for k,v in clip_map.items()):
                raise ValueError('--clips must contain a JSON object of names or null')
        if args.benchmark is not None:
            from .benchmark import benchmark
            print(json.dumps(benchmark(args.model, args.benchmark,
                                       round(240*args.scale), round(220*args.scale))))
            return 0
        app = QApplication.instance() or QApplication([])
        if args.renderer == 'panda':
            from .window3d import ThreeDWindow
            window = ThreeDWindow(args.scale, args.model, args.model_scale,
                                  (args.model_x, args.model_z), clip_map=clip_map,
                                  diagnostics=diagnostics, playback_speed=args.playback_speed,
                                  forward_heading=args.forward_heading,
                                  walk_speed=args.walk_speed)
        else:
            window = CatWindow(args.scale)
    except Exception as exc:
        print(f'DeskCat startup failed: {exc}', file=sys.stderr)
        if diagnostics:
            diagnostics.write('startup_error', message=str(exc))
            diagnostics.close()
        return 1
    if args.position:
        window.move(*args.position)
        window._x = float(window.x())
    window.show()
    if args.start_walking:
        from .states import State
        if window.renderer.clip_map[State.WALK] is None:
            print('DeskCat start-walking failed: model lacks a walk animation',file=sys.stderr)
            window.close()
            return 1
        window.machine.transition(State.WALK)
    if args.smoke_test:
        def finish():
            report = {"visible": window.isVisible(),
                      "state": window.machine.state.value,
                      "width": window.width(), "height": window.height()}
            if args.renderer == 'panda':
                report.update(renderer=window.renderer.driver, backend=window.renderer.backend,
                              dpr=window.devicePixelRatioF(),
                              render_width=window._image.width(),
                              render_height=window._image.height(),
                              corner_alpha=window._image.pixelColor(0,0).alpha(),
                              clip_map={s.value:c for s,c in window.renderer.clip_map.items()},
                              missing_states=window.renderer.missing_states)
            print(json.dumps(report))
            window.close()
            app.quit()
        QTimer.singleShot(250, finish)
    result = app.exec()
    return 1 if getattr(window, "render_error", None) else result
