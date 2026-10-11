"""Export measured cage pose deltas as ONE diagnostic glTF morph mesh, no clips.
No reskinning; original buffer/material/image/UV data and source vertex order kept.
"""
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor

def bake(source, snapshots, output):
    if output.exists():raise ValueError('Refuse to overwrite diagnostic GLB')
    doc,buf,_=read_glb(source);data=bytearray(buf[:doc['buffers'][0]['byteLength']]);mesh=doc['meshes'][0];prim=mesh['primitives'][0]
    rest=accessor(doc,buf,prim['attributes']['POSITION']);targets=[];names=[]
    for name,path in snapshots.items():
        d,b,_=read_glb(path);p=d['meshes'][0]['primitives'][0];ps=accessor(d,b,p['attributes']['POSITION'])
        if len(ps)!=len(rest):raise ValueError('Source-order vertex count changed')
        delta=[tuple(a-b for a,b in zip(pos,base)) for pos,base in zip(ps,rest)]
        data+=b'\0'*(-len(data)%4);offset=len(data)
        for row in delta:data.extend(struct.pack('<3f',*row))
        view=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(delta)*12,'target':34962})
        acc=len(doc['accessors']);doc['accessors'].append({'bufferView':view,'componentType':5126,'count':len(delta),'type':'VEC3','min':[min(v[i] for v in delta) for i in range(3)],'max':[max(v[i] for v in delta) for i in range(3)]})
        targets.append({'POSITION':acc});names.append(name)
    prim['targets']=targets;mesh['weights']=[0.0]*len(targets);mesh.setdefault('extras',{})['targetNames']=names
    doc['asset']['generator']='DeskCat one rejected cage trial / baked diagnostic poses only'
    doc['buffers'][0]['byteLength']=len(data);encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);data+=b'\0'*(-len(data)%4)
    body=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(data),0x004e4942)+data
    output.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
    return names

if __name__=='__main__':
    root=Path.cwd();report=json.loads((root/'docs/model-reports/stage12/comparison.json').read_text())
    names=bake(root/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb',{case:root/record['snapshot'] for case,record in report['models']['cage'].items() if case!='rest'},root/'assets/3d/tripo/deskcat_cage_trial_01_baked_poses.glb')
    print('Baked diagnostic morph targets:',names)
