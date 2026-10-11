"""Reproducible raw static profile comparisons; never evaluates source skin."""
import os,sys,json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont
from panda3d.core import *
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage17';app=QGuiApplication([])
def world(p):return Point3(p[0],-p[2],p[1])
def mesh(r,path):
 d,b,_=read_glb(path);parent=r.base.render.attachNewNode('static')
 for k,pr in enumerate(d['meshes'][0]['primitives']):
  at=pr['attributes'];p=accessor(d,b,at['POSITION']);ns=accessor(d,b,at['NORMAL']);uv=accessor(d,b,at['TEXCOORD_0']);ii=accessor(d,b,pr['indices'])
  raw=GeomVertexData('static',GeomVertexFormat.getV3n3t2(),Geom.UHStatic);raw.setNumRows(len(p));v=GeomVertexWriter(raw,'vertex');n=GeomVertexWriter(raw,'normal');t=GeomVertexWriter(raw,'texcoord')
  for a,c,u in zip(p,ns,uv):v.addData3(world(a));n.addData3(world(c));t.addData2(u[0],1-u[1])
  triangles=GeomTriangles(Geom.UHStatic)
  for j in range(0,len(ii),3):triangles.addVertices(ii[j][0],ii[j+1][0],ii[j+2][0])
  g=Geom(raw);g.addPrimitive(triangles);gn=GeomNode('surface');gn.addGeom(g);node=parent.attachNewNode(gn)
  mat=d['materials'][pr.get('material',0)];idx=mat['pbrMetallicRoughness']['baseColorTexture']['index'];img=d['images'][d['textures'][idx]['source']];bv=d['bufferViews'][img['bufferView']];f=ROOT/f'artifacts/stage17/texture_{k}.img';f.write_bytes(b[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']]);node.setTexture(r.base.loader.loadTexture(str(f)));node.setTwoSided(mat.get('doubleSided',False));node.setMaterialOff(20)
 return parent
r=PandaRenderer(width=1200,height=800);r.actor.cleanup();r.actor.removeNode();r.clips=[];r.has_skeleton=False;r.clip_map={s:None for s in State};r.actor=r.base.render.attachNewNode('unused')
views={'profile':([0,.29,0],[0,0,1],1.35),'left':([-.015,.245,.04],[0,0,1],.35),'right':([-.015,.245,-.04],[0,0,-1],.35),'below':([-.015,.245,0],[0,-1,.05],.4),'oblique_left':([-.015,.245,.025],[.5,-.65,1],.32),'oblique_right':([-.015,.245,-.025],[-.5,-.65,-1],.32)}
paths={'before':ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'}
candidate=ROOT/'assets/3d/retopo/deskcat_belly_profile_fix_01.glb'
if candidate.exists():paths['after']=candidate
for phase,path in paths.items():
 node=mesh(r,path)
 for name,(center,vector,film) in views.items():
  target=world(center);r.base.camera.setPos(target+world(vector)*3);r.base.camera.lookAt(target,Vec3(0,0,1));lens=OrthographicLens();lens.setFilmSize(film,film*800/1200);lens.setNearFar(.01,100);r.base.cam.node().setLens(lens);r.base.setBackgroundColor(.18,.18,.18,1);r.frame(0,{State.IDLE:1},1200,800).copy().save(str(OUT/f'images/{phase}_{name}.png'))
 node.removeNode()
if 'after' in paths:
 for name,out in [('profile','belly_profile_before_after'),('left','belly_left_closeup_before_after'),('right','belly_right_closeup_before_after'),('below','belly_below_before_after'),('oblique_left','belly_oblique_left_before_after'),('oblique_right','belly_oblique_right_before_after')]:
  a=QImage(str(OUT/f'images/before_{name}.png'));b=QImage(str(OUT/f'images/after_{name}.png'));canvas=QImage(2400,840,QImage.Format_RGB32);canvas.fill(QColor('#ededed'));q=QPainter(canvas);q.setPen(QColor('black'));q.setFont(QFont('Sans',20));q.drawText(20,30,'BEFORE — original static geometry');q.drawText(1220,30,'AFTER — local profile repair');q.drawImage(0,40,a);q.drawImage(1200,40,b);q.end();canvas.save(str(OUT/f'images/{out}.png'))
 QImage(str(OUT/'images/after_profile.png')).save(str(OUT/'images/side_profile_result.png'))
(OUT/'cameras.json').write_text(json.dumps({'views':views,'driver':r.driver,'resolution':[1200,800],'render':'Panda3D raw static base-color preview; not full PBR or Windows GUI'},indent=2)+'\n');r.close()
