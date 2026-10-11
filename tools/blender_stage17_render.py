"""CPU Cycles before/after views of saved scene; render only, never save it."""
from pathlib import Path
import bpy,json,sys
from mathutils import Vector
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage17';bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/rigging/deskcat_belly_profile_fix_01.blend'))
def world(p):return Vector((p[0],-p[2],p[1]))
source=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];after=bpy.data.objects['DeskCat belly profile fix 01 STATIC'];before=bpy.data.objects.new('RENDER_ONLY_ORIGINAL_NO_ARMATURE',source.data.copy());bpy.context.scene.collection.objects.link(before);before.matrix_world=source.matrix_world.copy()
for obj in bpy.context.scene.objects:obj.hide_render=True
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=False;scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.view_transform='Standard';scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.18,.18,.18,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.75
for name,pos,energy,size in [('key',(-1,-2,2),70,2),('fill',(1,1,1),35,2)]:
 light=bpy.data.lights.new(name,'AREA');light.energy=energy;light.shape='DISK';light.size=size;obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj);obj.location=pos;obj.rotation_euler=(Vector((0,0,.3))-obj.location).to_track_quat('-Z','Y').to_euler();obj.hide_render=False
camera=bpy.data.cameras.new('stage17 render camera');obj=bpy.data.objects.new('stage17 render camera',camera);scene.collection.objects.link(obj);scene.camera=obj;camera.type='ORTHO';camera.lens=50
views={'profile':([0,.29,0],[0,0,1],1.35),'left':([-.015,.245,.04],[0,0,1],.35),'right':([-.015,.245,-.04],[0,0,-1],.35),'oblique':([-.015,.245,.025],[.5,-.65,1],.32)}
for name,(center,vector,width) in views.items():
 target=world(center);obj.location=target+world(vector)*3;obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler();camera.ortho_scale=width
 for phase,body in ([('after',after)] if '--after-only' in sys.argv else [('before',before),('after',after)]):
  before.hide_render=True;after.hide_render=True;body.hide_render=False;scene.render.filepath=str(OUT/f'images/blender_{phase}_{name}.png');bpy.ops.render.render(write_still=True)
(OUT/'blender_render_check.json').write_text(json.dumps({'environment':'Linux Blender '+bpy.app.version_string,'engine':'Cycles CPU','samples':32,'denoising':False,'resolution':[1200,800],'views':views,'source_skin_evaluated':False,'file_saved_or_modified':False,'note':'PBR review; this build has no OpenImageDenoise support; no Windows GUI or deformation tested'},indent=2)+'\n')
