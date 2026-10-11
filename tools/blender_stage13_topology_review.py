"""Read-only classification evidence for solver topology. Never edits/saves mesh.
blender -b --factory-startup --python-exit-code 1 --python tools/blender_stage13_topology_review.py
"""
import bpy,hashlib,json,sys,math
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from topology_defect_clusters import connected_groups,cluster_defect_events
from rig_geometry_analysis import components,edge_faces
from blender_deformation_probe import inverse
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage13';WORK=ROOT/'artifacts/stage13'
SCENE=ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend';PRIOR=ROOT/'docs/model-reports/exact-weld-proxy'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else list(x))+'\n')
def region(p):
 x,y,z=p
 if x<-.4 and y>.4:return 'muzzle'
 if x>.32 and y<.34:return 'tail'
 if x>.07 and y<.36:return 'pelvis_hind_limb'
 if y<.30:return 'belly_ventral_coat'
 return 'back_upper_body'
def main():
 if OUT.exists() or WORK.exists():raise ValueError('Fresh report outputs required')
 OUT.mkdir(parents=True);WORK.mkdir(parents=True)
 frozen={str(p.relative_to(ROOT)):sha(p) for folder in ['assets/3d','assets/rigging','docs/model-reports'] for p in (ROOT/folder).rglob('*') if p.is_file() and OUT not in p.parents}
 write(OUT/'preserved_manifest.json',frozen)
 assert sha(SCENE)=='844c4316dd841d4f943f80da7810d32abde64290c5f29b84e7ce4bfb3242667a'
 bpy.ops.wm.open_mainfile(filepath=str(SCENE));proxy=bpy.data.objects['EXACT_WELD_PROXY_NO_WEIGHTS'];rig=bpy.data.objects['CAT_RIGIFY_TRIAL_02'];assert sum(b.use_deform for b in rig.data.bones)==46
 points=np.array([inverse(proxy.matrix_world@v.co) for v in proxy.data.vertices]);faces=np.array([f.vertices[:] for f in proxy.data.polygons])
 prior=json.loads((PRIOR/'preflight.json').read_text());mapping=json.loads((PRIOR/'vertex_map.json').read_text());assert np.array_equal(faces,mapping['proxy_faces_in_source_face_order'])
 edges=edge_faces([tuple(x) for x in faces]);vf=defaultdict(list)
 for i,f in enumerate(faces):
  for v in f:vf[int(v)].append(i)
 c0=set(prior['components'][0]['source_face_ids']);events=[]
 for kind,key in [('boundary','boundary_records'),('nonmanifold','nonmanifold_records')]:
  for index,e in enumerate(prior[key]):
   if e['component']!=0:continue
   events.append({'kind':kind,'prior_record_index':index,'proxy_vertices':e['proxy_edge'],'source_faces':e['source_faces'],'midpoint':e['midpoint']})
 fan_info=[]
 for v in prior['topology']['disconnected_vertex_fan_ids']:
  incident=vf[v];link_edges=[tuple(int(a) for a in faces[i] if a!=v) for i in incident];neighbors={a for e in link_edges for a in e};fans=components(neighbors,link_edges)
  fan_faces=[[i for i in incident if any(a in faces[i] for a in fan)] for fan in fans]
  info={'kind':'fan','proxy_vertex':v,'source_vertex_aliases':mapping['proxy_to_sources'][v],'proxy_vertices':[v],'source_faces':incident,'midpoint':points[v].tolist(),'fan_source_face_groups':fan_faces}
  fan_info.append(info);events.append(info)
 assert Counter(e['kind'] for e in events)=={'boundary':87,'nonmanifold':42,'fan':8}
 tri=points[faces];cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);areas=np.linalg.norm(cross,axis=1)/2;normals=np.divide(cross,np.linalg.norm(cross,axis=1)[:,None],out=np.zeros_like(cross),where=np.linalg.norm(cross,axis=1)[:,None]>0)
 # Virtual face adjacency partition: ignore junctions only in the diagnostic graph.
 # No face/edge/vertex is removed from Blender or from source arrays.
 face_links=[tuple(fs) for fs in edges.values() if len(fs)==2 and fs[0] in c0 and fs[1] in c0]
 partitions=[ids for ids in connected_groups(len(faces),face_links) if ids[0] in c0]
 partitions=sorted(partitions,key=lambda ids:(-len(ids),min(ids)));part_index={fi:i for i,ids in enumerate(partitions) for fi in ids}
 part_reports=[]
 for i,ids in enumerate(partitions):
  verts=sorted({int(v) for fi in ids for v in faces[fi]});p=points[verts];mean=p.mean(0);singular=np.linalg.svd(p-mean,compute_uv=False)
  e=edge_faces([tuple(faces[fi]) for fi in ids]);boundary=sum(len(f)==1 for f in e.values());nonman=sum(len(f)>2 for f in e.values());lengths=p.max(0)-p.min(0)
  part_reports.append({'partition':i,'source_face_ids':ids,'proxy_vertex_ids':verts,'faces':len(ids),'vertices':len(verts),'bounds':[p.min(0).tolist(),p.max(0).tolist()],'centroid':mean.tolist(),'region':region(mean),'sum_area':float(areas[ids].sum()),'pca_singular_values':singular.tolist(),'pca_thickness_ratio':float(singular[-1]/singular[0]) if singular[0] else 0,'boundary_edges_in_partition':boundary,'nonmanifold_edges_in_partition':nonman,'note':'Diagnostic face graph only; connectivity across all >2-face edges excluded. No actual segmentation or topology edits.'})
 clusters=[]
 for number,event_ids in enumerate(cluster_defect_events(events),1):
  es=[events[i] for i in event_ids];ids=sorted({int(f) for e in es for f in e['source_faces']});verts=sorted({int(v) for e in es for v in e['proxy_vertices']});p=points[verts];center=p.mean(0);ring=sorted({f for v in verts for f in vf[v]}-set(ids));boundary=[e for e in es if e['kind']=='boundary'];nm=[e for e in es if e['kind']=='nonmanifold'];fans=[e for e in es if e['kind']=='fan']
  bedges=[tuple(e['proxy_vertices']) for e in boundary];degrees=Counter(v for e in bedges for v in e);bg=components(degrees,bedges) if bedges else []
  candidate_loops=[{'proxy_vertex_ids':g,'degree_two_closed_graph':all(degrees[v]==2 for v in g),'points':points[g].tolist()} for g in bg]
  normal_pairs=[]
  for e in nm:
   fi=e['source_faces'];normal_pairs.append({'source_faces':fi,'pair_normal_angles_degrees':[{'faces':[int(a),int(b)],'angle':float(math.degrees(math.acos(float(np.clip(normals[a]@normals[b],-1,1)))))} for n,a in enumerate(fi) for b in fi[n+1:]]})
  partitions_hit=sorted({part_index[f] for f in ids});cluster={'id':f'D{number:02d}','region':region(center),'event_ids':event_ids,'counts':dict(Counter(e['kind'] for e in es)),'source_face_ids':ids,'context_source_face_ids':ring,'proxy_vertex_ids':verts,'source_vertex_aliases':{str(v):mapping['proxy_to_sources'][v] for v in verts},'bounds':[p.min(0).tolist(),p.max(0).tolist()],'center':center.tolist(),'boundary_graphs':candidate_loops,'normal_angle_evidence':normal_pairs,'diagnostic_partitions':partitions_hit,'fan_groups':[e for e in fans],'crossing_pairs_touching_faces':[pair for pair in prior['baseline_crossing_pairs'] if set(pair)&set(ids)],'category':'UNREVIEWED','confidence':'pending image review','proposed_operation':'No operation authorized'};clusters.append(cluster)
 write(OUT/'defect_register.json',{'source_scene_sha256':sha(SCENE),'c0_source_faces':len(c0),'events':events,'clusters':clusters,'counts':{'boundary':87,'nonmanifold':42,'fan':8,'clusters':len(clusters)},'clustering':'Events share a defect vertex or an incident source face. Context triangles are not used to fuse distant events. Zero spatial proximity merges.','baseline_crossing_pairs':prior['baseline_crossing_pairs'],'diagnostic_face_partitions':part_reports,'not_a_body_segmentation':'Ignoring junction edges is only a graph probe. A small planar patch is not automatically a removable fur sheet; watertight body identity still requires visual review.','operations_performed':{'mesh_edits':0,'weight_binds':0,'rig_generations':0,'exports':0,'scene_saves':0}})
 np.savez_compressed(WORK/'geometry.npz',points=points,faces=faces)
 assert all(sha(ROOT/p)==h for p,h in frozen.items())
 write(OUT/'scene_verification.json',{'scene_sha256':sha(SCENE),'deform_bones':46,'proxy_vertices':len(points),'triangles':len(faces),'read_only':True,'source_face_order_matches':True,'hashes_preserved':True,'saved_scene':False})
 print(json.dumps({'clusters':len(clusters),'partitions':[(p['partition'],p['faces'],p['boundary_edges_in_partition'],p['region']) for p in part_reports],'defects':dict(Counter(e['kind'] for e in events))}))
if __name__=='__main__':main()
