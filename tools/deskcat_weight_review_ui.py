"""Portable Blender sidebar. Embed in .blend Text; Run Script explicitly to register.
Only selection and diagnostic pose operators: never generates/applies new weights.
"""
import bpy
import json
import math
from mathutils import Vector,Quaternion

class DESKCAT_OT_select_review_zone(bpy.types.Operator):
    bl_idname='deskcat.select_review_zone';bl_label='Select editable review mask'
    def execute(self,context):
        mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS']
        if context.object and context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);context.view_layer.objects.active=mesh
        group=mesh.vertex_groups['EDIT_'+context.scene.deskcat_zone]
        ids={v.index for v in mesh.data.vertices if any(g.group==group.index and g.weight>0 for g in v.groups)}
        for vertex in mesh.data.vertices:vertex.select=vertex.index in ids
        masks=json.loads(bpy.data.texts['REGION_MASKS.json'].as_string());bone=masks['zones'][context.scene.deskcat_zone]['primary_bone']
        mesh.vertex_groups.active_index=mesh.vertex_groups[bone].index;mesh.data.use_paint_mask_vertex=True
        return {'FINISHED'}

class DESKCAT_OT_review_pose(bpy.types.Operator):
    bl_idname='deskcat.review_pose';bl_label='Show selected diagnostic pose'
    def execute(self,context):
        data=json.loads(bpy.data.texts['POSE_REVIEW.json'].as_string());zone=data['zones'][context.scene.deskcat_zone]
        rotations=data['poses'][zone['poses'][context.scene.deskcat_pose]]
        rig=bpy.data.objects['V6_17_BONES_UNVERIFIED']
        for bone in rig.pose.bones:bone.rotation_mode='QUATERNION';bone.rotation_quaternion=Quaternion()
        for name,degrees in rotations.items():
            bone=rig.pose.bones[name];axis=bone.bone.matrix_local.to_3x3().inverted()@Vector((0,1,0));bone.rotation_quaternion=Quaternion(axis,math.radians(degrees))
        context.view_layer.update();return {'FINISHED'}

class DESKCAT_PT_weight_review(bpy.types.Panel):
    bl_label='DeskCat v6 — review only';bl_idname='DESKCAT_PT_weight_review'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='DeskCat'
    def draw(self,context):
        layout=self.layout;layout.label(text='Unchanged v6; not production')
        layout.prop(context.scene,'deskcat_zone');layout.operator('deskcat.select_review_zone')
        layout.prop(context.scene,'deskcat_pose');layout.operator('deskcat.review_pose')
        layout.label(text='Geometry/UV/face/soles protected by masks + audit')
        layout.label(text='No automatic weights or GLB export')

CLASSES=(DESKCAT_OT_select_review_zone,DESKCAT_OT_review_pose,DESKCAT_PT_weight_review)

def register():
    masks=json.loads(bpy.data.texts['REGION_MASKS.json'].as_string())
    bpy.types.Scene.deskcat_zone=bpy.props.EnumProperty(name='Region',items=[(n,n.replace('_',' '),'') for n in masks['zones']])
    bpy.types.Scene.deskcat_pose=bpy.props.EnumProperty(name='Pose',items=[(n,n,'') for n in ('rest','plus10','plus15','minus10','minus15','hold_positive','hold_negative')])
    for cls in CLASSES:
        if hasattr(bpy.types,cls.__name__):bpy.utils.unregister_class(getattr(bpy.types,cls.__name__))
        bpy.utils.register_class(cls)

if __name__=='__main__':register()
