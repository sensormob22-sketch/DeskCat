"""ONE local backing design, created only in memory; no scene/GLB saved here."""
import sys,json,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_deformation_probe import pair_set,convert
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage15'
if (OUT/'patch_trial.json').exists():raise RuntimeError('One patch trial already exists; no second attempt permitted')
SOURCE=ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend'
sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest();assert sha=='844c4316dd841d4f943f80da7810d32abde64290c5f29b84e7ce4bfb3242667a'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
original=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE']
# Raw mesh data copy only: no evaluated Armature modifier or original 21-bone skin.
body=bpy.data.objects.new('STAGE15_RAW_STATIC_BODY_COPY',original.data.copy());body.matrix_world=original.matrix_world.copy();bpy.context.scene.collection.objects.link(body)
body.vertex_groups.clear()
assert len(body.modifiers)==0 and len(body.vertex_groups)==0
a=np.load(ROOT/'artifacts/stage15/source.npz');p=a['points'];faces=a['faces'];uv=a['uv']
# Choose ONE representative narrow slit ray through pixels 420/240 in oblique view.
# Backing is behind nearby white fur, not a guessed anatomical hole cap.
rays=json.loads((OUT/'rays_oblique.json').read_text());o0=np.array(rays[0]['origin']);d=np.array(rays[0]['direction']);d/=np.linalg.norm(d)
ox=(np.array(rays[6]['origin'])-o0)/30;oy=(np.array(rays[1]['origin'])-o0-ox*10)/40
outline=[[414,202],[436,204],[436,251],[433,280],[424,322],[410,314],[414,268]]
n=np.array([0.,-1.2,1.]);k=-.202
patch=[]
for x,y in outline:
 o=o0+(x-410)*ox+(y-200)*oy;t=(k-o@n)/(d@n);patch.append(o+t*d)
center=np.mean(patch,axis=0)-n/np.linalg.norm(n)*.0003
patch=np.array(patch+[center]);patch_faces=[]
for i in range(len(outline)):
 tri=[len(outline),i,(i+1)%len(outline)]
 if np.cross(patch[tri[1]]-patch[tri[0]],patch[tri[2]]-patch[tri[0]])@n<0:tri[1],tri[2]=tri[2],tri[1]
 patch_faces.append(tri)
# Reuse the UV neighborhood of existing white belly source face 12149.
# A tiny continuous UV rectangle retains its subtle beige/white variation.
patch_uv=[]
for v in patch:
 x=(v[0]-patch[:,0].min())/np.ptp(patch[:,0]);y=(v[1]-patch[:,1].min())/np.ptp(patch[:,1]);patch_uv.append([.798+x*.004,.6315+y*.0085])
mesh=bpy.data.meshes.new('STAGE15_ONE_SLIT_BACKING_EXPERIMENT');mesh.from_pydata([convert(v) for v in patch],[],patch_faces);mesh.update();layer=mesh.uv_layers.new(name='UVMap')
for poly in mesh.polygons:
 for li in poly.loop_indices:layer.data[li].uv=(patch_uv[mesh.loops[li].vertex_index][0],1-patch_uv[mesh.loops[li].vertex_index][1])
mesh.materials.append(original.data.materials[0]);obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.scene.collection.objects.link(obj)
# Strict crossings are separate from mere shared/near edge contacts.
combined=np.vstack([p,patch]);allfaces=[tuple(f) for f in faces]+[tuple(v+len(p) for v in f) for f in patch_faces]
pairs=pair_set(combined,allfaces);new=sorted(pair for pair in pairs if pair[1]>=len(faces))
result={'source_scene_sha256':sha,'trial':'ONE local backing, not a topology/solver repair','target_pixel_oblique':[420,240],'outline_pixels':outline,'points_gltf':patch.tolist(),'uv_gltf':patch_uv,'faces':patch_faces,'original_faces_untouched':16460,'new_vertices':len(patch),'new_faces':len(patch_faces),'new_diagnostic_face_ids':list(range(len(faces),len(allfaces))),'source_texture_neighborhood_reference_face':12149,'new_strict_crossing_pairs':new,'baseline_strict_crossing_pairs_original_source_ids':sorted(pair for pair in pairs if pair[1]<len(faces)), 'rejected':True, 'rejection_reasons':['10 new strict crossing pairs with existing fur','Visible flat strip and only partial slit coverage in oblique/underside views'], 'original_group_names_preserved':[g.name for g in original.vertex_groups], 'rig_def_bones_preserved':sum(b.use_deform for b in bpy.data.objects['CAT_RIGIFY_TRIAL_02'].data.bones),'normals_orientation':'Outward toward ventral +Z/-Y; triangle winding checked','scene_saved':False,'exported_glb':False,'existing_skin_used':False}
(OUT/'patch_trial.json').write_text(json.dumps(result,indent=2)+'\n')
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==sha
print(json.dumps({'new_vertices':len(patch),'new_faces':len(patch_faces),'new_strict_crossing_pairs':new,'baseline_strict_crossing_pairs_original_source_ids':sorted(pair for pair in pairs if pair[1]<len(faces)), 'rejected':True, 'rejection_reasons':['10 new strict crossing pairs with existing fur','Visible flat strip and only partial slit coverage in oblique/underside views'], 'original_group_names_preserved':[g.name for g in original.vertex_groups], 'rig_def_bones_preserved':sum(b.use_deform for b in bpy.data.objects['CAT_RIGIFY_TRIAL_02'].data.bones)}))
