"""Verify the bounded experimental artifact and its measured rejection, not production acceptance."""
import hashlib
import json
from pathlib import Path
import pytest
from tools.weight_handoff_contract import source_skin_weights
from tools.rig_readiness_audit import read_glb

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'docs/model-reports/stage11'
def load(name):return json.loads((REPORT/name).read_text())

def test_trial_has_dry_run_exact_sha_and_only_approved_rows():
    dry=load('dry_run.json');r=load('blender_comparison.json');diff=load('weight_diff.json')
    proposal=json.loads((ROOT/'docs/model-reports/stage10/tail_to_pelvis_proposal.json').read_text())
    assert hashlib.sha256((ROOT/'docs/model-reports/stage10/tail_to_pelvis_proposal.json').read_bytes()).hexdigest()==dry['proposal_sha256']==diff['proposal_sha256']
    assert dry['status']=='DRY_RUN_PASS_NO_WEIGHTS_APPLIED'
    ids={i for row in proposal['changes'] for i in row['source_vertex_ids']}
    assert len(ids)==21 and set(r['changed_source_vertex_ids'])==ids
    assert {row['source_vertex_id'] for row in diff['rows']}==ids
    expected={i:row['weights'] for row in proposal['changes'] for i in row['source_vertex_ids']}
    for row in diff['rows']:
        assert sum(row['after'].values())==pytest.approx(1,abs=2e-7)
        assert sum(w>0 for w in row['after'].values())<=4
        for name in row['before']:
            assert row['after'][name]==pytest.approx(expected[row['source_vertex_id']][name],abs=3e-8)
            if name not in ('pelvis','tail_base'):assert row['delta'][name]==0
    assert r['reopened_copy_weights_verified'] and r['no_animation_actions']


def test_inputs_byte_identical_and_new_copy_hashes_match():
    dry=load('dry_run.json');r=load('blender_comparison.json')
    for name,sha in dry['frozen_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha
    assert hashlib.sha256((ROOT/r['copy_scene']).read_bytes()).hexdigest()==r['copy_scene_sha256']
    assert hashlib.sha256((ROOT/r['export']).read_bytes()).hexdigest()==r['export_sha256']
    assert r['original_hashes_unchanged']


def test_all_thirteen_poses_show_no_crossing_improvement_and_frozen_c1():
    r=load('blender_comparison.json')
    assert len(r['comparisons'])==13
    for n,c in r['comparisons'].items():
        assert c['added_pairs']==c['removed_pairs']==[]
        assert c['max_displacement_outside_approved_ids']==0 and c['C1_vertex_displacement']==0
        assert r['trial'][n]['seam_gap_max']==0
    assert r['baseline']['tail_plus15']['new_pairs']==r['trial']['tail_plus15']['new_pairs']==44
    assert r['trial']['tail_plus15']['C2_intersects']
    assert r['trial']['tail_plus15']['regions']['C2_patch']['area_ratio']['min']<r['baseline']['tail_plus15']['regions']['C2_patch']['area_ratio']['min']
    assert r['trial']['tail_plus15']['regions']['C2_patch']['edge_ratio']['max']>r['baseline']['tail_plus15']['regions']['C2_patch']['edge_ratio']['max']


def test_actual_panda_skin_pose_sets_match_blender_and_freeze_export_weights():
    panda=load('panda_deformation.json');capture=load('panda_capture.json');r=load('blender_comparison.json')
    assert set(capture['models'])=={'v6_export','c2_export'}
    assert capture['models']['c2_export']['sha256']==r['export_sha256']
    for model,metadata in capture['models'].items():
        assert len(metadata['controlled_joints'])==17 and metadata['rest_bind_error']<2e-6
        assert len(panda['models'][model])==13
        for case,result in panda['models'][model].items():
            assert result['added_vs_preexport_blender_pairs']==result['removed_vs_preexport_blender_pairs']==[]
            assert result['panda_vs_preexport_blender_position_error_max']<1e-5
    for c in panda['comparisons'].values():
        assert c['added_pairs']==c['removed_pairs']==[] and c['outside_approved_ids_error_max']<1e-7
    source=ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
    names,old,_=source_skin_weights(source,ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb')
    _,new,_=source_skin_weights(source,ROOT/r['export']);ids=set(r['changed_source_vertex_ids'])
    assert all(old[i]==new[i] for i in range(len(old)) if i not in ids)
    assert r['export_weights']['dropped_among_approved_21']==0


def test_export_preserves_surface_uv_textures_and_validator_has_no_errors():
    audit=load('export_preservation.json');validator=load('glb_validator.json')
    assert audit['triangle_position_uv_oriented_multiset_equal_exact']
    assert audit['matched_signature_max_position_component_error']==0
    assert audit['matched_signature_max_uv_component_error']==0
    assert audit['embedded_texture_hash_multiset_equal'] and audit['texture_slot_semantic_materials_equal']
    assert audit['animation_count']==0 and audit['joint_count']==17
    assert validator['issues']['numErrors']==0
    doc,_,_=read_glb(ROOT/load('blender_comparison.json')['export'])
    assert all('COLOR_0' not in p['attributes'] for mesh in doc['meshes'] for p in mesh['primitives'])
