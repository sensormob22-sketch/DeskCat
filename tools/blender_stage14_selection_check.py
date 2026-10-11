"""Headless selection/provenance smoke check; no save, bind or mesh changes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import bpy
ROOT=Path.cwd()
OUT=ROOT/'docs/model-reports/stage14'
manifest=json.loads((OUT/'review_manifest.json').read_text())
scene=ROOT/manifest['source_scene']
assert hashlib.sha256(scene.read_bytes()).hexdigest()==manifest['source_scene_sha256']
bpy.ops.wm.open_mainfile(filepath=str(scene))

def signature():
    # Selection and hide_set deliberately excluded; geometry/UV/material/weights/bones frozen.
    meshes={o.name:{'vertices':[list(v.co) for v in o.data.vertices],
                   'faces':[list(p.vertices) for p in o.data.polygons],
                   'uv':[[list(d.uv) for d in layer.data] for layer in o.data.uv_layers],
                   'materials':[m.name for m in o.data.materials],
                   'weights':[[[g.group,g.weight] for g in v.groups] for v in o.data.vertices],
                   'matrix':[list(r) for r in o.matrix_world]} for o in bpy.data.objects if o.type=='MESH'}
    bones={o.name:[[b.name,b.parent.name if b.parent else None,list(b.head_local),list(b.tail_local),b.use_deform] for b in o.data.bones] for o in bpy.data.objects if o.type=='ARMATURE'}
    textures={i.name:hashlib.sha256(bytes(i.packed_file.data)).hexdigest() for i in bpy.data.images if i.packed_file}
    return hashlib.sha256(json.dumps({'meshes':meshes,'bones':bones,'textures':textures},sort_keys=True).encode()).hexdigest()

before=signature()
spec=importlib.util.spec_from_file_location('deskcat_review',OUT/'blender_review_selector.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.register()
cases=0
for c in manifest['clusters']:
    for name in manifest['objects']:
        for scope in ['CORE','CONTEXT']:
            ids=module.select_region(c['id'],name,scope)
            selected=[p.index for p in bpy.data.objects[name].data.polygons if p.select]
            assert selected==sorted(ids),(c['id'],name,scope)
            cases+=1
        fans=[g for f in c['fan_groups'] for g in f['fan_source_face_groups']]
        for i,group in enumerate(fans):
            assert module.select_region(c['id'],name,fan_index=i)==group
            assert [p.index for p in bpy.data.objects[name].data.polygons if p.select]==sorted(group)
            cases+=1
assert signature()==before
assert sum(b.use_deform for b in bpy.data.objects[manifest['rig']].data.bones)==46
assert hashlib.sha256(scene.read_bytes()).hexdigest()==manifest['source_scene_sha256']
result={'environment':'Linux Blender '+bpy.app.version_string+' headless','selection_cases':cases,'face_order_validated_both_objects':True,'mesh_uv_material_weights_bones_packed_texture_signature_preserved':True,'source_scene_hash_preserved':True,'source_scene_saved':False,'new_blend_files':0,'weight_binds':0,'mesh_edits':0,'gui_panel_interaction_tested':False,'panel_registered':True}
(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
