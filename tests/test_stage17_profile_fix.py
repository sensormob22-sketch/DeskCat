"""Artifact regression checks for the local static belly repair."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rig_readiness_audit import read_glb,accessor
REPORT=ROOT/'docs/model-reports/stage17'

@pytest.fixture(scope='module')
def artifact():
    source=read_glb(ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb')
    result=read_glb(ROOT/'assets/3d/retopo/deskcat_belly_profile_fix_01.glb')
    audit=json.loads((REPORT/'geometry_audit.json').read_text())
    return source,result,audit

def test_immutable_source_and_verified_result(artifact):
    source,result,audit=artifact
    assert hashlib.sha256(source[2]).hexdigest()==audit['source_sha256']
    assert hashlib.sha256(result[2]).hexdigest()==audit['output_glb_sha256']
    for path,h in json.loads((REPORT/'verification.json').read_text())['preserved_asset_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h

def test_original_vertices_uv_and_material_unchanged(artifact):
    source,result,audit=artifact
    sd,sb,_=source;rd,rb,_=result
    sa=sd['meshes'][0]['primitives'][0]['attributes'];ra=rd['meshes'][0]['primitives'][0]['attributes']
    for name in ['POSITION','NORMAL','TEXCOORD_0']:
        expected=accessor(sd,sb,sa[name]);assert accessor(rd,rb,ra[name])[:len(expected)]==expected
    assert sd['materials'][0]==rd['materials'][0]
    for i in range(3):
        a=sd['bufferViews'][sd['images'][i]['bufferView']];b=rd['bufferViews'][rd['images'][i]['bufferView']]
        assert sb[a['byteOffset']:a['byteOffset']+a['byteLength']]==rb[b['byteOffset']:b['byteOffset']+b['byteLength']]

def test_static_export_does_not_reuse_invalid_skin(artifact):
    _,result,audit=artifact
    d,_,_=result
    assert not d.get('skins') and not d.get('animations')
    assert len(d['meshes'][0]['primitives'])==3
    assert all('JOINTS_0' not in p['attributes'] and 'WEIGHTS_0' not in p['attributes'] for p in d['meshes'][0]['primitives'])
    assert audit['protected_face_5552_preserved']
    assert audit['changed_source_vertex_ids']==[]
    assert audit['rig_def_bones_in_scene']==46

def test_actual_export_closes_tested_gap_without_new_crossings():
    v=json.loads((REPORT/'verification.json').read_text())
    assert v['known_D14_ray']['source_face']==5552
    assert v['known_D14_ray']['new_hit_is_replacement_surface']
    assert v['new_crossings']==0
    assert set(v['new_patch_internal_edge_incidence'])=={'2'}
    for side in v['two_sided_ray_grid']:
        assert side['new_surface_first_hits']==side['rays']
        assert side['new_misses']==side['new_opposite_side_first_hits']==0

def test_validator_and_real_panda_import_correspond_to_result(artifact):
    _,result,audit=artifact
    validator=json.loads((REPORT/'validator_result.json').read_text())
    assert validator['issues']['numErrors']==0
    assert {m['code'] for m in validator['issues']['messages'] if m['severity']==1}=={'MESH_PRIMITIVE_GENERATED_TANGENT_SPACE'}
    panda=json.loads((REPORT/'panda_load_check.json').read_text())
    assert panda['sha256']==hashlib.sha256(result[2]).hexdigest()
    assert panda['nonbackground_pixels']>50000
    assert panda['clips']==[] and not panda['has_skeleton']
