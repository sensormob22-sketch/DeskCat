"""Preservation and rejected-trial evidence; does not certify a repaired model."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/model-reports/stage15'

def test_selected_gap_reveals_rear_color_and_neighbors_map_to_d14():
    rays=json.loads((OUT/'ray_diagnosis.json').read_text())['oblique']
    center=next(r for r in rays if r['pixel']==[420,240])['hits'][0]
    assert center['source_face_id']==5552
    assert center['point'][2]<-.08
    assert center['base_color_srgb_8bit']==[104,52,28]
    for pixel,face in [([410,200],12146),([420,285],12159),([404,315],12162)]:
        hit=next(r for r in rays if r['pixel']==pixel)['hits'][0]
        assert hit['source_face_id']==face and 'D14' in hit['stage13_core_or_context']
        assert hit['point'][2]>.05

def test_one_patch_is_rejected_without_exports_or_original_mesh_changes():
    p=json.loads((OUT/'patch_trial.json').read_text())
    assert p['trial_count']==1 and p['rejected']
    assert p['new_vertices']==8 and p['new_faces']==7
    assert p['new_diagnostic_face_ids']==list(range(16460,16467))
    assert len(p['new_strict_crossing_pairs'])==10
    assert p['baseline_crossing_count_exact_position_aliases']==81
    assert all(a<16460<=b for a,b in p['new_strict_crossing_pairs'])
    assert p['scene_raw_mesh_position_max_error_vs_source']==0
    assert p['scene_raw_mesh_loop_uv_max_error_vs_source']==0
    assert p['scene_raw_face_order_matches_source'] and p['rig_def_bones_verified']==46
    assert p['all_normals_outward'] and min(p['new_triangle_areas'])>0
    assert p['changed_original_vertices']==p['changed_original_uv']==p['source_images_replaced']==0
    assert not p['scene_saved'] and not p['exported_glb'] and not p['existing_skin_used']
    assert all(0<=x<=1 for row in p['uv_gltf'] for x in row)
    assert all(min(color)>150 for color in p['uv_vertex_base_colors'])

def test_old_assets_and_reports_preserved():
    frozen=json.loads((ROOT/'docs/model-reports/stage13/preserved_manifest.json').read_text())
    for name,expected in frozen.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    assert not list(OUT.rglob('*.blend')) and not list(OUT.rglob('*.glb'))
