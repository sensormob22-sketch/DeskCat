"""Create isolated exact-weld proxy and audit; no rig generation or weight binding.
blender -b --factory-startup --python-exit-code 1 --python tools/blender_exact_weld_proxy_preflight.py
"""
import bpy,hashlib,json,sys
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from exact_weld_proxy import build_exact_proxy
from rig_readiness_audit import read_glb,accessor
from rig_geometry_analysis import components,edge_faces,topology
from blender_deformation_probe import inverse,convert,pair_set
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/exact-weld-proxy';WORK=ROOT/'artifacts/exact_weld_proxy'
INPUT=ROOT/'assets/rigging/deskcat_retopo_rigify_trial_02.blend';SCENE=ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend';GLB=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name,data):
 (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else list(x))+'\n')
def mesh_signature(obj):
 m=obj.data
 return {'coords':hashlib.sha256(np.array([v.co[:] for v in m.vertices],dtype='<f4').tobytes()).hexdigest(),'faces':hashlib.sha256(np.array([f.vertices[:] for f in m.polygons],dtype='<i4').tobytes()).hexdigest(),'uv':hashlib.sha256(np.array([v.uv[:] for v in m.uv_layers.active.data],dtype='<f4').tobytes()).hexdigest(),'corner_normals':hashlib.sha256(np.array([n.vector[:] for n in m.corner_normals],dtype='<f4').tobytes()).hexdigest(),'materials':[x.name for x in m.materials],'weights':[[[g.group,g.weight] for g in v.groups] for v in m.vertices]}
def rig_signature(r):
 return [{'name':b.name,'parent':b.parent.name if b.parent else None,'deform':b.use_deform,'matrix':[[float(x) for x in row] for row in b.matrix_local]} for b in r.data.bones]
