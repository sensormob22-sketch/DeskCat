"""Experimental independent skinned calico and walk clip, no Blender or Bone Heat.
Usage: python tools/build_calico_walk_trial.py --output artifacts/deskcat_walk_trial.glb
Preserves original material/UV/geometry; NOT accepted as production deform/coat fix.
"""
import argparse, json, math, hashlib, struct
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/3d/retopo/deskcat_calico_retopo_16460_metadata_diag.glb"
DT = {5120:"i1", 5121:"u1",5122:"<i2",5123:"<u2",5125:"<u4",5126:"<f4"}
NS = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}
BODY = [("root",None,(0,0,0)),("pelvis","root",(.22,.345,0)),
 ("lumbar","pelvis",(.06,.382,0)),("chest","lumbar",(-.17,.38,0)),
 ("neck","chest",(-.29,.44,0)),("head","neck",(-.38,.485,0)),
 ("tail_base","pelvis",(.315,.30,0)),("tail_middle","tail_base",(.392,.15,.011)),
 ("tail_tip","tail_middle",(.45,.085,.023))]
for side in ("L","R"):
 f = [(-.22,.36,.065),(-.24,.205,.043),(-.283,.062,.066),(-.325,.012,.075)] if side=="L" else [(-.21,.36,-.065),(-.249,.205,-.042),(-.272,.062,-.046),(-.314,.012,-.05)]
 h = [(.23,.32,.083),(.16,.205,.11),(.216,.08,.088),(.177,.012,.1)] if side=="L" else [(.21,.32,-.085),(.095,.2,-.11),(.148,.08,-.089),(.108,.012,-.103)]
 for prefix,pts,parent in (("front",f,"chest"),("hind",h,"pelvis")):
  for i,point in enumerate(pts):
   BODY.append((f"{prefix}_{side}_{i}",parent if i==0 else f"{prefix}_{side}_{i-1}",point))
NAMES = [p[0] for p in BODY]
PIVOTS = np.array([p[2] for p in BODY],dtype=np.float64)
INDEX = {name:i for i,name in enumerate(NAMES)}

def read_glb(src):
 raw=src.read_bytes()
 if raw[:4]!=b"glTF" or struct.unpack_from("<I",raw,4)[0]!=2 or struct.unpack_from("<I",raw,8)[0]!=len(raw):
  raise ValueError("Not a valid glTF2 GLB header")
 off=12; chunks={}
 while off<len(raw):
  length,kind=struct.unpack_from("<II",raw,off);off+=8
  chunks[kind]=raw[off:off+length];off+=length
 return json.loads(chunks[0x4e4f534a]),bytearray(chunks[0x004e4942])
def get(doc,buf,i):
 a=doc["accessors"][i];view=doc["bufferViews"][a["bufferView"]]
 dt=np.dtype(DT[a["componentType"]]);n=NS[a["type"]]
 return np.ndarray((a["count"],n),dtype=dt,buffer=buf,offset=view.get("byteOffset",0)+a.get("byteOffset",0),
  strides=(view.get("byteStride",dt.itemsize*n),dt.itemsize)).copy()
def add(doc,buf,rows,kind,component=5126,vertex=False,bounds=False):
 data=np.ascontiguousarray(rows,dtype=np.dtype(DT[component]))
 if data.ndim==1:data=data[:,None]
 assert data.shape[1]==NS[kind]
 while len(buf)%4:buf.append(0)
 offset=len(buf);buf.extend(data.tobytes())
 view={"buffer":0,"byteOffset":offset,"byteLength":data.nbytes}
 if vertex:view["target"]=34962
 doc["bufferViews"].append(view)
 acc={"bufferView":len(doc["bufferViews"])-1,"componentType":component,"count":len(data),"type":kind}
 if bounds:acc.update(min=data.min(0).astype(float).tolist(),max=data.max(0).astype(float).tolist())
 doc["accessors"].append(acc);return len(doc["accessors"])-1
def smooth(a,b,v):
 t=np.clip((v-a)/(b-a),0,1);return t*t*(3-2*t)
