"""Actually capture default skin in Panda3D for original/metadata-copy. No rotations."""
import json,math,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from panda3d.core import GeomVertexReader,Thread
from deskcat.rendering.panda import PandaRenderer
from rig_readiness_audit import read_glb,accessor
root=Path.cwd();out=root/'docs/model-reports/existing-retopo-skin';work=root/'artifacts/existing_retopo_skin';results={}
r=None
try:
 for label,name in [('original','deskcat_calico_retopo_16460.glb'),('metadata','deskcat_calico_retopo_16460_metadata_diag.glb')]:
  path=root/'assets/3d/retopo'/name
  if r is None:r=PandaRenderer(path,width=450,height=350)
  else:r.load(path)
  a=r.actor;geoms=a.findAllMatches('**/+GeomNode');assert len(geoms)==1
  geom=geoms[0];assert geom.node().getNumGeoms()==1;vd=geom.node().getGeom(0).getVertexData()
  d,b,_=read_glb(path);p=d['meshes'][0]['primitives'][0];ps=accessor(d,b,p['attributes']['POSITION']);assert vd.getNumRows()==len(ps)
  reader=GeomVertexReader(vd,'vertex');raw=[]
  while not reader.isAtEnd():
   q=a.getRelativePoint(geom,reader.getData3());raw.append((q.x,q.z,-q.y))
  raw_error=max(math.dist(x,y) for x,y in zip(raw,ps));assert raw_error<1e-6
  a.getPartBundle('modelRoot').forceUpdate();animated=vd.animateVertices(True,Thread.getCurrentThread());reader=GeomVertexReader(animated,'vertex');values=[]
  while not reader.isAtEnd():
   q=a.getRelativePoint(geom,reader.getData3());values.append((q.x,q.z,-q.y))
  (work/f'panda_{label}.f32').write_bytes(b''.join(struct.pack('<3f',*v) for v in values))
  results[label]={'source_vertex_order_error':raw_error,'vertices':len(values),'actual_joint_count':len(a.getJoints()),'joint_names':[j.getName() for j in a.getJoints()],'max_default_vs_primitive_distance':max(math.dist(x,y) for x,y in zip(values,ps)),'joint_defaults':{j.getName():[[float(j.getDefaultValue().getCell(row,col)) for col in range(4)] for row in range(4)] for j in a.getJoints()},'driver':r.driver,'rotations_applied':0}
finally:
 if r:r.close()
(out/'panda_default.json').write_text(json.dumps(results,indent=2)+'\n')
