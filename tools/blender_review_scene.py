"""Prepare editable review scene with paw masks and provisional EMPTY markers.

No armature, constraints, skin weights, mesh changes or GLB export.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from rig_readiness_audit import read_glb,accessor
import hashlib


def prepare(model, review, landmarks, output, report):
    if output.exists():raise ValueError('Refusing to overwrite a review scene')
    geometry=json.loads(review.read_text());annotations=json.loads(landmarks.read_text())
    doc,binary,raw=read_glb(model);sha=hashlib.sha256(raw).hexdigest()
    if sha!=geometry['sha256'] or sha not in annotations['accepted_geometry_sha256']:
        raise ValueError('Source/review mismatch')
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(model.resolve()),merge_vertices=False)
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if len(meshes)!=1:raise ValueError('Expected one imported mesh')
    obj=meshes[0];mesh=obj.data
    prim=doc['meshes'][0]['primitives'][0]
    positions=accessor(doc,binary,prim['attributes']['POSITION'])
    if len(positions)!=len(mesh.vertices):raise ValueError('Blender changed vertex count')
    maximum=0.
    for v,p in zip(mesh.vertices,positions):
        q=obj.matrix_world@v.co
        maximum=max(maximum,(Vector((q.x,q.z,-q.y))-Vector(p)).length)
    if maximum>1e-7:raise ValueError('Blender source vertex ordering/coordinates changed; cannot assign raw IDs')
    attr=mesh.attributes.new('deskcat_source_vertex_id','INT','POINT')
    attr.data.foreach_set('value',list(range(len(positions))))
    counts={}
    for name,foot in geometry['paw_surface_segmentation']['feet'].items():
        for suffix,key in [('low_surface','source_vertex_ids'),('support_band','support_candidate_source_vertex_ids')]:
            group=obj.vertex_groups.new(name='REVIEW_'+name+'_'+suffix)
            group.add(foot[key],1,'REPLACE');counts[group.name]=len(foot[key])
    for name,region in annotations['regions'].items():
        marker=bpy.data.objects.new('PROVISIONAL_'+name,None)
        bpy.context.collection.objects.link(marker)
        x,y,z=region['center'];marker.location=(x,-z,y)
        marker.empty_display_type='SPHERE';marker.empty_display_size=.008
        marker.show_in_front=True;marker['not_a_bone']=True
    obj['model_sha256']=sha;obj['review_status']='REPAIR THEN RETEST; not rigged'
    obj['mask_groups_not_skin_weights']=True
    if any(o.type=='ARMATURE' for o in bpy.context.scene.objects):raise ValueError('Review scene must not create armature')
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output.resolve()),compress=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'source_sha256':sha,'blender':bpy.app.version_string,
                                 'source_vertex_order_max_error':maximum,'mask_groups':counts,
                                 'provisional_empty_markers':len(annotations['regions']),
                                 'armatures':0,'geometry_changes':0,'glb_exports':0,
                                 'scene_output':str(output)},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('model',type=Path)
    for flag in ('review','landmarks','output','report'):p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);prepare(a.model,a.review,a.landmarks,a.output,a.report)
