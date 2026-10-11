"""Package existing trial evidence, never repairs or exports geometry."""
import json,hashlib,csv,sys
from pathlib import Path
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QGuiApplication
import os
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/model-reports/stage15'
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication([])
# Comparable cameras and images: left original, right rejected single local backing.
for name in ['side','below','oblique']:
 before=QImage(str(OUT/f'images/before_{name}.png'));after=QImage(str(OUT/f'images/after_{name}.png'));assert not before.isNull() and before.size()==after.size()
 canvas=QImage(1800,645,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'));q=QPainter(canvas);q.setFont(QFont('DejaVu Sans',13));q.setPen(QColor('#151515'));q.drawText(12,28,'BEFORE / '+name);q.drawText(912,28,'AFTER / REJECTED — flat strip, crossings; not a corrected model');q.drawImage(0,45,before);q.drawImage(900,45,after);q.end();assert canvas.save(str(OUT/f'images/comparison_{name}.png'))
# Preserve only cropped visual evidence, not the large MP4 or full browser screenshot.
for time in ['10_5','16_5']:
 image=QImage(str(ROOT/f'artifacts/stage15/tripo_{time}.png'));assert not image.isNull();assert image.copy(315,150,1340,850).save(str(OUT/f'images/tripo_{time}.png'))
# Record sampled original base-color values at rays and on proposed UV (glTF v-down).
texture=QImage(str(ROOT/'artifacts/stage15/texture.png'));ray=json.loads((OUT/'ray_diagnosis.json').read_text());trial=json.loads((OUT/'patch_trial.json').read_text())
def color(uv):return list(texture.pixelColor(min(texture.width()-1,max(0,int(uv[0]*texture.width()))),min(texture.height()-1,max(0,int(uv[1]*texture.height())))).getRgb()[:3])
for view,rays in ray.items():
 for r in rays:
  for hit in r['hits']:hit['base_color_srgb_8bit']=color(hit['uv'])
(OUT/'ray_diagnosis.json').write_text(json.dumps(ray,indent=2)+'\n')
trial.update(rejected=True,rejection_reasons=['10 new strict crossing pairs with existing fur','Visible flat strip and partial slit coverage in underside/oblique views'],result='STOP: no scene save or GLB export',uv_vertex_base_colors=[color(u) for u in trial['uv_gltf']],trial_count=1)
(OUT/'patch_trial.json').write_text(json.dumps(trial,indent=2)+'\n')
frozen=json.loads((ROOT/'docs/model-reports/stage13/preserved_manifest.json').read_text())
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==s for n,s in frozen.items())
(OUT/'preservation.json').write_text(json.dumps({'all_stage13_frozen_files_unchanged':True,'files_checked':len(frozen),'source_scene_sha256':frozen['assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend'],'source_glb_sha256':frozen['assets/3d/retopo/deskcat_calico_retopo_16460.glb'],'video_sha256':hashlib.sha256(Path('/workspace/attachments/949ef1f6-fcb7-4d0d-9449-9397771545cd/Запись экрана 2026-10-11 151327.mp4').read_bytes()).hexdigest(),'scope':'Existing source models/scenes/reports byte hashes; new trial exists in JSON/images only, no blend/glb saved'},indent=2)+'\n')
