"""Static annotated topology review. No weights, bone motion or new rig export."""
import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont
from panda3d.core import OrthographicLens,Point3,Vec3,LineSegs,TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/exact-weld-proxy';IMAGES=OUT/'images';IMAGES.mkdir(exist_ok=True)
x=json.loads((OUT/'preflight.json').read_text());mapping=json.loads((OUT/'vertex_map.json').read_text());src=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
d,b,_=read_glb(src);pr=d['meshes'][0]['primitives'][0];source=accessor(d,b,pr['attributes']['POSITION']);points=[source[ids[0]] for ids in mapping['proxy_to_sources']];faces=mapping['proxy_faces_in_source_face_order']
lo=[min(p[i] for p in source) for i in range(3)];hi=[max(p[i] for p in source) for i in range(3)];scale=2/max(hi[i]-lo[i] for i in range(3));offset=(-(lo[0]+hi[0])/2*scale,(lo[2]+hi[2])/2*scale,-lo[1]*scale)
def world(p):return Point3(p[0]*scale+offset[0],-p[2]*scale+offset[1],p[1]*scale+offset[2])
def segment(lines,a,b):lines.moveTo(world(a));lines.drawTo(world(b))
def marker(lines,p,size=.003):
 for k in range(3):
  a=list(p);b=list(p);a[k]-=size;b[k]+=size;segment(lines,a,b)
colors=[(.2,.8,1,1),(1,.4,0,1),(.2,1,.35,1),(.85,.25,1,1)]
views={'side':((0,-4,1.1),(0,0,.65),2.4),'rear':((4,-.6,1.1),(0,0,.65),2.4),'underside':((.5,-2,-3),(0,0,.5),2.4)}
head=world((-.47,.463,0));tail=world((.405,.15,0));belly=world((.055,.205,0))
zooms={'muzzle front':((-4,head.y,head.z),tuple(head),.48),'muzzle side':((head.x,-4,head.z),tuple(head),.48),'tail junction/surface':((tail.x,-4,tail.z+.05),tuple(tail),.65),'belly and pelvis underside':((belly.x,-1,-3),tuple(belly),.85)}
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication([]);r=PandaRenderer(src,width=450,height=330)
meta={'driver':r.driver,'scale':scale,'offset':offset,'overview_cameras':views,'closeup_cameras':zooms,'overlay':'Yellow boundary edges; red >2-face edges; white disconnected fans; cyan tiny triangles; violet baseline strict crossing faces; component colors C1 cyan/C2 orange/C3 green/C4 violet. Depth disabled to expose occluded defects.','scope':'Actual source surface rendered by Panda, numerically identical to proxy triangle geometry. No skin motion; base color only, not full PBR.'}
def sheet(name,cameras):
 canvas=QImage(1350,85+len(cameras)*370,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'));q=QPainter(canvas);q.setPen(QColor('#161616'));q.setFont(QFont('DejaVu Sans',12));q.drawText(10,23,'EXACT WELD PROXY: topology gate FAILED. 0 heat binds / 0 bends.')
 q.setFont(QFont('DejaVu Sans',9));q.drawText(10,45,'Yellow: boundary | Red: >2-face edges | White: disconnected fans | Cyan: tiny faces | Violet: crossing triangles')
 q.drawText(10,64,'Right: disconnected facial components C1 cyan, C2 orange, C3 green, C4 violet. Overlays shown through surface.')
 for row,(view,(camera,target,film)) in enumerate(cameras.items()):
  for col in range(3):
   a=r.actor;a.setScale(scale);a.setPos(*offset);a.setMaterialOff(20)
   for stage in a.findAllTextureStages():
    if stage.getMode()!=TextureStage.MModulate:a.setTextureOff(stage,20)
   lens=OrthographicLens();lens.setFilmSize(film,film*330/450);lens.setNearFar(.01,100);r.base.cam.node().setLens(lens);r.base.camera.setPos(*camera);r.base.camera.lookAt(Point3(*target),Vec3(0,0,1));r.base.setBackgroundColor(.65,.65,.65,1)
   overlay=None
   if col:
    lines=LineSegs();lines.setThickness(3)
    if col==1:
     # Crossing triangles first, other edge defects remain legible on top.
     lines.setColor(.75,.25,.95,1);lines.setThickness(1.5)
     crossing_faces=sorted({i for pair in x['baseline_crossing_pairs'] for i in pair})
     for i in crossing_faces:
      f=faces[i]
      for k in range(3):segment(lines,points[f[k]],points[f[(k+1)%3]])
     lines.setColor(1,.9,.1,1);lines.setThickness(3)
     for e in x['boundary_records']:segment(lines,*e['endpoints'])
     lines.setColor(1,.1,.1,1);lines.setThickness(4)
     for e in x['nonmanifold_records']:segment(lines,*e['endpoints'])
     lines.setColor(1,1,1,1)
     for i in x['topology']['disconnected_vertex_fan_ids']:marker(lines,points[i])
     lines.setColor(.05,1,1,1)
     for e in x['tiny_source_faces']:
      for k in range(3):segment(lines,e['points'][k],e['points'][(k+1)%3])
    else:
     lines.setThickness(4)
     for component,color in zip(x['components'][1:],colors):
      lines.setColor(*color)
      for i in component['source_face_ids']:
       f=faces[i]
       for k in range(3):segment(lines,points[f[k]],points[f[(k+1)%3]])
      marker(lines,component['centroid'],.002)
    overlay=r.base.render.attachNewNode(lines.create());overlay.setDepthTest(False);overlay.setDepthWrite(False);overlay.setLightOff()
   top=90+row*370;q.setPen(QColor('#161616'));q.drawText(col*450+8,top,view+' / '+['source surface','topology defects','C1-C4 facial islands'][col]);q.drawImage(col*450,top+8,r.frame(0,{State.IDLE:1},450,330).copy())
   if overlay:overlay.removeNode()
 q.end();canvas.save(str(IMAGES/name))
sheet('overview.png',views);sheet('closeups.png',zooms);r.close();(OUT/'image_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
