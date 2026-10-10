"""Read-only preservation checks for Blender skin export; order may change."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
if __package__:
    from .rig_readiness_audit import read_glb, accessor
else:
    from rig_readiness_audit import read_glb, accessor


def audit_export(source, exported):
    a,ab,ar=read_glb(source);b,bb,br=read_glb(exported)
    def signatures(doc,binary):
        counts=Counter();surface=Counter();exact_surface=Counter();vertices=triangles=0
        for mesh in doc['meshes']:
            for p in mesh['primitives']:
                positions=accessor(doc,binary,p['attributes']['POSITION'])
                uv=accessor(doc,binary,p['attributes']['TEXCOORD_0'])
                keys=[tuple(round(x,6) for x in (*v,*u)) for v,u in zip(positions,uv)]
                exact_keys=[(*v,*u) for v,u in zip(positions,uv)]
                counts.update(keys)
                index=[v[0] for v in accessor(doc,binary,p['indices'])]
                for k in range(0,len(index),3):
                    tri=tuple(keys[i] for i in index[k:k+3])
                    surface[min(tri,tri[1:]+tri[:1],tri[2:]+tri[:2])]+=1
                    exact_tri=tuple(exact_keys[i] for i in index[k:k+3])
                    exact_surface[min(exact_tri,exact_tri[1:]+exact_tri[:1],exact_tri[2:]+exact_tri[:2])]+=1
                vertices+=len(positions);triangles+=len(accessor(doc,binary,p['indices']))//3
        return counts,vertices,triangles,surface,exact_surface
    sa,va,ta,fa,ea=signatures(a,ab);sb,vb,tb,fb,eb=signatures(b,bb)
    def images(doc,binary):
        out=[]
        for im in doc.get('images',[]):
            view=doc['bufferViews'][im['bufferView']];start=view.get('byteOffset',0)
            data=binary[start:start+view['byteLength']]
            out.append({'name':im.get('name'),'mimeType':im.get('mimeType'),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        return out
    ia,ib=images(a,ab),images(b,bb)
    from collections import defaultdict
    def normals_by_signature(doc,binary):
        result=defaultdict(list)
        for mesh in doc['meshes']:
            for p in mesh['primitives']:
                ps=accessor(doc,binary,p['attributes']['POSITION']);uv=accessor(doc,binary,p['attributes']['TEXCOORD_0']);ns=accessor(doc,binary,p['attributes']['NORMAL'])
                for v,u,n in zip(ps,uv,ns):result[tuple(round(x,6) for x in (*v,*u))].append(n)
        return result
    def position_uv_values(doc,binary):
        result=defaultdict(list)
        for mesh in doc['meshes']:
            for p in mesh['primitives']:
                ps=accessor(doc,binary,p['attributes']['POSITION']);uv=accessor(doc,binary,p['attributes']['TEXCOORD_0'])
                for v,u in zip(ps,uv):result[tuple(round(x,6) for x in (*v,*u))].append((*v,*u))
        return result
    old_values=position_uv_values(a,ab);new_values=position_uv_values(b,bb)
    max_position_error=max_uv_error=0.
    for key,values in new_values.items():
        if key not in old_values:continue
        for value in values:
            closest=min(old_values[key],key=lambda v:sum(abs(x-y) for x,y in zip(v,value)))
            max_position_error=max(max_position_error,max(abs(x-y) for x,y in zip(closest[:3],value[:3])))
            max_uv_error=max(max_uv_error,max(abs(x-y) for x,y in zip(closest[3:],value[3:])))
    original_normals=normals_by_signature(a,ab);new_normals=normals_by_signature(b,bb);angles=[]
    for key,values in new_normals.items():
        if key not in original_normals:continue
        for n in values:
            def angle(old):
                denominator=math.sqrt(sum(x*x for x in old)*sum(x*x for x in n))
                if denominator==0:raise ValueError('Zero-length normal')
                dot=sum(x*y for x,y in zip(old,n))/denominator
                return math.degrees(math.acos(max(-1,min(1,dot))))
            angles.append(min(angle(old) for old in original_normals[key]))
    angles.sort()
    normal_review={'max_angle_degrees':max(angles),'p50_angle_degrees':angles[len(angles)//2],
        'p99_angle_degrees':angles[int(len(angles)*.99)],'over_one_degree':sum(x>1 for x in angles),
        'method':'Closest source normal within rounded 1e-6 position+UV signature; permits exporter splits/order changes.'}

    def material_meaning(doc, imgs):
        import copy
        mats=copy.deepcopy(doc.get('materials',[]))
        for mat in mats:
            slots=[mat,mat.get('pbrMetallicRoughness',{})]
            for slot in slots:
                for key,value in slot.items():
                    if key.endswith('Texture') and isinstance(value,dict) and 'index' in value:
                        texture=doc['textures'][value['index']]
                        value['index']=imgs[texture['source']]['sha256']
        return mats
    joints=[];weight_errors=[];invalid_joints=0
    for mesh in b['meshes']:
        for p in mesh['primitives']:
            js=accessor(b,bb,p['attributes']['JOINTS_0']);ws=accessor(b,bb,p['attributes']['WEIGHTS_0'])
            joints+=js;weight_errors.extend(abs(sum(w)-1) for w in ws)
            invalid_joints+=sum(j>=len(b['skins'][0]['joints']) for row in js for j in row)
    return {'source_sha256':hashlib.sha256(ar).hexdigest(),'export_sha256':hashlib.sha256(br).hexdigest(),
        'source_vertices':va,'export_vertices':vb,'source_triangles':ta,'export_triangles':tb,
        'position_uv_multiset_equal_rounded_1e6':sa==sb,'position_uv_missing_signatures':sum((sa-sb).values()),
        'position_uv_extra_signatures':sum((sb-sa).values()),'triangle_position_uv_oriented_multiset_equal_rounded_1e6':fa==fb,
        'triangle_position_uv_oriented_multiset_equal_exact':ea==eb,
        'texture_slot_semantic_materials_equal':material_meaning(a,ia)==material_meaning(b,ib),
        'matched_signature_max_position_component_error':max_position_error,'matched_signature_max_uv_component_error':max_uv_error,'source_images':ia,'export_images':ib,
        'embedded_texture_hash_multiset_equal':Counter(i['sha256'] for i in ia)==Counter(i['sha256'] for i in ib),
        'source_materials':a.get('materials'),'export_materials':b.get('materials'),
        'materials_json_equal':a.get('materials')==b.get('materials'),'normal_comparison':normal_review,
        'source_extensions_used':a.get('extensionsUsed',[]),'export_extensions_used':b.get('extensionsUsed',[]),
        'source_extensions_required':a.get('extensionsRequired',[]),'export_extensions_required':b.get('extensionsRequired',[]),
        'source_samplers':a.get('samplers',[]),'export_samplers':b.get('samplers',[]),
        'skin_count':len(b.get('skins',[])),'joint_count':len(b['skins'][0]['joints']),
        'animation_count':len(b.get('animations',[])),'max_weight_sum_error':max(weight_errors),'invalid_joint_indices':invalid_joints,
        'limits':'Rounded vertex+UV multiset allows exporter reorder; node transforms, shading and tangents need separate validation and real rendering. Not a full PBR equivalence certification.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('exported',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=audit_export(a.source,a.exported);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:r[k] for k in ['position_uv_multiset_equal_rounded_1e6','embedded_texture_hash_multiset_equal','materials_json_equal','skin_count','joint_count','animation_count']}))
