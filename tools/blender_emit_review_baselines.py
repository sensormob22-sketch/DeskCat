"""Read the shipped scene's exact bone weights for editable source IDs into JSON.
Does not alter or save Blender objects, weights, geometry or materials.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import bpy


def emit(scene,masks_path):
    masks=json.loads(masks_path.read_text());bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS'];rig=bpy.data.objects['V6_17_BONES_UNVERIFIED'];names=[b.name for b in rig.data.bones]
    all_rows=[];ids=set(v for zone in masks['zones'].values() for v in zone['editable_source_vertex_ids']);selected={}
    for vertex in mesh.data.vertices:
        row={n:0. for n in names}
        for group in vertex.groups:
            name=mesh.vertex_groups[group.group].name
            if name in names:row[name]=group.weight
        all_rows.extend(row.values())
        if vertex.index in ids:selected[str(vertex.index)]={n:w for n,w in row.items() if w>0}
    digest=hashlib.sha256(struct.pack('<'+'f'*len(all_rows),*all_rows)).hexdigest()
    if digest!=masks['bone_weight_sha256_float32']:raise ValueError('Unexpected bone weight change')
    masks['baseline_vertex_weights']=selected;masks['baseline_rows_basis']='Exact float32 Blender weights, including small influences dropped by GLB exporter. External JSON annotation only; shipped scene contains the same actual weights.'
    masks_path.write_text(json.dumps(masks,indent=2)+'\n');print(json.dumps({'editable_baseline_rows':len(selected),'weights_changed':0,'scene_saved':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',type=Path,required=True);p.add_argument('--masks',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);emit(a.scene,a.masks)
