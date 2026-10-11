"""Actually open the proposed GLB in DeskCat/Panda3D and capture walk motion.

Requires the repository's three-d dependencies. These smoke checks do not certify
natural animal gait, knee topology, or fur continuity: inspect frame PNGs.
"""
from pathlib import Path
import argparse,json
import numpy as np
from deskcat.states import State
from deskcat.rendering.panda import PandaRenderer
from deskcat.rendering.gltf_scene import load_scene

def main(model,out):
 out.mkdir(parents=True,exist_ok=True)
 r=PandaRenderer(model,width=480,height=440)
 try:
  assert r.has_skeleton, "No Panda3D Character skeleton"
  assert "walk" in r.clips, "Panda3D did not import walk animation"
  # Software backend and Tripo PBR are not a full shading fidelity test.
  r.actor.setMaterialOff(10)
  from panda3d.core import TextureStage
  for stage in r.actor.findAllTextureStages():
   if stage.getMode()!=TextureStage.MModulate:
    r.actor.setTextureOff(stage,10)
  views=[]
  for i in range(9):
   img=r.frame(.20,{State.WALK:1.0},480,440)
   path=out/f"walk_{i:02}.png"
   assert img.save(str(path))
   rgb=img.constBits()
   from PIL import Image
   arr=np.asarray(Image.open(path).convert("RGBA"),dtype=np.uint8)
   views.append(arr)
  frames=np.asarray(views)
  unique_frames=len({hash(x.tobytes()) for x in frames})
  alpha_px=int(np.count_nonzero(frames[0,:,:,3]>12))
  diffs=[int(np.abs(frames[i].astype("int16")-frames[0].astype("int16")).sum()) for i in range(1,9)]
  status={"panda_has_skeleton":True,"walk_animation_imported":True,
   "actual_distinct_frames":unique_frames,"visible_alpha_pixel_count":alpha_px,
   "frame_difference_sums":diffs,"camera_orbit_verified":False,
   "limb_anatomy_certified":False,"coat_gaps_fixed":False,
   "note":"Panda renderer base-color preview only; manual review of knees, paws, collisions and coat still required"}
  if alpha_px<150:raise ValueError(f"Actor invisible: {status}")
  if unique_frames<3 or not any(v>100000 for v in diffs):raise ValueError(f"Animation did not visibly move: {status}")
  (out/"panda_smoke.json").write_text(json.dumps(status,indent=2)+"\n")
  print(json.dumps(status,indent=2))
 finally:r.close()

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--model",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
 args=p.parse_args();main(args.model,args.out)
