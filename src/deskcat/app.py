import argparse
import json
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .window import CatWindow


def main(argv=None):
    parser = argparse.ArgumentParser(description="DeskCat transparent desktop prototype")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--smoke-test", action="store_true",
                        help="show window, run event loop, report and exit after 250 ms")
    args = parser.parse_args(argv)
    if not 0.5 <= args.scale <= 3:
        parser.error("--scale must be between 0.5 and 3")
    app = QApplication.instance() or QApplication([])
    window = CatWindow(args.scale)
    window.show()
    if args.smoke_test:
        def finish():
            print(json.dumps({"visible": window.isVisible(),
                              "state": window.machine.state.value,
                              "width": window.width(), "height": window.height()}))
            window.close()
            app.quit()
        QTimer.singleShot(250, finish)
    return app.exec()
