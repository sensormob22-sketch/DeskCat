"""Read-only reload smoke check of committed candidate and exact source map."""
import bpy,hashlib,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_deformation_probe import inverse
from rig_readiness_audit import read_glb,accessor
root=Path.cwd();out=root/'docs/model-reports/exact-weld-proxy';scene=root/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend';mapping=json.loads((out/'vertex_map.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(scene));render=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];proxy=bpy.data.objects['EXACT_WELD_PROXY_NO_WEIGHTS'];rig=bpy.data.objects['CAT_RIGIFY_TRIAL_02']
d,b,_=read_glb(root/'assets/3d/retopo/deskcat_calico_retopo_16460.glb');pr=d['meshes'][0]['primitives'][0];ps=np.array(accessor(d,b,pr['attributes']['POSITION']));faces=np.array(accessor(d,b,pr['indices'])).reshape(-1,3)
p=np.array([inverse(proxy.matrix_world@v.co) for v in proxy.data.vertices]);r=np.array([inverse(render.matrix_world@v.co) for v in render.data.vertices]);reconstruction=float(abs(p[mapping['source_to_proxy']]-ps).max());uv_error=float(abs(np.array([x.uv[:] for x in proxy.data.uv_layers.active.data])-np.array([x.uv[:] for x in render.data.uv_layers.active.data])).max())
assert reconstruction==uv_error==0 and np.array_equal(r,ps)
assert np.array_equal(np.array([f.vertices[:] for f in proxy.data.polygons]),mapping['proxy_faces_in_source_face_order'])
assert np.array_equal(np.array([f.vertices[:] for f in render.data.polygons]),faces)
assert sum(b.use_deform for b in rig.data.bones)==46 and not proxy.vertex_groups and not proxy.modifiers
assert all(not v.groups for v in render.data.vertices)
result={'reloaded_scene_sha256':hashlib.sha256(scene.read_bytes()).hexdigest(),'proxy_vertices':len(p),'source_vertices':len(r),'face_count':len(proxy.data.polygons),'position_reconstruction_max_error':reconstruction,'proxy_source_loop_uv_error':uv_error,'existing_deform_bones':46,'proxy_has_weights':False,'proxy_has_armature_modifier':False,'render_weights_remain_empty':True,'generated_or_bound':False}
(out/'reload_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
