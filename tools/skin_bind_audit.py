"""Read-only glTF linear skin rest/bind inspection. No rigging acceptance claim."""
import argparse
import json
import math
from pathlib import Path
import struct
if __package__:
    from .rig_readiness_audit import read_glb,accessor,node_transform,product,identity
else:
    from rig_readiness_audit import read_glb,accessor,node_transform,product,identity


def inspect(path):
    d,b,_=read_glb(path)
    if len(d.get('skins',[]))!=1:raise ValueError('Expected one real skin for bind inspection')
    worlds={}
    def walk(i,parent,ancestors):
        if i in ancestors:raise ValueError('Cyclic node hierarchy')
        worlds[i]=product(parent,node_transform(d['nodes'][i]))
        for child in d['nodes'][i].get('children',[]):walk(child,worlds[i],ancestors|{i})
    for i in d['scenes'][d.get('scene',0)]['nodes']:walk(i,identity(),set())
    skin=d['skins'][0];a=d['accessors'][skin['inverseBindMatrices']];view=d['bufferViews'][a['bufferView']]
    if a['type']!='MAT4' or a['componentType']!=5126 or 'sparse' in a:raise ValueError('Unsupported inverse bind encoding')
    if a['count']!=len(skin['joints']):raise ValueError('Inverse bind count mismatch')
    offset=view.get('byteOffset',0)+a.get('byteOffset',0);stride=view.get('byteStride',64)
    end=view.get('byteOffset',0)+view['byteLength']
    if stride<64 or offset+(a['count']-1)*stride+64>end:raise ValueError('Truncated inverse bind matrices')
    matrices=[struct.unpack_from('<16f',b,offset+stride*i) for i in range(a['count'])]
    if not all(math.isfinite(v) for row in matrices for v in row):raise ValueError('Nonfinite bind transform')
    jointmat=[product(worlds[j],ib) for j,ib in zip(skin['joints'],matrices)]
    worst=0.;vertices=0;headvertices=0;headwrong=0;sumerror=0.
    for i,node in enumerate(d['nodes']):
        if 'skin' not in node:continue
        for p in d['meshes'][node['mesh']]['primitives']:
            positions=accessor(d,b,p['attributes']['POSITION']);js=accessor(d,b,p['attributes']['JOINTS_0']);ws=accessor(d,b,p['attributes']['WEIGHTS_0'])
            if not len(positions)==len(js)==len(ws):raise ValueError('Skin attribute count mismatch')
            for v,joints,weights in zip(positions,js,ws):
                result=[0.,0.,0.];vertices+=1
                if any(j<0 or j>=len(jointmat) for j in joints) or any(w<0 or w>1 for w in weights):raise ValueError('Invalid joints or weights')
                sumerror=max(sumerror,abs(sum(weights)-1))
                for j,w in zip(joints,weights):
                    m=jointmat[j]
                    for row in range(3):result[row]+=w*(sum(m[k*4+row]*v[k] for k in range(3))+m[12+row])
                # Bind-space geometry world position uses mesh world transform.
                expected=[sum(worlds[i][k*4+row]*v[k] for k in range(3))+worlds[i][12+row] for row in range(3)]
                worst=max(worst,math.dist(expected,result))
                if v[0]<-.35 and v[1]>.30:
                    headvertices+=1
                    if any(w>0 and d['nodes'][skin['joints'][j]].get('name')!='root' for j,w in zip(joints,weights)):headwrong+=1
    return {'method':'glTF joint world matrix * inverse bind matrix, weighted per vertex; compared to mesh world rest coordinates',
            'vertices':vertices,'joints':len(skin['joints']),'max_rest_bind_displacement':worst,'max_weight_sum_error':sumerror,
            'protected_head_vertices':headvertices,'protected_head_vertices_with_nonroot_weight':headwrong,
            'static_audit_status':'Existing rig_readiness_audit intentionally rejects skinned meshes; this is separate bind inspection.',
            'limits':'Rest linear skin only; does not certify anatomical placement, animation, tangents, volume preservation or production weights.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('model',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=inspect(a.model);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
