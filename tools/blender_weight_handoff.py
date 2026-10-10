"""Prepare an unchanged v6 weight-paint handoff, not a new skin experiment.
Run in Blender background; all diagnostic GLBs stay in ignored artifacts.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Vector,Quaternion
from blender_deformation_probe import inverse,convert,pair_set,write_snapshot
from blender_weight_diagnostics import heatmap
from rig_geometry_analysis import mesh_data
from rig_readiness_audit import read_glb,accessor

ZONES={
 'tail_to_pelvis':{'bone':'tail_base','neighbors':['pelvis'],'holds':['combined_holdout','combined_holdout_opposite'],'view':'tail'},
 'thoracic_abdomen':{'bone':'thoracic','neighbors':['lumbar','root'],'holds':['pelvis_spine','pelvis_spine_opposite'],'view':'thorax'},
 'left_hip':{'bone':'hip_HL','neighbors':['pelvis','stifle_HL'],'holds':['combined_holdout','combined_holdout_opposite'],'view':'hip'},
 'right_shoulder_paw':{'bone':'shoulder_FR','neighbors':['thoracic','elbow_FR','wrist_FR'],'holds':['front_bend','front_bend_opposite'],'view':'front'},
 'wrist_to_sole':{'bone':'wrist_FR','neighbors':['elbow_FR','wrist_FL','elbow_FL'],'additional_probe_bones':['wrist_FL'],'holds':['front_bend','front_bend_opposite'],'view':'wrist'},
 'hock_to_sole':{'bone':'hock_HR','neighbors':['stifle_HR','hock_HL','stifle_HL'],'additional_probe_bones':['hock_HL'],'holds':['hind_bend','hind_bend_opposite'],'view':'hock'},
}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def pose(rig,rotations):
    for pb in rig.pose.bones:pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion()
    for name,degrees in rotations.items():
        pb=rig.pose.bones[name];axis=pb.bone.matrix_local.to_3x3().inverted()@Vector((0,1,0))
        pb.rotation_quaternion=Quaternion(axis,math.radians(degrees))
    bpy.context.view_layer.update()

def crossing_point(a,b,triangle):
    direction=b-a;v0,v1,v2=map(Vector,triangle);e1=v1-v0;e2=v2-v0;p=direction.cross(e2);det=e1.dot(p)
    if abs(det)<=1e-9:return None
    tvec=a-v0;u=tvec.dot(p)/det;q=tvec.cross(e1);v=direction.dot(q)/det;t=e2.dot(q)/det
    if 1e-6<t<1-1e-6 and u>1e-6 and v>1e-6 and u+v<1-1e-6:return list(a+t*direction)
    return None

def main(scene,source,original,report,work,output,blend):
    if work.exists() or output.exists() or blend.exists():raise ValueError('New output paths required')
    work.mkdir(parents=True);output.mkdir(parents=True);blend.parent.mkdir(parents=True,exist_ok=True)
    expected=json.loads(Path('docs/model-reports/stage8/preserved_manifest.json').read_text())
    expected['deskcat_calico_h25_v1_skinprobe_v6.glb']='e6ea0f3cdbf0230233cddf259d720fac61aab481cb134eb06ac3a6d2108cd51d'
    for name,value in expected.items():
        if sha(Path('assets/3d/tripo')/name)!=value:raise ValueError('Protected GLB changed')
    d,b,_=read_glb(source);primitive=d['meshes'][0]['primitives'][0]
    positions=np.array(accessor(d,b,primitive['attributes']['POSITION']));normals=np.array(accessor(d,b,primitive['attributes']['NORMAL']))
    source_indices=np.array(accessor(d,b,primitive['indices'])).reshape(-1,3)
    canonical,faces,sources,source_sha=mesh_data(source);cp=np.array(canonical);ids=[sources[i][0] for i in range(len(cp))]
    source_to_canonical={s:i for i,entries in sources.items() for s in entries}
    adjacency=[set() for _ in cp]
    for f in faces:
        for a,c in zip(f,f[1:]+f[:1]):adjacency[a].add(c);adjacency[c].add(a)
    bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    pose(rig,{})
    restored=np.array([inverse(mesh.matrix_world@v.co) for v in mesh.data.vertices])
    if restored.shape!=positions.shape or np.max(abs(restored-positions))>1e-7:raise ValueError('Not original-order v6 scene')
    if not np.array_equal(np.array([list(p.vertices) for p in mesh.data.polygons]),source_indices):raise ValueError('Source face ordering mismatch')
    names=[x.name for x in rig.data.bones];weights=np.zeros((len(positions),len(names)))
    for vertex in mesh.data.vertices:
        for group in vertex.groups:
            name=mesh.vertex_groups[group.group].name
            if name in names:weights[vertex.index,names.index(name)]=group.weight
    from weight_handoff_contract import source_skin_weights
    archived=np.load('artifacts/stage8_v6/weights.npz');archived_names=archived['bone_names'].tolist()
    baseline=archived['weights'][:,[archived_names.index(n) for n in names]]
    if np.max(abs(weights-baseline))>1e-7:raise ValueError('Scene weights differ from archived v6 Blender calculation')
    _,export_rows,_=source_skin_weights(source,Path('assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb'))
    export_weights=np.array([[row[n] for n in names] for row in export_rows])
    export_weight_difference={'maximum_component_difference':float(abs(weights-export_weights).max()),'source_vertices_differing_above_1e7':int(np.count_nonzero(abs(weights-export_weights).max(1)>1e-7)),'positive_influences_dropped_in_export':int(np.count_nonzero((weights>0)&(export_weights==0))),'basis':'Scene restores original pre-export Blender v6 weights; GLB exporter drops small influences and renormalizes. No weights adjusted to hide this difference.'}
    baseline_digest=hashlib.sha256(weights.astype('<f4').tobytes()).hexdigest()
    reference_report=json.loads(report.read_text());baseline_pairs={tuple(x) for x in reference_report['baseline_pairs']}
    outcomes={};snapshot_cache={};zone_records={};expanded_norm=np.array([convert(n) for n in normals])
    for key,zone in ZONES.items():
        bone=zone['bone'];probe_bones=[bone,*zone.get('additional_probe_bones',[])]
        cases={'rest':{},**{label:{name:angle for name in probe_bones} for label,angle in [('plus10',10),('plus15',15),('minus10',-10),('minus15',-15)]}}
        cases.update({label:reference_report['poses'][n]['rotations_degrees_about_blender_world_y'] for label,n in zip(('hold_positive','hold_negative'),zone['holds'])})
        zone_records[key]={**zone,'heatmap_bones':probe_bones,'poses':{},'status':'UNEDITED_V6_REVIEW_MASK_ONLY'}
        for label,rotations in cases.items():
            cache_key=tuple(sorted(rotations.items()))
            if cache_key not in snapshot_cache:
                pose(rig,rotations);ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();posed=np.array([inverse(ev.matrix_world@v.co) for v in m.vertices]);ev.to_mesh_clear()
                current=posed[ids];pairs=pair_set(current,faces);new=pairs-baseline_pairs
                tris=current[np.array(faces)];old=cp[np.array(faces)]
                old_area=np.linalg.norm(np.cross(old[:,1]-old[:,0],old[:,2]-old[:,0]),axis=1)
                area=np.linalg.norm(np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]),axis=1)/np.maximum(old_area,1e-30)
                bad=set(np.flatnonzero((area<.5)|(area>2)).tolist())
                details=[]
                for a,c in sorted(new):
                    ta,tb=[Vector(p) for p in current[list(faces[a])]],current[list(faces[c])]
                    points=[]
                    for t1,t2 in ((ta,tb),([Vector(p) for p in tb],ta)):
                        for i in range(3):
                            point=crossing_point(t1[i],t1[(i+1)%3],t2)
                            if point is not None and not any(np.linalg.norm(np.array(point)-p)<1e-7 for p in points):points.append(point)
                    details.append({'source_face_pair':[a,c],'cross_points_gltf':points})
                name=f'pose_{len(snapshot_cache):02d}';path=work/(name+'.glb')
                blended=np.zeros_like(expanded_norm)
                for j,n in enumerate(names):
                    pb=rig.pose.bones[n];transform=(pb.matrix@pb.bone.matrix_local.inverted()).to_3x3();blended+=weights[:,j,None]*(expanded_norm@np.array(transform).T)
                blended/=np.maximum(np.linalg.norm(blended,axis=1,keepdims=True),1e-20)
                write_snapshot(source,path,posed,np.array([inverse(n) for n in blended]))
                outcomes[name]={'rotations':rotations,'new_pairs':len(new),'retained_baseline_pairs':len(pairs&baseline_pairs),'new_crossings':details,'area_distorted_source_face_ids':sorted(bad),'area_ratio_percentiles':np.percentile(area,[1,5,50,95,99]).tolist(),'source_face_count':len(faces),'snapshot':str(path),'snapshot_sha256':sha(path)}
                snapshot_cache[cache_key]=name
            zone_records[key]['poses'][label]=snapshot_cache[cache_key]
        heatmap(source,work/(key+'_heatmap.glb'),weights[:,[names.index(n) for n in probe_bones]].sum(1))
    # Landmark regions are review selections, not replacement weight envelopes.
    head=((cp[:,0]<-.35)&(cp[:,1]>.30))|((cp[:,0]<-.275)&(cp[:,1]>.41))
    feet=json.loads(Path('docs/model-reports/stage6/localprep_geometry_review.json').read_text())['paw_surface_segmentation']['feet']
    sole_sources=set(v for info in feet.values() for v in info['source_vertex_ids'])
    soles={source_to_canonical[v] for v in sole_sources};protected=set(np.flatnonzero(head))|soles
    masks={}
    for key,zone in zone_records.items():
        core_faces=set();distorted=set()
        for name in zone['poses'].values():
            info=outcomes[name];core_faces.update(f for p in info['new_crossings'] for f in p['source_face_pair']);distorted.update(info['area_distorted_source_face_ids'])
        seeds={v for f in core_faces for v in faces[f]}
        if key=='tail_to_pelvis':coverage=set(np.flatnonzero((cp[:,0]>.25)&(cp[:,0]<.37)&(cp[:,1]<.32)&(abs(cp[:,2])<.10)))
        elif key=='thoracic_abdomen':coverage=set(np.flatnonzero((cp[:,0]>-.32)&(cp[:,0]<.16)&(cp[:,1]>.16)&(cp[:,1]<.37)))
        elif key=='left_hip':coverage=set(np.flatnonzero((cp[:,0]>.12)&(cp[:,0]<.32)&(cp[:,1]>.13)&(cp[:,1]<.39)&(cp[:,2]>.005)))
        elif key=='right_shoulder_paw':coverage=set(np.flatnonzero((cp[:,0]<-.13)&(cp[:,0]>-.35)&(cp[:,1]<.43)&(cp[:,2]<.005)))
        else:
            labels=('front_left','front_right') if key.startswith('wrist') else ('hind_left','hind_right')
            coverage={source_to_canonical[v] for name in labels for v in feet[name]['source_vertex_ids']}
            for _ in range(6):coverage|={b for a in list(coverage) for b in adjacency[a]}
        # Holdout poses can fail elsewhere: keep global measurements, but
        # only mark pairs touching this anatomical review coverage.
        core_faces={f for f in core_faces if any(v in coverage for v in faces[f])}
        seeds={v for f in core_faces for v in faces[f]}
        distorted_in_area={f for f in distorted if any(v in coverage for v in faces[f])}
        selected=seeds|{v for f in distorted_in_area for v in faces[f]}
        for _ in range(3):selected|={b for a in list(selected) for b in adjacency[a]}
        editable=selected-protected
        expand=lambda vertices:sorted(v for i in vertices for v in sources[i])
        masks[key]={'vertex_group':'EDIT_'+key,'primary_bone':zone['bone'],'suggested_adjacent_bones':zone['neighbors'],
                    'heatmap_bones':zone['heatmap_bones'],
                    'observed_problem_source_face_ids':sorted(core_faces),'distorted_faces_in_review_area':sorted(f for f in distorted if any(v in selected for v in faces[f])),
                    'observed_problem_source_vertex_ids':expand(seeds),'editable_source_vertex_ids':expand(editable),
                    'review_coverage_source_vertex_ids':expand(selected|coverage),'protected_problem_source_vertex_ids':expand(seeds&protected),
                    'selection_basis':'measured crossing/distorted faces touching named review coverage + three topological rings; REVIEW_ is wider anatomical context, not a defect or weight prescription',
                    'scene_face_attribute':'PROBLEM_'+key}
        group=mesh.vertex_groups.new(name='EDIT_'+key)
        if editable:group.add(expand(editable),1,'REPLACE')
        attr=mesh.data.attributes.new('PROBLEM_'+key,'BOOLEAN','FACE')
        for i in core_faces:attr.data[i].value=True
        reviewgroup=mesh.vertex_groups.new(name='REVIEW_'+key)
        if selected or coverage:reviewgroup.add(expand(selected|coverage),1,'REPLACE')
    for name,vertices in [('PROTECT_HEAD_EYES_EARS',set(np.flatnonzero(head))),('PROTECT_SOLES',soles)]:
        group=mesh.vertex_groups.new(name=name);group.add(sorted(v for i in vertices for v in sources[i]),1,'REPLACE');group.lock_weight=True
    mesh.vertex_groups['root'].lock_weight=True
    for name,bones in [(z,[zone['bone']]) for z,zone in ZONES.items()]:
        values=weights[:,[names.index(n) for n in ZONES[name].get('additional_probe_bones',[])+bones]].sum(1);color=mesh.data.color_attributes.new(name='HEAT_'+name,type='FLOAT_COLOR',domain='POINT')
        for i,t in enumerate(values):color.data[i].color=(max(0,2*t-1),1-abs(2*t-1),max(0,1-2*t),1)
    for name,domain,count in [('source_vertex_id','POINT',len(positions)),('source_face_id','FACE',len(faces))]:
        attr=mesh.data.attributes.new(name,'INT',domain)
        for i in range(count):attr.data[i].value=i
    mesh.name='WORKING_V6_UNCHANGED_WEIGHTS';mesh['source_sha256']=source_sha;mesh['bone_weight_sha256_float32']=baseline_digest;mesh['mask_groups_do_not_deform']=True
    mesh.lock_location=mesh.lock_rotation=mesh.lock_scale=(True,True,True);mesh.data.use_paint_mask_vertex=True
    initially_selected=set(masks['tail_to_pelvis']['editable_source_vertex_ids'])
    for vertex in mesh.data.vertices:vertex.select=vertex.index in initially_selected
    mesh.vertex_groups.active_index=mesh.vertex_groups['tail_base'].index
    rig.name='V6_17_BONES_UNVERIFIED';rig.show_in_front=True;rig.data.show_axes=True
    guide_collection=bpy.data.collections.new('BONE_AXIS_GUIDES');bpy.context.scene.collection.children.link(guide_collection)
    for bone in rig.data.bones:
        guide=bpy.data.objects.new('AXIS_'+bone.name,None);guide.empty_display_type='ARROWS';guide.empty_display_size=.025;guide.matrix_world=rig.matrix_world@bone.matrix_local;guide.hide_render=True;guide.hide_select=True;guide_collection.objects.link(guide)
    from blender_finalize_weight_handoff import align_axis_guides
    if align_axis_guides(rig)>1e-7:raise ValueError('Bone guide head mismatch')
    pose(rig,{})
    before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(original.resolve()),merge_vertices=False)
    collection=bpy.data.collections.new('READ_ONLY_ORIGINAL_REFERENCE_TOGGLE_VISIBILITY');bpy.context.scene.collection.children.link(collection)
    for obj in set(bpy.data.objects)-before:
        for parent in list(obj.users_collection):parent.objects.unlink(obj)
        collection.objects.link(obj);obj.name='REFERENCE_ORIGINAL_'+obj.name;obj.hide_select=True;obj.hide_render=True;obj.lock_location=obj.lock_rotation=obj.lock_scale=(True,True,True)
    collection.hide_viewport=True;collection.hide_render=True
    masks_doc={'status':'REVIEW_SELECTIONS_NO_WEIGHTS_CHANGED','source_sha256':source_sha,'source_vertex_count':len(positions),'source_face_count':len(faces),'bone_weight_sha256_float32':baseline_digest,'protected_source_vertex_ids':sorted(v for i in protected for v in sources[i]),'zones':masks,'constraints':{'same_weights_on_exact_position_uv_seam_copies':True,'max_deforming_influences':4,'normalization_tolerance':1e-6,'geometry_uv_texture_changes_allowed':False,'automatic_weight_application_authorized':False}}
    (output/'region_masks.json').write_text(json.dumps(masks_doc,indent=2)+'\n')
    (output/'pose_review.json').write_text(json.dumps({'zones':zone_records,'poses':outcomes,'baseline_pairs':sorted(baseline_pairs),'limits':'Same stage8 strict noncoplanar intersection method. Additional ±10/15 pose diagnostics only; no bone or weight editing.'},indent=2)+'\n')
    for name,text in [('REGION_MASKS.json',json.dumps(masks_doc,indent=2)),('POSE_REVIEW.json',json.dumps({'zones':zone_records,'poses':{n:x['rotations'] for n,x in outcomes.items()}},indent=2)),('READ_ME_FIRST.txt','UNEDITED V6 — NOT PRODUCTION\n17 deforming groups unchanged. EDIT_/REVIEW_/PROTECT_ are masks, not bones.\nsource_vertex_id and source_face_id preserve localprep numbering.\nRoot and protection groups locked. Per-vertex protection requires mask selection and final audit; GUI locks can be bypassed.\nGeometry, UV, materials and texture bytes must not be changed.\nNo new skinprobe, no gait, no Tripo. Select EDIT_ zone, then an actual bone before painting.\nShow HEAT_ point-color layers through Attribute shading; they never replace the character material.\nReference original is hidden/read-only by convention. Unhide collection for comparison.\nCurrent file opens at rest; controlled poses are documented, not animation actions.')]:
        block=bpy.data.texts.new(name);block.write(text)
    ui=bpy.data.texts.new('DESKCAT_REVIEW_UI.py');ui.write(Path('tools/deskcat_weight_review_ui.py').read_text())
    bpy.ops.file.pack_all()
    for image in bpy.data.images:
        if image.source=='FILE' and not image.packed_file:raise ValueError('External image not packed')
    bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);bpy.context.view_layer.objects.active=mesh
    bpy.context.scene['handoff_status']='REVIEWABLE_UNEDITED_V6_NOT_PRODUCTION'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend.resolve()),compress=True)
    scene_audit={'blender':bpy.app.version_string,'scene':str(blend),'scene_sha256':sha(blend),'source_sha256':source_sha,'protected_glb_hashes':expected,'vertices':len(positions),'faces':len(faces),'deforming_bones':names,'weights_max_difference_from_v6_computed':float(np.max(abs(weights-baseline))),'weights_float32_sha256':baseline_digest,'changed_geometry_vertices':int(np.count_nonzero(np.max(abs(restored-positions),axis=1)>1e-7)),'packed_images':[{'name':im.name,'sha256':hashlib.sha256(bytes(im.packed_file.data)).hexdigest(),'bytes':im.packed_file.size} for im in bpy.data.images if im.packed_file], 'v6_glb_weight_difference':export_weight_difference,'input_scene_sha256':sha(scene),'new_animation_actions':len(bpy.data.actions),'new_skinprobe_exported':False,'distinct_diagnostic_poses':len(outcomes),'limits':'UV and bone-weight persistence must also be checked after reopening the delivered file. Protection is selection/locks plus audit, not an unbreakable Blender permission system.'}
    (output/'scene_audit.json').write_text(json.dumps(scene_audit,indent=2)+'\n')
    print(json.dumps({'scene':str(blend),'poses':len(outcomes),'masks':{k:len(x['editable_source_vertex_ids']) for k,x in masks.items()}}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,default=Path('artifacts/stage8_v6/experimental_probe.blend'))
    p.add_argument('--source',type=Path,default=Path('assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'))
    p.add_argument('--original',type=Path,default=Path('assets/3d/tripo/deskcat_calico_h25_v1.glb'))
    p.add_argument('--report',type=Path,default=Path('docs/model-reports/stage8/v6/deformation.json'))
    for key in ('work','output','blend'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);main(a.scene,a.source,a.original,a.report,a.work,a.output,a.blend)
