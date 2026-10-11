"""Read-only audit of failed setup copy; does not regenerate Rigify or bind weights."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from blender_deformation_probe import inverse
from rig_readiness_audit import read_glb,accessor
root=Path.cwd();out=root/'docs/model-reports/rigify-retopo';source=root/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0];ps=np.array(accessor(d,b,p['attributes']['POSITION']));uv=np.array(accessor(d,b,p['attributes']['TEXCOORD_0']));indices=np.array(accessor(d,b,p['indices'])).reshape(-1,3)
bpy.ops.wm.open_mainfile(filepath=str(root/'assets/rigging/deskcat_retopo_rigify_trial_01.blend'))
m=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];actual=np.array([inverse(m.matrix_world@v.co) for v in m.data.vertices]);fs=np.array([list(f.vertices) for f in m.data.polygons]);assert np.array_equal(fs,indices)
loop_uv=np.array([v.uv[:] for v in m.data.uv_layers.active.data]);expected_uv=uv[indices.flatten()].copy();expected_uv[:,1]=1-expected_uv[:,1]
uv_error=float(abs(loop_uv-expected_uv).max());pos_error=float(abs(actual-ps).max());assert uv_error<1e-7 and pos_error<1e-7
images={hashlib.sha256(im.packed_file.data).hexdigest() for im in bpy.data.images if im.packed_file};expected=set(json.loads((out/'input_audit.json').read_text())['texture_sha256']);assert expected.issubset(images)
report={'scene':str(Path('assets/rigging/deskcat_retopo_rigify_trial_01.blend')),'geometry_basis':'Uploaded raw primitive, existing non-neutral skin discarded only in copy','vertex_count':len(ps),'triangle_count':len(fs),'max_geometry_error_against_input_primitive':pos_error,'max_uv_error':uv_error,'source_face_indices_identical':True,'all_three_input_texture_payloads_packed_identically':True,'mesh_bone_weight_groups':len(m.vertex_groups),'generation_failed':True,'auto_weighting_run':False,'bend_tests_run':False,'skinned_glb_exported':False,'blender_version':bpy.app.version_string}
(out/'copy_preservation.json').write_text(json.dumps(report,indent=2)+'\n')
