"""Read-only pose/intersection/weight localization from an experimental Blender scene."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Vector,Quaternion
import math
from rig_geometry_analysis import mesh_data,components
from rig_readiness_audit import read_glb,accessor
from blender_deformation_probe import inverse


def heatmap(source,path,values):
    if path.exists():raise ValueError('New diagnostic heatmap path required')
    d,b,_=read_glb(source);data=bytearray(b[:d['buffers'][0]['byteLength']]);data+=b'\0'*(-len(data)%4)
    # Explicit scalar legend: 0 blue -> .5 green -> 1 red. No production textures edited.
    t=np.clip(values,0,1);colors=np.column_stack([np.clip(2*t-1,0,1),1-np.abs(2*t-1),np.clip(1-2*t,0,1),np.ones(len(t))]).astype('<f4')
    offset=len(data);raw=colors.tobytes();data+=raw
    view=len(d['bufferViews']);d['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(raw),'target':34962})
    attr=len(d['accessors']);d['accessors'].append({'bufferView':view,'componentType':5126,'count':len(t),'type':'VEC4'})
    d['meshes'][0]['primitives'][0]['attributes']['COLOR_0']=attr
    d['materials']=[{'name':'DIAGNOSTIC_WEIGHT_COLOR_NOT_CHARACTER_MATERIAL','pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1}}]
    d['buffers'][0]['byteLength']=len(data)
    encoded=json.dumps(d,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);data+=b'\0'*(-len(data)%4)
    body=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(data),0x004e4942)+data
    path.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)


def diagnose(source,scene,report,output):
    if output.exists():raise ValueError('New diagnostic output required')
    output.mkdir(parents=True)
    doc,binary,raw=read_glb(source);r=json.loads(report.read_text())
    if hashlib.sha256(raw).hexdigest()!=r['source_sha256']:raise ValueError('Source mismatch')
    original=np.array(accessor(doc,binary,doc['meshes'][0]['primitives'][0]['attributes']['POSITION']))
    canonical,faces,sources,_=mesh_data(source);ids=[sources[i][0] for i in range(len(canonical))]
    bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH');rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    imported=np.array([inverse(obj.matrix_world@v.co) for v in obj.data.vertices])
    if imported.shape!=original.shape or np.max(np.abs(imported-original))>1e-7:raise ValueError('Source order mismatch')
    names=[g.name for g in obj.vertex_groups];weights=np.zeros((len(original),len(names)))
    for v in obj.data.vertices:
        for g in v.groups:weights[v.index,g.group]=g.weight
    np.savez_compressed(output/'weights.npz',weights=weights,source_positions=original,bone_names=np.array(names))
    maps={'tail': ['tail_base'],'pelvis':['pelvis'],'spine':['lumbar','thoracic'],
          'right_shoulder':['shoulder_FR'],'left_shoulder':['shoulder_FL'],'hips':['hip_HL','hip_HR'],
          'hind_limbs':[n for n in names if n.endswith(('_HL','_HR'))]}
    stats={}
    for name,bones in maps.items():
        values=weights[:,[names.index(n) for n in bones]].sum(axis=1)
        heatmap(source,output/(name+'.glb'),values)
        positive=original[values>1e-5]
        stats[name]={'bones':bones,'vertices_nonzero':int((values>1e-5).sum()),'weight_max':float(values.max()),
            'affected_aabb':{'min':positive.min(axis=0).tolist(),'max':positive.max(axis=0).tolist()},'legend':'0 blue / 0.5 green / 1 red'}
    pts=np.array(canonical);fs=np.array(faces);localizations={}
    for pose in r['poses']:
        for pb in rig.pose.bones:pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion()
        for bone,deg in r['poses'][pose]['rotations_degrees_about_blender_world_y'].items():
            pb=rig.pose.bones[bone];axis=pb.bone.matrix_local.to_3x3().inverted()@Vector((0,1,0));pb.rotation_quaternion=Quaternion(axis,math.radians(deg))
        bpy.context.view_layer.update();obj_eval=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=obj_eval.to_mesh()
        posed=np.array([inverse(obj_eval.matrix_world@v.co) for v in me.vertices]);obj_eval.to_mesh_clear()
        pairs=r['poses'][pose]['new_source_face_pairs'];faceids=sorted({f for pair in pairs for f in pair})
        affected=sorted({v for f in faceids for v in faces[f]})
        # Components connect crossing faces and shared source vertices; these are
        # review clusters, not a count of independently certified defects.
        all_edges=[tuple(pair) for pair in pairs];owner={}
        for f in faceids:
            for v in faces[f]:
                if v in owner:all_edges.append((owner[v],f))
                owner[v]=f
        clusters=components(faceids,all_edges);cluster_records=[]
        for group in clusters:
            vids=sorted({v for f in group for v in faces[f]});positions=pts[vids];moves=posed[[ids[i] for i in vids]]
            cluster_records.append({'source_face_ids':group,'canonical_vertex_ids':vids,
                'source_vertex_ids':sorted(v for i in vids for v in sources[i]),
                'rest_aabb':{'min':positions.min(axis=0).tolist(),'max':positions.max(axis=0).tolist()},
                'posed_aabb':{'min':moves.min(axis=0).tolist(),'max':moves.max(axis=0).tolist()},
                'rest_centroid':positions.mean(axis=0).tolist(),'pair_count':sum(a in group and b in group for a,b in pairs)})
        pair_records=[]
        for a,b in pairs:
            rows=weights[[ids[v] for face in (a,b) for v in faces[face]]]
            variation=float(np.ptp(rows,axis=0).max())
            pair_records.append({'source_face_pair':[a,b], 'max_weight_variation':variation,
                                 'single_bone_rigid_pair':variation<1e-8 and int((rows[0]>0).sum())==1})
        vertex_records={str(v):{'position_gltf':original[v].tolist(),'dominant_bone':names[int(weights[v].argmax())],
                               'weights':{names[j]:float(w) for j,w in enumerate(weights[v]) if w>0}} for i in affected for v in sources[i]}
        localizations[pose]={'new_pairs':len(pairs),'affected_faces':len(faceids),'affected_source_vertices':len(vertex_records),
            'clusters':cluster_records,'affected_vertex_weights':vertex_records,
            'new_source_face_pairs':pairs,
            'pair_weight_classification':pair_records,
            'single_bone_rigid_new_pair_count':sum(record['single_bone_rigid_pair'] for record in pair_records),
            'affected_face_area_ratios':{str(f):float(np.linalg.norm(np.cross(posed[[ids[v] for v in faces[f]]][1]-posed[ids[faces[f][0]]],posed[[ids[v] for v in faces[f]]][2]-posed[ids[faces[f][0]]])) / max(np.linalg.norm(np.cross(pts[faces[f][1]]-pts[faces[f][0]],pts[faces[f][2]]-pts[faces[f][0]])),1e-30)) for f in faceids}}
    result={'source_sha256':r['source_sha256'],'scene':str(scene),'report':str(report),'weight_heatmaps':stats,
            'localization':localizations,'limits':'Crossing pair sets from measured report; source IDs verified against scene. Connected clusters are review regions, not certified defects. No source edits/export of character.'}
    (output/'diagnostics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({p:{'pairs':v['new_pairs'],'clusters':len(v['clusters']),'vertices':v['affected_source_vertices']} for p,v in localizations.items()}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','scene','report','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);diagnose(a.source,a.scene,a.report,a.output)
