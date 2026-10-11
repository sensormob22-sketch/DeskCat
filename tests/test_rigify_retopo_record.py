"""Recorded failed attempt must not be exposed as a successfully bound model."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/model-reports/rigify-retopo'

def test_single_generation_failed_before_weighting_and_export():
    r=json.loads((OUT/'generation.json').read_text())
    assert r['attempts']==1 and r['auto_weight_attempts']==0
    assert r['accepted'] is False and 'position is disjoint' in r['error']
    v=json.loads((OUT/'copy_preservation.json').read_text())
    assert v['mesh_bone_weight_groups']==0 and v['bend_tests_run'] is False
    assert v['skinned_glb_exported'] is False

def test_retopo_copy_preserves_source_uv_and_textures():
    r=json.loads((OUT/'copy_preservation.json').read_text())
    assert r['triangle_count']==16460
    assert r['max_geometry_error_against_input_primitive']==0
    assert r['max_uv_error']==0 and r['source_face_indices_identical']
    assert r['all_three_input_texture_payloads_packed_identically']
    source=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==json.loads((OUT/'input_audit.json').read_text())['sha256']

def test_existing_model_hashes_unchanged():
    for name,expected in json.loads((OUT/'preserved_manifest.json').read_text()).items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
