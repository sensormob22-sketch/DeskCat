"""Read-only source/copy, UV, local topology and gap-ray checks in Blender."""
import sys,json,hashlib
from pathlib import Path
import bpy,numpy as np
from collections import Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor
from blender_deformation_probe import pair_set
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage17';audit=json.loads((OUT/'geometry_audit.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
source=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb';candidate=ROOT/'assets/3d/retopo/deskcat_belly_profile_fix_01.glb';scene=ROOT/'assets/rigging/deskcat_belly_profile_fix_01.blend'
assert sha(source)==audit['source_sha256'];assert sha(candidate)==audit['output_glb_sha256'];assert sha(scene)==audit['output_blend_sha256']
def arrays(path):
 d,b,_=read_glb(path);p=d['meshes'][0]['primitives'][0];a=p['attributes'];return d,b,np.array(accessor(d,b,a['POSITION'])),np.array(accessor(d,b,a['TEXCOORD_0'])),np.array(accessor(d,b,p['indices']),int).reshape(-1,3)
sd,sb,sp,suv,sf=arrays(source);d,b,p,uv,f=arrays(candidate);assert np.array_equal(p[:len(sp)],sp);assert np.array_equal(uv[:len(sp)],suv)
for row in json.loads((OUT/'cut_vertex_provenance.json').read_text()):
 vi=row['vertex_id'];face=sf[row['source_face_id']];weights=np.array(row['barycentric']);assert abs(weights.sum()-1)<1e-9
 assert np.max(np.abs(p[vi]-weights@sp[face]))<1e-7;assert np.max(np.abs(uv[vi]-weights@suv[face]))<1e-7
def images(doc,binary):
 result=[]
 for image in doc['images']:
  v=doc['bufferViews'][image['bufferView']];result.append(binary[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])
 return result
assert images(sd,sb)==images(d,b)[:3];assert sd['materials'][0]==d['materials'][0]
owner=audit['retained_output_face_source_ids'];clipped=set(audit['clipped_source_face_ids']);removed=set(audit['removed_source_face_ids']);unchanged=[]
for i,source_id in enumerate(owner):
 if source_id not in clipped:assert np.array_equal(f[i],sf[source_id]);unchanged.append(source_id)
assert len(set(unchanged))==len(sf)-len(removed)-len(clipped)
allp=[p];allf=[f];offset=len(p)
for pr in d['meshes'][0]['primitives'][1:]:
 pts=np.array(accessor(d,b,pr['attributes']['POSITION']));faces=np.array(accessor(d,b,pr['indices']),int).reshape(-1,3);allp.append(pts);allf.append(faces+offset);offset+=len(pts)
points=np.vstack(allp);faces=np.vstack(allf);oldtree=BVHTree.FromPolygons([Vector(v) for v in sp],sf.tolist(),all_triangles=True);tree=BVHTree.FromPolygons([Vector(v) for v in points],faces.tolist(),all_triangles=True)
_,first,inv=np.unique(points,axis=0,return_index=True,return_inverse=True);actual_pairs=pair_set(points[first],inv[faces].tolist())
new_actual=[pair for pair in actual_pairs if pair[1]>=len(f)];assert not new_actual
original_source_pairs=sorted(set(tuple(sorted((owner[a],owner[z]))) for a,z in actual_pairs if z<len(f)))
_,oldfirst,oldinv=np.unique(sp,axis=0,return_index=True,return_inverse=True);baseline_pairs=pair_set(sp[oldfirst],oldinv[sf].tolist());assert len(baseline_pairs)==81
assert set(original_source_pairs)<=baseline_pairs
def topology(triangles):
 edges=Counter(tuple(sorted((int(a),int(z)))) for face in triangles for a,z in zip(face,np.roll(face,-1)))
 return {'boundary_edges':sum(v==1 for v in edges.values()),'nonmanifold_edges':sum(v>2 for v in edges.values())}
top_before=topology(oldinv[sf]);top_after=topology(inv[faces]);assert top_after['boundary_edges']<=top_before['boundary_edges'];assert top_after['nonmanifold_edges']<=top_before['nonmanifold_edges']
actual_edges=Counter(tuple(sorted((int(a),int(z)))) for face in inv[faces] for a,z in zip(face,np.roll(face,-1)))
patch_edges={tuple(sorted((int(a),int(z)))) for face in inv[faces][len(f):] for a,z in zip(face,np.roll(face,-1))};assert all(actual_edges[e]==2 for e in patch_edges)
assert np.array_equal(points[faces].reshape(-1,3).min(0),sp[sf].reshape(-1,3).min(0));assert np.array_equal(points[faces].reshape(-1,3).max(0),sp[sf].reshape(-1,3).max(0))
rays=json.loads((ROOT/'docs/model-reports/stage15/rays_oblique.json').read_text());r=next(r for r in rays if r['pixel']==[420,240]);o=Vector(r['origin']);direction=Vector(r['direction']).normalized();oldhit=oldtree.ray_cast(o,direction);hit=tree.ray_cast(o,direction);assert oldhit[2]==5552;assert hit[2]>=len(f)
samples=[]
for sign,name in [(1,'left'),(-1,'right')]:
 old_through=0;new_through=0;miss=0;patch_hits=0
 for x in np.linspace(-.09,.03,31):
  for y in np.linspace(.216,.29,24):
   origin=Vector((float(x),float(y),float(sign)));direction=Vector((0,0,-sign));a=oldtree.ray_cast(origin,direction);h=tree.ray_cast(origin,direction)
   if a[0] is not None and a[0][2]*sign<=0:old_through+=1
   if h[0] is None:miss+=1
   elif h[0][2]*sign<=0:new_through+=1
   elif h[2]>=len(f):patch_hits+=1
 samples.append({'side':name,'rays':31*24,'old_opposite_side_first_hits':old_through,'new_opposite_side_first_hits':new_through,'new_misses':miss,'new_surface_first_hits':patch_hits})
 assert new_through==0 and miss==0 and patch_hits==31*24
