"""Read-only static cluster atlas; overlays are diagram nodes, not mesh edits."""
import json,os,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont
from panda3d.core import OrthographicLens,Point3,Vec3,LineSegs,TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage13';IMGS=OUT/'images';IMGS.mkdir(exist_ok=True)
x=json.loads((OUT/'defect_register.json').read_text());old=json.loads((ROOT/'docs/model-reports/exact-weld-proxy/preflight.json').read_text());mapping=json.loads((ROOT/'docs/model-reports/exact-weld-proxy/vertex_map.json').read_text());src=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
d,b,_=read_glb(src);source=accessor(d,b,d['meshes'][0]['primitives'][0]['attributes']['POSITION']);ps=[source[a[0]] for a in mapping['proxy_to_sources']];faces=mapping['proxy_faces_in_source_face_order']
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication([]);r=PandaRenderer(src,width=550,height=270);a=r.actor;a.setScale(1);a.setPos(0,0,0);a.setMaterialOff(20)
for stage in a.findAllTextureStages():
 if stage.getMode()!=TextureStage.MModulate:a.setTextureOff(stage,20)
def world(p):return Point3(p[0],-p[2],p[1])
def segment(lines,p,q):lines.moveTo(world(p));lines.drawTo(world(q))
def camera_frame(center,film,side=0,solid=False):
 target=world(center)
 dirs=[(0,-4,.35),(0,4,.35),(.2,-1,-4),(-4,0,.2),(4,0,.2)]
 direction=dirs[side];r.base.camera.setPos(target+Vec3(*direction));r.base.camera.lookAt(target,Vec3(0,0,1));lens=OrthographicLens();lens.setFilmSize(film,film*270/550);lens.setNearFar(.01,100);r.base.cam.node().setLens(lens);r.base.setBackgroundColor(.65,.65,.65,1)
 a.clearTexture();a.clearColor()
 if solid:a.setTextureOff(30);a.setColor(.75,.75,.75,1,30)
 else:
  for stage in a.findAllTextureStages():
   if stage.getMode()!=TextureStage.MModulate:a.setTextureOff(stage,20)
def overlay(clusters,context=False):
 lines=LineSegs();lines.setThickness(1.2)
 if context:
  lines.setColor(.45,.45,.45,1)
  for i in sorted({v for c in clusters for v in c['context_source_face_ids']}):
   f=faces[i]
   for k in range(3):segment(lines,ps[f[k]],ps[f[(k+1)%3]])
 for c in clusters:
  lines.setColor(.7,.2,.95,1);lines.setThickness(1.8)
  for i in c['source_face_ids']:
   f=faces[i]
   for k in range(3):segment(lines,ps[f[k]],ps[f[(k+1)%3]])
  for ei in c['event_ids']:
   e=x['events'][ei]
   if e['kind']=='fan':
    lines.setColor(1,1,1,1);lines.setThickness(4);p=list(e['midpoint'])
    for k in range(3):
     p1=p[:];p2=p[:];p1[k]-=.0015;p2[k]+=.0015;segment(lines,p1,p2)
   else:
    lines.setColor(*( (1,.1,.1,1) if e['kind']=='nonmanifold' else (1,.9,.1,1)));lines.setThickness(3);segment(lines,*[ps[v] for v in e['proxy_vertices']])
 node=r.base.render.attachNewNode(lines.create());node.setDepthTest(False);node.setDepthWrite(False);node.setLightOff();return node
meta={'driver':r.driver,'coordinates':'glTF X head-negative/Y-up/Z-left converted to Panda X/-Z/Y, scale 1','overlay':'Yellow boundary/red >2-face/white disconnected fan/violet incident source triangles/gray context ring. Depth disabled. Texture and solid paired views.','cluster_cameras':{},'scope':'Unchanged source surface, static base-color previews. Diagnostic overlays only. Not a skin test or repair.'}
for page in range(3):
 clusters=x['clusters'][page*8:(page+1)*8];canvas=QImage(1100,65+len(clusters)*310,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'));q=QPainter(canvas);q.setFont(QFont('DejaVu Sans',10));q.setPen(QColor('#151515'));q.drawText(10,22,'STAGE 13: inspection only — yellow boundary / red >2-face / white fans / violet source triangles')
 q.drawText(10,43,'Left: texture; right: solid from another side. Gray: context. Overlays show through surface. IDs in defect_register.json.')
 for row,c in enumerate(clusters):
  center=c['center'];spans=[c['bounds'][1][i]-c['bounds'][0][i] for i in range(3)];film=max(.045,max(spans)*2.8)
  if c['region']=='muzzle':film=max(film,.095)
  sides=[0 if center[2]>=0 else 1,2 if c['region'] in ['tail','belly_ventral_coat','pelvis_hind_limb'] else (1 if center[2]>=0 else 0)]
  meta['cluster_cameras'][c['id']]={'center':center,'film_size':film,'directions':sides}
  top=70+row*310;q.drawText(10,top,c['id']+' '+c['region']+' '+str(c['counts'])+' / faces '+str(len(c['source_face_ids'])))
  for col in range(2):
   camera_frame(center,film,sides[col],solid=col==1);node=overlay([c],context=True);q.drawImage(col*550,top+8,r.frame(0,{State.IDLE:1},550,270).copy());node.removeNode()
 q.end();canvas.save(str(IMGS/f'clusters_{page+1}.png'))
regions={'tail':([.41,.115,.025],.24,0),'belly':([-.015,.23,.015],.32,2),'back_neck':([-.22,.44,0],.27,0),'pelvis':([.22,.315,0],.25,2),'muzzle':([-.46,.467,.035],.19,3)}
canvas=QImage(1100,65+len(regions)*310,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'));q=QPainter(canvas);q.setPen(QColor('#151515'));q.setFont(QFont('DejaVu Sans',10));q.drawText(10,25,'REGIONAL CONTEXT: unchanged source left / highlighted local clusters right. No planned operation applied.')
for row,(label,(center,film,side)) in enumerate(regions.items()):
 selected=[c for c in x['clusters'] if c['region']=={'belly':'belly_ventral_coat','back_neck':'back_upper_body','pelvis':'pelvis_hind_limb'}.get(label,label)]
 top=70+row*310;q.drawText(10,top,label+' : '+', '.join(c['id'] for c in selected))
 for col in range(2):
  camera_frame(center,film,side);node=overlay(selected) if col else None;q.drawImage(col*550,top+8,r.frame(0,{State.IDLE:1},550,270).copy())
  if node:node.removeNode()
q.end();canvas.save(str(IMGS/'regional_context.png'));r.close();(OUT/'image_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
