"""CI regression: zoom expands the desktop alpha buffer without clipping fur.

Run with QT_QPA_PLATFORM=offscreen and the rebuilt Stage 18 experimental GLB.
This validates Qt buffer dimensions + Panda3D alpha bounds, not physical DWM.
"""
import argparse
import json
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt

from deskcat.window3d import ThreeDWindow
from deskcat.states import State


def alpha_bounds(image):
    width, height = image.width(), image.height()
    alpha = bytes(image.constBits())[3::4]
    indices = [i for i, a in enumerate(alpha) if a > 12]
    if len(indices) < 200:
        raise AssertionError('Missing visible cat pixels')
    xs = [i % width for i in indices]
    ys = [i // width for i in indices]
    box = [min(xs), min(ys), max(xs), max(ys)]
    if min(box[0], box[1], width - 1 - box[2], height - 1 - box[3]) < 2:
        raise AssertionError(f'Cat touched/crossed alpha framebuffer edge: {box} vs {width}x{height}')
    return box


def main(model, out):
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    win = ThreeDWindow(scale=1.5, model=model, model_scale=.9,
                       forward_heading=180, walk_speed=0)
    try:
        win.show()
        app.processEvents()
        baseline_size = (win.width(), win.height())
        reference_scale = win.renderer.model_scale
        win.machine.transition(State.WALK)
        win.machine.update(.3)
        base_img = win.render_frame(0)
        base_bounds = alpha_bounds(base_img)
        base_width = base_bounds[2] - base_bounds[0]
        speed_before = win.renderer.matched_walk_speed(win.height())
        assert speed_before is not None and speed_before > 0
        assert base_img.save(str(out / 'zoom_initial.png'))
        win.zoom_to(1.6)
        app.processEvents()
        assert win.renderer.model_scale > reference_scale * 1.1
        assert win.width() > baseline_size[0]
        assert win.height() > baseline_size[1]
        assert win.renderer._size == (win._image.width(), win._image.height())
        assert win.renderer.matched_walk_speed(win.height()) > speed_before
        if win.width() > win.screen().availableGeometry().width():
            raise AssertionError('Zoom viewport exceeds desktop geometry')
        result = []
        for direction, label in ((1, 'right'), (-1, 'left')):
            win.renderer.direction = direction
            win.renderer.heading = win.renderer.forward_heading + (180 if direction < 0 else 0)
            for i in range(5):
                image = win.renderer.frame(.32, {State.WALK: 1.0},
                                           win._image.width(), win._image.height())
                box = alpha_bounds(image)
                if i == 2:
                    assert image.save(str(out / f'zoom_{label}.png'))
                result.append((label, i, box))
        enlarged_width = max(x[2][2] - x[2][0] for x in result)
        assert enlarged_width > base_width * 1.10, 'Model did not grow visually with zoom'
        zoom_size = (win.width(), win.height())
        # Key R restores the startup scale AND the matching alpha framebuffer.
        win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R,
                                   Qt.KeyboardModifier.NoModifier))
        assert abs(win.renderer.model_scale - reference_scale) < 1e-6
        assert (win.width(), win.height()) == baseline_size
        assert win._image.width() == round(win.width() * win.devicePixelRatioF())
        assert win._image.height() == round(win.height() * win.devicePixelRatioF())
        alpha_bounds(win._image)
        payload = dict(initial_size=baseline_size, zoom_size=zoom_size,
                       base_bounds=base_bounds, zoom_bounds=result,
                       max_enlarged_cat_width=enlarged_width,
                       initial_speed=speed_before,
                       framing='PASS', physical_dwm='NOT TESTED')
        (out / 'zoom_report.json').write_text(json.dumps(payload, indent=2))
        print(json.dumps({k: v for k, v in payload.items() if k != 'zoom_bounds'}, indent=2))
    finally:
        win.close()
        app.processEvents()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    options = parser.parse_args()
    main(options.model, options.out)
