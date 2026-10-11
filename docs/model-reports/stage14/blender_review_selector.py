"""Selection-only Blender review panel. Open source scene; run from Text Editor.
Place review_manifest.json alongside this script. Never saves or edits topology.
"""
import bpy
import hashlib
import json
from pathlib import Path


def load_manifest():
    candidates = []
    if '__file__' in globals():
        candidates.append(Path(__file__).resolve().parent / 'review_manifest.json')
    space = getattr(bpy.context, 'space_data', None)
    text = getattr(space, 'text', None)
    if text and text.filepath:
        candidates.append(Path(bpy.path.abspath(text.filepath)).parent / 'review_manifest.json')
    candidates.append(Path(bpy.data.filepath).parent / 'review_manifest.json')
    for candidate in candidates:
        if candidate.is_file():
            return json.loads(candidate.read_text())
    raise RuntimeError('Keep review_manifest.json next to the script opened in Text Editor.')


MANIFEST = load_manifest()


def verify_object(obj):
    expected = MANIFEST['objects'][obj.name]
    faces = [list(p.vertices) for p in obj.data.polygons]
    digest = hashlib.sha256(json.dumps(faces,separators=(',', ':')).encode()).hexdigest()
    if len(obj.data.vertices) != expected['vertices'] or digest != expected['face_order_sha256']:
        raise RuntimeError('Topology/source face order changed; selection refused: ' + obj.name)


def select_region(cluster_id, object_name, scope='CORE', fan_index=None):
    """Only selection/visibility; safe headless entry point as well as UI action."""
    obj = bpy.data.objects[object_name]
    verify_object(obj)
    c = next(c for c in MANIFEST['clusters'] if c['id'] == cluster_id)
    ids = c['source_face_ids']
    if scope == 'CONTEXT':
        ids = sorted(set(ids+c['context_source_face_ids']))
    if fan_index is not None:
        choices = [group for f in c['fan_groups'] for group in f['fan_source_face_groups']]
        ids = choices[fan_index]
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for name in MANIFEST['objects']:
        other = bpy.data.objects[name]
        other.hide_set(name != object_name)
        if name == object_name:
            other.hide_viewport = False
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for v in obj.data.vertices:
        v.select=False
    for e in obj.data.edges:
        e.select=False
    for p in obj.data.polygons:
        p.select=p.index in set(ids)
    bpy.context.tool_settings.mesh_select_mode=(False,False,True)
    return list(ids)


class DESKCAT_OT_review_select(bpy.types.Operator):
    bl_idname='deskcat.review_select'
    bl_label='Select exact source faces'
    bl_description='Select only; never edits geometry, weights, or saves scene'
    def execute(self,context):
        try:
            fan=context.scene.deskcat_review_fan
            select_region(context.scene.deskcat_review_cluster,context.scene.deskcat_review_object,
                          context.scene.deskcat_review_scope,None if fan<0 else fan)
            bpy.ops.object.mode_set(mode='EDIT')
            # Frame only when a VIEW_3D context is available. Headless never needs one.
            for area in context.screen.areas:
                if area.type=='VIEW_3D':
                    region=next(r for r in area.regions if r.type=='WINDOW')
                    with context.temp_override(area=area,region=region):
                        bpy.ops.view3d.view_selected(use_all_regions=False)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'},str(error))
            return {'CANCELLED'}


class DESKCAT_PT_review(bpy.types.Panel):
    bl_label='DeskCat: topology review only'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='DeskCat'
    def draw(self,context):
        layout=self.layout
        for name in ['cluster','object','scope','fan']:
            layout.prop(context.scene,'deskcat_review_'+name)
        layout.operator('deskcat.review_select')
        c=next(c for c in MANIFEST['clusters'] if c['id']==context.scene.deskcat_review_cluster)
        groups=[g for f in c['fan_groups'] for g in f['fan_source_face_groups']]
        layout.label(text=f'Fan -1 = all; 0..{len(groups)-1} = listed fans')
        layout.label(text='Orange faces = selection. No repair.')
        layout.label(text='Save As a NEW review scene only.')


def register():
    for cls in [DESKCAT_OT_review_select,DESKCAT_PT_review]:
        previous=getattr(bpy.types,cls.__name__,None)
        if previous:
            bpy.utils.unregister_class(previous)
        bpy.utils.register_class(cls)
    bpy.types.Scene.deskcat_review_cluster=bpy.props.EnumProperty(name='Cluster',items=[(c['id'],c['id']+' / '+c['region'],c['review_kind']) for c in MANIFEST['clusters']])
    bpy.types.Scene.deskcat_review_object=bpy.props.EnumProperty(name='Surface',items=[(n,n,'Original face IDs preserved') for n in MANIFEST['objects']])
    bpy.types.Scene.deskcat_review_scope=bpy.props.EnumProperty(name='Selection',items=[('CORE','Core','Incident defect faces'),('CONTEXT','Core + one-ring','Context is not a repair mask')])
    bpy.types.Scene.deskcat_review_fan=bpy.props.IntProperty(name='Fan (-1 all)',default=-1,min=-1,max=10)


if __name__=='__main__':
    register()
