"""Load the exported file through panda3d-gltf and capture its actual profile."""
import os,json,hashlib
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QGuiApplication
from panda3d.core import OrthographicLens,Point3,Vec3
from deskcat.rendering.panda import PandaRenderer
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage17';path=ROOT/'assets/3d/retopo/deskcat_belly_profile_fix_01.glb'
app=QGuiApplication([]);r=PandaRenderer(path,width=1200,height=800)
assert not r.has_skeleton and not r.clips
r.actor.setScale(1);r.actor.setPos(0,0,0)
geoms=list(r.actor.findAllMatches('**/+GeomNode'));assert geoms
low,high=r.actor.getTightBounds();assert abs((high.z-low.z)-.6)<.2
r.base.camera.setPos(0,-3,.29);r.base.camera.lookAt(Point3(0,0,.29),Vec3(0,0,1));lens=OrthographicLens();lens.setFilmSize(1.35,.9);lens.setNearFar(.01,100);r.base.cam.node().setLens(lens);r.base.setBackgroundColor(.18,.18,.18,1)
frame=r.frame(0,{},1200,800);data=bytes(frame.constBits());nonbackground=sum(data[i:i+3]!=data[:3] for i in range(0,len(data),4));assert nonbackground>50000
frame.save(str(OUT/'images/panda_actual_glb_profile.png'))
result={'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'loader':'project load_scene / panda3d-gltf 1.3.0','driver':r.driver,'geometry_nodes':len(geoms),'nonbackground_pixels':nonbackground,'last_frame_ms':r.last_frame_ms,'has_skeleton':r.has_skeleton,'clips':r.clips,'preview':'base color lighting; full PBR/Windows GUI not tested'}
(OUT/'panda_load_check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));r.close()