def main():
 if SCENE.exists() or OUT.exists() or WORK.exists():raise ValueError('New outputs required; no overwrite')
 OUT.mkdir(parents=True);WORK.mkdir(parents=True)
 frozen={str(p.relative_to(ROOT)):sha(p) for folder in ['assets/3d','assets/rigging','docs/model-reports'] for p in (ROOT/folder).rglob('*') if p.is_file() and OUT not in p.parents}
 write('preserved_manifest.json',frozen)
 assert sha(INPUT)=='64556e8468b2ae702fcb737ca352e94fce736c4ebc2a043e0e6371ceae4b7bbe'
 bpy.ops.wm.open_mainfile(filepath=str(INPUT));m=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];rig=bpy.data.objects['CAT_RIGIFY_TRIAL_02'];old_mesh=mesh_signature(m);old_rig=rig_signature(rig);assert sum(b.use_deform for b in rig.data.bones)==46
 d,buf,_=read_glb(GLB);pr=d['meshes'][0]['primitives'][0];source=np.array(accessor(d,buf,pr['attributes']['POSITION']));source_faces=np.array(accessor(d,buf,pr['indices'])).reshape(-1,3)
 existing=np.array([inverse(m.matrix_world@v.co) for v in m.data.vertices]);assert np.array_equal(existing,source)
 assert np.array_equal(np.array([f.vertices[:] for f in m.data.polygons]),source_faces)
 points,faces,forward,reverse=build_exact_proxy(source.tolist(),source_faces.tolist());points=np.array(points);faces=np.array(faces)
 assert np.array_equal(points[forward],source);assert np.array_equal(faces,np.array(forward)[source_faces]);assert sorted(i for ids in reverse for i in ids)==list(range(19464))
 data=bpy.data.meshes.new('EXACT_WELD_SOLVER_ONLY');data.from_pydata([convert(p) for p in points],[],faces.tolist());data.update()
 proxy=bpy.data.objects.new('EXACT_WELD_PROXY_NO_WEIGHTS',data);bpy.context.scene.collection.objects.link(proxy)
 assert len(data.vertices)==len(points) and len(data.polygons)==len(faces);assert np.array_equal(np.array([f.vertices[:] for f in data.polygons]),faces)
 uv=data.uv_layers.new(name=m.data.uv_layers.active.name);uv.data.foreach_set('uv',np.array([x.uv[:] for x in m.data.uv_layers.active.data],dtype=np.float32).flatten())
 for material in m.data.materials:data.materials.append(material)
 data.normals_split_custom_set([n.vector[:] for n in m.data.corner_normals]);data.update()
 proxy.hide_render=True;proxy.hide_set(True);proxy['purpose']='Solver preflight only; not bound; exact welding only'
 map_record={'source_sha256':sha(GLB),'source_vertices':len(source),'proxy_vertices':len(points),'tolerance':0,'order':'First source occurrence, deterministic','source_to_proxy':forward,'proxy_to_sources':reverse,'proxy_faces_in_source_face_order':faces.tolist(),'all_source_vertices_covered':True,'position_reconstruction_max_error':0,'new_faces_added':0,'source_faces_removed':0,'no_proximity_weld':True};write('vertex_map.json',map_record)
 np.savez_compressed(WORK/'proxy_arrays.npz',positions=points,faces=faces,source=source)
 regions=json.loads((ROOT/'docs/model-reports/stage6/anatomical_landmarks.json').read_text())['regions']
 # Region spheres are annotation hints only: old source IDs never reused.
 regions.update({'tail_base':{'center':[.315,.3,0],'radius':.07},'face':{'center':[-.38,.48,0],'radius':.1},'belly':{'center':[-.02,.20,0],'radius':.15}})
 def labels(pt):return [n for n,r in regions.items() if np.linalg.norm(np.array(pt)-r['center'])<=r['radius']]
 edges=edge_faces([tuple(f) for f in faces]);groups=components(range(len(points)),edges);group_index={v:i for i,g in enumerate(groups) for v in g}
 t=points[faces];areas=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)/2
 component_reports=[]
 for i,g in enumerate(groups):
  ids=[fi for fi,f in enumerate(faces) if group_index[int(f[0])]==i];p=points[g];centroid=p.mean(0)
  component_reports.append({'component':i,'vertices':len(g),'faces':len(ids),'proxy_vertex_ids':g,'source_vertex_ids':sorted(v for c in g for v in reverse[c]),'source_face_ids':ids,'bounds':[p.min(0).tolist(),p.max(0).tolist()],'centroid':centroid.tolist(),'regions':labels(centroid),'boundary_edges':sum(len(fs)==1 and a in g for (a,b),fs in edges.items()),'nonmanifold_edges':sum(len(fs)>2 and a in g for (a,b),fs in edges.items()),'area':float(areas[ids].sum())})
 def edge_records(predicate):
  result=[]
  for e,fs in edges.items():
   if not predicate(fs):continue
   mid=points[list(e)].mean(0)
   result.append({'proxy_edge':e,'endpoints':points[list(e)].tolist(),'source_vertex_aliases':[reverse[e[0]],reverse[e[1]]],'source_faces':fs,'component':group_index[e[0]],'regions':labels(mid),'midpoint':mid.tolist()})
  return result
 boundaries=edge_records(lambda f:len(f)==1);nonmanifold=edge_records(lambda f:len(f)>2)
 # Incidence edges =2 but inconsistent winding; not silently treated as closed shell.
 winding=defaultdict(list)
 for f in faces:
  for a,b in zip(f,np.roll(f,-1)):winding[tuple(sorted((int(a),int(b))))].append(1 if a<b else -1)
 inconsistent=edge_records(lambda fs:False)
 for e,signs in winding.items():
  if len(signs)==2 and sum(signs)!=0:inconsistent.append({'proxy_edge':e,'endpoints':points[list(e)].tolist(),'source_faces':edges[e],'regions':labels(points[list(e)].mean(0))})
 degenerate=np.where(areas==0)[0].tolist();tiny=np.where((areas>0)&(areas<1e-8))[0].tolist()
 tiny_records=[{'source_face_id':i,'area':float(areas[i]),'points':t[i].tolist(),'regions':labels(t[i].mean(0))} for i in tiny]
 crossings=sorted(pair_set(points,faces.tolist()))
 duplicate_groups=defaultdict(list)
 for i,f in enumerate(faces):duplicate_groups[tuple(sorted(int(v) for v in f))].append(i)
 duplicate_face_groups=[v for v in duplicate_groups.values() if len(v)>1]
 topo=topology(points.tolist(),[tuple(f) for f in faces],regions)
 contact=json.loads((ROOT/'docs/model-reports/rigify-corrected/preflight.json').read_text())['anatomy'];paws={k:sorted({forward[v] for v in x['paw_vertices']}) for k,x in contact.items()};paw_collisions={a+'_'+b:sorted(set(paws[a])&set(paws[b])) for a in paws for b in paws if a<b}
 # Safe solver gate is conservatively fail-closed: unresolved nonmanifold body,
 # duplicate faces/fans/crossings are not repaired under exact welding permission.
 reasons=[]
 if nonmanifold:reasons.append('Unresolved >2-face edges remain; local surface identity is ambiguous')
 if topo['disconnected_vertex_fans']:reasons.append('Disconnected fans share vertices; exact welding is not a clean manifold solver shell')
 if duplicate_face_groups:reasons.append('Coincident duplicate faces remain; no face deletion was authorized')
 if degenerate:reasons.append('Zero-area faces remain')
 if any(paw_collisions.values()):reasons.append('Exact aliases unexpectedly bridge distinct observed paw patches')
 report={'source_scene_sha256':sha(INPUT),'source_glb_sha256':sha(GLB),'exact_weld_tolerance':0,'proxy_vertices':len(points),'triangles':len(faces),'components':component_reports,'topology':topo,'boundary_records':boundaries,'nonmanifold_records':nonmanifold,'inconsistent_winding_records':inconsistent,'degenerate_source_face_ids':degenerate,'tiny_face_threshold':1e-8,'tiny_source_faces':tiny_records,'minimum_area':float(areas.min()),'duplicate_source_face_groups':duplicate_face_groups,'baseline_crossing_pairs':crossings,'baseline_crossing_pair_count':len(crossings),'baseline_crossings_are_not_alone_a_rejection':True,'paw_patch_proxy_ids':paws,'cross_paw_aliases':paw_collisions,'no_added_geometry_edges':True,'gate':{'pass':not reasons,'reasons':reasons,'automatic_weight_attempts':0,'new_rig_generations':0,'bends_run':0,'skinned_glb_exported':False},'limitations':'Uncalibrated GLB scene units. Region spheres are provisional anatomy annotations, not new bone placement. Strict crossing test excludes shared vertices and does not certify coplanar overlaps. Tiny threshold is display/triage only. Open components alone are not proof heat cannot work; unresolved nonmanifold contacts prevent approving this bounded trial.'}
 write('preflight.json',report)
 assert old_mesh==mesh_signature(m) and old_rig==rig_signature(rig)
 assert np.array_equal(np.array([x.uv[:] for x in data.uv_layers.active.data]),np.array([x.uv[:] for x in m.data.uv_layers.active.data]))
 packed={i.name:hashlib.sha256(i.packed_file.data).hexdigest() for i in bpy.data.images if i.packed_file}
 bpy.ops.wm.save_as_mainfile(filepath=str(SCENE),compress=True)
 assert all(sha(ROOT/p)==h for p,h in frozen.items())
 write('preservation.json',{'render_mesh_signature':old_mesh,'render_unchanged':True,'existing_rig_bones_unchanged':True,'rig_signature':old_rig,'deform_bones':46,'proxy_loop_uv_identical':True,'no_coordinate_displacement':True,'packed_image_sha256':packed,'scene_sha256':sha(SCENE)})
 print(json.dumps({'vertices':len(points),'components':len(groups),'boundary':len(boundaries),'nonmanifold':len(nonmanifold),'duplicates':len(duplicate_face_groups),'fan_defects':topo['disconnected_vertex_fans'],'crossings':len(crossings),'gate_pass':not reasons,'attempts':0}))
if __name__=='__main__':main()
