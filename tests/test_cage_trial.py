"""Frozen outputs: preservation, truthful discrete export, and failure gates."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from rig_readiness_audit import read_glb

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'docs/model-reports/stage12'

def test_all_previous_models_and_scenes_unchanged():
    manifest=json.loads((REPORT/'preserved_manifest.json').read_text())
    assert len(manifest)>=8
    for path,expected in manifest.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path

def test_diagnostic_morph_glb_preserves_original_data_and_materials():
    original,buf,_=read_glb(ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb')
    baked,newbuf,_=read_glb(ROOT/'assets/3d/tripo/deskcat_cage_trial_01_baked_poses.glb')
    assert newbuf[:original['buffers'][0]['byteLength']]==buf[:original['buffers'][0]['byteLength']]
    for key in ('materials','textures','images','samplers','extensionsUsed','extensionsRequired'):
        assert baked.get(key)==original.get(key)
    assert baked['meshes'][0]['primitives'][0]['attributes']==original['meshes'][0]['primitives'][0]['attributes']
    assert len(baked['meshes'][0]['primitives'][0]['targets'])==10
    assert 'skins' not in baked and 'animations' not in baked

def test_no_new_bone_weights_and_no_protected_deformation_difference():
    r=json.loads((REPORT/'comparison.json').read_text());m=json.loads((ROOT/'docs/model-reports/stage9/data/region_masks.json').read_text())
    assert r['bone_weights_sha256_float32']==m['bone_weight_sha256_float32']
    for pose in r['models']['cage'].values():
        assert pose['max_difference_outside_masks']==0
        assert pose['max_difference_protected']==0

def test_failed_quality_gates_are_explicit():
    r=json.loads((REPORT/'comparison.json').read_text());a=r['models']['v6'];b=r['models']['cage']
    assert b['tail_plus15']['new_pairs']>a['tail_plus15']['new_pairs']
    assert b['combined_positive']['new_pairs']>a['combined_positive']['new_pairs']
    assert b['hip_plus15']['seam_gap_max']>1e-3
    decision=json.loads((REPORT/'decision.json').read_text())
    assert decision['choice']=='B' and decision['production_ready'] is False

def test_actual_panda_morphs_and_validator():
    panda=json.loads((REPORT/'panda_morph.json').read_text())
    assert len(panda['cases'])==11
    assert max(p['max_position_error'] for p in panda['cases'].values())<2e-6
    audit=json.loads((REPORT/'seam_and_runtime_audit.json').read_text())
    assert all(p['same_pair_set_as_blender_snapshot'] for p in audit['actual_panda_crossings'].values())
    assert json.loads((REPORT/'glb_validator.json').read_text())['issues']['numErrors']==0
