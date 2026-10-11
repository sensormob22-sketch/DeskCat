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


def mirror_hind_right_skin(doc, buf):
    """Transfer LEFT hind skin behavior onto the RIGHT, with x-shift registration.

    Right-leg surface is about .05 model-units further toward -X; naive Z
    reflection would sample the wrong left-leg vertices. Use the same four
    hind bones but mapped L->R, preserving the original mesh and coat.
    """
    names = {n['name']:i for i,n in enumerate(doc['nodes'])}
    left = [names[f'hind_L_{i}'] for i in range(4)]
    right = [names[f'hind_R_{i}'] for i in range(4)]
    mapping = {left[i]:right[i] for i in range(4)}
    seen = set()
    changed = 0
    median_distances = []
    for primitive in doc['meshes'][0]['primitives']:
        attrs = primitive['attributes']
        key = (attrs['POSITION'],attrs['JOINTS_0'],attrs['WEIGHTS_0'])
        if key in seen: continue
        seen.add(key)
        pos = acc(doc,buf,attrs['POSITION'])
        ids = acc(doc,buf,attrs['JOINTS_0']).astype(int)
        weights = acc(doc,buf,attrs['WEIGHTS_0']).astype(float)
        right_mass = (weights * np.isin(ids,right)).sum(axis=1)
        left_mass = (weights * np.isin(ids,left)).sum(axis=1)
        donors = np.flatnonzero((pos[:,2]>.025)&(pos[:,1]<.25)&(left_mass>.65))
        recipients = np.flatnonzero((pos[:,2]<-.025)&(pos[:,1]<.19)&
                                 (pos[:,0]>.02)&(pos[:,0]<.28)&(right_mass>.65))
        if len(recipients)==0:continue
        if len(donors)<300:raise ValueError('Cannot find mirrored left hind paw')
        a = pos[recipients].astype(float).copy()
        a[:,0] += .02+.035*np.clip((.30-a[:,1])/.30,0,1)
        a[:,2] *= -1
        donor_pos = pos[donors].astype(float)
        nearest,distances = [],[]
        for i in range(0,len(a),96):
            chunk = a[i:i+96]
            dist2 = np.sum((chunk[:,None,:]-donor_pos[None,:,:])**2,axis=2)
            idx = np.argmin(dist2,axis=1)
            nearest.extend(donors[idx].tolist())
            distances.extend(np.sqrt(dist2[np.arange(len(idx)),idx]).tolist())
        nearest = np.array(nearest,dtype=int)
        dist = np.array(distances)
        median_distances.extend(dist.tolist())
        weighted = np.zeros((len(recipients),len(doc['skins'][0]['joints'])))
        for slot in range(4):
            src_joint = ids[nearest,slot]
            dst_joint = np.array([mapping.get(j,int(j)) for j in src_joint])
            weighted[np.arange(len(recipients)),dst_joint] += weights[nearest,slot]
        donor_right_mass = weighted[:,right].sum(axis=1)
        for ri,vi in enumerate(recipients):
            y = float(pos[vi,1]); distance=float(dist[ri])
            if distance>.028 or donor_right_mass[ri]<.6: continue
            feather = min(1.0, float(smooth((.195-y)/.105)))
            feather *= float(smooth((.030-distance)/.018))
            original = np.zeros(weighted.shape[1],dtype=float)
            for slot in range(4):original[ids[vi,slot]] += weights[vi,slot]
            candidate = (1-feather)*original + feather*weighted[ri]
            best = np.argsort(candidate)[-4:][::-1]
            out_weights = candidate[best]
            out_weights /= max(1e-20,out_weights.sum())
            if max(abs(candidate-original))<1e-5:continue
            for field,row,format_code in (('JOINTS_0',best,'<4H'),
                                          ('WEIGHTS_0',out_weights,'<4f')):
                accessor=doc['accessors'][attrs[field]]
                v=doc['bufferViews'][accessor['bufferView']]
                stride=v.get('byteStride',8 if field=='JOINTS_0' else 16)
                off=v.get('byteOffset',0)+accessor.get('byteOffset',0)+int(vi)*stride
                struct.pack_into(format_code,buf,off,*row)
            changed+=1
    if changed<300:raise ValueError(f'Mirror transfer modified too few points: {changed}')
    return {'right_hind_vertices_mirrored':changed,
            'mirror_match_median_distance':float(np.median(median_distances)),
            'approach':'left_hind_skin_reflected_with_anatomical_surface_registration'}



