"""Numerical neutral gate and static snapshots from actual Panda capture, no skin edits."""
import json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from rig_readiness_audit import read_glb
root=Path.cwd();out=root/'docs/model-reports/existing-retopo-skin';work=root/'artifacts/existing_retopo_skin'
reference=np.load(work/'reference.npz');bl=np.load(work/'blender.npz');panda={n:np.array(list(struct.iter_unpack('<3f',(work/f'panda_{n}.f32').read_bytes()))) for n in ['original','metadata']}
def delta(a,b):return float(np.linalg.norm(a-b,axis=1).max())
audit={'actual_panda_vs_gltf_formula':delta(panda['original'],reference['gltf_default']),'actual_panda_vs_blender_enabled':delta(panda['original'],bl['enabled']),'metadata_vs_original_actual_panda':delta(panda['metadata'],panda['original']),'gltf_default_vs_raw_primitive':delta(reference['gltf_default'],reference['primitive']),'actual_panda_vs_raw_primitive':delta(panda['original'],reference['primitive']),'blender_enabled_vs_formula':delta(bl['enabled'],reference['gltf_default']),'gate':'FAIL_NEUTRAL_IDENTITY_BIND_NOT_REPRODUCED','bend_tests_run':False,'reason':'Blender follows stored identity node transforms; Panda loader reconstructs rest transforms from inverse bind matrices. Defaults disagree, so neutral interoperability fails.'}
assert audit['metadata_vs_original_actual_panda']==0
assert audit['actual_panda_vs_raw_primitive']<2e-6
d,b,_=read_glb(root/'assets/3d/retopo/deskcat_calico_retopo_16460.glb')
# Test, rather than assume, a simplistic first-joint IBM explanation.
joint=json.loads((out/'skin_audit.json').read_text())['joints'][0];matrix=np.array(joint['inverse_bind_matrix']);pts=np.column_stack([reference['primitive'],np.ones(len(reference['primitive']))]);rigid=(pts@matrix.T)[:,:3]
audit['rejected_first_joint_ibm_hypothesis_error']=delta(bl['disabled'],rigid)
def snapshot(name,positions):
 doc=json.loads(json.dumps(d));data=bytearray(b);p=doc['meshes'][0]['primitives'][0]
 p['attributes'].pop('JOINTS_0');p['attributes'].pop('WEIGHTS_0');doc.pop('skins');doc['nodes']=[{'mesh':0}];doc['scenes']=[{'nodes':[0]}];doc['scene']=0
 a=doc['accessors'][p['attributes']['POSITION']];v=doc['bufferViews'][a['bufferView']];start=v.get('byteOffset',0)+a.get('byteOffset',0)
 for i,point in enumerate(positions):struct.pack_into('<3f',data,start+i*v.get('byteStride',12),*point)
 a['min']=positions.min(0).tolist();a['max']=positions.max(0).tolist();j=json.dumps(doc,separators=(',',':')).encode();j+=b' '*(-len(j)%4);body=struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(data),0x004e4942)+data;(work/(name+'.glb')).write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
snapshot('panda_actual',panda['original'])
write=(out/'neutral_gate.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit))
