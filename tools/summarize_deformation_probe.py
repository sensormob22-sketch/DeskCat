"""Read-only factual summary and conservative scores for a non-production skin probe."""
import argparse
import json
import math
from pathlib import Path
from statistics import median
if __package__:
    from .rig_readiness_audit import read_glb,accessor
else:
    from rig_readiness_audit import read_glb,accessor


def positions(path):
    d,b,_=read_glb(path)
    return accessor(d,b,d['meshes'][0]['primitives'][0]['attributes']['POSITION'])


def summarize(source, snapshots, deformation, feet_report, output):
    rest=positions(source);report=json.loads(deformation.read_text());feet=json.loads(feet_report.read_text())['paw_surface_segmentation']['feet']
    measurements={}
    for name in ('rest','front_bend','hind_bend','pelvis_spine','tail_bend'):
        posed=positions(snapshots/f'{name}.glb')
        if len(posed)!=len(rest):raise ValueError('Snapshot source vertex order is required')
        paws={}
        for foot,info in feet.items():
            ids=info['source_vertex_ids'];sample=ids[::max(1,len(ids)//24)][:24]
            before=[math.dist(rest[a],rest[b]) for i,a in enumerate(sample) for b in sample[i+1:]]
            after=[math.dist(posed[a],posed[b]) for i,a in enumerate(sample) for b in sample[i+1:]]
            errors=[abs(a-b) for a,b in zip(before,after)]
            paws[foot]={'sampled_internal_distance_pairs':len(before),'rigid_shape_max_pair_distance_error':max(errors),
                        'min_y':min(posed[i][1] for i in ids),
                        'height_change':min(posed[i][1] for i in ids)-min(rest[i][1] for i in ids),
                        'floor_contact_status':'not enforced; this is an unconstrained pose, not a gait'}
        protected=[i for i,v in enumerate(rest) if v[0]<-.35 and v[1]>.30]
        measurements[name]={'paw_rigidity_and_floor':paws,'protected_head_source_vertices':len(protected),
                            'protected_head_max_displacement':max(math.dist(rest[i],posed[i]) for i in protected)}
    scores={}
    for pose,p in report['poses'].items():
        if not pose.startswith('isolated_'):continue
        name=pose[len('isolated_'):]
        if p['new_pairs'] or p['edge_ratio_max']>2 or p['edge_ratio_min']<.5:
            grade='FAIL_EXPERIMENTAL_WEIGHTS'
        elif p['area_below_half_faces'] or p['edge_ratio_max']>1.25 or p['edge_ratio_min']<.8:
            grade='REVIEW_NOT_ACCEPTED'
        else:grade='LIMITED_PROBE_PASS_NOT_PRODUCTION'
        scores[name]={'grade':grade,'relative_bend_degrees':p['rotations_degrees_about_blender_world_y'][name],
                      'new_crossing_pairs':p['new_pairs'],'edge_ratio_min':p['edge_ratio_min'],'edge_ratio_max':p['edge_ratio_max'],
                      'faces_area_below_half':p['area_below_half_faces'],
                      'warning':'Whole-mesh extrema can be dominated by tiny fur triangles; grade is a conservative diagnostic, not anatomy certification.'}
    result={'measurements':measurements,'joint_scores':scores,
            'score_criteria':'FAIL: any new strict crossing pair or edge ratio outside [0.5,2]. REVIEW: any face area below half or edge ratio outside [0.8,1.25]. Other: limited small-angle probe only. Visual/anatomical signoff still required.',
            'decision':'REJECT_CURRENT_SKIN; REFINE_BONE_AND_WEIGHT_MASKS_BEFORE_GEOMETRY_SURGERY',
            'reason':'Crossings respond strongly to weights. No proof yet that deleting/smoothing original fur is necessary. Tail root, right shoulder, hip/groin and spine envelopes need manual masks and narrower pose retest.'}
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','snapshots','deformation','feet-report','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=summarize(a.source,a.snapshots,a.deformation,a.feet_report,a.output)
    print(json.dumps({n:r['grade'] for n,r in r['joint_scores'].items()}))
