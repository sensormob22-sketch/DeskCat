"""Static original-surface views for one ventral appearance experiment."""
import os,sys,json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QFont,QColor
from panda3d.core import OrthographicLens,Point3,Point2,Vec3,LineSegs,TextureStage,GeomVertexData,GeomVertexFormat,GeomVertexWriter,Geom,GeomTriangles,GeomNode
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage15';app=QGuiApplication([])
SOURCE=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
r=PandaRenderer(width=900,height=600)
# Bootstrap offscreen window from the project's valid test model, then discard it.
# Never load or evaluate the retopo model's unusable original skin.
r.actor.cleanup();r.actor.removeNode();r.clips=[];r.has_skeleton=False;r.clip_map={state:None for state in State}
d,b,_=read_glb(SOURCE);primitive=d['meshes'][0]['primitives'][0];points=accessor(d,b,primitive['attributes']['POSITION']);indices=[i[0] for i in accessor(d,b,primitive['indices'])];faces=[indices[i:i+3] for i in range(0,len(indices),3)]
def world(p):return Point3(p[0],-p[2],p[1])
texture_file=ROOT/'artifacts/stage15/texture.png'
texture_file.parent.mkdir(parents=True,exist_ok=True)
view=d['bufferViews'][d['images'][0]['bufferView']];texture_file.write_bytes(b[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']])
source_normals=accessor(d,b,primitive['attributes']['NORMAL']);source_uv=accessor(d,b,primitive['attributes']['TEXCOORD_0'])
raw=GeomVertexData('UNCHANGED_RAW_SOURCE_NO_SKIN',GeomVertexFormat.getV3n3t2(),Geom.UHStatic);raw.setNumRows(len(points));v=GeomVertexWriter(raw,'vertex');n=GeomVertexWriter(raw,'normal');t=GeomVertexWriter(raw,'texcoord')
for p,normal,uv in zip(points,source_normals,source_uv):v.addData3(world(p));n.addData3(world(normal));t.addData2(uv[0],1-uv[1])
triangles=GeomTriangles(Geom.UHStatic)
for face in faces:triangles.addVertices(*face)
geom=Geom(raw);geom.addPrimitive(triangles);node=GeomNode('raw_source_without_armature');node.addGeom(geom);r.actor=r.base.render.attachNewNode(node);r.actor.setTexture(r.base.loader.loadTexture(str(texture_file)));r.actor.setMaterialOff(20);r.actor.setTwoSided(True)
center=[-.015,.235,.025];film=.205
views={'side':[0,.12,1],'below':[0,-1,.05],'oblique':[.5,-.65,1]}
patch_node=None
if (OUT/'patch_trial.json').exists():
 trial=json.loads((OUT/'patch_trial.json').read_text());vdata=GeomVertexData('one_local_backing',GeomVertexFormat.getV3n3t2(),Geom.UHStatic);vdata.setNumRows(len(trial['points_gltf']));vw=GeomVertexWriter(vdata,'vertex');nw=GeomVertexWriter(vdata,'normal');tw=GeomVertexWriter(vdata,'texcoord')
 pts=[world(p) for p in trial['points_gltf']];normals=[Vec3(0,0,0) for p in pts]
 for a,b,c in trial['faces']:
  normal=(pts[b]-pts[a]).cross(pts[c]-pts[a]);normal.normalize()
  for i in [a,b,c]:normals[i]+=normal
 for p,n,uv in zip(pts,normals,trial['uv_gltf']):
  n.normalize();vw.addData3(p);nw.addData3(n);tw.addData2(uv[0],1-uv[1])
 tris=GeomTriangles(Geom.UHStatic)
 for f in trial['faces']:tris.addVertices(*f)
 geom=Geom(vdata);geom.addPrimitive(tris);node=GeomNode('STAGE15_one_slit_backing');node.addGeom(geom);patch_node=r.base.render.attachNewNode(node);patch_node.setTexture(r.base.loader.loadTexture(str(ROOT/'artifacts/stage15/texture.png')));patch_node.setMaterialOff(20);patch_node.setTwoSided(True);patch_node.hide()
meta={'center':center,'film_width':film,'views':views,'driver':r.driver,'scope':'Raw static source surface; no source skin or animation applied. Base-color preview.'}
for name,vector in views.items():
 target=world(center);r.base.camera.setPos(target+world(vector)*3);r.base.camera.lookAt(target,Vec3(0,0,1));lens=OrthographicLens();lens.setFilmSize(film,film*600/900);lens.setNearFar(.01,100);r.base.cam.node().setLens(lens);r.base.setBackgroundColor(.18,.18,.18,1)
 rays=[]
 for u,v in [(410,200),(420,240),(420,285),(404,315),(390,250),(450,250),(440,200),(380,300)]:
  near=Point3();far=Point3();lens.extrude(Point2(2*u/900-1,1-2*v/600),near,far);m=r.base.cam.getMat(r.base.render);a=m.xformPoint(near);b=m.xformPoint(far);rays.append({'pixel':[u,v],'origin':[a.x,a.z,-a.y],'direction':[b.x-a.x,b.z-a.z,-b.y+a.y]})
 (OUT/f'rays_{name}.json').write_text(json.dumps(rays,indent=2)+'\n')
 if patch_node:patch_node.hide()
 image=r.frame(0,{State.IDLE:1},900,600).copy();image.save(str(OUT/f'images/before_{name}.png'))
 if patch_node:
  patch_node.show();r.frame(0,{State.IDLE:1},900,600).copy().save(str(OUT/f'images/after_{name}.png'));patch_node.hide()
 lines=LineSegs();lines.setThickness(2)
 register=json.loads((ROOT/'docs/model-reports/stage13/defect_register.json').read_text())
 for c in register['clusters']:
  if c['id'] not in ['D06','D14','D17']:continue
  lines.setColor(*{'D06':(1,.1,.1,1),'D14':(.1,1,.1,1),'D17':(.2,.5,1,1)}[c['id']])
  for fi in c['source_face_ids']:
   f=faces[fi]
   for i in range(3):lines.moveTo(world(points[f[i]]));lines.drawTo(world(points[f[(i+1)%3]]))
 node=r.base.render.attachNewNode(lines.create());node.setDepthTest(False);node.setLightOff();r.frame(0,{State.IDLE:1},900,600).copy().save(str(OUT/f'images/location_{name}.png'));node.removeNode()
r.close();(OUT/'camera_initial.json').write_text(json.dumps(meta,indent=2)+'\n')
