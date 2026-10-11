"""Review packet completeness and correspondence; not animation certification."""
import csv
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/model-reports/stage14'

def test_packet_covers_exact_review_masks_and_vertex_aliases():
    r=json.loads((OUT/'review_manifest.json').read_text())
    prior=json.loads((ROOT/'docs/model-reports/stage13/defect_register.json').read_text())
    mapping=json.loads((ROOT/'docs/model-reports/exact-weld-proxy/vertex_map.json').read_text())
    assert {c['id'] for c in r['clusters']}=={'D04','D06','D09','D14','D17','D24','D05','D07','D15','D18'}
    for c in r['clusters']:
        original=next(x for x in prior['clusters'] if x['id']==c['id'])
        assert c['source_face_ids']==original['source_face_ids']
        assert c['context_source_face_ids']==original['context_source_face_ids']
        assert c['fan_groups']==original['fan_groups']
        allverts={v for fi in c['source_face_ids']+c['context_source_face_ids'] for v in mapping['proxy_faces_in_source_face_order'][fi]}
        assert set(map(int,c['source_vertex_aliases']))==allverts
        for v in allverts:assert c['source_vertex_aliases'][str(v)]==mapping['proxy_to_sources'][v]
    rows=list(csv.DictReader((OUT/'face_decisions.csv').open()))
    assert {(x['cluster'],int(x['source_face_id'])) for x in rows}=={(c['id'],fi) for c in r['clusters'] for fi in c['source_face_ids']}
    assert all(not row['decision'] for row in rows)

def test_archive_is_complete_and_has_no_duplicated_models():
    checks=json.loads((OUT/'package_checksums.json').read_text())
    with zipfile.ZipFile(OUT/'DeskCat_Topology_Review.zip') as z:
        assert not any(n.lower().endswith(('.blend','.glb')) for n in z.namelist())
        assert (OUT/'DeskCat_Topology_Review.zip').stat().st_size<2_000_000
        for name,sha in checks.items():
            assert hashlib.sha256(z.read('DeskCat_Topology_Review/'+name)).hexdigest()==sha
            assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==sha
    for link in json.loads((OUT/'source_links.json').read_text()):
        assert '/74199b9/' in link['download']
        assert hashlib.sha256((ROOT/link['path']).read_bytes()).hexdigest()==link['sha256']

def test_actual_blender_selection_smoke_preserved_data():
    v=json.loads((OUT/'verification.json').read_text())
    assert v['selection_cases']>=40
    assert v['face_order_validated_both_objects']
    assert v['mesh_uv_material_weights_bones_packed_texture_signature_preserved']
    assert v['source_scene_hash_preserved']
    assert not v['source_scene_saved']
    assert v['mesh_edits']==v['weight_binds']==v['new_blend_files']==0
