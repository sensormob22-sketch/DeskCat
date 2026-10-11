"""Local selected-to-active normal bake, fading micro-fur into smooth belly.

Runs after geometry build; modifies only this stage's new copy/materials. Source
images/materials/geometry and existing Rigify data remain untouched.
"""
import bpy,numpy as np,json,sys,struct,hashlib
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor
from blender_deformation_probe import convert
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage17';GLB=ROOT/'assets/3d/retopo/deskcat_belly_profile_fix_01.glb';BLEND=ROOT/'assets/rigging/deskcat_belly_profile_fix_01.blend'
if json.loads((OUT/'geometry_audit.json').read_text()).get('local_normal_bake'):
 raise FileExistsError('Normal bake already applied. Rebuild the separate Stage17 diagnostic first; never append another bake to the published result.')
doc,b,_=read_glb(GLB);binary=bytearray(b[:doc['buffers'][0]['byteLength']]);pr=doc['meshes'][0]['primitives'][1];p=np.array(accessor(doc,b,pr['attributes']['POSITION']));uv=np.array(accessor(doc,b,pr['attributes']['TEXCOORD_0']));n=np.array(accessor(doc,b,pr['attributes']['NORMAL']));faces=[];material_indices=[]
for mi,pr in enumerate(doc['meshes'][0]['primitives'][1:]):
 f=np.array(accessor(doc,b,pr['indices']),int).reshape(-1,3);faces.extend(f.tolist());material_indices.extend([mi]*len(f))
bpy.ops.wm.open_mainfile(filepath=str(BLEND));body=bpy.data.objects['DeskCat belly profile fix 01 STATIC'];original=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];source=bpy.data.objects.new('NORMAL_BAKE_TEMP_SOURCE_RAW_NO_ARMATURE',original.data.copy());bpy.context.scene.collection.objects.link(source);source.matrix_world=original.matrix_world.copy()
mesh=bpy.data.meshes.new('NORMAL_BAKE_TEMP_TARGET_PATCH');mesh.from_pydata([convert(v) for v in p],[],faces);mesh.update();layer=mesh.uv_layers.new(name='UVMap')
for poly,mi in zip(mesh.polygons,material_indices):
 poly.material_index=mi;poly.use_smooth=True
 for li in poly.loop_indices:u=uv[mesh.loops[li].vertex_index];layer.data[li].uv=(float(u[0]),float(1-u[1]))
mesh.normals_split_custom_set([tuple(convert(n[l.vertex_index])) for l in mesh.loops]);target=bpy.data.objects.new('NORMAL_BAKE_TEMP_TARGET_PATCH',mesh);bpy.context.scene.collection.objects.link(target)
images=[]
for name in ['left','right']:
 material=bpy.data.materials.new('TEMP_NORMAL_BAKE_'+name);material.use_nodes=True;image=bpy.data.images.new('TEMP_NORMAL_BAKE_'+name,width=768,height=768,alpha=False);image.colorspace_settings.name='Non-Color';node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;material.node_tree.nodes.active=node;mesh.materials.append(material);images.append(image)
for o in bpy.context.scene.objects:o.hide_render=True
for o in bpy.context.view_layer.objects:o.select_set(False)
source.hide_render=False;source.hide_set(False);source.select_set(True);target.hide_render=False;target.hide_set(False);target.select_set(True);bpy.context.view_layer.objects.active=target
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.render.bake.use_selected_to_active=True;scene.render.bake.cage_extrusion=.04;scene.render.bake.max_ray_distance=.08;scene.render.bake.margin=12
bpy.ops.object.bake(type='NORMAL')
def append_view(data):
 binary.extend(b'\0'*(-len(binary)%4));index=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':len(data)});binary.extend(data);return index
for mi,(name,image) in enumerate(zip(['left','right'],images)):
 vals=np.array(image.pixels[:]).reshape(768,768,4)[::-1,:,:3]
 # Thin source cards can bake back-facing or missing samples into the smooth
 # skin. Discard those and keep only gentle tangent detail; no new dark dents.
 normal_vector=2*vals-1;valid=(normal_vector[:,:,2]>.25)&(np.linalg.norm(normal_vector,axis=2)<1.15);xy=normal_vector[:,:,:2];xy[~valid]=0;length=np.linalg.norm(xy,axis=2);xy*=np.minimum(1,.22/np.maximum(length,1e-9))[:,:,None];normal_vector=np.dstack((xy,np.sqrt(np.maximum(0,1-np.sum(xy**2,axis=2)))));vals=(normal_vector+1)/2
 y=.34-np.arange(768)/767*.18;alpha=np.clip((y-.245)/.060,0,1);alpha=alpha*alpha*(3-2*alpha);vals=vals*alpha[:,None,None]+np.array([.5,.5,1.])*(1-alpha[:,None,None]);path=OUT/f'belly_profile_{name}_normal.png';Image.fromarray(np.clip(vals*255,0,255).astype(np.uint8)).save(path)
 material=body.data.materials[mi+1];nodes=material.node_tree.nodes;image=bpy.data.images.load(str(path));image.colorspace_settings.name='Non-Color';image.pack();tex=nodes.new('ShaderNodeTexImage');tex.image=image;normal=nodes.new('ShaderNodeNormalMap');material.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color']);material.node_tree.links.new(normal.outputs['Normal'],nodes.get('Principled BSDF').inputs['Normal'])
 image_id=len(doc['images']);doc['images'].append({'bufferView':append_view(path.read_bytes()),'mimeType':'image/png','name':path.stem});texture_id=len(doc['textures']);doc['textures'].append({'source':image_id,'sampler':0});doc['materials'][mi+1]['normalTexture']={'index':texture_id}
bpy.data.objects.remove(source,do_unlink=True);bpy.data.objects.remove(target,do_unlink=True)
for o in bpy.context.view_layer.objects:o.select_set(False)
body.hide_render=False;body.hide_set(False);body.select_set(True);bpy.context.view_layer.objects.active=body;bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
doc['buffers'][0]['byteLength']=len(binary);encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4);bodydata=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary;GLB.write_bytes(struct.pack('<4sII',b'glTF',2,len(bodydata)+12)+bodydata)
audit=json.loads((OUT/'geometry_audit.json').read_text());audit['output_glb_sha256']=hashlib.sha256(GLB.read_bytes()).hexdigest();audit['output_blend_sha256']=hashlib.sha256(BLEND.read_bytes()).hexdigest();audit['local_normal_bake']={'engine':'Cycles CPU selected-to-active','source':'raw original, no Armature','cage_extrusion':.04,'max_ray_distance':.08,'UV_padding':12,'tangent_detail_xy_max':.22,'reject_normal_Z_below':.25,'reject_normal_length_above':1.15,'normal_detail_fade_Y_gltf':[.245,.305],'geometry_changed_by_bake':False,'source_materials_or_images_changed':False};(OUT/'geometry_audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit['local_normal_bake']))
