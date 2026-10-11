"""Explicit microscopic boundary collapse, separate output, no remesh or rig.

Asset-specific reviewed operation: source vertex 5276 -> existing 5278 position.
This closes the collinear three-edge boundary left by exact-degenerate cleanup.
Vertex/UV seams are NOT merged: only one position changes and one newly
zero-area triangle is omitted. Callers must provide the expected source hash.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
if __package__:
    from .rig_readiness_audit import read_glb, accessor, audit
    from .rig_geometry_analysis import mesh_data, edge_faces
else:
    from rig_readiness_audit import read_glb, accessor, audit
    from rig_geometry_analysis import mesh_data, edge_faces


def cross(a,b,c):
    u,v=([b[k]-a[k] for k in range(3)],[c[k]-a[k] for k in range(3)])
    return (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])


def repair(source, output, expected_sha, vertex=5276, anchor=5278, limit=1e-6):
    source,output=Path(source),Path(output)
    if source.resolve()==output.resolve() or output.exists():
        raise ValueError('Output must be a new separate file')
    doc,binary,raw=read_glb(source)
    if hashlib.sha256(raw).hexdigest()!=expected_sha:
        raise ValueError('Unexpected source SHA-256')
    audit(source)
    ps,faces,sources,_=mesh_data(source)
    edges=edge_faces(faces)
    boundary={e for e,fs in edges.items() if len(fs)==1}
    if len(boundary)!=3 or len({v for e in boundary for v in e})!=3:
        raise ValueError('Expected a reviewed three-edge boundary, no generic hole fill')
    moved=next(i for i,ids in sources.items() if vertex in ids)
    anchored=next(i for i,ids in sources.items() if anchor in ids)
    if len(sources[moved]) != 1:
        raise ValueError('Moved position has attribute seam duplicates; manual mask required')
    if tuple(sorted((moved,anchored))) not in boundary:
        raise ValueError('Collapse must follow the reviewed boundary edge')
    primitive=doc['meshes'][0]['primitives'][0]
    acc=doc['accessors'][primitive['attributes']['POSITION']]
    view=doc['bufferViews'][acc['bufferView']]
    old=accessor(doc,binary,primitive['attributes']['POSITION'])
    target=old[anchor]
    delta=math.dist(old[vertex],target)
    if not math.isfinite(limit) or not 0<limit<=1e-6 or not 0<delta<=limit:
        raise ValueError('Displacement exceeds microscopic correction limit')
    new=list(old)
    new[vertex]=target
    indices=[v[0] for v in accessor(doc,binary,primitive['indices'])]
    kept,removed,angles=[],[],[]
    for offset in range(0,len(indices),3):
        tri=indices[offset:offset+3]
        before=cross(*(old[i] for i in tri))
        after=cross(*(new[i] for i in tri))
        if after==(0,0,0):
            if vertex not in tri:
                raise ValueError('Unrelated degenerate triangle: source must be cleaned first')
            removed.append(offset//3)
        else:
            if vertex in tri:
                la=math.sqrt(sum(x*x for x in before));lb=math.sqrt(sum(x*x for x in after))
                dot=sum(x*y for x,y in zip(before,after))/(la*lb)
                if dot<=0:
                    raise ValueError('Local correction would flip an incident face')
                angles.append(math.degrees(math.acos(min(1,max(-1,dot)))))
            kept.extend(tri)
    if len(removed)!=1:
        raise ValueError('Expected exactly one newly collapsed local triangle')
    patched=bytearray(binary[:doc['buffers'][0]['byteLength']])
    location=view.get('byteOffset',0)+acc.get('byteOffset',0)+vertex*view.get('byteStride',12)
    struct.pack_into('<3f',patched,location,*target)
    patched.extend(b'\0'*(-len(patched)%4))
    index_offset=len(patched)
    index_bytes=struct.pack('<'+'I'*len(kept),*kept)
    patched.extend(index_bytes)
    primitive['indices']=len(doc['accessors'])
    doc['accessors'].append({'bufferView':len(doc['bufferViews']),'componentType':5125,'type':'SCALAR',
                             'count':len(kept),'min':[min(kept)],'max':[max(kept)]})
    doc['bufferViews'].append({'buffer':0,'byteOffset':index_offset,'byteLength':len(index_bytes),'target':34963})
    # Reviewed position is interior to original AABB; preserve min/max metadata.
    for axis in range(3):
        if target[axis]<min(p[axis] for p in old) or target[axis]>max(p[axis] for p in old):
            raise ValueError('Target outside original bounds')
    doc['buffers'][0]['byteLength']=len(patched)
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4)
    patched.extend(b'\0'*(-len(patched)%4))
    body=struct.pack('<II',len(encoded),0x4E4F534A)+encoded+struct.pack('<II',len(patched),0x004E4942)+patched
    candidate=struct.pack('<4sII',b'glTF',2,len(body)+12)+body
    # Verify closure using the prospective exact-coordinate analysis, no GLB write yet.
    changed_points=list(ps);changed_points[moved]=ps[anchored]
    canonical={};remap=[]
    for p in changed_points:
        if p not in canonical:canonical[p]=len(canonical)
        remap.append(canonical[p])
    topology_faces=[tuple(remap[v] for v in f) for i,f in enumerate(faces) if i not in removed]
    after_edges=edge_faces(topology_faces)
    if any(len(fs)!=2 for fs in after_edges.values()):
        raise ValueError('Correction does not close boundary as an edge manifold')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(candidate)
    return {'source':str(source),'source_sha256':expected_sha,'output':str(output),
            'candidate_sha256':hashlib.sha256(candidate).hexdigest(),
            'changed_source_vertex_ids':[vertex],'anchor_source_vertex_id':anchor,
            'position_before':list(old[vertex]),'position_after':list(target),
            'maximum_displacement':delta,'removed_source_triangle_ids':removed,
            'retained_incident_normal_angle_max_degrees':max(angles,default=0),
            'boundary_edges_before':3,'boundary_edges_after':0,
            'scope':'microscopic local boundary cleanup only; no anatomical repositioning or rig-ready claim'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--expected-sha256',required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();result=repair(a.source,a.output,a.expected_sha256)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