def dist(points,a,b):
 d=b-a;t=np.clip(((points-a)@d)/(d@d+1e-20),0,1)
 return np.linalg.norm(points-a-t[:,None]*d,axis=1)

def weights(points):
 x,y,z=points.T;n=len(points);w=np.zeros((n,len(BODY)),dtype=np.float64)
 def assign(name,val):w[:,INDEX[name]]+=val
 for name,c,r in (("pelvis",.22,.145),("lumbar",.06,.13),("chest",-.17,.15),("neck",-.29,.075),("head",-.38,.13)):
  assign(name,np.exp(-.5*((x-c)/r)**2))
 assign("head",20*smooth(-.31,-.41,x)*smooth(.33,.43,y))
 for side,sign in (("L",1),("R",-1)):
  for prefix,cx,width in (("front",-.25,.075),("hind",.17,.095)):
   names=[f"{prefix}_{side}_{i}" for i in range(4)]
   piv=np.array([PIVOTS[INDEX[name]] for name in names])
   seg=np.column_stack([dist(points,piv[i],piv[i+1]) for i in range(3)])
   gate=smooth(.365,.20,y)*smooth(-.002,.04,sign*z)*np.exp(-.5*((x-cx)/width)**2)
   gate*=smooth(.10,.015,seg.min(axis=1))
   strength=gate*(.70+.30*smooth(.29,.09,y))
   basis=np.column_stack([np.exp(-.5*(seg[:,0]/.07)**2),np.exp(-.5*(seg[:,1]/.062)**2),
    np.exp(-.5*(seg[:,2]/.045)**2),np.exp(-.5*(np.linalg.norm(points-piv[3],axis=1)/.055)**2)])
   basis/=np.maximum(basis.sum(1,keepdims=True),1e-10)
   w*=(1-strength)[:,None]
   for i,name in enumerate(names):assign(name,10*strength*basis[:,i])
 tail=np.clip((x-.29)/.11,0,1)*smooth(.37,.15,y)*smooth(.1,.025,np.abs(z-.009))
 a=PIVOTS[INDEX["tail_base"]];b=PIVOTS[INDEX["tail_middle"]];c=PIVOTS[INDEX["tail_tip"]]
 p=np.exp(-(dist(points,a,b)/.08)**2);q=np.exp(-(dist(points,b,c)/.08)**2)
 parts=np.column_stack([p,q,q*smooth(.16,.075,y)])
 parts/=np.maximum(parts.sum(1,keepdims=True),1e-10)
 w*=(1-tail)[:,None]
 for i,name in enumerate(("tail_base","tail_middle","tail_tip")):assign(name,tail*parts[:,i]*12)
 ids=np.argsort(w,axis=1)[:,-4:][:,::-1];values=np.take_along_axis(w,ids,axis=1)
 values/=np.maximum(values.sum(1,keepdims=True),1e-20)
 if not np.isfinite(values).all() or not np.allclose(values.sum(1),1):raise ValueError("Bad weights")
 return ids.astype(np.uint16),values.astype(np.float32)

# Each foot is planted for three quarters of the 1.6 s cycle. During that
# interval the toe advances exactly STRIDE in body-local +X: when the body
# travels toward -X by the matching amount, its world contact point is fixed.
# Only the remaining quarter cycle is airborne (one swinging paw at a time).
STRIDE = .09
STANCE_FRACTION = .75
CYCLE_SECONDS = 1.6
SWING_HEIGHT = .045

def toe_trajectory(phase):
 phase = phase % 1.0
 if phase < STANCE_FRACTION:
  return STRIDE * phase / STANCE_FRACTION, 0.0
 u = (phase-STANCE_FRACTION)/(1-STANCE_FRACTION)
 return STRIDE*(1-u), SWING_HEIGHT*math.sin(math.pi*u)