def enforce_symmetric_rest_skeleton(doc, buf):
    """Mirror both R chains from L in WORLD rest coordinates, preserving GLB mesh.

    Every right rest segment has exactly the same length and sagittal angle
    as its corresponding left segment. Its inverse bind matrix is rebuilt
    from the new joint position, so the original geometry stays in bind pose.
    """
    names={n.get('name'):i for i,n in enumerate(doc['nodes'])}
    parent={child:i for i,node in enumerate(doc['nodes'])
            for child in node.get('children',[])}
    pivots=bone_pivots(doc)
    changed=[]
    for prefix in ('front','hind'):
        for j in range(4):
            left=f'{prefix}_L_{j}'; right=f'{prefix}_R_{j}'
            mirror=pivots[left].copy()
            mirror[2]=-mirror[2]
            ri=names[right]
            p=parent[ri]
            parent_global=pivots[doc['nodes'][p]['name']]
            doc['nodes'][ri]['translation']=(mirror-parent_global).astype(float).tolist()
            pivots[right]=mirror
            changed.append(right)
    skin=doc['skins'][0]
    accessor=doc['accessors'][skin['inverseBindMatrices']]
    view=doc['bufferViews'][accessor['bufferView']]
    assert accessor['componentType']==5126 and accessor['type']=='MAT4'
    offset=view.get('byteOffset',0)+accessor.get('byteOffset',0)
    stride=view.get('byteStride',64)
    for slot,node_idx in enumerate(skin['joints']):
        name=doc['nodes'][node_idx].get('name')
        if name in changed:
            # glTF MAT4 is column-major; indices 12:15 are the translation.
            struct.pack_into('<3f',buf,offset+slot*stride+12*4,
                             *(-pivots[name]).astype(float))
    verification=bone_pivots(doc)
    max_error=0.0
    for prefix in ('front','hind'):
        for j in range(4):
            a=verification[f'{prefix}_L_{j}']
            b=verification[f'{prefix}_R_{j}']
            max_error=max(max_error,float(np.max(np.abs(a-np.array([b[0],b[1],-b[2]])))))
    if max_error>1e-6:raise ValueError('Right leg rest joints not exactly mirrored')
    return {'right_leg_joints_mirrored':len(changed),
            'maximum_rest_mirror_error':max_error,
            'inverse_bind_matrices_updated':len(changed),
            'rest_geometry_unchanged':True}


# Walking reference: independent 4-beat feline walk; stance toes are planted.
CYCLE_SECONDS = 1.6
STRIDE = .09
STANCE = .75
SWING_HEIGHT = .032
PHASES = {'hind_L':0.0, 'front_L':.25, 'hind_R':.5, 'front_R':.75}

def toe_path(phase):
    phase = phase % 1.0
    if phase < STANCE:
        return STRIDE * phase / STANCE, 0.0, 0.0
    u = (phase - STANCE) / (1 - STANCE)
    slope = STRIDE * (1-STANCE) / STANCE
    x = STRIDE * (2*u**3-3*u*u+1) + slope * ((u**3-2*u*u+u) + (u**3-u*u))
    y = SWING_HEIGHT * math.sin(math.pi*u)**2
    paw_roll = .035 * math.sin(2*math.pi*u)
    return x,y,paw_roll

def rot(angle):
    return np.array([[math.cos(angle),-math.sin(angle)],
                     [math.sin(angle),math.cos(angle)]])

