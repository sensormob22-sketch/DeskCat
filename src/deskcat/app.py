import argparse
import json
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
    parser.add_argument('--model', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'assets/3d/test_cat.glb')
    parser.add_argument('--model-scale', type=float, default=1.0)
    parser.add_argument('--model-x', type=float, default=0.0)
    parser.add_argument('--model-z', type=float, default=0.0)
    parser.add_argument('--position', type=int, nargs=2, metavar=('X', 'Y'))
    parser.add_argument('--benchmark', type=int, metavar='FRAMES')
    args = parser.parse_args(argv)
    if not 0.5 <= args.scale <= 3:
        parser.error("--scale must be between 0.5 and 3")
    if not 0.25 <= args.model_scale <= 3:
        parser.error('--model-scale must be between 0.25 and 3')
    if args.benchmark is not None and args.benchmark < 10:
        parser.error('--benchmark requires at least 10 frames')
    try:
        if args.benchmark is not None:
            from .benchmark import benchmark
            print(json.dumps(benchmark(args.model, args.benchmark,
                                       round(240*args.scale), round(220*args.scale))))
            return 0
        app = QApplication.instance() or QApplication([])
        if args.renderer == 'panda':
            from .window3d import ThreeDWindow
            window = ThreeDWindow(args.scale, args.model, args.model_scale,
                                  (args.model_x, args.model_z))
        else:
            window = CatWindow(args.scale)
    except Exception as exc:
        print(f'DeskCat startup failed: {exc}', file=sys.stderr)
        return 1
    if args.position:
        window.move(*args.position)
        window._x = float(window.x())
    window.show()
    if args.smoke_test:
        def finish():
            report = {"visible": window.isVisible(),
                      "state": window.machine.state.value,
                      "width": window.width(), "height": window.height()}
            if args.renderer == 'panda':
                report.update(renderer=window.renderer.driver,
                              dpr=window.devicePixelRatioF(),
                              render_width=window._image.width(),
                              render_height=window._image.height(),
                              corner_alpha=window._image.pixelColor(0,0).alpha())
            print(json.dumps(report))
            window.close()
            app.quit()
        QTimer.singleShot(250, finish)
    result = app.exec()
    return 1 if getattr(window, "render_error", None) else result
