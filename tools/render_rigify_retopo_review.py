"""Matched static review: original, uploaded primitive, failed metarig. No bend simulation."""
import json,math,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont
from panda3d.core import OrthographicLens,Point3,Vec3,LineSegs,TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor

root=Path.cwd();out=root/'docs/model-reports/rigify-retopo';imgs=out/'images';imgs.mkdir(exist_ok=True)
original=root/'assets/3d/tripo/deskcat_calico_h25_v1.glb';candidate=root/'artifacts/rigify_retopo/input_rest.glb'
d,b,_=read_glb(candidate);pts=accessor(d,b,d['meshes'][0]['primitives'][0]['attributes']['POSITION'])
lo=[min(p[i] for p in pts) for i in range(3)];hi=[max(p[i] for p in pts) for i in range(3)];scale=2/max(hi[i]-lo[i] for i in range(3));offset=(-(lo[0]+hi[0])/2*scale,(lo[2]+hi[2])/2*scale,-lo[1]*scale)
def world(p):return Point3(p[0]*scale+offset[0],-p[2]*scale+offset[1],p[1]*scale+offset[2])
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication.instance() or QGuiApplication([])
r=PandaRenderer(candidate,width=450,height=350);layout=json.loads((out/'metarig_layout.json').read_text())['bones']
views={'side':((0,-4,1.1),(0,0,.65)),'rear':((4,-.6,1.1),(0,0,.65)),'underside':((.5,-2,-3),(0,0,.5))}
meta={'driver':r.driver,'images':'STATIC rest comparison only; generation failed before heat weights or controlled bends; bones drawn through depth; base color, not certified PBR','scale':scale,'offset':offset,'cameras':views}
for style in ['texture','solid']:
 canvas=QImage(1350,1200,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'));q=QPainter(canvas);q.setPen(QColor('#161616'));q.setFont(QFont('DejaVu Sans',13));q.drawText(12,25,'Original highres | uploaded retopo primitive | failed Cat metarig — '+style)
 q.setFont(QFont('DejaVu Sans',10));q.drawText(12,47,'No automatic weights, no bend tests. Red gap is the failed Rigify tail/spine connection. Matched cameras.')
 for row,(view,(camera,target)) in enumerate(views.items()):
  for col,path in enumerate([original,candidate,candidate]):
   r.load(path);a=r.actor;a.setScale(scale);a.setPos(*offset);a.setMaterialOff(20)
   for stage in a.findAllTextureStages():
    if stage.getMode()!=TextureStage.MModulate:a.setTextureOff(stage,20)
   if style=='solid':a.setTextureOff(30);a.setColor(.75,.75,.75,1,30)
   lens=OrthographicLens();lens.setFilmSize(2.4,1.86);lens.setNearFar(.01,100);r.base.cam.node().setLens(lens);r.base.camera.setPos(*camera);r.base.camera.lookAt(Point3(*target),Vec3(0,0,1));r.base.setBackgroundColor(.70,.70,.70,1)
   overlay=None
   if col==2:
    lines=LineSegs();lines.setThickness(3);lines.setColor(.1,1,.3,1)
    for bone in layout.values():lines.moveTo(world(bone['head_gltf']));lines.drawTo(world(bone['tail_gltf']))
    lines.setColor(1,.05,.05,1);lines.setThickness(5);lines.moveTo(world(layout['spine']['head_gltf']));lines.drawTo(world(layout['tail.001']['head_gltf']))
    overlay=r.base.render.attachNewNode(lines.create());overlay.setDepthTest(False);overlay.setDepthWrite(False);overlay.setLightOff()
   q.setPen(QColor('#161616'));q.drawText(col*450+10,80+row*370,view+' / '+['original','retopo unskinned basis','FAILED generation'][col]);frame=r.frame(0,{State.IDLE:1},450,350);q.drawImage(col*450,90+row*370,frame.copy())
   if overlay:overlay.removeNode()
 q.end();canvas.save(str(imgs/(style+'_rest_and_metarig.png')))
r.close();(out/'image_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
