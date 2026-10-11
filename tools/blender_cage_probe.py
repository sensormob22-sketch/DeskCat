"""One fixed, local Mesh Deform feasibility trial, not a skin/weight optimizer.
Run: blender -b --factory-startup --python tools/blender_cage_probe.py
The two closed cages have explicit ring controls; original bone weights stay intact.
"""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Vector
from blender_deformation_probe import convert, inverse, pair_set, write_snapshot
from blender_weight_handoff import pose, crossing_point
from rig_geometry_analysis import mesh_data
from rig_readiness_audit import read_glb, accessor

ROOT = Path.cwd()
OUT = ROOT/'docs/model-reports/stage12'
WORK = ROOT/'artifacts/stage12_cage'
COPY = ROOT/'assets/rigging/deskcat_cage_trial_01.blend'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, data): p.write_text(json.dumps(data, indent=2, default=lambda v:v.item() if isinstance(v,np.generic) else v)+'\n')
def stats(a):
    return {'min':float(a.min()), 'max':float(a.max()),
            'p1_p5_p50_p95_p99':np.percentile(a,[1,5,50,95,99]).tolist()}

def main():
    if WORK.exists() or COPY.exists() or OUT.exists(): raise ValueError('Use new trial paths')
    frozen = {str(p.relative_to(ROOT)):sha(p) for folder in ('assets/3d/tripo','assets/rigging')
              for p in (ROOT/folder).glob('*') if p.is_file()}
    expected=json.loads((ROOT/'docs/model-reports/stage9/data/scene_audit.json').read_text())
    for name,h in expected['protected_glb_hashes'].items():
        if frozen['assets/3d/tripo/'+name]!=h: raise ValueError('Frozen model mismatch')
    scene=ROOT/'assets/rigging/deskcat_v6_weight_handoff.blend'
    if sha(scene)!=expected['scene_sha256']: raise ValueError('Frozen scene mismatch')
    source=ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
    masks=json.loads((ROOT/'docs/model-reports/stage9/data/region_masks.json').read_text())
    review=json.loads((ROOT/'docs/model-reports/stage9/data/pose_review.json').read_text())
    d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0]
    original=np.array(accessor(d,b,p['attributes']['POSITION']))
    normals=np.array(accessor(d,b,p['attributes']['NORMAL']))
    cp,faces,sources,_=mesh_data(source);cp=np.array(cp);faces=np.array(faces)
    first=[sources[i][0] for i in range(len(cp))]
    aliases={j:entries for entries in sources.values() for j in entries}
    baseline_pairs={tuple(x) for x in review['baseline_pairs']}
    resttri=cp[faces];oldareas=np.linalg.norm(np.cross(resttri[:,1]-resttri[:,0],resttri[:,2]-resttri[:,0]),axis=1)/2
    edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
    oldlength=np.linalg.norm(cp[edges[:,0]]-cp[edges[:,1]],axis=1)
    OUT.mkdir(parents=True);WORK.mkdir(parents=True)
    bpy.ops.wm.open_mainfile(filepath=str(scene));mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS'];rig=bpy.data.objects['V6_17_BONES_UNVERIFIED']
    names=[bone.name for bone in rig.data.bones]
    def weights():
        w=np.zeros((len(original),len(names)),dtype='<f4')
        for v in mesh.data.vertices:
            for g in v.groups:
                n=mesh.vertex_groups[g.group].name
                if n in names:w[v.index,names.index(n)]=g.weight
        return w
    weight_sha=hashlib.sha256(weights().tobytes()).hexdigest()
    if weight_sha!=masks['bone_weight_sha256_float32']: raise ValueError('Baseline weight mismatch')
    def fingerprint():
        return {'positions':hashlib.sha256(np.array([v.co[:] for v in mesh.data.vertices],dtype='<f4').tobytes()).hexdigest(),
                'uv':hashlib.sha256(np.array([v.uv[:] for v in mesh.data.uv_layers.active.data],dtype='<f4').tobytes()).hexdigest(),
                'faces':hashlib.sha256(np.array([p.vertices[:] for p in mesh.data.polygons],dtype='<i4').tobytes()).hexdigest(),
                'packed_textures':sorted(hashlib.sha256(im.packed_file.data).hexdigest() for im in bpy.data.images if im.packed_file)}
    before=fingerprint();pose(rig,{})
    cases={'rest':{}}
    for bone,label in [('tail_base','tail'),('hip_HL','hip')]:
        for angle in (10,15):
            for sign,s in [(1,'plus'),(-1,'minus')]:cases[f'{label}_{s}{angle}']={bone:sign*angle}
    cases['combined_positive']={'tail_base':15,'hip_HL':15,'pelvis':5,'lumbar':-5}
    cases['combined_negative']={'tail_base':-15,'hip_HL':-15,'pelvis':-5,'lumbar':5}
    protected=set(masks['protected_source_vertex_ids'])
    regions={n:set(masks['zones'][n]['editable_source_vertex_ids'])-protected for n in ('tail_to_pelvis','left_hip')}
    # Exact-position aliases receive identical masks; protected aliases remain excluded.
    regions={n:{j for i in ids for j in aliases[i]}-protected for n,ids in regions.items()}
    adjacency=[set() for _ in original]
    for f in mesh.data.polygons:
        for a,b in zip(f.vertices,(*f.vertices[1:],f.vertices[0])):
            adjacency[a].update(aliases[b]);adjacency[b].update(aliases[a])
    def local_mask(ids):
        boundary={i for i in ids if adjacency[i]-ids};dist={i:0 for i in boundary};front=boundary
        for step in range(1,4):
            nxt={j for i in front for j in adjacency[i] if j in ids and j not in dist}
            dist.update({j:step for j in nxt});front=nxt
        return {i:(dist.get(i,4)+1)/5 for i in ids}
    tail=local_mask(regions['tail_to_pelvis']);hip=local_mask(regions['left_hip'])
    hip={i:v*(1-tail.get(i,0)) for i,v in hip.items()}
    union=set(tail)|set(hip)
    def measure(ps):
        c=ps[first];pairs=pair_set(c,faces.tolist());new=pairs-baseline_pairs;t=c[faces]
        ar=np.divide(np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)/2,oldareas,out=np.ones_like(oldareas),where=oldareas>1e-14)
        er=np.divide(np.linalg.norm(c[edges[:,0]]-c[edges[:,1]],axis=1),oldlength,out=np.ones_like(oldlength),where=oldlength>1e-10)
        regions_out={}
        for n,ids in regions.items():
            cm=np.array([i in ids for i in first]);fm=cm[faces].any(1);em=cm[edges].any(1)
            regions_out[n]={'new_pairs':sum(cm[faces[list(pair)]].any() for pair in new),'area_ratio':stats(ar[fm]),'edge_ratio':stats(er[em]),'area_below_half':int((ar[fm]<.5).sum()),'area_above_double':int((ar[fm]>2).sum()),'bounds':{'min':ps[list(ids)].min(0).tolist(),'max':ps[list(ids)].max(0).tolist()}}
        crossings=[]
        for a,b in sorted(new):
            marks=[]
            ta,tb=[Vector(v) for v in c[faces[a]]],[Vector(v) for v in c[faces[b]]]
            for u,v in [(ta,tb),(tb,ta)]:
                for i in range(3):
                    hit=crossing_point(u[i],u[(i+1)%3],v)
                    if hit is not None:marks.append(hit)
            crossings.append({'source_face_pair':[int(a),int(b)],'cross_points_gltf':marks})
        return {'new_pairs':len(new),'new_source_face_pairs':[list(pair) for pair in sorted(new)],'retained_baseline_pairs':len(pairs&baseline_pairs),'crossings':crossings,'regions':regions_out,'area_ratio':stats(ar),'edge_ratio':stats(er),'seam_gap_max':max(float(np.linalg.norm(ps[entries]-ps[entries[0]],axis=1).max()) for entries in sources.values())}
    def evaluated():
        ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()
        ps=np.array([inverse(ev.matrix_world@v.co) for v in m.vertices]);ev.to_mesh_clear();return ps
    outcomes={'v6':{},'cage':{}};baseline={}
    for key,rot in cases.items():
        pose(rig,rot);ps=evaluated();baseline[key]=ps;outcomes['v6'][key]=measure(ps)
        np.savez_compressed(WORK/f'v6_{key}.npz',positions=ps)
        write_snapshot(source,WORK/f'v6_{key}.glb',ps,normals)
        print('v6',key,outcomes['v6'][key]['new_pairs'],flush=True)
    pose(rig,{})
    arm=next(m for m in mesh.modifiers if m.type=='ARMATURE');arm.show_viewport=False
    cages=[];definitions=[]
    for zone,mask,axis,bone,parent,reverse in [('tail_to_pelvis',tail,0,'tail_base','pelvis',False),('left_hip',hip,1,'hip_HL','pelvis',True)]:
        points=original[list(mask)];lo=points.min(0)-.02;hi=points.max(0)+.02
        other=[i for i in range(3) if i!=axis];corners=[(0,0),(.5,0),(1,0),(1,.5),(1,1),(.5,1),(0,1),(0,.5)]
        vertices=[]
        for ring,t in enumerate((0,1/3,2/3,1)):
            for a,b in corners:
                pt=np.zeros(3);pt[axis]=lo[axis]+t*(hi[axis]-lo[axis]);pt[other[0]]=lo[other[0]]+a*(hi[other[0]]-lo[other[0]]);pt[other[1]]=lo[other[1]]+b*(hi[other[1]]-lo[other[1]]);vertices.append(convert(pt))
        # Winding fixed by signed volume; 32 vertices / 26 closed faces.
        fs=[tuple(reversed(range(8))),tuple(range(24,32))]
        fs += [(r*8+j,r*8+(j+1)%8,(r+1)*8+(j+1)%8,(r+1)*8+j) for r in range(3) for j in range(8)]
        data=bpy.data.meshes.new('CAGE_'+zone);data.from_pydata(vertices,[],fs);data.update()
        cage=bpy.data.objects.new('CAGE_'+zone,data);bpy.context.scene.collection.objects.link(cage);cage.display_type='WIRE';cage.hide_render=True
        group=mesh.vertex_groups.new(name='CAGE_MASK_'+zone)
        for i,w in mask.items():group.add([i],w,'REPLACE')
        mod=mesh.modifiers.new('LOCAL_CAGE_'+zone,'MESH_DEFORM');mod.object=cage;mod.vertex_group=group.name;mod.precision=5;mod.use_dynamic_bind=False
        bpy.context.view_layer.objects.active=mesh;mesh.select_set(True)
        bpy.ops.object.meshdeform_bind(modifier=mod.name)
        if not mod.is_bound:raise ValueError('Mesh Deform binding failed')
        coefficients=[0,.15,.65,1]
        if reverse:coefficients.reverse()
        cages.append((cage,np.array([v.co[:] for v in cage.data.vertices]),coefficients,bone,parent))
        definitions.append({'zone':zone,'bounds_gltf':[lo.tolist(),hi.tolist()],'vertices':32,'faces':26,'axis_gltf':axis,'ring_child_coefficients':coefficients,'child':bone,'parent':parent,'source_mask':{str(i):w for i,w in sorted(mask.items())},'bound':mod.is_bound,'precision':mod.precision})
        print('BOUND',zone,len(mask),flush=True)
    # Cage displacement precedes LBS restricted to its complement. No original bone-group writes.
    for cage,*_ in cages:pass
    complement=mesh.vertex_groups.new(name='V6_OUTSIDE_CAGES')
    for i in range(len(original)):complement.add([i],1-tail.get(i,0)-hip.get(i,0),'REPLACE')
    arm.vertex_group=complement.name;arm.show_viewport=True
    bpy.context.view_layer.objects.active=mesh
    bpy.ops.object.modifier_move_down(modifier=arm.name);bpy.ops.object.modifier_move_down(modifier=arm.name)
    cage_rest_volumes={}
    def volume(cage):
        cage.data.calc_loop_triangles();v=np.array([v.co[:] for v in cage.data.vertices]);f=np.array([t.vertices[:] for t in cage.data.loop_triangles]);return float(abs(np.einsum('ij,ij->i',v[f[:,0]],np.cross(v[f[:,1]],v[f[:,2]])).sum()/6))
    for cage,*_ in cages:cage_rest_volumes[cage.name]=volume(cage)
    def set_cages(rot):
        pose(rig,rot)
        for cage,rest,coeff,bone,parent in cages:
            transforms=[np.array(rig.pose.bones[n].matrix@rig.data.bones[n].matrix_local.inverted()) for n in (parent,bone)]
            pts=np.column_stack([rest,np.ones(len(rest))]);a=pts@transforms[0].T;b=pts@transforms[1].T
            for i,v in enumerate(cage.data.vertices):v.co=(a[i,:3]*(1-coeff[i//8])+b[i,:3]*coeff[i//8]).tolist()
            cage.data.update()
        bpy.context.view_layer.update()
    for key,rot in cases.items():
        set_cages(rot);ps=evaluated();record=measure(ps);delta=np.linalg.norm(ps-baseline[key],axis=1)
        record.update(cage_volume_ratios={cage.name:volume(cage)/cage_rest_volumes[cage.name] for cage,*_ in cages},max_difference_outside_masks=float(delta[[i for i in range(len(original)) if i not in union]].max()),max_difference_protected=float(delta[list(protected)].max()),max_difference_inside=float(delta[list(union)].max()))
        outcomes['cage'][key]=record;np.savez_compressed(WORK/f'cage_{key}.npz',positions=ps)
        write_snapshot(source,WORK/f'cage_{key}.glb',ps,normals)
        print('cage',key,record['new_pairs'],flush=True)
    set_cages({});mesh.name='CAGE_TRIAL_01_ORIGINAL_WEIGHTS';rig.name='V6_RIG_UNCHANGED'
    if fingerprint()!=before or hashlib.sha256(weights().tobytes()).hexdigest()!=weight_sha:raise ValueError('Source geometry/UV/texture/weights changed')
    bpy.ops.wm.save_as_mainfile(filepath=str(COPY),compress=True)
    if any(sha(ROOT/p)!=h for p,h in frozen.items()):raise ValueError('Frozen input modified')
    write(OUT/'preserved_manifest.json',frozen)
    write(OUT/'cage_definitions.json',{'method':'Two fixed closed 32-control cages; explicit four-ring control coefficients; geodesic boundary feather masks; no fitting or source bone-weight writes','cages':definitions})
    write(OUT/'comparison.json',{'blender':bpy.app.version_string,'cases':cases,'baseline_pairs':sorted(baseline_pairs),'models':outcomes,'preservation':before,'bone_weights_sha256_float32':weight_sha,'scene_sha256':sha(COPY),'normals_limit':'Static preview snapshots retain rest split normals for matched base-color/solid/wire comparisons. They are not final shading or animations.','volume_limit':'Closed cage signed volume only. Detailed mesh is not a certified watertight solid; no tissue-volume claim.'})

if __name__=='__main__':main()
