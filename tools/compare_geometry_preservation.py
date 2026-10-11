"""Compare unchanged vertex ordering, texture payloads and real render frames."""
import argparse
import hashlib
import json
import math
from pathlib import Path
if __package__:
    from .rig_readiness_audit import read_glb, accessor, audit
else:
    from rig_readiness_audit import read_glb, accessor, audit


def compare(original, candidate, before, after):
    a,ab,ar=read_glb(original);b,bb,br=read_glb(candidate)
    pa=a['meshes'][0]['primitives'][0];pb=b['meshes'][0]['primitives'][0]
    positions=accessor(a,ab,pa['attributes']['POSITION']);new_positions=accessor(b,bb,pb['attributes']['POSITION'])
    if len(positions)!=len(new_positions):raise ValueError('Vertex count changed; cannot assert stable source IDs')
    changed=[i for i,(p,q) in enumerate(zip(positions,new_positions)) if p!=q]
    maps=[]
    for i,image in enumerate(a['images']):
        va=a['bufferViews'][image['bufferView']];vb=b['bufferViews'][b['images'][i]['bufferView']]
        def digest(data,view):
            start=view.get('byteOffset',0)
            return hashlib.sha256(data[start:start+view['byteLength']]).hexdigest()
        ha,hb=digest(ab,va),digest(bb,vb)
        maps.append({'name':image.get('name'),'source_sha256':ha,'candidate_sha256':hb,'identical':ha==hb})
    from PySide6.QtGui import QImage
    frames={}
    for path in sorted(Path(before).glob('*.png')):
        other=Path(after)/path.name
        x=QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
        y=QImage(str(other)).convertToFormat(QImage.Format.Format_RGBA8888)
        if x.isNull() or y.isNull() or x.size()!=y.size():raise ValueError('Missing or differently sized comparison image')
        ba,bc=bytes(x.constBits()),bytes(y.constBits())
        frames[path.name]={'identical_rgba':ba==bc,'source_rgba_sha256':hashlib.sha256(ba).hexdigest(),
                           'candidate_rgba_sha256':hashlib.sha256(bc).hexdigest(),
                           'changed_pixels':0 if ba==bc else sum(ba[i:i+4]!=bc[i:i+4] for i in range(0,len(ba),4))}
    if len(frames)!=9:raise ValueError('Expected all nine comparable real inspection views')
    original_audit,candidate_audit=audit(original),audit(candidate)
    return {'source_sha256':hashlib.sha256(ar).hexdigest(),'candidate_sha256':hashlib.sha256(br).hexdigest(),
            'changed_vertex_ids':changed,'vertex_count':len(positions),
            'maximum_displacement':max((math.dist(positions[i],new_positions[i]) for i in changed),default=0),
            'normal_arrays_identical':accessor(a,ab,pa['attributes']['NORMAL'])==accessor(b,bb,pb['attributes']['NORMAL']),
            'uv_arrays_identical':accessor(a,ab,pa['attributes']['TEXCOORD_0'])==accessor(b,bb,pb['attributes']['TEXCOORD_0']),
            'materials_identical':a['materials']==b['materials'],'texture_descriptors_identical':a['textures']==b['textures'],
            'texture_maps':maps,'aabb_identical':original_audit['bounding_box']==candidate_audit['bounding_box'],
            'protected_face_vertices':sum(p[0]<-.35 and p[1]>.4 for p in positions),
            'changed_protected_face_vertex_ids':[i for i in changed if positions[i][0]<-.35 and positions[i][1]>.4],
            'frame_comparison':frames,'scope':'base-color inspection preview, not full PBR, weights or animated deformation'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original',type=Path);p.add_argument('candidate',type=Path)
    p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=compare(a.original,a.candidate,a.before,a.after)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({'changed_vertices':r['changed_vertex_ids'],'all_maps_identical':all(v['identical'] for v in r['texture_maps']),
                      'identical_frames':sum(v['identical_rgba'] for v in r['frame_comparison'].values()),'total_frames':len(r['frame_comparison'])}))
