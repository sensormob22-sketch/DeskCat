"""Reopen a delivered .blend and verify weights, data, packed textures and review UI."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from blender_deformation_probe import inverse,pair_set
from rig_geometry_analysis import mesh_data
from rig_readiness_audit import read_glb,accessor


def verify(scene,source,data,output):
    bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS'];rig=bpy.data.objects['V6_17_BONES_UNVERIFIED']
    masks=json.loads((data/'region_masks.json').read_text());audit=json.loads((data/'scene_audit.json').read_text())
    if hashlib.sha256(scene.read_bytes()).hexdigest()!=audit['scene_sha256']:raise ValueError('Delivered scene hash mismatch')
    d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0];ps=np.array(accessor(d,b,p['attributes']['POSITION']));uv=np.array(accessor(d,b,p['attributes']['TEXCOORD_0']));indices=np.array(accessor(d,b,p['indices'])).reshape(-1,3)
    restored=np.array([inverse(mesh.matrix_world@v.co) for v in mesh.data.vertices]);position_error=float(abs(restored-ps).max())
    if position_error>1e-7:raise ValueError('Geometry mismatch')
    if not np.array_equal(np.array([list(poly.vertices) for poly in mesh.data.polygons]),indices):raise ValueError('Face/source order mismatch')
    if any(x.value!=i for i,x in enumerate(mesh.data.attributes['source_vertex_id'].data)):raise ValueError('Vertex ID mismatch')
    if any(x.value!=i for i,x in enumerate(mesh.data.attributes['source_face_id'].data)):raise ValueError('Face ID mismatch')
    loopids=np.array([loop.vertex_index for loop in mesh.data.loops]);expected_uv=uv[loopids].copy();expected_uv[:,1]=1-expected_uv[:,1]
    actual_uv=np.array([x.uv[:] for x in mesh.data.uv_layers.active.data]);uv_error=float(abs(actual_uv-expected_uv).max())
    if uv_error>1e-7:raise ValueError('UV mismatch')
    names=[x.name for x in rig.data.bones];weights=np.zeros((len(ps),len(names)),dtype='<f4')
    for v in mesh.data.vertices:
        for group in v.groups:
            name=mesh.vertex_groups[group.group].name
            if name in names:weights[v.index,names.index(name)]=group.weight
    digest=hashlib.sha256(weights.tobytes()).hexdigest()
    if digest!=masks['bone_weight_sha256_float32']:raise ValueError('Deforming weights changed')
    protected=set(masks['protected_source_vertex_ids']);counts={}
    for zone,mask in masks['zones'].items():
        group=mesh.vertex_groups[mask['vertex_group']];selected={v.index for v in mesh.data.vertices if any(g.group==group.index and g.weight>0 for g in v.groups)}
        if selected!=set(mask['editable_source_vertex_ids']) or selected&protected:raise ValueError('Editable/protected selection mismatch')
        counts[zone]=len(selected)
        for label,sub in mask.get('subregions',{}).items():
            subgroup=mesh.vertex_groups[sub['vertex_group']]
            actual={v.index for v in mesh.data.vertices if any(g.group==subgroup.index and g.weight>0 for g in v.groups)}
            if actual!=set(sub['editable_source_vertex_ids']) or actual&protected:raise ValueError('Foot submask mismatch')
    original=Path('assets/3d/tripo/deskcat_calico_h25_v1.glb');od,ob,_=read_glb(original)
    texture_hashes={hashlib.sha256(ob[(v:=od['bufferViews'][im['bufferView']]).get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']]).hexdigest() for im in od['images']}
    packed={hashlib.sha256(bytes(im.packed_file.data)).hexdigest() for im in bpy.data.images if im.packed_file}
    if not texture_hashes<=packed:raise ValueError('Original texture bytes missing')
    if any(im.source=='FILE' and not im.packed_file for im in bpy.data.images):raise ValueError('External image dependency')
    reference=bpy.data.collections['READ_ONLY_ORIGINAL_REFERENCE_TOGGLE_VISIBILITY']
    if not reference.hide_viewport or not all(o.hide_select for o in reference.objects):raise ValueError('Reference protection missing')
    axis_error=max((bpy.data.objects['AXIS_'+bone.name].matrix_world.translation-(rig.matrix_world@rig.pose.bones[bone.name].matrix).translation).length for bone in rig.data.bones)
    if axis_error>1e-7:raise ValueError('Axis guides do not match bone heads')
    if len(bpy.data.actions):raise ValueError('Unexpected animation actions')
    exec(compile(bpy.data.texts['DESKCAT_REVIEW_UI.py'].as_string(),'DESKCAT_REVIEW_UI.py','exec'),{'__name__':'__main__'})
    ui={};canonical,faces,sources,_=mesh_data(source);first=[sources[i][0] for i in range(len(canonical))];baseline={tuple(x) for x in json.loads((data/'pose_review.json').read_text())['baseline_pairs']}
    review=json.loads((data/'pose_review.json').read_text())
    for zone in masks['zones']:
        bpy.context.scene.deskcat_zone=zone;bpy.ops.deskcat.select_review_zone()
        selected={v.index for v in mesh.data.vertices if v.select}
        if selected!=set(masks['zones'][zone]['editable_source_vertex_ids']):raise ValueError('UI selects wrong region')
        bpy.context.scene.deskcat_pose='plus15';bpy.ops.deskcat.review_pose()
        ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();cp=np.array([inverse(ev.matrix_world@v.co) for v in m.vertices])[first];ev.to_mesh_clear()
        count=len(pair_set(cp,faces)-baseline);expected=review['poses'][review['zones'][zone]['poses']['plus15']]['new_pairs']
        if count!=expected:raise ValueError('Masks changed evaluated skin pose')
        posed_axis_error=max((bpy.data.objects['AXIS_'+bone.name].matrix_world.translation-(rig.matrix_world@rig.pose.bones[bone.name].matrix).translation).length for bone in rig.data.bones)
        if posed_axis_error>1e-7:raise ValueError('Posed axis guide mismatch')
        ui[zone]={'axis_guide_head_error_max':posed_axis_error,'selection_matches_mask':True,'plus15_new_pairs':count,'expected_new_pairs':expected}
    bpy.context.scene.deskcat_pose='rest';bpy.ops.deskcat.review_pose()
    result={'status':'REOPENED_FILE_AND_REVIEW_UI_VERIFIED','scene_sha256':audit['scene_sha256'],'blender':bpy.app.version_string,'geometry_component_error_max':position_error,'uv_component_error_max_after_gltf_v_conversion':uv_error,'source_vertex_ids_exact':True,'source_face_ids_exact':True,'bone_weight_digest_unchanged':digest,'editable_region_counts':counts,'packed_original_texture_hashes':sorted(texture_hashes),'external_image_dependencies':0,'protected_reference_hidden':True,'animation_actions':0,'axis_guide_head_error_max':axis_error,'review_ui':ui,'limits':'Sidebar registration and operators tested headless; actual interactive viewport/mouse painting and remote browser access were not tested. UV values compared using glTF->Blender V flip tolerance 1e-7.'}
    output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('scene','source','data','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);verify(a.scene,a.source,a.data,a.output)