def leg_contact_angles(points, travel, height):
 """Planar two-link IK to the ankle with an unchanged toe-to-ankle vector.

 Returns the three LOCAL joint angles for upper, lower and paw segments.
 This preserves original bone lengths and the paw's global orientation.
 """
 p0,p1,p2,p3 = np.asarray(points,dtype=np.float64)[:,:2]
 target=p2+np.array([travel,height])
 l1=np.linalg.norm(p1-p0);l2=np.linalg.norm(p2-p1)
 delta=target-p0;d=np.linalg.norm(delta)
 if not abs(l1-l2)+1e-8 < d <= l1+l2+1e-7:
  raise ValueError("Unreachable walking ankle target")
 unit=delta/d
 along=(l1*l1-l2*l2+d*d)/(2*d)
 lateral=math.sqrt(max(0.0,l1*l1-along*along))
 rest_cross=(p2[0]-p0[0])*(p1[1]-p0[1])-(p2[1]-p0[1])*(p1[0]-p0[0])
 knee=p0+along*unit+math.copysign(lateral,rest_cross)*np.array([-unit[1],unit[0]])
 angle=lambda v: math.atan2(v[1],v[0])
 hip=angle(knee-p0)-angle(p1-p0)
 knee_local=angle(target-knee)-angle(p2-p1)-hip
 paw_local=-hip-knee_local
 return (hip,knee_local,paw_local)

def animate(doc,buf):
 time=np.linspace(0,CYCLE_SECONDS,33,dtype=np.float32);t=add(doc,buf,time,"SCALAR",bounds=True)
 anim={"name":"walk","samplers":[],"channels":[]}
 def channel(bone,path,data):
  idx=add(doc,buf,data,"VEC3" if path=="translation" else "VEC4")
  j=len(anim["samplers"]);anim["samplers"].append({"input":t,"output":idx,"interpolation":"LINEAR"})
  anim["channels"].append({"sampler":j,"target":{"node":INDEX[bone],"path":path}})
 def rot(a):return [0,0,math.sin(float(a)/2),math.cos(float(a)/2)]
 # All four planted toes follow the same constant-velocity local backstroke.
 # The stable contact interval lasts 75%; exactly one leg swings at a time.
 # Rotation is solved from the unchanged source bone lengths by 2D IK.
 offsets={("hind","L"):0.0,("front","L"):.25,
          ("hind","R"):.5,("front","R"):.75}
 for (prefix,side),offset in offsets.items():
  keys=[f"{prefix}_{side}_{i}" for i in range(4)]
  points=np.array([PIVOTS[INDEX[name]] for name in keys])
  poses=[leg_contact_angles(points,*toe_trajectory(float(t)/CYCLE_SECONDS+offset)) for t in time]
  for i in range(3):
   channel(keys[i],"rotation",[rot(a[i]) for a in poses])
 # This is a contact-constrained toe-joint gait, not a certified final skin.
 # The attached 3D fur/mesh still needs physical Windows inspection.
 doc.setdefault("extras",{})["deskcat_gait"]={
  "clip":"walk","period_seconds":CYCLE_SECONDS,
  "stance_fraction":STANCE_FRACTION,"toe_stance_travel_source_units":STRIDE,
  "forward_source_axis":"-X","toe_contact_method":"planar_2link_IK",
  "limb_motion":"four_independent_legs_one_swing_at_a_time"
 }
 pos=PIVOTS[INDEX["pelvis"]]
 channel("pelvis","translation",np.column_stack([np.full(len(time),pos[0]),pos[1]+.004*(1-np.cos(4*math.pi*time/1.6)),np.full(len(time),pos[2])]))
 channel("tail_base","rotation",[rot(.06*math.sin(2*math.pi*float(t)/1.6)) for t in time])
 idle={"name":"idle","samplers":[],"channels":[]}
 idle_rot=np.array([[0,0,math.sin(.015*math.sin(2*math.pi*float(x)/1.6)),math.cos(.015*math.sin(2*math.pi*float(x)/1.6))] for x in time],dtype=np.float32)
 out=add(doc,buf,idle_rot,"VEC4")
 idle["samplers"].append({"input":t,"output":out,"interpolation":"LINEAR"})
 idle["channels"].append({"sampler":0,"target":{"node":INDEX["tail_base"],"path":"rotation"}})
 doc["animations"]=[idle,anim]

