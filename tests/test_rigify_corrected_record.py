"""Acceptance gates for the one corrected Rigify attempt, not deformation approval."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/model-reports/rigify-corrected'
def load(name):return json.loads((OUT/name).read_text())
def test_preflight_preserves_tail_and_checks_all_connected_components():
 p=load('preflight.json');assert p['structural_pass'] and p['visual_anatomy_review_pass']
 assert not p['errors'] and all(x['pass'] for x in p['chains'])
 assert {x['bone'] for x in p['chains']}=={'tail.001','spine.004'}
 assert p['spine_points_gltf'][0]==p['tail_points_gltf'][0]==[.315,.3,0]
 for x in p['anatomy'].values():
  assert x['side_correct'] and x['distal_height_descending'] and x['longitudinal_region_correct']
  assert min(x['segment_lengths'])>0 and x['paw_vertices']
 scene=ROOT/'assets/rigging/deskcat_retopo_rigify_trial_02_preflight.blend'
 assert hashlib.sha256(scene.read_bytes()).hexdigest()==p['prepared_scene_sha256']
def test_heat_failure_prevents_false_acceptance_or_bends():
 g=load('generation.json');w=load('weights.json');gate=load('neutral_gate.json')
 assert g['attempts']==g['auto_weight_attempts']==1 and g['generated']
 assert g['bones']==280 and g['deform_bones']==46
 assert g['failure_stage']=='automatic_heat_binding' and not g['accepted']
 assert g['auto_weighted_vertices']==0 and g['unweighted_vertices']==19464
 assert len(w['rows'])==19464 and all(not x for x in w['rows'])
 assert not gate['blender_and_local_weight_gate_pass'] and not gate['panda_neutral_gate_tested']
 assert not g['bend_tests_run'] and not g['skinned_glb_exported']
 assert 'failed to find solution' in (OUT/'blender_attempt.log').read_text()
def test_existing_sources_and_new_scene_preservation():
 for path,digest in load('preserved_manifest.json').items():
  assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
 x=load('failure_inspection.json')
 assert x['raw_position_max_error']==x['source_loop_uv_max_error_after_v_flip']==0
 assert x['before_after_generation_mesh_uv_materials_images_identical'] and x['packed_images_bit_identical_to_source']
 assert x['no_mesh_changes_applied'] and x['bends_run']==0
 assert hashlib.sha256((ROOT/'assets/rigging/deskcat_retopo_rigify_trial_02.blend').read_bytes()).hexdigest()==x['scene_sha256']
def test_no_hidden_generation_or_bind_retry_in_tool():
 tree=ast.parse((ROOT/'tools/blender_rigify_retopo_corrected.py').read_text())
 calls=[ast.unparse(x.func) for x in ast.walk(tree) if isinstance(x,ast.Call)]
 assert calls.count('bpy.ops.pose.rigify_generate')==1
 assert calls.count('bpy.ops.object.parent_set')==1
 text=(ROOT/'tools/blender_rigify_retopo_corrected.py').read_text()
 assert 'attempt_started.json' in text and 'Prepared scene changed' in text
