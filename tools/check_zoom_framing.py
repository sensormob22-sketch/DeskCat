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
        base_size = (win.width(), win.height())
        fixed_buffer_size = win.renderer._size
        assert fixed_buffer_size == win._render_size
        init_scale = win.renderer.model_scale
        base_image = win.grab().toImage()
        initial_bounds = alpha_bounds(base_image)
        initial_cat_width = initial_bounds[2] - initial_bounds[0]
        initial_speed = win.renderer.matched_walk_speed(win.height())
        assert base_image.save(str(out/'zoom_initial.png'))
        win.machine.transition(State.WALK)
        win.machine.update(.3)
        result = []
        # Move both directions while changing zoom repeatedly, including a
        # shrink-back and subsequent enlarge (reported user crash path).
        for j, scale in enumerate((1.1, 1.3, 1.6, 2.0, 1.5, 1.0,
                                   .65, .9, 1.5, 2.0, .9)):
            win.zoom_to(scale)
            app.processEvents()
            assert win.renderer._size == fixed_buffer_size
            assert win._render_size == fixed_buffer_size
            for direction in (1, -1):
                win._direction = direction
                win.renderer.heading = win.renderer.forward_heading + (
                    180 if direction < 0 else 0)
                win._image = win.render_frame(.08)
                win.update()
                app.processEvents()
                display = win.grab().toImage()
                bounds = alpha_bounds(display)
                if j in (3, 7):
                    label = 'large' if j == 3 else 'small'
                    assert display.save(str(out/f'zoom_{label}_{direction}.png'))
                result.append({'stage':j,'zoom':win.renderer.model_scale,
                    'direction':direction,'widget':[win.width(),win.height()],
                    'bounds':bounds})
                assert win.renderer._size == fixed_buffer_size
        # Compare on-screen composited cat silhouettes, not fixed source buffer
        # pixels: the Qt widget, rather than the GPU buffer, grows with zoom.
        win.zoom_to(1.6)
        win._image = win.render_frame(.08)
        win.update()
        app.processEvents()
        enlarged = win.grab().toImage()
        bbox = alpha_bounds(enlarged)
        assert (bbox[2]-bbox[0]) > initial_cat_width*1.1
        assert win.renderer.matched_walk_speed(win.height()) > initial_speed
        assert win.width() > base_size[0]
        assert win.renderer._size == fixed_buffer_size
        win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R,
                                   Qt.KeyboardModifier.NoModifier))
        app.processEvents()
        assert (win.width(), win.height()) == base_size
        assert abs(win.renderer.model_scale-init_scale)<1e-6
        assert win.renderer._size == fixed_buffer_size
        assert win.render_error is None
        result_path=out/'zoom_report.json'
        payload={'initial_widget':base_size,'immutable_rgba_gpu_buffer':fixed_buffer_size,
                 'zoom_samples':result,'initial_speed_px_s':initial_speed,
                 'increased_cat_width':bbox[2]-bbox[0],
                 'status':'PASS fixed-size GPU readback, zoom in/out and directions',
                 'physical_windows_dwm':'NOT TESTED'}
        result_path.write_text(json.dumps(payload,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in payload.items() if k!='zoom_samples'},indent=2))
    finally:
        win.close()
        app.processEvents()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    options = parser.parse_args()
    main(options.model, options.out)
