"""Stage8 preserves the character and reports failures rather than hiding them."""
from pathlib import Path
import hashlib
import json

from tools.skin_export_audit import audit_export
from tools.skin_bind_audit import inspect
from tools.rig_readiness_audit import read_glb, accessor

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'docs/model-reports/stage8'
EXPORT=ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb'


def test_four_inputs_remain_byte_identical():
    expected=json.loads((ROOT/'docs/model-reports/stage7/source_manifest.json').read_text())
    for name,sha in expected.items():
        assert hashlib.sha256((ROOT/'assets/3d/tripo'/name).read_bytes()).hexdigest()==sha


def test_v6_preserves_exact_surface_uv_and_texture_payloads():
    r=audit_export(ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb',EXPORT)
    assert r['triangle_position_uv_oriented_multiset_equal_exact']
    assert r['matched_signature_max_position_component_error']==0
    assert r['matched_signature_max_uv_component_error']==0
    assert r['embedded_texture_hash_multiset_equal']
    assert r['texture_slot_semantic_materials_equal']
    assert r['source_triangles']==r['export_triangles']==100790
    assert r['skin_count']==1 and r['joint_count']==17 and r['animation_count']==0


def test_v6_bind_and_protected_face():
    r=inspect(EXPORT)
    assert r['max_rest_bind_displacement']<1e-6
    assert r['max_weight_sum_error']<1e-6
    assert r['protected_head_vertices_with_nonroot_weight']==0


def test_v6_actual_parent_hierarchy():
    d,_,_=read_glb(EXPORT);names={x.get('name'):i for i,x in enumerate(d['nodes'])}
    for child,parent in [('lumbar','thoracic'),('pelvis','lumbar'),('tail_base','pelvis'),('shoulder_FR','thoracic'),('hip_HL','pelvis')]:
        assert names[child] in d['nodes'][names[parent]].get('children',[])


def test_connected_tail_mask_excludes_paws_and_foreign_surface():
    r=json.loads((REPORT/'v6/weight_mask_audit.json').read_text())
    assert r['tail_mask_canonical_vertices']==5374
    assert r['tail_weight_max_outside_connected_mask']==0
    assert all(value==0 for value in r['paw_tail_max'].values())
    assert r['seam_weight_difference_max']==0
    assert r['weight_sum_error_max']<1e-12
    assert r['max_influences']<=4


def test_same_angles_stable_baseline_and_opposite_holdouts():
    a=json.loads((REPORT/'v5/deformation.json').read_text());b=json.loads((REPORT/'v6/deformation.json').read_text())
    assert a['baseline_pairs']==b['baseline_pairs'] and len(a['baseline_pairs'])==16
    assert len(a['poses'])==len(b['poses'])==43
    for name,pose in b['poses'].items():
        assert pose['rotations_degrees_about_blender_world_y']==a['poses'][name]['rotations_degrees_about_blender_world_y']
        assert pose['seam_gap_max']<1e-6
        assert pose['protected_head_max_displacement']<1e-6
    for name in ('tail_bend','isolated_pelvis','isolated_shoulder_FR'):
        angles=b['poses'][name]['rotations_degrees_about_blender_world_y']
        assert b['poses'][name+'_opposite']['rotations_degrees_about_blender_world_y']=={n:-v for n,v in angles.items()}


def test_failed_deformations_remain_explicit_and_validator_is_not_acceptance():
    r=json.loads((REPORT/'comparison.json').read_text())
    assert r['status']=='REJECTED_FOR_PRODUCTION_STOP_AFTER_ONE_CYCLE'
    for name in ('tail_bend','isolated_thoracic','isolated_hip_HL_opposite','combined_holdout_opposite'):
        assert r['cases'][name]['assessment']=='FAIL'
    assert r['cases']['tail_bend']['v6']['new_pairs']==44
    assert r['cases']['isolated_pelvis']['v6']['new_pairs']==1
    assert json.loads((REPORT/'v6/validation.json').read_text())['issues']['numErrors']==0


def test_actual_exported_tail_weights_have_no_outside_mask_influence():
    mask=json.loads((REPORT/'v6/weight_mask_audit.json').read_text())
    a,ab,_=read_glb(ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb')
    ap=a['meshes'][0]['primitives'][0]
    positions=accessor(a,ab,ap['attributes']['POSITION'])
    allowed={tuple(positions[i]) for i in mask['tail_mask_source_vertex_ids']}
    d,b,_=read_glb(EXPORT);p=d['meshes'][0]['primitives'][0]
    joint=d['skins'][0]['joints'];tail=next(i for i,n in enumerate(joint) if d['nodes'][n].get('name')=='tail_base')
    ps=accessor(d,b,p['attributes']['POSITION']);js=accessor(d,b,p['attributes']['JOINTS_0']);ws=accessor(d,b,p['attributes']['WEIGHTS_0'])
    influenced=0
    for position,indices,weights in zip(ps,js,ws):
        value=sum(w for j,w in zip(indices,weights) if j==tail)
        if value>0:
            influenced+=1
            assert tuple(position) in allowed
    assert influenced>1000