def torso_angles(t):
    phase = float(t) / CYCLE_SECONDS
    # Clearly visible yet restrained feline back flexion, roughly 2 degrees
    # per spinal section. The forepaw IK below compensates torso movement.
    lumbar = .034*math.sin(4*math.pi*phase+.15)+.008*math.sin(2*math.pi*phase)
    chest = -.026*math.sin(4*math.pi*phase+.62)-.007*math.sin(2*math.pi*phase+.7)
    neck = .011*math.sin(2*math.pi*phase+.8)+.007*math.sin(4*math.pi*phase+.4)
    head = -.78*(lumbar+chest+neck)+.006*math.sin(4*math.pi*phase+1)
    return {'lumbar':lumbar,'chest':chest,'neck':neck,'head':head}

def bone_pivots(doc):
    parent={child:i for i,node in enumerate(doc['nodes'])
            for child in node.get('children',[])}
    cache={}
    def recurse(index):
        if index not in cache:
            own=np.array(doc['nodes'][index].get('translation',[0,0,0]),dtype=float)
            cache[index]=own+(recurse(parent[index]) if index in parent else 0)
        return cache[index]
    return {n['name']:recurse(i) for i,n in enumerate(doc['nodes']) if 'name' in n}

def solve_toe_ik(points, toe_target, roll):
    p0,p1,p2,p3 = points
    target = toe_target - rot(roll) @ (p3-p2)
    l1=np.linalg.norm(p1-p0);l2=np.linalg.norm(p2-p1)
    delta=target-p0;d=np.linalg.norm(delta)
    maximum=l1+l2-1e-6
    if d>maximum:
        if d-maximum>.00012:
            raise ValueError('Unreachable stance target (no bone lengthening permitted)')
        delta *= maximum/d
        target=p0+delta
        d=maximum
    if d<=abs(l1-l2)+1e-8:
        raise ValueError('Folded knee target is unreachable')
    axis=delta/d;along=(l1*l1-l2*l2+d*d)/(2*d)
    lateral=math.sqrt(max(0.,l1*l1-along*along))
    cross=np.linalg.det(np.stack((p2-p0,p1-p0)))
    joint=p0+along*axis+math.copysign(lateral,cross)*np.array([-axis[1],axis[0]])
    direction=lambda v:math.atan2(v[1],v[0])
    first=direction(joint-p0)-direction(p1-p0)
    second=direction(target-joint)-direction(p2-p1)-first
    third=roll-first-second
    return first,second,third

def to_quaternions(angles):
    angles=np.array(angles,dtype=float)
    return np.column_stack((np.zeros(len(angles)),np.zeros(len(angles)),
                            np.sin(angles/2),np.cos(angles/2)))


def yaw_pitch_quaternions(pitch, yaw):
    """Local Y yaw and Z pitch; glTF source is Y-up, so Y turns the muzzle."""
    pitch=np.asarray(pitch,dtype=float)
    yaw=np.asarray(yaw,dtype=float)
    sy=np.sin(yaw/2);cy=np.cos(yaw/2)
    sz=np.sin(pitch/2);cz=np.cos(pitch/2)
    result=np.column_stack((sy*sz, sy*cz, cy*sz, cy*cz))
    assert np.allclose((result*result).sum(axis=1),1,atol=1e-6)
    return result

