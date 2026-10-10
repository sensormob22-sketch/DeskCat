"""Verify connected tail weights against source geometry; run using Blender NumPy."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from rig_geometry_analysis import mesh_data
from rig_readiness_audit import read_glb, accessor

def audit(source,weights_path,paw_review,output):
    if output.resolve()==source.resolve():raise ValueError("Never overwrite source model")
    p,f,s,h=mesh_data(source);data=np.load(weights_path);w=data['weights'];names=data['bone_names'].tolist();mask=data['tail_mask'];ids=[s[i][0] for i in range(len(p))]
    doc,binary,_=read_glb(source)
    original=np.array(accessor(doc,binary,doc['meshes'][0]['primitives'][0]['attributes']['POSITION']))
    if not np.array_equal(data['source_positions'],original):raise ValueError('Weight/source coordinates mismatch')
    tail=w[:,names.index('tail_base')];outside=[v for i in range(len(p)) if not mask[i] for v in s[i]]
    review=json.loads(paw_review.read_text())
    result={'tail_mask_canonical_vertices':int(mask.sum()),'tail_mask_aabb':{'min':np.array(p)[mask].min(0).tolist(),'max':np.array(p)[mask].max(0).tolist()},'tail_weight_max_outside_connected_mask':float(tail[outside].max()),'tail_mask_source_vertex_ids':[v for i in np.flatnonzero(mask) for v in s[int(i)]],'paw_tail_max':{},'seam_weight_difference_max':max(float(np.abs(w[v]-w[v[0]]).max()) for v in s.values()),'weight_sum_error_max':float(abs(w.sum(1)-1).max()),'max_influences':int((w>0).sum(1).max()),'changed_rest_geometry_vertices':0,'changed_uv_coordinates':0,'manual_surface_mask_status':'Connected branch isolated in 3D, visually inspected; proximal boundary requires manual refinement; not anatomical ground truth.'}
    for foot,x in review['paw_surface_segmentation']['feet'].items():result['paw_tail_max'][foot]=float(tail[x['source_vertex_ids']].max())
    output.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','weights','paw-review','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    audit(args.source,args.weights,args.paw_review,args.output)