def build(source,out,report):
 if out.exists() or report.exists():raise FileExistsError("Refusing overwrite; use unique paths")
 doc,bin=read_glb(source)
 if len(doc["meshes"])!=1 or len(doc["meshes"][0]["primitives"])!=1:raise ValueError("Wrong mesh shape")
 prim=doc["meshes"][0]["primitives"][0]
 pos=get(doc,bin,prim["attributes"]["POSITION"]).astype(np.float32)
 if pos.shape!=(19464,3):raise ValueError("Expected exact 19464 source vertices")
 unique,rev=np.unique(pos,axis=0,return_inverse=True);ji,w=weights(unique)
 ja=ji[rev];wa=w[rev]
 prim["attributes"]["JOINTS_0"]=add(doc,bin,ja,"VEC4",5123,vertex=True)
 prim["attributes"]["WEIGHTS_0"]=add(doc,bin,wa,"VEC4",vertex=True)
 prim["attributes"].pop("JOINTS_1",None);prim["attributes"].pop("WEIGHTS_1",None)
 nodes=[]
 for name,parent,pivot in BODY:
  vector=np.array(pivot)-PIVOTS[INDEX[parent]] if parent else np.array(pivot)
  nodes.append({"name":name,"translation":vector.tolist()})
 for idx,(name,parent,pivot) in enumerate(BODY):
  if parent:nodes[INDEX[parent]].setdefault("children",[]).append(idx)
 nodes.append({"name":"DeskCatCalicoSkinTrial","mesh":0,"skin":0})
 doc["nodes"]=nodes;doc["scenes"]=[{"nodes":[0,len(nodes)-1]}];doc["scene"]=0
 doc.pop("cameras",None)
 ibm=np.array([[1,0,0,0,0,1,0,0,0,0,1,0,-p[0],-p[1],-p[2],1] for p in PIVOTS],dtype=np.float32)
 doc["skins"]=[{"inverseBindMatrices":add(doc,bin,ibm,"MAT4"),"joints":list(range(len(BODY))),
   "skeleton":0,"name":"DeskCatExperimental25JointRig"}]
 animate(doc,bin)
 # Fix pre-existing accessor metadata errors without changing original vertex payloads.
 for n,acc in enumerate(doc["accessors"]):
  if "min" in acc and "bufferView" in acc:
   vals=get(doc,bin,n)
   acc["min"]=vals.min(axis=0).astype(float).tolist()
   if "max" in acc:acc["max"]=vals.max(axis=0).astype(float).tolist()
 doc["asset"]["generator"]="DeskCat experimental procedural rig (not production-accepted)"
 doc.setdefault("extras",{})["deskcat_status"]="EXPERIMENTAL; geometry/coat NOT repaired"
 doc["buffers"]=[{"byteLength":len(bin)}]
 encoded=json.dumps(doc,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf8")
 encoded+=b" "*(-len(encoded)%4);bin+=b"\0"*(-len(bin)%4)
 data=struct.pack("<4sII",b"glTF",2,12+8+len(encoded)+8+len(bin))
 data+=struct.pack("<II",len(encoded),0x4e4f534a)+encoded+struct.pack("<II",len(bin),0x004e4942)+bin
 out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
 coverage={name:int(np.any((ja==i)&(wa>0),axis=1).sum()) for i,name in enumerate(NAMES)}
 information={"accepted":False,"source":str(source),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
  "output_sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"source_vertices":len(pos),
  "unique_positions":len(unique),"new_joint_count":len(BODY),"max_influences":4,
  "per_bone_positive_vertices":coverage,"seam_weight_variance":0,
  "walk_clip_generated":True,"rest_mesh_source_coordinates_preserved":True,
  "coat_gaps_fixed":False,"actual_blender_panda_deformation_tested":False,
  "scope":"Diagnostic skin candidate only. Must visually check ankle/knee/four paws, intersections, seam continuity and locomotion in Panda3D."}
 report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(information,indent=2,ensure_ascii=False)+"\n")
 return information

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--input",type=Path,default=SOURCE)
 p.add_argument("--output",type=Path,default=ROOT/"artifacts/rig_rescue/deskcat_calico_walk_trial.glb")
 p.add_argument("--report",type=Path,default=ROOT/"artifacts/rig_rescue/rig_trial.json")
 a=p.parse_args();print(json.dumps(build(a.input,a.output,a.report),indent=2))
