"""Protect metadata-only scope and failed neutral gate against unsafe continuation."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rig_readiness_audit import read_glb
REPORT=ROOT/'docs/model-reports/existing-retopo-skin'
def load(name):return json.loads((REPORT/name).read_text())
def test_metadata_only_copy_preserves_payload_and_all_other_json():
 a,b,_=read_glb(ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb')
 c,d,_=read_glb(ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460_metadata_diag.glb')
 assert b==d
 changes=load('metadata_fix.json')['changes'];assert {x['accessor'] for x in changes}=={2,4,6}
 for x in changes:
  assert c['accessors'][x['accessor']]['min']==x['after']
  c['accessors'][x['accessor']]['min']=x['before']
 assert a==c
 assert load('metadata_validator.json')['issues']['numErrors']==0

def test_existing_sources_untouched():
 for path,digest in load('preserved_manifest.json').items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest

def test_skin_distribution_does_not_certify_deformation():
 a=load('skin_audit.json');assert a['skin_joint_count']==21
 assert a['weights']['max_sum_error']==0
 assert a['weights']['all_rows_are_1_0_0_0']
 assert a['weights']['joint_contributions'][0]['positive_vertices']==19451
 assert a['default_bind']['all_node_local_transforms_identity']

def test_failed_neutral_gate_blocks_rotations_and_future_generation():
 gate=load('neutral_gate.json');assert gate['gate'].startswith('FAIL') and not gate['bend_tests_run']
 assert gate['blender_enabled_vs_formula']<2e-6
 assert gate['actual_panda_vs_raw_primitive']<2e-6
 assert gate['actual_panda_vs_blender_enabled']>.8
 assert gate['metadata_vs_original_actual_panda']==0
 preflight=load('rigify_connection_preflight.json')
 assert not preflight['applied'] and preflight['generation_calls']==0
 assert not preflight['proposal_structural_errors']
 assert preflight['proposal']['reverse_connection_gap_after']==0

 assert all(c['pass'] for c in preflight['chain_checks_proposed'])
 assert not all(c['pass'] for c in preflight['chain_checks_before'])