def original_signature():
 obj=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];rig=bpy.data.objects['CAT_RIGIFY_TRIAL_02']
 data={'positions':[list(v.co) for v in obj.data.vertices],'faces':[list(p.vertices) for p in obj.data.polygons],'uv':[list(l.uv) for l in obj.data.uv_layers.active.data],'groups':[(g.name,g.index) for g in obj.vertex_groups],'weights':[[(g.group,g.weight) for g in v.groups] for v in obj.data.vertices],'bones':[(x.name,x.parent.name if x.parent else None,x.use_deform,[list(row) for row in x.matrix_local]) for x in rig.data.bones],'images':[(i.name,hashlib.sha256(i.packed_file.data).hexdigest()) for i in bpy.data.images if i.packed_file and not i.name.startswith('belly_profile_')]}
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend'));signature=original_signature()
bpy.ops.wm.open_mainfile(filepath=str(scene));assert original_signature()==signature
obj=bpy.data.objects['DeskCat belly profile fix 01 STATIC'];assert len(obj.modifiers)==0;assert len(obj.data.polygons)==len(faces);assert len(obj.data.materials)==3;assert sum(x.use_deform for x in bpy.data.objects['CAT_RIGIFY_TRIAL_02'].data.bones)==46
patch_pr=d['meshes'][0]['primitives'][1];patch_points=np.array(accessor(d,b,patch_pr['attributes']['POSITION']));patch_uv=np.array(accessor(d,b,patch_pr['attributes']['TEXCOORD_0']));geometry=np.vstack([p,patch_points]);expected=geometry[audit['blender_used_glb_geometry_vertex_ids']]
position_error=np.abs(np.array([(v.co.x,v.co.z,-v.co.y) for v in obj.data.vertices])-expected).max();assert position_error<1e-7
patch_map=json.loads((OUT/'patch_export_map.json').read_text());patch_faces=np.zeros((audit['new_patch_triangles'],3),int)
for k,pr in enumerate(d['meshes'][0]['primitives'][1:],1):patch_faces[patch_map[f'glb_primitive_{k}_patch_triangle_ids']]=np.array(accessor(d,b,pr['indices']),int).reshape(-1,3)
expected_uv=np.vstack([uv[f].reshape(-1,2),patch_uv[patch_faces].reshape(-1,2)]);expected_uv[:,1]=1-expected_uv[:,1];uv_error=np.abs(np.array([l.uv[:] for l in obj.data.uv_layers.active.data])-expected_uv).max();assert uv_error<1e-7
retained_ids=set(v for poly in obj.data.polygons[:len(f)] for v in poly.vertices);patch_ids=set(v for poly in obj.data.polygons[len(f):] for v in poly.vertices);shared=retained_ids&patch_ids;assert len(shared)==audit['rim_vertices'];assert retained_ids|patch_ids==set(range(len(obj.data.vertices)))
assert not audit['new_strict_crossings'];assert set(audit['patch_edge_incidence_counts'])=={'2'}
curvature={}
for sign,name in [(1,'left'),(-1,'right')]:
 q=patch_points[patch_points[:,2]*sign>=0];q=q-q.mean(0);_,_,vh=np.linalg.svd(q,full_matrices=False);dist=q@vh[-1];curvature[name]={'plane_rms':float(np.sqrt(np.mean(dist**2))),'plane_max_error':float(np.max(abs(dist)))};assert curvature[name]['plane_max_error']>.005
preserved={}
for folder in ['assets/3d','assets/rigging']:
 for path in sorted((ROOT/folder).rglob('*')):
  if path.is_file() and 'belly_profile_fix_01' not in path.name:preserved[str(path.relative_to(ROOT))]=sha(path)
result={'environment':'Linux Blender '+bpy.app.version_string+' headless','original_positions_unchanged':len(sp),'original_uv_rows_unchanged':len(sp),'cut_vertices_barycentric_position_uv_verified':len(p)-len(sp),'whole_original_faces_unchanged':len(set(unchanged)),'original_images_byte_identical':3,'source_material_json_identical':True,'source_scene_mesh_uv_weights_bones_packed_images_signature_unchanged':True,'rig_def_bones_preserved':46,'editable_blend_vertices':len(obj.data.vertices),'editable_blend_orphan_vertices':0,'editable_blend_boundary_shared_vertices':len(shared),'output_blend_loop_uv_error_vs_glb_max':float(uv_error),'output_blend_position_error_vs_glb_max':float(position_error),'known_D14_ray':{'source_face':oldhit[2],'new_global_triangle':hit[2],'new_hit_position_gltf':list(hit[0]),'new_hit_is_replacement_surface':True},'two_sided_ray_grid':samples,'rendered_global_bounds_unchanged':True,'patch_edges_all_incidence_two_including_join':True,'patch_curvature_plane_fit_gltf_units':curvature,'source_triangle_crossings':len(baseline_pairs),'topology_before':top_before,'topology_after':top_after,'actual_export_triangle_crossings':len(actual_pairs),'remaining_source_crossing_pairs_unique':original_source_pairs,'new_crossings':len(new_actual),'new_patch_internal_edge_incidence':audit['patch_edge_incidence_counts'],'preserved_asset_sha256':preserved,'animation_or_bone_heat_tested':False,'Windows_GUI_tested':False}
(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['whole_original_faces_unchanged','new_crossings','known_D14_ray','two_sided_ray_grid']}))
