"""Verify zero-tolerance aliasing, conserved geometry, and the failed solver gate."""
import hashlib,json,math,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from exact_weld_proxy import build_exact_proxy
from rig_readiness_audit import read_glb,accessor
OUT=ROOT/'docs/model-reports/exact-weld-proxy'
def load(name):return json.loads((OUT/name).read_text())
def test_exact_aliasing_does_not_merge_nearby_surfaces_or_drop_faces():
 pts=[(0,0,0),(1,0,0),(0,1,0),(0,0,0),(0,0,1e-12)]
 faces=[(0,1,2),(3,1,2),(0,3,4)]
 p,f,forward,reverse=build_exact_proxy(pts,faces)
 assert len(p)==4 and forward==[0,1,2,0,3] and reverse[0]==[0,3]
 assert f[0]==f[1] and len(f)==3 and f[2]==(0,0,3)
 assert [p[i] for i in forward]==pts
@pytest.mark.parametrize('points,faces', [([(math.nan,0,0)],[]),([(0,0,0)],[(0,0,2)]),([(0,0,0)],[(0,0)])])
def test_invalid_input_rejected(points,faces):
 with pytest.raises(ValueError):build_exact_proxy(points,faces)
def test_source_alias_map_is_complete_exact_and_reversible():
 d,b,_=read_glb(ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb');pr=d['meshes'][0]['primitives'][0]
 ps=accessor(d,b,pr['attributes']['POSITION']);indices=[v[0] for v in accessor(d,b,pr['indices'])];faces=[indices[i:i+3] for i in range(0,len(indices),3)]
 p,f,forward,reverse=build_exact_proxy(ps,faces);stored=load('vertex_map.json')
 assert len(ps)==19464 and len(p)==8253 and len(f)==16460
 assert stored['source_to_proxy']==forward and stored['proxy_to_sources']==reverse
 assert stored['proxy_faces_in_source_face_order']==[list(v) for v in f]
 assert sorted(i for ids in reverse for i in ids)==list(range(19464))
 assert [p[i] for i in forward]==ps
 assert stored['tolerance']==0 and stored['new_faces_added']==stored['source_faces_removed']==0

def test_preflight_failure_blocks_binding_transfer_bends_and_export():
 x=load('preflight.json');gate=x['gate'];assert not gate['pass']
 assert gate['automatic_weight_attempts']==gate['new_rig_generations']==gate['bends_run']==0
 assert not gate['skinned_glb_exported']
 assert x['topology']['boundary_edges']==109 and x['topology']['nonmanifold_edges_more_than_two_faces']==42
 assert x['topology']['disconnected_vertex_fans']==8 and x['baseline_crossing_pair_count']==81
 assert [c['vertices'] for c in x['components']]==[8190,20,17,15,11]
 assert all(e['component']==0 for e in x['nonmanifold_records'])
 assert not any(x['cross_paw_aliases'].values())
 assert x['degenerate_source_face_ids']==[] and len(x['tiny_source_faces'])==2

def test_existing_scene_models_reports_and_masks_unchanged():
 for path,digest in load('preserved_manifest.json').items():
  assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
 p=load('preservation.json');assert p['render_unchanged'] and p['existing_rig_bones_unchanged']
 assert p['deform_bones']==46 and p['proxy_loop_uv_identical'] and p['no_coordinate_displacement']
 assert hashlib.sha256((ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend').read_bytes()).hexdigest()==p['scene_sha256']
