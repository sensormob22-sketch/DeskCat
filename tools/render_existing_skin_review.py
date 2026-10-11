"""Matched static review: original, uploaded primitive, failed metarig. No bend simulation."""
import json,math,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont
from panda3d.core import OrthographicLens,Point3,Vec3,LineSegs,TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor

root=Path.cwd();out=root/'docs/model-reports/existing-retopo-skin';imgs=out/'images';imgs.mkdir(exist_ok=True)
paths=[root/'artifacts/existing_retopo_skin'/(n+'.glb') for n in ['primitive','gltf_formula','blender_enabled','blender_disabled','panda_actual']]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication([]);r=PandaRenderer(paths[0],width=360,height=300)
views={'side':((0,-4,.3),(0,0,.15)),'rear':((4,0,.3),(0,0,.15)),'underside':((0,-.5,-4),(0,0,.15))}
labels=['Raw POSITION','glTF formula','Blender Armature ON','Blender Armature OFF','Actual Panda snapshot']
for style in ['texture','solid']:
 canvas=QImage(1800,1020,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'));q=QPainter(canvas);q.setFont(QFont('DejaVu Sans',11));q.drawText(10,25,'Fixed cameras / default poses only / no joint rotations / '+style)
 for row,(view,(camera,target)) in enumerate(views.items()):
  for col,path in enumerate(paths):
   r.load(path);a=r.actor;a.setScale(1);a.setPos(0,0,0);a.setMaterialOff(20)
   for stage in a.findAllTextureStages():
    if stage.getMode()!=TextureStage.MModulate:a.setTextureOff(stage,20)
   if style=='solid':a.setTextureOff(30);a.setColor(.75,.75,.75,1,30)
   lens=OrthographicLens();lens.setFilmSize(1.6,1.33);lens.setNearFar(.01,100);r.base.cam.node().setLens(lens);r.base.camera.setPos(*camera);r.base.camera.lookAt(Point3(*target),Vec3(0,0,1));r.base.setBackgroundColor(.70,.70,.70,1)
   q.drawText(col*360+5,50+row*320,view+' / '+labels[col]);q.drawImage(col*360,60+row*320,r.frame(0,{State.IDLE:1},360,300).copy())
 q.end();canvas.save(str(imgs/(style+'_default_comparison.png')))
r.close();(out/'image_metadata.json').write_text(json.dumps({'cameras':views,'scale':1,'offset':[0,0,0],'note':'Static snapshots from measured positions. Rest normals retained; base color only, not a PBR validation. No rotations.'},indent=2)+'\n')
