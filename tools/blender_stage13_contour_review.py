"""Read-only closed-boundary evidence; run after the topology review in Blender Python.
No caps, vertex movement, scene saves or weights are performed.
"""
import json,numpy as np
from pathlib import Path
out=Path.cwd()/'docs/model-reports/stage13';a=np.load(Path.cwd()/'artifacts/stage13/geometry.npz');p=a['points'];f=a['faces'];t=p[f];normal=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);normal/=np.linalg.norm(normal,axis=1)[:,None];x=json.loads((out/'defect_register.json').read_text());results=[]
for c in x['clusters']:
 for loop in c['boundary_graphs']:
  if not loop['degree_two_closed_graph']:continue
  ids=set(loop['proxy_vertex_ids']);es=[x['events'][i] for i in c['event_ids'] if x['events'][i]['kind']=='boundary' and set(x['events'][i]['proxy_vertices'])<=ids];ns=normal[[e['source_faces'][0] for e in es]];mean=ns.mean(0);spread=float(np.degrees(np.arccos(np.clip(ns@mean/max(np.linalg.norm(mean),1e-15),-1,1))).max());pts=p[sorted(ids)];s=np.linalg.svd(pts-pts.mean(0),compute_uv=False);area=float(np.linalg.norm(np.cross(pts[1]-pts[0],pts[2]-pts[0]))/2) if len(ids)==3 else None
  dist=np.linalg.norm(pts[:,None]-pts[None,:],axis=2);ia,ib=np.unravel_index(dist.argmax(),dist.shape);ordered=sorted(ids);va,vb=ordered[ia],ordered[ib];axis=p[vb]-p[va];param=(pts-p[va])@axis/(axis@axis);residual=np.linalg.norm(pts-p[va]-param[:,None]*axis,axis=1);long=[e for e in es if set(e['proxy_vertices'])=={va,vb}];tjunction={'endpoint_proxy_ids':[va,vb],'intermediate_proxy_parameters':{str(v):float(t) for v,t in zip(ordered,param) if v not in [va,vb]},'max_collinear_residual':float(residual.max()),'long_edge_source_faces':[fi for e in long for fi in e['source_faces']],'exact_collinear':bool(np.all(residual==0)),'proposed_only':True}
  results.append({'t_junction_evidence':tjunction,'cluster':c['id'],'vertices':sorted(ids),'adjacent_source_faces':[e['source_faces'][0] for e in es],'loop_vertex_count':len(ids),'adjacent_normal_max_deviation_deg':spread,'pca_thickness_ratio':float(s[-1]/s[0]) if s[0] else None,'triangle_cap_area_if_triangular':area,'proved_anatomical_body_hole':False,'note':'Closed graph does not prove skin/body identity. A cap is not created or automatically endorsed.'})
(out/'closed_contour_evidence.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
