"""Read-only selection, source preservation and archive validation. Never saves a scene."""
import bpy,json,hashlib,importlib.util,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'docs/model-reports/stage16';manifest=json.loads((out/'review_manifest.json').read_text());source=root/manifest['source_scene'];assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_scene_sha256']
bpy.ops.wm.open_mainfile(filepath=str(source))
# Only copies of selection state are changed; freeze all mesh coordinates/UV/bones/textures.
def signature():
 value={'meshes':{o.name:{'v':[v.co[:] for v in o.data.vertices],'f':[p.vertices[:] for p in o.data.polygons],'uv':[[v.uv[:] for v in l.data] for l in o.data.uv_layers],'materials':[m.name for m in o.data.materials],'weights':[[[g.group,g.weight] for g in v.groups] for v in o.data.vertices]} for o in bpy.data.objects if o.type=='MESH'},'bones':{o.name:[[b.name,b.parent.name if b.parent else '',b.head_local[:],b.tail_local[:],b.use_deform] for b in o.data.bones] for o in bpy.data.objects if o.type=='ARMATURE'},'images':{i.name:hashlib.sha256(bytes(i.packed_file.data)).hexdigest() for i in bpy.data.images if i.packed_file}}
 return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
before=signature();spec=importlib.util.spec_from_file_location('stage16_selector',out/'blender_review_selector.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.register();cases=0
for group in manifest['clusters']:
 for name in manifest['objects']:
  for scope in ['CORE','CONTEXT']:
   ids=module.select_region(group['id'],name,scope);assert sorted(ids)==[p.index for p in bpy.data.objects[name].data.polygons if p.select];cases+=1
assert before==signature();assert sum(b.use_deform for b in bpy.data.objects[manifest['rig']].data.bones)==46
checks=json.loads((out/'package_checksums.json').read_text())
with zipfile.ZipFile(out/'DeskCat_Belly_Coat_Addendum.zip') as z:
 assert not any(n.lower().endswith(('.blend','.glb','.rar','.mp4')) for n in z.namelist())
 for name,h in checks.items():assert hashlib.sha256(z.read('DeskCat_Belly_Coat_Addendum/'+name)).hexdigest()==h==hashlib.sha256((out/name).read_bytes()).hexdigest()
for x in json.loads((out/'source_links.json').read_text()):assert hashlib.sha256((root/x['path']).read_bytes()).hexdigest()==x['sha256']
assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_scene_sha256']
result={'environment':'Linux Blender '+bpy.app.version_string+' headless','selection_cases':cases,'both_mesh_face_orders_validated':True,'unchanged_mesh_uv_material_weights_bone_texture_signature':True,'source_scene_sha256_preserved':True,'source_links_hashes_valid':True,'zip_checksums_valid':True,'archive_bytes':(out/'DeskCat_Belly_Coat_Addendum.zip').stat().st_size,'new_geometry':0,'new_weight_binds':0,'new_scene_saves':0,'new_glb_exports':0,'gui_tested':False,'acceptance_of_new_cosmetic_repair':False}
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
