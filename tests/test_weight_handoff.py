"""The handoff must stay unchanged and reject unsafe/out-of-scope proposals."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from tools import weight_handoff_contract as contract

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'docs/model-reports/stage9'
SOURCE=ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
SKIN=ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb'
SCENE=ROOT/'assets/rigging/deskcat_v6_weight_handoff.blend'

def load(name):return json.loads((REPORT/name).read_text())

@pytest.fixture(scope='module')
def correspondence():return contract.source_skin_weights(SOURCE,SKIN)

@pytest.fixture
def validator(monkeypatch,correspondence):
    monkeypatch.setattr(contract,'source_skin_weights',lambda *args:correspondence)
    return lambda patch:contract.validate_proposal(patch,load('data/region_masks.json'),SOURCE,SKIN,SCENE)


def test_five_glbs_and_delivered_blend_hashes_are_frozen():
    r=load('data/scene_audit.json')
    for name,sha in r['protected_glb_hashes'].items():
        assert hashlib.sha256((ROOT/'assets/3d/tripo'/name).read_bytes()).hexdigest()==sha
    assert hashlib.sha256(SCENE.read_bytes()).hexdigest()==r['scene_sha256']
    assert r['changed_geometry_vertices']==0 and not r['new_skinprobe_exported']
    assert r['new_animation_actions']==0


def test_reopened_scene_and_sidebar_preserve_actual_v6_pose():
    r=load('data/reopened_scene_audit.json');m=load('data/region_masks.json')
    assert r['geometry_component_error_max']==0
    assert r['uv_component_error_max_after_gltf_v_conversion']==0
    assert r['bone_weight_digest_unchanged']==m['bone_weight_sha256_float32']
    assert r['external_image_dependencies']==0
    assert r['axis_guide_head_error_max']<1e-7
    assert all(x['axis_guide_head_error_max']<1e-7 for x in r['review_ui'].values())
    assert len(r['review_ui'])==6
    assert all(x['selection_matches_mask'] and x['plus15_new_pairs']==x['expected_new_pairs'] for x in r['review_ui'].values())


def test_masks_cover_observed_faces_with_seam_consistent_editable_vertices(correspondence):
    _,_,positions=correspondence;m=load('data/region_masks.json');protected=set(m['protected_source_vertex_ids']);seams={}
    for i,p in enumerate(positions):seams.setdefault(tuple(p),[]).append(i)
    for zone in m['zones'].values():
        ids=set(zone['editable_source_vertex_ids'])
        assert ids and not ids&protected
        assert all(0<=i<m['source_vertex_count'] for i in ids)
        assert all(0<=f<m['source_face_count'] for f in zone['observed_problem_source_face_ids'])
        assert all(set(seams[tuple(positions[i])])<=ids for i in ids)
    for name,labels in [('wrist_to_sole',{'FL','FR'}),('hock_to_sole',{'HL','HR'})]:
        subs=m['zones'][name]['subregions'];assert set(subs)==labels
        left,right=sorted(labels)
        assert not set(subs[left]['editable_source_vertex_ids'])&set(subs[right]['editable_source_vertex_ids'])


def test_review_poses_have_both_signs_and_actual_crossing_points():
    r=load('data/pose_review.json')
    assert len(r['poses'])==33 and len(r['baseline_pairs'])==16
    for zone in r['zones'].values():
        poses=zone['poses'];assert set(poses)=={'rest','plus10','plus15','minus10','minus15','hold_positive','hold_negative'}
        for angle in (10,15):
            positive=r['poses'][poses[f'plus{angle}']]['rotations'];negative=r['poses'][poses[f'minus{angle}']]['rotations']
            assert negative=={name:-v for name,v in positive.items()}
        for name in poses.values():
            assert all(x['cross_points_gltf'] for x in r['poses'][name]['new_crossings'])
    assert r['poses'][r['zones']['left_hip']['poses']['minus15']]['new_pairs']==162
    assert r['poses'][r['zones']['tail_to_pelvis']['poses']['plus15']]['new_pairs']==44


def test_proposal_validator_is_read_only_and_checks_actual_skin_correspondence(validator,correspondence):
    names,rows,ps=correspondence
    assert len(ps)==len(rows)==58450 and len(names)==17
    assert all(abs(sum(row.values())-1)<1e-6 for row in rows)
    result=validator(load('proposal_template.json'))
    assert result['valid_for_review'] and not result['weights_applied'] and not result['new_skinprobe_exported']
    assert result['changed_source_vertices_proposed']==0


def test_protected_vertices_and_wrong_baseline_are_rejected(validator):
    patch=load('proposal_template.json');patch['changes']=[{'source_vertex_ids':[load('data/region_masks.json')['protected_source_vertex_ids'][0]],'weights':{'pelvis':1}}]
    with pytest.raises(ValueError,match='protected'):validator(patch)
    patch['baseline_scene_sha256']='0'*64
    with pytest.raises(ValueError,match='Scene hash'):validator(patch)


def test_bad_weights_and_bone_bleed_are_rejected(validator):
    patch=load('proposal_template.json');v=load('data/region_masks.json')['zones'][patch['region']]['editable_source_vertex_ids'][0]
    for row in ({'pelvis':.5},{'pelvis':float('nan')},{'pelvis':1.1,'tail_base':-.1},{'hip_HR':1}):
        patch['changes']=[{'source_vertex_ids':[v],'weights':row}]
        with pytest.raises(ValueError):validator(patch)


def test_exact_position_seam_copies_must_receive_same_proposed_weights(validator,correspondence):
    patch=load('proposal_template.json');m=load('data/region_masks.json');_,_,positions=correspondence;ids=set(m['zones']['tail_to_pelvis']['editable_source_vertex_ids']);groups={}
    for i,p in enumerate(positions):groups.setdefault(tuple(p),[]).append(i)
    copies=next(group for group in groups.values() if len(group)>1 and set(group)<=ids)
    patch['changes']=[{'source_vertex_ids':copies[:1],'weights':{'pelvis':.5,'tail_base':.5}}]
    with pytest.raises(ValueError,match='seam'):validator(patch)
    patch['changes'][0]['source_vertex_ids']=copies
    assert validator(patch)['changed_source_vertices_proposed']==len(copies)


def test_wrong_foot_bone_cannot_be_assigned_to_left_sole_transition(validator):
    patch=load('proposal_template.json');patch['region']='wrist_to_sole';left=load('data/region_masks.json')['zones']['wrist_to_sole']['subregions']['FL']
    patch['changes']=[{'source_vertex_ids':left['editable_source_vertex_ids'][:1],'weights':{'wrist_FR':1}}]
    with pytest.raises(ValueError,match='cross-foot'):validator(patch)
