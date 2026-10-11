"""Read-only recovery/audit of already measured cage snapshots. No rebinding/fitting."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Vector
from blender_deformation_probe import inverse,pair_set
from blender_weight_handoff import crossing_point
from rig_geometry_analysis import mesh_data

root=Path.cwd();out=root/'docs/model-reports/stage12';work=root/'artifacts/stage12_cage'
source=root/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
cp,faces,aliases,_=mesh_data(source);cp=np.array(cp);faces=np.array(faces);first=[aliases[i][0] for i in range(len(cp))]
rest=cp[faces];area=np.linalg.norm(np.cross(rest[:,1]-rest[:,0],rest[:,2]-rest[:,0]),axis=1)/2
edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
length=np.linalg.norm(cp[edges[:,0]]-cp[edges[:,1]],axis=1)
review=json.loads((root/'docs/model-reports/stage9/data/pose_review.json').read_text());old={tuple(p) for p in review['baseline_pairs']}
masks=json.loads((root/'docs/model-reports/stage9/data/region_masks.json').read_text())
defs=json.loads((out/'cage_definitions.json').read_text());regions={c['zone']:set(map(int,c['source_mask'])) for c in defs['cages']}
protected=masks['protected_source_vertex_ids'];union=set().union(*regions.values());outside=sorted(set(range(58450))-union)
cases={'rest':{}}
for bone,label in [('tail_base','tail'),('hip_HL','hip')]:
    for angle in (10,15):
        for sign,s in [(1,'plus'),(-1,'minus')]:cases[f'{label}_{s}{angle}']={bone:sign*angle}
cases['combined_positive']={'tail_base':15,'hip_HL':15,'pelvis':5,'lumbar':-5}
cases['combined_negative']={'tail_base':-15,'hip_HL':-15,'pelvis':-5,'lumbar':5}
def stat(v):return {'min':float(v.min()),'max':float(v.max()),'p1_p5_p50_p95_p99':np.percentile(v,[1,5,50,95,99]).tolist()}
result={}
for label in ('v6','cage'):
    result[label]={}
    for case in cases:
        ps=np.load(work/f'{label}_{case}.npz')['positions'];c=ps[first];tri=c[faces];pairs=pair_set(c,faces.tolist());new=pairs-old
        ar=np.divide(np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2,area,out=np.ones_like(area),where=area>1e-14)
        er=np.divide(np.linalg.norm(c[edges[:,0]]-c[edges[:,1]],axis=1),length,out=np.ones_like(length),where=length>1e-10)
        loc={}
        for zone,ids in regions.items():
            vm=np.array([i in ids for i in first]);fm=vm[faces].any(1);em=vm[edges].any(1)
            loc[zone]={'new_pairs':int(sum(vm[faces[list(pair)]].any() for pair in new)),'area_ratio':stat(ar[fm]),'edge_ratio':stat(er[em]),'area_below_half':int((ar[fm]<.5).sum()),'area_above_double':int((ar[fm]>2).sum()),'bounds':{'min':ps[list(ids)].min(0).tolist(),'max':ps[list(ids)].max(0).tolist()}}
        crossings=[]
        for a,b in sorted(new):
            marks=[];ta,tb=[Vector(p) for p in c[faces[a]]],[Vector(p) for p in c[faces[b]]]
            for u,v in [(ta,tb),(tb,ta)]:
                for i in range(3):
                    hit=crossing_point(u[i],u[(i+1)%3],v)
                    if hit is not None:marks.append(hit)
            crossings.append({'source_face_pair':[int(a),int(b)],'cross_points_gltf':marks})
        entry={'new_pairs':len(new),'new_source_face_pairs':sorted(new),'retained_baseline_pairs':len(pairs&old),'crossings':crossings,'area_ratio':stat(ar),'edge_ratio':stat(er),'regions':loc,'seam_gap_max':max(float(np.linalg.norm(ps[ids]-ps[ids[0]],axis=1).max()) for ids in aliases.values()),'snapshot':str((work/f'{label}_{case}.glb').relative_to(root))}
        delta=np.linalg.norm(ps-np.load(work/f'v6_{case}.npz')['positions'],axis=1)
        entry.update(max_difference_outside_masks=float(delta[outside].max()),max_difference_protected=float(delta[protected].max()),max_difference_inside=float(delta[list(union)].max()))
        result[label][case]=entry
        print(label,case,entry['new_pairs'],flush=True)
# Inspect the already saved copy only; no deformation cycle or scene save.
bpy.ops.wm.open_mainfile(filepath=str(root/'assets/rigging/deskcat_cage_trial_01.blend'))
mesh=bpy.data.objects['CAGE_TRIAL_01_ORIGINAL_WEIGHTS'];rig=bpy.data.objects['V6_RIG_UNCHANGED'];names=[b.name for b in rig.data.bones]
w=np.zeros((58450,len(names)),dtype='<f4')
for v in mesh.data.vertices:
    for g in v.groups:
        n=mesh.vertex_groups[g.group].name
        if n in names:w[v.index,names.index(n)]=g.weight
digest=hashlib.sha256(w.tobytes()).hexdigest();assert digest==masks['bone_weight_sha256_float32']
def vol(vertices,fs):return float(abs(sum(np.dot(vertices[a],np.cross(vertices[b],vertices[c])) for a,b,c in fs)/6))
volume_ratios={}
for definition in defs['cages']:
    cage=bpy.data.objects['CAGE_'+definition['zone']];cage.data.calc_loop_triangles();fs=[list(t.vertices) for t in cage.data.loop_triangles];rest=np.array([v.co[:] for v in cage.data.vertices]);rv=vol(rest,fs)
    volume_ratios[cage.name]={}
    for case,rot in cases.items():
        from blender_weight_handoff import pose
        pose(rig,rot);transforms=[np.array(rig.pose.bones[n].matrix@rig.data.bones[n].matrix_local.inverted()) for n in [definition['parent'],definition['child']]]
        pts=np.column_stack([rest,np.ones(len(rest))]);a=pts@transforms[0].T;b=pts@transforms[1].T;coeff=np.repeat(definition['ring_child_coefficients'],8)[:,None];posed=a[:,:3]*(1-coeff)+b[:,:3]*coeff
        volume_ratios[cage.name][case]=vol(posed,fs)/rv
frozen=json.loads((out/'preserved_manifest.json').read_text());assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
payload={'environment':'Linux; Blender 4.3.2 headless; fixed single cycle','cases':cases,'baseline_pairs':sorted(old),'models':result,'cage_volume_ratios':volume_ratios,'bone_weights_sha256_float32':digest,'preserved_file_hashes_verified':True,'normals_limit':'Preview snapshots retain rest split normals. Texture color, silhouette and wire views, not certified final shading.','volume_limit':'Signed volume of the closed proxy cages only. The high-resolution mesh is not certified watertight; no claim of tissue-volume preservation.','recovery_note':'Initial experiment completed all 22 measured poses and saved its copy. Final JSON serialization failed on NumPy int64; this read-only audit recovers the same snapshot measurements without rerunning or adjusting deformation.'}
(out/'comparison.json').write_text(json.dumps(payload,indent=2)+'\n')
