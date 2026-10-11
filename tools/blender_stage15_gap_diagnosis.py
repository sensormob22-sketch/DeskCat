"""Read-only camera rays on original raw geometry, not the invalid original skin."""
import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage15'
d,b,_=read_glb(ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb');pr=d['meshes'][0]['primitives'][0]
p=np.array(accessor(d,b,pr['attributes']['POSITION']));uv=np.array(accessor(d,b,pr['attributes']['TEXCOORD_0']));idx=np.array([i[0] for i in accessor(d,b,pr['indices'])]).reshape(-1,3);tri=p[idx]
register=json.loads((ROOT/'docs/model-reports/stage13/defect_register.json').read_text());sets={c['id']:set(c['source_face_ids']+c['context_source_face_ids']) for c in register['clusters'] if c['id'] in ['D06','D14','D17']}
def cast(o,direction):
 direction=direction/np.linalg.norm(direction);e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0];h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h);inv=np.divide(1,det,out=np.zeros(len(det)),where=abs(det)>1e-12);s=o-tri[:,0];u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=inv*(q@direction);t=inv*np.einsum('ij,ij->i',e2,q);ids=np.where((abs(det)>1e-12)&(u>=0)&(v>=0)&(u+v<=1)&(t>0))[0];ids=ids[np.argsort(t[ids])]
 return [{'source_face_id':int(i),'distance':float(t[i]),'point':(o+t[i]*direction).tolist(),'uv':((1-u[i]-v[i])*uv[idx[i,0]]+u[i]*uv[idx[i,1]]+v[i]*uv[idx[i,2]]).tolist(),'stage13_core_or_context':[k for k,fs in sets.items() if int(i) in fs]} for i in ids[:8]]
if __name__=='__main__':
 result={}
 for name in ['side','below','oblique']:
  rays=json.loads((OUT/f'rays_{name}.json').read_text());result[name]=[dict(ray,hits=cast(np.array(ray['origin']),np.array(ray['direction']))) for ray in rays]
 (OUT/'ray_diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
 np.savez_compressed(ROOT/'artifacts/stage15/source.npz',points=p,faces=idx,uv=uv)
 for r in result['oblique']:print(r['pixel'],[(h['source_face_id'],h['point'],h['stage13_core_or_context']) for h in r['hits'][:2]])