def recalculate_gait(doc,buf):
    names={n['name']:i for i,n in enumerate(doc['nodes']) if 'name' in n}
    pivots=bone_pivots(doc)
    walk=next(a for a in doc['animations'] if a['name']=='walk')
    timeline=acc(doc,buf,walk['samplers'][0]['input']).ravel()
    assert len(timeline)==33 and abs(float(timeline[-1])-CYCLE_SECONDS)<1e-5
    original={(c['target']['node'],c['target']['path']):c['sampler']
              for c in walk['channels']}
    per_bone={f'{limb}_{i}':[] for limb in PHASES for i in range(3)}
    # Shoulder-blade protraction makes contact reachable as the back flexes,
    # instead of stretching foreleg bone lengths when the spine bends.
    shoulder_translation={limb:[] for limb in PHASES if limb.startswith('front')}
    max_shoulder_shift=0.0
    spine={n:[] for n in ('lumbar','chest','neck','head')}
    pose_error=0.0
    center_lumbar=pivots['lumbar'][:2];center_chest=pivots['chest'][:2]
    for ti in timeline:
        t=float(ti)
        angles=torso_angles(t)
        for n,value in angles.items():spine[n].append(value)
        after_lumbar=center_lumbar
        after_chest=(after_lumbar + rot(angles['lumbar']) @
                     (center_chest-center_lumbar))
        front_heading=angles['lumbar']+angles['chest']
        for limb,phase_offset in PHASES.items():
            path=np.array([pivots[f'{limb}_{i}'][:2] for i in range(4)])
            dx,dy,roll=toe_path(t/CYCLE_SECONDS+phase_offset)
            final_toe=path[3]+[dx,dy]
            parent_angle=front_heading if limb.startswith('front') else 0.0
            parent_origin=after_chest if limb.startswith('front') else None
            if parent_origin is not None:
                desired_local_toe=(center_chest +
                    rot(-parent_angle)@(final_toe-parent_origin))
            else:
                desired_local_toe=final_toe
            target_roll=roll-parent_angle
            # Two-link IK has an immutable physical reach. Instead of allowing
            # the right (or left) leg to elastically elongate, gently slide
            # the scapula root toward the foot by the missing reach only.
            ankle_goal=desired_local_toe-rot(target_roll)@(path[3]-path[2])
            reach=(np.linalg.norm(path[1]-path[0])+
                   np.linalg.norm(path[2]-path[1])-.00008)
            reach_vector=ankle_goal-path[0]
            distance=np.linalg.norm(reach_vector)
            shift=np.zeros(2)
            if distance>reach:
                shift=(distance-reach)*reach_vector/distance
                if np.linalg.norm(shift)>.025:
                    raise ValueError('Scapular slide exceeded natural reach budget')
            if limb in shoulder_translation:
                rest=np.array(doc['nodes'][names[limb+'_0']]['translation'],dtype=float)
                shoulder_translation[limb].append(
                    [rest[0]+shift[0],rest[1]+shift[1],rest[2]])
            max_shoulder_shift=max(max_shoulder_shift,float(np.linalg.norm(shift)))
            moved_path=path+shift
            a=solve_toe_ik(moved_path,desired_local_toe,target_roll)
            for i in range(3):
                per_bone[f'{limb}_{i}'].append(a[i])
            current=(parent_origin + rot(parent_angle)@(moved_path[0]-center_chest)
                     if parent_origin is not None else moved_path[0].copy())
            total=parent_angle
            for k,part in enumerate(a):
                total+=part
                current += rot(total) @ (moved_path[k+1]-moved_path[k])
            pose_error=max(pose_error,float(np.linalg.norm(current-final_toe)))
    if pose_error>1.2e-4:raise ValueError('Toe contact reconstruction error')
    # Replace leg channels, keep the existing natural tail animation byte-identical.
    for bone,angles in per_bone.items():
        node=names[bone];j=original.get((node,'rotation'))
        if j is None:raise ValueError(f'Missing joint rotation channel {bone}')
        walk['samplers'][j]['output']=add_vec4(doc,buf,to_quaternions(angles))
    for limb,poses in shoulder_translation.items():
        node=names[limb+'_0']
        if (node,'translation') in original:
            raise ValueError('Original shoulder translation must remain unmodified')
        i=len(walk['samplers'])
        translations=np.ascontiguousarray(poses,dtype='<f4')
        if translations.shape!=(len(timeline),3):
            raise ValueError('Bad shoulder translation track length')
        buf.extend(b'\x00'*(-len(buf)%4))
        off=len(buf);buf.extend(translations.tobytes())
        doc['bufferViews'].append({'buffer':0,'byteOffset':off,
                                   'byteLength':translations.nbytes})
        doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,
                                 'componentType':5126,'count':len(poses),
                                 'type':'VEC3'})
        walk['samplers'].append({'input':walk['samplers'][0]['input'],
                                'output':len(doc['accessors'])-1,
                                'interpolation':'LINEAR'})
        walk['channels'].append({'sampler':i,
                                 'target':{'node':node,'path':'translation'}})
    for bone,angles in spine.items():
        node=names[bone]
        if (node,'rotation') in original:raise ValueError('Existing spine channel conflict')
        i=len(walk['samplers'])
        if bone in ('neck','head'):
            phase=timeline/CYCLE_SECONDS
            yaw=(.024 if bone=='neck' else .063)*np.sin(
                2*math.pi*phase+(.35 if bone=='neck' else .10))
            rotation=yaw_pitch_quaternions(angles,yaw)
        else:
            rotation=to_quaternions(angles)
        walk['samplers'].append({'input':walk['samplers'][0]['input'],
                                'output':add_vec4(doc,buf,rotation),
                                'interpolation':'LINEAR'})
        walk['channels'].append({'sampler':i,
                                 'target':{'node':node,'path':'rotation'}})
    doc.setdefault('extras',{})['deskcat_gait']={
        'clip':'walk','period_seconds':CYCLE_SECONDS,
        'stance_fraction':STANCE,'toe_stance_travel_source_units':STRIDE,
        'forward_source_axis':'-X','toe_contact_method':'four_beat_planar_IK_spine_compensated',
        'source_reference':'user walking-cat video October 2026',
    }
    return {'max_toe_contact_error_source_units':pose_error,
            'stance_fraction':STANCE,'stride':STRIDE,
            'walking_spine_head_channels':len(spine),
            'four_independent_legs':True,
            'head_yaw_amplitude_radians':.063,
            'neck_yaw_amplitude_radians':.024,
            'lumbar_pitch_amplitude_radians':.042,
            'maximum_scapula_protraction_source_units':max_shoulder_shift}

