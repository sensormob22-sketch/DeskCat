"""Experimental asset must preserve the character and provide real bind data."""
from pathlib import Path
import hashlib
import json
import struct

import pytest
from tools.skin_export_audit import audit_export
from tools.rig_readiness_audit import read_glb, accessor, node_transform, product

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
EXPORT=ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v5.glb'
REPORT=ROOT/'docs/model-reports/stage7/deformation.json'


def test_export_preserves_character_surface_uv_and_original_texture_bytes():
    r=audit_export(SOURCE,EXPORT)
    assert r['source_sha256']=='0e98d05ce6184779a1cac655474f7e3738c2dedb46824f72fc93a46163082bc6'
    assert r['embedded_texture_hash_multiset_equal']
    assert r['texture_slot_semantic_materials_equal']
    assert r['triangle_position_uv_oriented_multiset_equal_rounded_1e6']
    assert r['triangle_position_uv_oriented_multiset_equal_exact']
    assert r['matched_signature_max_position_component_error']==0
    assert r['matched_signature_max_uv_component_error']==0
    assert r['source_triangles']==r['export_triangles']==100790


def test_real_skin_normalized_weights_and_no_animation_promises():
    r=audit_export(SOURCE,EXPORT)
    assert r['skin_count']==1 and r['joint_count']==17
    assert r['animation_count']==0
    assert r['invalid_joint_indices']==0
    assert r['max_weight_sum_error']<1e-6
    d,b,_=read_glb(EXPORT)
    prim=d['meshes'][0]['primitives'][0]
    weights=accessor(d,b,prim['attributes']['WEIGHTS_0'])
    assert all(all(0<=w<=1 for w in row) for row in weights)
    assert any(sum(w>0 for w in row)>1 for row in weights)


def test_export_inverse_bind_matrices_actually_preserve_rest_shape():
    d,b,_=read_glb(EXPORT)
    worlds={}
    def walk(i,parent):
        worlds[i]=product(parent,node_transform(d['nodes'][i]))
        for child in d['nodes'][i].get('children',[]):walk(child,worlds[i])
    identity=(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)
    for i in d['scenes'][d.get('scene',0)]['nodes']:walk(i,identity)
    skin=d['skins'][0];a=d['accessors'][skin['inverseBindMatrices']];view=d['bufferViews'][a['bufferView']]
    offset=view.get('byteOffset',0)+a.get('byteOffset',0)
    matrices=[struct.unpack_from('<16f',b,offset+64*i) for i in range(a['count'])]
    jointmat=[product(worlds[j],ib) for j,ib in zip(skin['joints'],matrices)]
    p=d['meshes'][0]['primitives'][0]
    positions=accessor(d,b,p['attributes']['POSITION']);js=accessor(d,b,p['attributes']['JOINTS_0']);ws=accessor(d,b,p['attributes']['WEIGHTS_0'])
    worst=0
    for v,joints,weights in zip(positions,js,ws):
        result=[0.,0.,0.]
        for j,w in zip(joints,weights):
            m=jointmat[j]
            for row in range(3):result[row]+=w*(sum(m[k*4+row]*v[k] for k in range(3))+m[12+row])
        worst=max(worst,max(abs(a-b) for a,b in zip(v,result)))
    assert worst<1e-6


def test_deformation_classifies_old_and_new_pairs_by_stable_face_ids():
    r=json.loads(REPORT.read_text());base={tuple(p) for p in r['baseline_pairs']}
    stage6=json.loads((ROOT/'docs/model-reports/stage6/localprep_geometry_review.json').read_text())
    assert base=={tuple(p['source_face_pair']) for p in stage6['self_intersection']['examples']}
    assert len(base)==16
    assert r['poses']['rest']['new_pairs']==0
    for name,pose in r['poses'].items():
        new={tuple(p) for p in pose['new_source_face_pairs']};retained={tuple(p) for p in pose['retained_source_face_pairs']}
        assert not new&base
        assert retained<=base
        assert pose['strict_crossing_pairs']==len(new)+len(retained)
        assert pose['protected_head_max_displacement']==0
    assert r['poses']['tail_bend']['new_pairs']>0  # failed experiment must not be reported as accepted


def test_preserved_input_hashes():
    expected={'deskcat_calico_h25_v1.glb':'ff2a9e1d7280e4784913413fb45b10a2bdeadc125c80791a50f918a3ae646150',
              'deskcat_calico_h25_v1_rigprep.glb':'cab5d4a2205c644bdbb24a340777cf172e80969515290ae441bb78a29ce4df2c',
              SOURCE.name:'0e98d05ce6184779a1cac655474f7e3738c2dedb46824f72fc93a46163082bc6'}
    for name,sha in expected.items():assert hashlib.sha256((SOURCE.parent/name).read_bytes()).hexdigest()==sha


def test_bind_audit_includes_lower_muzzle_and_refuses_static_asset():
    from tools.skin_bind_audit import inspect
    r=inspect(EXPORT)
    assert r['max_rest_bind_displacement']<1e-6
    assert r['protected_head_vertices']==6026
    assert r['protected_head_vertices_with_nonroot_weight']==0
    with pytest.raises(ValueError,match='one real skin'):
        inspect(SOURCE)


def test_coincident_seam_positions_get_identical_skin_influences():
    d,b,_=read_glb(EXPORT);p=d['meshes'][0]['primitives'][0]
    positions=accessor(d,b,p['attributes']['POSITION']);js=accessor(d,b,p['attributes']['JOINTS_0']);ws=accessor(d,b,p['attributes']['WEIGHTS_0'])
    seen={}
    for v,joints,weights in zip(positions,js,ws):
        influence=tuple(sorted((j,w) for j,w in zip(joints,weights) if w>0))
        if v in seen:assert seen[v]==influence
        else:seen[v]=influence


def test_refined_bone_heads_pass_all_three_parity_diagnostics():
    review=json.loads((ROOT/'docs/model-reports/stage7/joint_placement_review.json').read_text())
    for name in ('hip_HL','hip_HR','stifle_HL','tail_base'):
        assert review[name]['odd_parity_votes']==3


def test_all_bone_guide_endpoints_are_inside_by_three_rays():
    r=json.loads((ROOT/'docs/model-reports/stage7/bone_endpoint_review.json').read_text())
    assert len(r)==17
    for bone in r.values():
        assert bone['head_gltf']['odd_parity_votes']==3
        assert bone['tail_gltf']['odd_parity_votes']==3


def test_pose_comparisons_use_identical_camera_and_model_normalization():
    metadata=[json.loads((ROOT/f'docs/model-reports/stage7/views/{pose}/cameras.json').read_text()) for pose in ('rest','front_bend','hind_bend','pelvis_spine','tail_bend')]
    reference=metadata[0]
    for m in metadata:
        assert m['views']==reference['views']
        assert m['fixed_model_scale']==reference['fixed_model_scale']
        assert m['fixed_model_offset']==reference['fixed_model_offset']
        assert m['reference_model']==reference['reference_model']
