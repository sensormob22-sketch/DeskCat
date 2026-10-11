"""Stage 18 experimental rig: put the already-tested 25-joint gait on Stage 17's
ACTUAL curved-belly repaired mesh, including both new profile texture materials.

Run: python tools/build_stage18_rigged_belly.py
Never changes source GLB or the old Rigify scene; no Blender heat solver.
The generated model is NOT production-approved without manual anatomy/coat review.
"""
from pathlib import Path
import argparse, hashlib, json, struct
import numpy as np
import build_calico_walk_trial as rig

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"assets/3d/retopo/deskcat_belly_profile_fix_01.glb"
EXPECTED_SHA256="90403331a772d54b7ed25f9bb6852985a0f2e81daad174a53c074fbae1d806c4"

def fingerprint(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def build(source,output,report):
 if output.exists() or report.exists():raise FileExistsError("Refuse to overwrite trial; choose new output names")
 if source.resolve()==output.resolve():raise ValueError("Input/output must differ")
 actual=fingerprint(source)
 if actual!=EXPECTED_SHA256:raise ValueError("Unknown Stage 17 source hash: "+actual)
 doc,blob=rig.read_glb(source)
 if len(doc["meshes"])!=1 or len(doc["meshes"][0]["primitives"])!=3:raise ValueError("Expected Stage 17 single mesh, three material primitives")
 if doc.get("skins") or doc.get("animations"):raise ValueError("Stage 17 input must be static; do not inherit stale skin")
 prims=doc["meshes"][0]["primitives"]
 old_summary=[]
 for i,pr in enumerate(prims):
  attrs=pr["attributes"]
  if not {"POSITION","NORMAL","TEXCOORD_0"}.issubset(attrs):raise ValueError("Geometry attrs missing")
  old_summary.append({"primitive":i,"material":pr.get("material"),
    "position_accessor":attrs["POSITION"],"normal_accessor":attrs["NORMAL"],
    "uv_accessor":attrs["TEXCOORD_0"],"index_accessor":pr["indices"],
    "vertices":len(rig.get(doc,blob,attrs["POSITION"]))})
 if [x["vertices"] for x in old_summary][0]!=19464:raise ValueError("Stage 17 retained source POSITION not matched")
 if old_summary[1]["position_accessor"]!=old_summary[2]["position_accessor"]:raise ValueError("Left/right patch geometry not shared")
 original_blobs=bytes(blob[:doc["buffers"][0]["byteLength"]])
 all_pos=[rig.get(doc,blob,p["attributes"]["POSITION"]).astype(np.float32) for p in prims]
 coords=np.vstack(all_pos)
 uniques,reverse=np.unique(coords,axis=0,return_inverse=True)
 joint_idx,weight_vals=rig.weights(uniques.astype(np.float64))
 joints=joint_idx[reverse];weights=weight_vals[reverse]
 if not np.allclose(weights.sum(1),1,atol=1e-6):raise AssertionError("Weights do not sum to 1")
 seen={};start=0
 for pi,p in enumerate(prims):
  key=p["attributes"]["POSITION"];n=len(all_pos[pi])
  if key in seen:
   joint_acc,weight_acc=seen[key]
   if not np.array_equal(all_pos[pi],all_pos[1]):raise ValueError("Repeated attribute shape differs")
  else:
   joint_acc=rig.add(doc,blob,joints[start:start+n],"VEC4",5123,vertex=True)
   weight_acc=rig.add(doc,blob,weights[start:start+n],"VEC4",5126,vertex=True)
   seen[key]=(joint_acc,weight_acc)
  p["attributes"]["JOINTS_0"]=joint_acc
  p["attributes"]["WEIGHTS_0"]=weight_acc
  if "JOINTS_1" in p["attributes"] or "WEIGHTS_1" in p["attributes"]:
   raise ValueError("Unexpected second skin influence set")
  start+=n
 # Create same exact skeleton structure as the previously Panda-tested trial.
 nodes=[]
 for name,parent,pivot in rig.BODY:
  global_xyz=np.array(pivot,dtype=float)
  local=global_xyz-rig.PIVOTS[rig.INDEX[parent]] if parent else global_xyz
  nodes.append({"name":name,"translation":local.tolist()})
 for i,(name,parent,pivot) in enumerate(rig.BODY):
  if parent:nodes[rig.INDEX[parent]].setdefault("children",[]).append(i)
 nodes.append({"name":"DeskCat_Stage17_CurvedBelly_Skinned","mesh":0,"skin":0})
 doc["nodes"]=nodes;doc["scene"]=0;doc["scenes"]=[{"nodes":[0,len(nodes)-1]}]
 ibm=np.array([[1,0,0,0,0,1,0,0,0,0,1,0,-p[0],-p[1],-p[2],1] for p in rig.PIVOTS],dtype=np.float32)
 doc["skins"]=[{"inverseBindMatrices":rig.add(doc,blob,ibm,"MAT4"),
               "joints":list(range(len(rig.BODY))),"skeleton":0,"name":"DeskCatStage18NoBoneHeatRig"}]
 rig.animate(doc,blob)
 # The precise Stage 17 geometry, normals, indices, UVs, images, and three
 # original material choices stay byte-identical. Only extra glTF accessors,
 # skin/nodes and animation are added.
 if bytes(blob[:len(original_blobs)])!=original_blobs:raise AssertionError("Corrupted Stage 17 source binary")
 doc["asset"]["generator"]="DeskCat Stage18 experimental skin+gait over Stage17 curved belly"
 doc.setdefault("extras",{})["deskcat_status"]="EXPERIMENTAL, leg anatomy and deforming belly not accepted"
 doc["buffers"]=[{"byteLength":len(blob)}]
 encoded=json.dumps(doc,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf8")
 encoded+=b" "*(-len(encoded)%4)
 blob+=b"\0"*(-len(blob)%4)
 glb=struct.pack("<4sII",b"glTF",2,12+8+len(encoded)+8+len(blob))
 glb+=struct.pack("<II",len(encoded),0x4e4f534a)+encoded+struct.pack("<II",len(blob),0x004e4942)+blob
 output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(glb)
 perbone={name:int(np.any((joints==i)&(weights>0),axis=1).sum()) for i,name in enumerate(rig.NAMES)}
 trial={"status":"experimental_skinned_candidate","accepted":False,
        "input_file":str(source),"input_sha256":actual,"output_file":str(output),
        "output_sha256":fingerprint(output),
        "primitives":[{**d,"joint_accessor":prims[i]["attributes"]["JOINTS_0"],
                       "weight_accessor":prims[i]["attributes"]["WEIGHTS_0"]} for i,d in enumerate(old_summary)],
        "source_geometry_binary_prefix_unchanged":True,
        "source_uv_normal_material_texture_accessors_unchanged":True,
        "source_nonpatched_vertices":19464,"source_patched_vertices":len(all_pos[1]),
        "same_patch_vertex_weights_in_both_material_primitives":True,
        "source_unique_vertex_positions_with_aliases":int(len(uniques)),
        "joint_count":len(rig.BODY),"influences_max":4,
        "weight_sums_normalized":True,"per_bone_positive_vertices":perbone,
        "animations":["idle","walk"],"workshop_note":"Defining skin channels is not proof of natural quadruped gait.",
        "unmet_acceptance":["real left/right belly deforming ray checks", "full silhouette/paw contact",
          "no new significant crossings/fur seams", "Windows live motion UI"]}
 report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(trial,ensure_ascii=False,indent=2)+"\n")
 return trial

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--source",type=Path,default=SOURCE)
 p.add_argument("--output",type=Path,default=ROOT/"artifacts/rig_rescue/deskcat_belly_skinned_trial.glb")
 p.add_argument("--report",type=Path,default=ROOT/"artifacts/rig_rescue/stage18_build.json")
 a=p.parse_args()
 d=build(a.source,a.output,a.report)
 print(json.dumps({k:d[k] for k in ("status","output_sha256","joint_count","animations","source_unique_vertex_positions_with_aliases")},indent=2))
