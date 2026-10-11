"""Windows offscreen test: real mesh zoom, native pixels, unchanged GPU size."""
import argparse,json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from deskcat.window3d import ThreeDWindow
from deskcat.states import State

def bounds(image):
    w,h=image.width(),image.height()
    alphas=bytes(image.constBits())[3::4]
    points=[i for i,a in enumerate(alphas) if a>12]
    if len(points)<200:raise AssertionError('Invisible cat in zoom frame')
    xs=[i%w for i in points];ys=[i//w for i in points]
    box=[min(xs),min(ys),max(xs),max(ys)]
    if min(box[0],box[1],w-1-box[2],h-1-box[3])<1:
        raise AssertionError(f'Cat clipped at zoom: {box} ({w}x{h})')
    return box

def main(model,out):
    out.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    win=ThreeDWindow(scale=1.0,model=model,model_scale=.9,
                     forward_heading=180,walk_speed=0)
    try:
        win.show();app.processEvents()
        original_size=(win.width(),win.height())
        original_scale=win.renderer.model_scale
        immutable=win.renderer._size
        assert immutable==win._render_size
        assert immutable[0]>original_size[0] and immutable[1]>original_size[1]
        first=bounds(win._image)
        cat_width=first[2]-first[0]
        speed=win.renderer.matched_walk_speed(original_size[1])
        records=[]
        win.machine.transition(State.WALK);win.machine.update(.3)
        for i,requested in enumerate((.6,.85,1.12,1.6,.5,1.15,1.5,.9,1.3)):
            win.zoom_to(requested);app.processEvents()
            assert win.renderer._size==immutable
            for direction in (-1,1):
                win._direction=direction
                win.renderer.heading=win.renderer.forward_heading+(180 if direction<0 else 0)
                win._image=win.render_frame(.08)
                assert win._image.width()==round(win.width()*win._render_dpr)
                assert win._image.height()==round(win.height()*win._render_dpr)
                assert win.renderer._size==immutable
                box=bounds(win._image)
                records.append({'scale':win.renderer.model_scale,'direction':direction,
                                'pixels':[win._image.width(),win._image.height()],
                                'bounds':box})
                if i in (2,5,7):
                    assert win._image.save(str(out/f'zoom_{i}_{direction}.png'))
        win.zoom_to(1.1);win._image=win.render_frame(0)
        expanded=bounds(win._image)
        assert (expanded[2]-expanded[0])>cat_width*1.1
        assert win.renderer.matched_walk_speed(original_size[1])>speed
        win.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_R,
                                   Qt.KeyboardModifier.NoModifier))
        win._image=win.render_frame(0)
        assert (win.width(),win.height())==original_size
        assert abs(win.renderer.model_scale-original_scale)<1e-6
        assert win.renderer._size==immutable
        bounds(win._image)
        summary={'status':'PASS','original_widget':original_size,
                 'immutable_gpu_buffer':immutable,'zoom_checks':records,
                 'native_pixel_crop':True,'no_bitmap_upsampling':True,
                 'real_windows_dwm':'NOT VERIFIED'}
        (out/'zoom_report.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps({k:v for k,v in summary.items() if k!='zoom_checks'},indent=2))
    finally:
        win.close();app.processEvents()

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();main(a.model,a.out)
