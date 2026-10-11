"""One explicitly approved C2 trial; mandatory dry-run gate, frozen inputs, no optimization."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Vector
from blender_deformation_probe import inverse, convert, pair_set, write_snapshot
from blender_weight_handoff import pose, crossing_point
from rig_geometry_analysis import mesh_data
from rig_readiness_audit import read_glb, accessor
from weight_handoff_contract import validate_proposal, source_skin_weights
from skin_export_audit import audit_export

PROPOSAL_SHA = '5de3474984a5b5466e5d1f1fe182d28b0baebe6585c2f814fe8e720175dd744e'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, obj): path.write_text(json.dumps(obj, indent=2)+'\n')

def run(root, output, work, copy, export, apply):
    stage9 = root/'docs/model-reports/stage9/data'
    source = root/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
    skin = root/'assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb'
    scene = root/'assets/rigging/deskcat_v6_weight_handoff.blend'
    proposal_file = root/'docs/model-reports/stage10/tail_to_pelvis_proposal.json'
    proposal = json.loads(proposal_file.read_text()); masks = json.loads((stage9/'region_masks.json').read_text())
    manifest = json.loads((stage9/'scene_audit.json').read_text())
    if sha(proposal_file) != PROPOSAL_SHA: raise ValueError('Exact approved proposal SHA mismatch')
    protected_hashes = {root/'assets/3d/tripo'/name: value for name,value in manifest['protected_glb_hashes'].items()}
    protected_hashes[scene] = manifest['scene_sha256']; protected_hashes[proposal_file] = PROPOSAL_SHA
    for path, expected in protected_hashes.items():
        if sha(path) != expected: raise ValueError('Frozen input hash mismatch: '+str(path))
    validation = validate_proposal(proposal,masks,source,skin,scene)
    bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS']; rig=bpy.data.objects['V6_17_BONES_UNVERIFIED']
    names=[bone.name for bone in rig.data.bones]
    def weights():
        result=np.zeros((len(mesh.data.vertices),len(names)),dtype='<f4')
        for v in mesh.data.vertices:
            for g in v.groups:
                name=mesh.vertex_groups[g.group].name
                if name in names:result[v.index,names.index(name)]=g.weight
        return result
    original_weights=weights(); digest=hashlib.sha256(original_weights.tobytes()).hexdigest()
    if digest!=masks['bone_weight_sha256_float32']:raise ValueError('Actual Blender baseline weight SHA mismatch')
    for key,row in masks['baseline_vertex_weights'].items():
        if any(original_weights[int(key),names.index(n)]!=w for n,w in row.items()):raise ValueError('Baseline JSON/Blender mismatch')
    ids={i for entry in proposal['changes'] for i in entry['source_vertex_ids']}
    others=set().union(*(set(z['editable_source_vertex_ids']) for n,z in masks['zones'].items() if n!='tail_to_pelvis'))
    if len(ids)!=21 or ids & (others|set(masks['protected_source_vertex_ids'])):raise ValueError('Unexpected/frozen source IDs')
    if ids & {3789,3791,3793,4258,4260,4261}:raise ValueError('C1 must remain unchanged')
    if any(a.value!=i for i,a in enumerate(mesh.data.attributes['source_vertex_id'].data)):raise ValueError('Source ID mismatch')
    def fingerprint():
        values={
          'geometry':np.array([v.co[:] for v in mesh.data.vertices],dtype='<f4').tobytes(),
          'uv':np.array([v.uv[:] for v in mesh.data.uv_layers.active.data],dtype='<f4').tobytes(),
          'faces':np.array([p.vertices[:] for p in mesh.data.polygons],dtype='<i4').tobytes(),
          'bones':np.array([b.matrix_local[:] for b in rig.data.bones],dtype='<f4').tobytes()}
        result={key:hashlib.sha256(value).hexdigest() for key,value in values.items()}
        result['packed_images']=sorted(sha256_image(im) for im in bpy.data.images if im.packed_file)
        result['materials']=list(mesh.data.materials.keys())
        result['nondeforming_groups']={g.name:hashlib.sha256(np.array([next((x.weight for x in v.groups if x.group==g.index),0) for v in mesh.data.vertices],dtype='<f4').tobytes()).hexdigest() for g in mesh.vertex_groups if g.name not in names}
        return result
    frozen_fingerprint=fingerprint()
    gate={'status':'DRY_RUN_PASS_NO_WEIGHTS_APPLIED','proposal_sha256':PROPOSAL_SHA,'scene_sha256':sha(scene),
          'bone_weights_sha256_float32':digest,'frozen_hashes':{str(p):v for p,v in protected_hashes.items()},
          'read_only_validation':validation,'source_vertex_ids':sorted(ids),'changed_bones_allowed':['pelvis','tail_base'],
          'frozen_other_masks_overlap':[],'frozen_fingerprint':frozen_fingerprint,'blender':bpy.app.version_string}
    output.mkdir(parents=True,exist_ok=True)
    gate_path=output/'dry_run.json'
    if not apply:
        if gate_path.exists():raise ValueError('Existing dry-run report: choose new path')
        write(gate_path,gate);print('DRY_RUN_PASS');return
    if not gate_path.exists() or json.loads(gate_path.read_text())!=gate:raise ValueError('Matching prior successful dry-run required')
    if copy.exists() or export.exists() or work.exists():raise ValueError('New scene/diagnostic/export paths required')
    work.mkdir(parents=True);copy.parent.mkdir(parents=True,exist_ok=True);export.parent.mkdir(parents=True,exist_ok=True)
    doc,binary,_=read_glb(source);prim=doc['meshes'][0]['primitives'][0]
    original_positions=np.array(accessor(doc,binary,prim['attributes']['POSITION']))
    original_normals=np.array(accessor(doc,binary,prim['attributes']['NORMAL']))
    canonical,faces,sources,_=mesh_data(source);canonical=np.array(canonical);arrays=np.array(faces)
    first=[sources[i][0] for i in range(len(canonical))];resttri=canonical[arrays]
    oldareas=np.linalg.norm(np.cross(resttri[:,1]-resttri[:,0],resttri[:,2]-resttri[:,0]),axis=1)/2
    edgeids=np.unique(np.sort(np.concatenate([arrays[:,[0,1]],arrays[:,[1,2]],arrays[:,[2,0]]]),axis=1),axis=0)
    oldlength=np.linalg.norm(canonical[edgeids[:,0]]-canonical[edgeids[:,1]],axis=1)
    baseline_pairs={tuple(pair) for pair in json.loads((stage9/'pose_review.json').read_text())['baseline_pairs']}
    source_to_canonical={j:i for i,aliases in sources.items() for j in aliases}
    regions={'C1':{3789,3791,3793,4258,4260,4261},'C2_patch':ids,
             'tail':set(masks['zones']['tail_to_pelvis']['review_coverage_source_vertex_ids']),
             'left_hip':set(masks['zones']['left_hip']['review_coverage_source_vertex_ids']),
             'pelvis':{i for i,p in enumerate(original_positions) if np.linalg.norm(p-np.array([.19,.35,0]))<.13}}
    canonical_regions={n:{source_to_canonical[j] for j in entries} for n,entries in regions.items()}
    roi={n:np.array([i in entries for i in range(len(canonical))]) for n,entries in canonical_regions.items()}
    cases={'rest':{}}
    for angle in (5,10,15):
        for sign,label in ((1,'plus'),(-1,'minus')):cases[f'tail_{label}{angle}']={'tail_base':sign*angle}
    review=json.loads((stage9/'pose_review.json').read_text())
    for label in ('hold_positive','hold_negative'):
        cases[label]=review['poses'][review['zones']['tail_to_pelvis']['poses'][label]]['rotations']
    cases.update(pelvis_plus5={'pelvis':5},pelvis_minus5={'pelvis':-5},hip_plus15={'hip_HL':15},hip_minus15={'hip_HL':-15})
    def summarize(points):
        cp=points[first];pairs=pair_set(cp,faces);new=pairs-baseline_pairs
        tri=cp[arrays];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
        lengths=np.linalg.norm(cp[edgeids[:,0]]-cp[edgeids[:,1]],axis=1)
        ar=np.divide(area,oldareas,out=np.ones_like(area),where=oldareas>1e-14)
        er=np.divide(lengths,oldlength,out=np.ones_like(lengths),where=oldlength>1e-10)
        def stats(a):return {'min':float(a.min(initial=1)), 'max':float(a.max(initial=1)), 'p1_p5_p50_p95_p99':np.percentile(a,[1,5,50,95,99]).tolist() if len(a) else []}
        reg={}
        for name,vm in roi.items():
            fm=vm[arrays].any(axis=1);em=vm[edgeids].any(axis=1)
            reg[name]={'new_pairs':sum(any(vm[v] for f in pair for v in faces[f]) for pair in new),
                       'area_ratio':stats(ar[fm]),'edge_ratio':stats(er[em]),
                       'area_below_half':int((ar[fm]<.5).sum()),'area_above_double':int((ar[fm]>2).sum())}
        details=[]
        for a,b in sorted(new):
            ta=[Vector(p) for p in cp[list(faces[a])]];tb=[Vector(p) for p in cp[list(faces[b])]];marks=[]
            for t1,t2 in ((ta,tb),(tb,ta)):
                for i in range(3):
                    pt=crossing_point(t1[i],t1[(i+1)%3],t2)
                    if pt is not None and not any(np.linalg.norm(np.array(pt)-q)<1e-7 for q in marks):marks.append(pt)
            details.append({'source_face_pair':[a,b],'cross_points_gltf':marks})
        return {'new_pairs':len(new),'retained_baseline_pairs':len(pairs&baseline_pairs),
                'new_source_face_pairs':[list(p) for p in sorted(new)],'crossings':details,
                'C1_intersects':(6971,7816) in pairs,'C2_intersects':(7323,7586) in pairs,
                'area_ratio':stats(ar),'edge_ratio':stats(er),'area_below_half':int((ar<.5).sum()),
                'area_above_double':int((ar>2).sum()),'regions':reg,
                'seam_gap_max':max(float(np.linalg.norm(points[entries]-points[entries[0]],axis=1).max()) for entries in sources.values())}
    # Save matrices/positions as ignored numerical evidence; static snapshots are not skinned models.
    conversion=np.array([[1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]])
    def evaluate(label,w):
        outcomes={}
        for case,rotations in cases.items():
            pose(rig,rotations);ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());tmp=ev.to_mesh()
            ps=np.array([inverse(ev.matrix_world@v.co) for v in tmp.vertices]);ev.to_mesh_clear()
            local={}
            for n in names:
                bone=rig.pose.bones[n];mat=bone.parent.matrix.inverted()@bone.matrix if bone.parent else bone.matrix
                local[n]=(conversion.T@np.array(mat)@conversion).tolist()
            np.savez_compressed(work/f'{label}_{case}.npz',positions=ps)
            result=summarize(ps);result.update(rotations=rotations,joint_local_matrices_gltf=local)
            # Exactly the original split-normal blending used in stage9.
            normal_bl=np.array([convert(n) for n in original_normals]);blended=np.zeros_like(normal_bl)
            for j,n in enumerate(names):
                bone=rig.pose.bones[n];transform=np.array((bone.matrix@bone.bone.matrix_local.inverted()).to_3x3())
                blended+=w[:,j,None]*(normal_bl@transform.T)
            blended/=np.maximum(np.linalg.norm(blended,axis=1,keepdims=True),1e-20)
            snapshot=work/f'{label}_{case}.glb';write_snapshot(source,snapshot,ps,np.array([inverse(n) for n in blended]))
            result['snapshot']=str(snapshot);outcomes[case]=result
            print(label,case,result['new_pairs'],flush=True)
        pose(rig,{});return outcomes
    baseline=evaluate('v6',original_weights)
    # New file first: never save under the original scene path.
    bpy.ops.wm.save_as_mainfile(filepath=str(copy.resolve()),compress=True)
    try:
        for entry in proposal['changes']:
            for i in entry['source_vertex_ids']:
                for n in ('pelvis','tail_base'):
                    mesh.vertex_groups[n].add([i],entry['weights'][n],'REPLACE')
        adjusted=weights();changed=np.flatnonzero(np.any(adjusted!=original_weights,axis=1))
        if set(changed)!=ids:raise ValueError('Unexpected changed source IDs')
        allowed_columns=[names.index(n) for n in ('pelvis','tail_base')]
        frozen_columns=[j for j in range(len(names)) if j not in allowed_columns]
        if not np.array_equal(adjusted[:,frozen_columns],original_weights[:,frozen_columns]):raise ValueError('Unexpected changed bone')
        for entry in proposal['changes']:
            for i in entry['source_vertex_ids']:
                if not np.array_equal(adjusted[i],np.array([entry['weights'][n] for n in names],dtype='<f4')):raise ValueError('Unexpected applied weight row')
        if fingerprint()!=frozen_fingerprint:raise ValueError('Protected geometry/UV/material/mask/bone data changed')
    except Exception:
        for i in ids:
            for n in ('pelvis','tail_base'):mesh.vertex_groups[n].add([i],float(original_weights[i,names.index(n)]),'REPLACE')
        if not np.array_equal(weights(),original_weights):raise RuntimeError('Rollback verification failed')
        raise
    differences=[{'source_vertex_id':i,'before':dict(zip(names,map(float,original_weights[i]))),
                  'after':dict(zip(names,map(float,adjusted[i]))),
                  'delta':dict(zip(names,map(float,adjusted[i]-original_weights[i])))} for i in sorted(ids)]
    write(output/'weight_diff.json',{'proposal_sha256':PROPOSAL_SHA,'changed_vertices':len(ids),'rows':differences,
                                   'float32_assignment_max_error':max(abs(entry['weights'][n]-float(adjusted[i,names.index(n)])) for entry in proposal['changes'] for i in entry['source_vertex_ids'] for n in names)})
    trial=evaluate('c2_trial',adjusted)
    if fingerprint()!=frozen_fingerprint:raise ValueError('Frozen scene data changed during tests')
    bpy.ops.wm.save_as_mainfile(filepath=str(copy.resolve()),compress=True)
    bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(export.resolve()),export_format='GLB',use_selection=True,export_animations=False,
                            export_skins=True,export_all_influences=False,export_texcoords=True,export_normals=True,
                            export_materials='EXPORT',export_yup=True,export_vertex_color='NONE')
    export_audit=audit_export(source,export);write(output/'export_preservation.json',export_audit)
    exported_names,rows,_=source_skin_weights(source,export)
    exported_weights=np.array([[row[n] for n in names] for row in rows],dtype='<f4')
    lost=(adjusted>0)&(exported_weights==0)
    export_report={'cutoff':'Blender 4.3.2 drops influences <=0.0001, then renormalizes',
                   'positive_influences_dropped':int(lost.sum()),'max_component_delta':float(abs(adjusted-exported_weights).max()),
                   'source_vertices_differing_above_1e7':int((abs(adjusted-exported_weights).max(1)>1e-7).sum()),
                   'dropped_among_approved_21':int(lost[list(ids)].sum()),
                   'max_component_delta_among_approved_21':float(abs(adjusted[list(ids)]-exported_weights[list(ids)]).max())}
    np.savez_compressed(work/'baseline_trial_export_weights.npz',baseline=original_weights,trial=adjusted,export=exported_weights,names=names)
    comparisons={}
    for case in cases:
        old=np.load(work/f'v6_{case}.npz')['positions'];new=np.load(work/f'c2_trial_{case}.npz')['positions']
        delta=np.linalg.norm(new-old,axis=1);before={tuple(x) for x in baseline[case]['new_source_face_pairs']};after={tuple(x) for x in trial[case]['new_source_face_pairs']}
        comparisons[case]={'v6_new_pairs':len(before),'trial_new_pairs':len(after),'added_pairs':[list(p) for p in sorted(after-before)],
                           'removed_pairs':[list(p) for p in sorted(before-after)],'max_displacement_from_v6':float(delta.max()),
                           'max_displacement_outside_approved_ids':float(delta[[i for i in range(len(delta)) if i not in ids]].max()),
                           'C1_vertex_displacement':float(delta[[3789,3791,3793,4258,4260,4261]].max())}
    for path,expected in protected_hashes.items():
        if sha(path)!=expected:raise ValueError('Frozen input changed')
    # Confirm saved copy persistence independently of its in-memory history.
    bpy.ops.wm.open_mainfile(filepath=str(copy.resolve()))
    mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS'];rig=bpy.data.objects['V6_17_BONES_UNVERIFIED']
    if not np.array_equal(weights(),adjusted) or fingerprint()!=frozen_fingerprint:raise ValueError('Reopened copy mismatch')
    result={'status':'ONE_C2_TRIAL_COMPLETED_NOT_PRODUCTION','proposal_sha256':PROPOSAL_SHA,'original_hashes_unchanged':True,
            'copy_scene':str(copy),'copy_scene_sha256':sha(copy),'export':str(export),'export_sha256':sha(export),
            'changed_source_vertex_ids':sorted(ids),'changed_bones':['pelvis','tail_base'],'reopened_copy_weights_verified':True,
            'baseline_weight_sha256_float32':digest,'trial_weight_sha256_float32':hashlib.sha256(adjusted.tobytes()).hexdigest(),
            'geometry_uv_bones_masks_materials_fingerprint':frozen_fingerprint,'baseline_pairs':sorted(baseline_pairs),
            'baseline':baseline,'trial':trial,'comparisons':comparisons,'export_weights':export_report,
            'regions_source_vertex_ids':{n:sorted(v) for n,v in regions.items()},'blender':bpy.app.version_string,
            'no_animation_actions':len(bpy.data.actions)==0,'no_production_asset':True,
            'limits':'Strict noncoplanar crossings; tiny fur faces can dominate strain extrema. Pose tests are not feline ROM certification. Panda3D actual-export evaluation is a separate required report.'}
    write(output/'blender_comparison.json',result);print('ONE_TRIAL_COMPLETE',flush=True)

def sha256_image(im):return hashlib.sha256(bytes(im.packed_file.data)).hexdigest()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    for name in ('output','work','copy','export'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--apply-approved-proposal',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    run(args.root,args.output,args.work,args.copy,args.export,args.apply_approved_proposal)