def add_idle_spine_head(doc,buf):
    idle=next(a for a in doc['animations'] if a['name']=='idle')
    timeline=acc(doc,buf,idle['samplers'][0]['input']).ravel()
    names={n['name']:i for i,n in enumerate(doc['nodes']) if 'name' in n}
    for bone,amplitude,phase in (('lumbar',.003,0),('chest',-.003,.3),
                                  ('neck',.004,.3),('head',-.004,.5)):
        a=amplitude*np.sin(2*math.pi*timeline/CYCLE_SECONDS+phase)
        idx=len(idle['samplers'])
        idle['samplers'].append({'input':idle['samplers'][0]['input'],
             'output':add_vec4(doc,buf,to_quaternions(a)), 'interpolation':'LINEAR'})
        idle['channels'].append({'sampler':idx,
            'target':{'node':names[bone],'path':'rotation'}})
    return 4


def polish(source,output,report=None):
    source=Path(source);output=Path(output)
    if not source.is_file() or source.resolve()==output.resolve() or output.exists():
        raise ValueError('Expected an existing input and a NEW output')
    doc,buf=read(source)
    assert len(doc['meshes'][0]['primitives'])==3
    before_bytes=bytes(buf)
    original_animations={a['name']:len(a['channels']) for a in doc['animations']}
    symmetric=enforce_symmetric_rest_skeleton(doc,buf)
    repaired=mirror_hind_right_skin(doc,buf)
    gait=recalculate_gait(doc,buf)
    idle_channels=add_idle_spine_head(doc,buf)
    for image in doc['images']:
        v=doc['bufferViews'][image['bufferView']]
        b=v.get('byteOffset',0);n=v['byteLength']
        assert before_bytes[b:b+n]==buf[b:b+n]
    doc['buffers'][0]['byteLength']=len(buf)
    doc.setdefault('extras',{})['deskcat_polish']={'right_hind_lower_leg':'mirror_left_hind_skin_and_rest_joints',
         'spine_head':'spine_compensated_gait_and_idle','tail':'original_channels_unchanged',
         'source_mesh_uv_images':'preserved'}
    js=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode('utf8')
    js+=b' '*(-len(js)%4);buf+=b'\x00'*(-len(buf)%4)
    packed=(struct.pack('<4sII',b'glTF',2,12+8+len(js)+8+len(buf))+
            struct.pack('<II',len(js),0x4e4f534a)+js+
            struct.pack('<II',len(buf),0x004e4942)+buf)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(packed)
    result={'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'output_sha256':hashlib.sha256(packed).hexdigest(),
      'symmetric_bind_pose':symmetric,'weight_fix':repaired,'gait':gait,'idle_spine_channels_added':idle_channels,'initial_channel_counts':original_animations,
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
