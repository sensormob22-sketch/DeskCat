"""Measure already-created rejected backing; never constructs a Blender patch."""
import json,sys
from pathlib import Path
import numpy as np
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_deformation_probe import pair_set,inverse
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage15';trial=json.loads((OUT/'patch_trial.json').read_text());a=np.load(ROOT/'artifacts/stage15/source.npz');p=a['points'];f=a['faces'];patch=np.array(trial['points_gltf']);pf=np.array(trial['faces']);t=patch[pf];normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);area=np.linalg.norm(normals,axis=1)/2;expected=np.array([0,-1.2,1.]);baseline=pair_set(p,[tuple(x) for x in f]);trial['baseline_crossing_count_raw_source']=len(baseline)
mapping=json.loads((ROOT/'docs/model-reports/exact-weld-proxy/vertex_map.json').read_text());canonical=p[[ids[0] for ids in mapping['proxy_to_sources']]];cf=[tuple(face) for face in mapping['proxy_faces_in_source_face_order']];canonical_base=pair_set(canonical,cf);canonical_all=pair_set(np.vstack([canonical,patch]),cf+[tuple(int(v)+len(canonical) for v in face) for face in pf]);new=sorted(pair for pair in canonical_all if pair[1]>=len(cf));assert new==[tuple(pair) for pair in trial['new_strict_crossing_pairs']]
trial['baseline_crossing_count_exact_position_aliases']=len(canonical_base);trial['baseline_pairs_exact_position_aliases']=sorted(canonical_base);trial['crossing_metric_note']='Use exact-position alias topology to exclude UV seam contacts: baseline 81, new backing pairs 10. Raw-ID baseline 101 includes 20 alias/shared-position contact candidates and is not the comparable Stage13 metric.'
trial['new_triangle_area_sum']=float(area.sum());trial['new_triangle_areas']=area.tolist();trial['normal_unit_gltf']=(normals/np.linalg.norm(normals,axis=1)[:,None]).tolist();trial['all_normals_outward']=bool(np.all(normals@expected>0));trial['patch_bounds_gltf']=[patch.min(0).tolist(),patch.max(0).tolist()];trial['baseline_strict_crossing_pairs_original_source_ids']=sorted(baseline)
trial['changed_original_vertices']=0;trial['changed_original_uv']=0;trial['source_images_replaced']=0;trial['existing_skin_used']=False
scene=ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend';bpy.ops.wm.open_mainfile(filepath=str(scene));original=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];actual=np.array([inverse(original.matrix_world@v.co) for v in original.data.vertices]);actual_faces=np.array([poly.vertices[:] for poly in original.data.polygons]);assert np.array_equal(actual_faces,f)
position_error=float(np.abs(actual-p).max());assert position_error<1e-7
expected_uv=a['uv'][f].reshape(-1,2).copy();expected_uv[:,1]=1-expected_uv[:,1];actual_uv=np.array([loop.uv[:] for loop in original.data.uv_layers.active.data]);uv_error=float(np.abs(actual_uv-expected_uv).max());assert uv_error<1e-7
trial['scene_raw_mesh_position_max_error_vs_source']=position_error;trial['scene_raw_mesh_loop_uv_max_error_vs_source']=uv_error;trial['scene_raw_face_order_matches_source']=True;trial['rig_def_bones_verified']=sum(b.use_deform for b in bpy.data.objects['CAT_RIGIFY_TRIAL_02'].data.bones);assert trial['rig_def_bones_verified']==46
(OUT/'patch_trial.json').write_text(json.dumps(trial,indent=2)+'\n');print(json.dumps({'area':float(area.sum()),'baseline_raw_pairs':len(baseline),'outward':bool(np.all(normals@expected>0))}))
