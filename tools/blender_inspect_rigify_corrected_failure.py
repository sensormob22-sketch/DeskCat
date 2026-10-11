"""Read-only evidence after the sole failed heat bind. No pose/weight edits."""
import bpy,hashlib,json,sys
from pathlib import Path
from collections import Counter
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor
from rig_geometry_analysis import components,edge_faces
from blender_deformation_probe import inverse,pair_set
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/rigify-corrected';SCENE=ROOT/'assets/rigging/deskcat_retopo_rigify_trial_02.blend'
def digest(x):return hashlib.sha256(x).hexdigest()
def state(path):
 bpy.ops.wm.open_mainfile(filepath=str(path));m=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];bpy.context.view_layer.update()
 p=np.array([inverse(m.matrix_world@v.co) for v in m.data.vertices]);uv=np.array([v.uv[:] for v in m.data.uv_layers.active.data]);faces=np.array([v.vertices[:] for v in m.data.polygons])
 images={i.name:digest(i.packed_file.data) for i in bpy.data.images if i.packed_file}
 materials=[]
 for slot in m.material_slots:
  mat=slot.material;nodes=[]
  for n in mat.node_tree.nodes:
   inputs={}
   for socket in n.inputs:
    if not hasattr(socket,'default_value'):continue
    value=socket.default_value
    if isinstance(value,(float,int,bool,str)):inputs[socket.name]=value
    elif hasattr(value,'__len__'):inputs[socket.name]=list(value)
   nodes.append({'type':n.bl_idname,'name':n.name,'image':n.image.name if hasattr(n,'image') and n.image else None,'inputs':inputs})
  materials.append({'name':mat.name,'nodes':nodes,'links':sorted((x.from_node.name,x.from_socket.name,x.to_node.name,x.to_socket.name) for x in mat.node_tree.links)})
 return m,p,uv,faces,{'positions':digest(p.astype('<f8').tobytes()),'uv':digest(uv.astype('<f8').tobytes()),'faces':digest(faces.astype('<i4').tobytes()),'images':images,'materials':materials}
_,_,_,_,before=state(SCENE.with_name('deskcat_retopo_rigify_trial_02_preflight.blend'))
m,p,uv,faces,after=state(SCENE)
d,b,_=read_glb(ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb');pr=d['meshes'][0]['primitives'][0];src=np.array(accessor(d,b,pr['attributes']['POSITION']));suv=np.array(accessor(d,b,pr['attributes']['TEXCOORD_0']));si=np.array(accessor(d,b,pr['indices'])).reshape(-1,3)
assert np.array_equal(faces,si);error=float(np.linalg.norm(p-src,axis=1).max());uv_expected=suv[si.flatten()];uv_expected[:,1]=1-uv_expected[:,1];uv_error=float(abs(uv-uv_expected).max())
assert error<1e-7 and uv_error<1e-7 and before==after
image_hashes=[]
for image in d['images']:
 view=d['bufferViews'][image['bufferView']];start=view.get('byteOffset',0);image_hashes.append(digest(b[start:start+view['byteLength']]))
assert sorted(image_hashes)==sorted(after['images'].values())
def stats(faces,number):
 e=edge_faces([tuple(x) for x in faces]);c=components(range(number),e)
 return {'vertices':number,'edge_connected_components':len(c),'component_sizes':sorted([len(x) for x in c],reverse=True),'boundary_edges':sum(len(v)==1 for v in e.values()),'nonmanifold_edges':sum(len(v)>2 for v in e.values()),'degenerate_faces':sum(len(set(f))<3 for f in faces),'minimum_area':float(np.linalg.norm(np.cross(p[si[:,1]]-p[si[:,0]],p[si[:,2]]-p[si[:,0]]),axis=1).min()/2)}
canonical,remap=np.unique(p,axis=0,return_inverse=True)
baseline_pairs=sorted(pair_set(canonical,remap[faces].tolist()))
report={'baseline_crossing_pairs':baseline_pairs,'baseline_crossing_pair_count':len(baseline_pairs),'bends_run':0,'posed_intersections_tested':False,'scene_sha256':digest(SCENE.read_bytes()),'before_after_generation_mesh_uv_materials_images_identical':before==after,'before_after':after,'raw_position_max_error':error,'source_loop_uv_max_error_after_v_flip':uv_error,'packed_images_bit_identical_to_source':True,'indexed_mesh_topology':stats(faces,len(p)),'exact_position_weld_analysis_only_topology':stats(remap[faces],len(canonical)),'no_mesh_changes_applied':True,'actual_warning':'Bone Heat Weighting: failed to find solution for one or more bones','reason_limit':'Blender reported a bone-heat solution failure but no specific bone or solver pivot. Connectivity/boundary statistics identify possible prerequisites for a future binding strategy; they do not prove the sole mathematical failure cause. No welding, topology repair or rebind was done.'}
(OUT/'failure_inspection.json').write_text(json.dumps(report,indent=2)+'\n')
r=bpy.data.objects['CAT_RIGIFY_TRIAL_02'];layout={x.name:{'head_gltf':inverse(r.matrix_world@x.head_local),'tail_gltf':inverse(r.matrix_world@x.tail_local),'parent':x.parent.name if x.parent else None} for x in r.data.bones if x.use_deform}
(OUT/'post_bind_layout.json').write_text(json.dumps({'bones':layout,'status':'Generated DEF bones, all heat weight groups empty, no rotations'},indent=2)+'\n')
print('Surface/UV/material/image preservation verified; baseline crossings:',len(baseline_pairs))
