"""Postprocess Stage18 GLB; preserve source geometry, fur textures and tail clip.

Add very subtle lumbar/chest/neck/head movement; stabilize right rear ankle
by reducing overlapping lower-leg skin weights. This is an experimental,
non-destructive candidate, not accepted anatomy or production skinning.
"""
import argparse
import json
import hashlib
import math
import struct
from pathlib import Path

import numpy as np

COMP = {5123:'<u2', 5125:'<u4', 5126:'<f4'}
NCOMP = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}


def read(path):
    raw=path.read_bytes()
    if raw[:4]!=b'glTF' or struct.unpack_from('<I',raw,8)[0]!=len(raw):
        raise ValueError('Bad GLB header')
    n, tag=struct.unpack_from('<II',raw,12)
    if tag!=0x4e4f534a: raise ValueError('Missing glTF JSON chunk')
    doc=json.loads(raw[20:20+n]); at=20+n
    length,tag=struct.unpack_from('<II',raw,at)
    if tag!=0x004e4942:raise ValueError('Missing glTF BIN chunk')
    return doc,bytearray(raw[at+8:at+8+length])


def acc(doc, buf, num):
    a=doc['accessors'][num]; view=doc['bufferViews'][a['bufferView']]
    dt=np.dtype(COMP[a['componentType']]); width=NCOMP[a['type']]
    off=view.get('byteOffset',0)+a.get('byteOffset',0)
    stride=view.get('byteStride',width*dt.itemsize)
    return np.ndarray((a['count'],width),dtype=dt,buffer=buf,
                      offset=off,strides=(stride,dt.itemsize)).copy()


def add_vec4(doc,buf,values):
    values=np.ascontiguousarray(values,dtype='<f4')
    assert values.ndim==2 and values.shape[1]==4
    buf.extend(b'\x00'*(-len(buf)%4))
    offset=len(buf);buf.extend(values.tobytes())
    doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':values.nbytes})
    doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,
                             'componentType':5126,'count':len(values),'type':'VEC4'})
    return len(doc['accessors'])-1


def smooth(t):
    t=np.clip(t,0,1);return t*t*(3-2*t)


def fix_right_ankle(doc,buf):
    names={n.get('name'):i for i,n in enumerate(doc['nodes'])}
    hip,knee,hock,paw=[names['hind_R_'+str(i)] for i in range(4)]
    count=0; max_delta=0
    seen=set()
    for p in doc['meshes'][0]['primitives']:
        a=p['attributes']; key=a['WEIGHTS_0']
        if key in seen:continue
        seen.add(key)
        pos=acc(doc,buf,a['POSITION']); joints=acc(doc,buf,a['JOINTS_0']); weights=acc(doc,buf,key)
        v=doc['bufferViews'][doc['accessors'][key]['bufferView']]
        start=v.get('byteOffset',0)+doc['accessors'][key].get('byteOffset',0)
        stride=v.get('byteStride',16)
        mass=(weights*np.isin(joints,[hip,knee,hock,paw])).sum(axis=1)
        eligible=((pos[:,2]<-.028)&(pos[:,0]>.025)&(pos[:,0]<.27)&
                  (pos[:,1]>=0)&(pos[:,1]<.105)&(mass>=.65))
        for i in np.flatnonzero(eligible):
            y=float(pos[i,1]); original=weights[i].astype(float)
            if y<.072:
                t=float(smooth((y-.025)/.048));target={hock:t,paw:1-t}
            else:
                t=float(smooth((y-.072)/.12));target={knee:t,hock:1-t}
            if any(value>.001 and bone not in joints[i] for bone,value in target.items()):
                continue
            candidate=original.copy()
            for slot,bone in enumerate(joints[i]):
                if bone in (hip,knee,hock,paw):candidate[slot]=mass[i]*target.get(int(bone),0)
            if abs(candidate.sum()-1)>.001:continue
            feather=.90*(1-float(smooth((y-.075)/.03)))
            candidate=original*(1-feather)+candidate*feather
            candidate/=candidate.sum()
            delta=float(max(abs(candidate-original)))
            if delta<1e-7:continue
            struct.pack_into('<4f',buf,start+int(i)*stride,*candidate)
            count+=1;max_delta=max(max_delta,delta)
    if count<100:raise ValueError('Expected right-hind vertices not found')
    return {'right_hind_vertices_adjusted':count,'max_weight_delta':max_delta}


def add_spine_head(doc,buf):
    names={n.get('name'):i for i,n in enumerate(doc['nodes'])}
    result={}
    for anim in doc['animations']:
        mode=anim['name']
        if mode not in ('idle','walk'):continue
        timeline=acc(doc,buf,anim['samplers'][0]['input']).ravel()
        period=float(timeline[-1])
        if mode=='walk':
            recipe={'lumbar':(.018,.1),'chest':(-.024,.35),
                    'neck':(.025,-.22),'head':(-.012,.5)}
        else:
            recipe={'lumbar':(.004,0),'chest':(-.004,.2),
                    'neck':(.006,.15),'head':(-.004,.35)}
        prior={(c['target']['node'],c['target']['path']) for c in anim['channels']}
        for bone,(magnitude,shift) in recipe.items():
            index=names[bone]
            if (index,'rotation') in prior:raise ValueError('Would replace original channel')
            a=magnitude*np.sin(2*math.pi*timeline/period+shift)
            q=np.stack([np.zeros(len(a)),np.zeros(len(a)),np.sin(a/2),np.cos(a/2)],axis=1)
            out=add_vec4(doc,buf,q)
            anim['channels'].append({'sampler':len(anim['samplers']),
                 'target':{'node':index,'path':'rotation'}})
            anim['samplers'].append({'input':anim['samplers'][0]['input'],
                 'output':out,'interpolation':'LINEAR'})
        result[mode]=len(recipe)
    return result


def polish(source,output,report=None):
    source=Path(source);output=Path(output)
    if not source.is_file() or source.resolve()==output.resolve() or output.exists():
        raise ValueError('Expected an existing input and a NEW output')
    doc,buf=read(source)
    assert len(doc['meshes'][0]['primitives'])==3
    before_bytes=bytes(buf)
    original_animations={a['name']:len(a['channels']) for a in doc['animations']}
    repaired=fix_right_ankle(doc,buf)
    channels=add_spine_head(doc,buf)
    for image in doc['images']:
        v=doc['bufferViews'][image['bufferView']]
        b=v.get('byteOffset',0);n=v['byteLength']
        assert before_bytes[b:b+n]==buf[b:b+n]
    doc['buffers'][0]['byteLength']=len(buf)
    doc.setdefault('extras',{})['deskcat_polish']={'right_hind_lower_leg':'experimental_weight_rebalance',
         'spine_head':'subtle_cyclic','tail':'original_channels_unchanged',
         'source_mesh_uv_images':'preserved'}
    js=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode('utf8')
    js+=b' '*(-len(js)%4);buf+=b'\x00'*(-len(buf)%4)
    packed=(struct.pack('<4sII',b'glTF',2,12+8+len(js)+8+len(buf))+
            struct.pack('<II',len(js),0x4e4f534a)+js+
            struct.pack('<II',len(buf),0x004e4942)+buf)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(packed)
    result={'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'output_sha256':hashlib.sha256(packed).hexdigest(),
      'weight_fix':repaired,'channels_added':channels,'initial_channel_counts':original_animations,
      'geometry_and_images_unchanged':True,'tail_animation_unchanged':True,
      'production_accepted':False}
    if report:
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--report',type=Path)
    a=p.parse_args();print(json.dumps(polish(a.input,a.output,a.report),indent=2))
