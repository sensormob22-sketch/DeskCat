"""Extract real posed bone guides from the experimental Blender scene. Read-only."""
import argparse
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Vector,Quaternion
import math
import sys


def extract(scene, report, output):
    r=json.loads(report.read_text());bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    snapshots=scene.parent;poses={};hashes={}
    for name in ('rest','front_bend','hind_bend','pelvis_spine','tail_bend'):
        for pb in rig.pose.bones:pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion()
        for bone,deg in r['poses'][name]['rotations_degrees_about_blender_world_y'].items():
            pb=rig.pose.bones[bone];axis=pb.bone.matrix_local.to_3x3().inverted() @ Vector((0,1,0))
            pb.rotation_quaternion=Quaternion(axis,math.radians(deg))
        bpy.context.view_layer.update()
        def gltf(v):return [v.x,v.z,-v.y]
        poses[name]={pb.name:{'head_gltf':gltf(rig.matrix_world @ pb.head),'tail_gltf':gltf(rig.matrix_world @ pb.tail)} for pb in rig.pose.bones}
        hashes[name]=hashlib.sha256((snapshots/f'{name}.glb').read_bytes()).hexdigest()
    output.write_text(json.dumps({'status':'PROVISIONAL_GUIDES_NOT_ANATOMICAL_APPROVAL','poses':poses,'model_sha256_by_pose':hashes},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('scene','report','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);extract(a.scene,a.report,a.output)
