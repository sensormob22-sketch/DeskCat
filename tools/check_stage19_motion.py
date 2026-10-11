"""Stage19 integrity: mirror right hind skin; preserve left paw, tail and fur."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from finish_calico_stage18 import read,acc

def check(raw_file,candidate_file,out):
    original,b0=read(raw_file);new,b1=read(candidate_file)
    geometry_checked=0
    for a,c in zip(original['meshes'][0]['primitives'],new['meshes'][0]['primitives']):
        for label in ('POSITION','NORMAL','TEXCOORD_0'):
            assert np.array_equal(acc(original,b0,a['attributes'][label]),
                                  acc(new,b1,c['attributes'][label]))
            geometry_checked+=1
        assert np.array_equal(acc(original,b0,a['indices']),acc(new,b1,c['indices']))
        geometry_checked+=1
    for a,c in zip(original['images'],new['images']):
        v0=original['bufferViews'][a['bufferView']]
        v1=new['bufferViews'][c['bufferView']]
        s0=v0.get('byteOffset',0);s1=v1.get('byteOffset',0)
        n=v0['byteLength']
        assert b0[s0:s0+n]==b1[s1:s1+n]
    tail_hashes=[]
    for animation in original['animations']:
        changed=next(a for a in new['animations'] if a['name']==animation['name'])
        for channel in animation['channels']:
            node=channel['target']['node']
            if original['nodes'][node].get('name')!='tail_base':continue
            source=animation['samplers'][channel['sampler']]['output']
            matching=next(c for c in changed['channels'] if c['target']==channel['target'])
            dest=changed['samplers'][matching['sampler']]['output']
            assert np.array_equal(acc(original,b0,source),acc(new,b1,dest))
            tail_hashes.append(hashlib.sha256(acc(original,b0,source).tobytes()).hexdigest())
    a=original['meshes'][0]['primitives'][0]['attributes']
    c=new['meshes'][0]['primitives'][0]['attributes']
    P=acc(original,b0,a['POSITION'])
    old_id=acc(original,b0,a['JOINTS_0'])
    new_id=acc(new,b1,c['JOINTS_0'])
    old_w=acc(original,b0,a['WEIGHTS_0'])
    new_w=acc(new,b1,c['WEIGHTS_0'])
    mask=(P[:,2]<-.025)&(P[:,1]<.19)&(P[:,0]>.02)&(P[:,0]<.28)
    changed=np.any(old_id!=new_id,axis=1)|np.any(abs(old_w-new_w)>1e-6,axis=1)
    count=int(np.count_nonzero(changed&mask))
    assert 300<count<2000
    assert not np.any(changed & (P[:,2]>.01)), 'Left leg modified by right skin transfer'
    assert np.allclose(new_w.sum(axis=1),1,atol=1e-5)
    gait=new.get('extras',{}).get('deskcat_gait',{})
    assert gait.get('toe_contact_method')=='four_beat_planar_IK_spine_compensated'
    assert abs(gait.get('stance_fraction',0)-.75)<1e-7
    outcome={'status':'PASS','geometry_fields_unchanged':geometry_checked,
             'original_tail_sha256':tail_hashes,
             'right_hind_mirrored_vertices':count,
             'untouched_left_leg':True,'untouched_texture_images':True,
             'gait_contract':gait,'live_windows_anatomy':'NOT VERIFIED'}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(outcome,indent=2),encoding='utf8')
    print(json.dumps(outcome,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();check(a.raw,a.candidate,a.out)
