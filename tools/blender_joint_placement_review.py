"""Read-only ray-parity diagnostic, not anatomical certification.
Self-intersections, fur and ray tangencies limit inside/outside interpretation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_geometry_analysis import mesh_data
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def parity_at(tree, center):
    center=Vector(center);votes=[]
    for direction in [(1,.137,.231),(.191,1,.117),(.151,.113,1)]:
        direction=Vector(direction).normalized();q=center.copy();hits=0
        for _ in range(100):
            co,_,_,distance=tree.ray_cast(q,direction,5)
            if co is None:break
            hits+=1;q=co+direction*1e-6
        else:raise ValueError('Ray did not complete; do not classify ambiguous geometry')
        votes.append(hits)
    return votes


def review(source, landmarks, output):
    points,faces,_,sha=mesh_data(source)
    cfg=json.loads(landmarks.read_text())
    if sha not in cfg['accepted_geometry_sha256']:raise ValueError('Landmarks do not match source')
    tree=BVHTree.FromPolygons(points,faces,all_triangles=True)
    result={}
    for name,info in cfg['regions'].items():
        center=Vector(info['center']);_,_,_,distance=tree.find_nearest(center)
        votes=parity_at(tree,center)
        result[name]={'center_gltf':info['center'],'nearest_surface_distance':distance,
            'positive_ray_hit_counts':votes,'odd_parity_votes':sum(v%2 for v in votes),
            'limits':'Provisional parity on self-intersecting furry mesh; not certified anatomical bone center.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({n:v['odd_parity_votes'] for n,v in result.items()}))

def review_bones(source, report, output):
    points,faces,_,sha=mesh_data(source);r=json.loads(report.read_text())
    if sha!=r['source_sha256']:raise ValueError('Bone report source mismatch')
    tree=BVHTree.FromPolygons(points,faces,all_triangles=True)
    out={}
    for name,spec in r['bones'].items():
        out[name]={}
        for key in ('head_gltf','tail_gltf'):
            center=spec[key];hits=parity_at(tree,center)
            _,_,_,distance=tree.find_nearest(Vector(center))
            out[name][key]={'position':center,'odd_parity_votes':sum(n%2 for n in hits),
                            'nearest_surface_distance':distance,'ray_hits':hits}
    output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({n:{k:v['odd_parity_votes'] for k,v in s.items()} for n,s in out.items()}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('source','output'):parser.add_argument('--'+key,type=Path,required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--landmarks',type=Path);group.add_argument('--bones-report',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.landmarks:review(args.source,args.landmarks,args.output)
    else:review_bones(args.source,args.bones_report,args.output)
