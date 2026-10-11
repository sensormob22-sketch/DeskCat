"""Audit actual Panda3D deformed vertex captures; does not open/change any scene."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from blender_deformation_probe import pair_set
from rig_geometry_analysis import mesh_data

def run(source,report_path,capture_path,work,output):
    report=json.loads(report_path.read_text());capture=json.loads(capture_path.read_text())
    rest,faces,sources,_=mesh_data(source);rest=np.array(rest);faces=np.array(faces);first=[sources[i][0] for i in range(len(rest))]
    baseline={tuple(p) for p in report['baseline_pairs']}
    tris=rest[faces];areas=np.linalg.norm(np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]),axis=1)/2
    edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
    lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
    source_to_canonical={j:i for i,aliases in sources.items() for j in aliases}
    regions={n:{source_to_canonical[i] for i in ids} for n,ids in report['regions_source_vertex_ids'].items()}
    mask={n:np.array([i in ids for i in range(len(rest))]) for n,ids in regions.items()}
    def stats(values):return {'min':float(values.min(initial=1)),'max':float(values.max(initial=1)),'p1_p5_p50_p95_p99':np.percentile(values,[1,5,50,95,99]).tolist()}
    outcomes={};positions={}
    for model,data in capture['models'].items():
        cases={}
        for case,evidence in data['poses'].items():
            ps=np.fromfile(evidence['positions_f32'],dtype='<f4').reshape(-1,3)
            if len(ps)!=evidence['source_vertex_count']:raise ValueError('Capture size mismatch')
            cp=ps[first];pairs=pair_set(cp,faces.tolist());new=pairs-baseline
            tri=cp[faces];a=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
            l=np.linalg.norm(cp[edges[:,0]]-cp[edges[:,1]],axis=1)
            ar=np.divide(a,areas,out=np.ones_like(a),where=areas>1e-14);er=np.divide(l,lengths,out=np.ones_like(l),where=lengths>1e-10)
            # Keep precision differences separate from the proposal and cutoff.
            counterpart='v6' if model=='v6_export' else 'c2_trial'
            blend=np.load(work/f'{counterpart}_{case}.npz')['positions']
            error=np.linalg.norm(ps-blend,axis=1)
            regional={}
            for n,vm in mask.items():
                fm=vm[faces].any(axis=1);em=vm[edges].any(axis=1)
                regional[n]={'new_pairs':sum(any(vm[v] for f in pair for v in faces[f]) for pair in new),
                             'area_ratio':stats(ar[fm]),'edge_ratio':stats(er[em]),
                             'area_below_half':int((ar[fm]<.5).sum()),'area_above_double':int((ar[fm]>2).sum())}
            same={tuple(p) for p in report['baseline' if model=='v6_export' else 'trial'][case]['new_source_face_pairs']}
            cases[case]={'new_pairs':len(new),'retained_baseline_pairs':len(pairs&baseline),
                         'new_source_face_pairs':[list(p) for p in sorted(new)],'C1_intersects':(6971,7816) in pairs,'C2_intersects':(7323,7586) in pairs,
                         'area_ratio':stats(ar),'edge_ratio':stats(er),'regions':regional,
                         'panda_vs_preexport_blender_position_error_max':float(error.max()),
                         'added_vs_preexport_blender_pairs':[list(p) for p in sorted(new-same)],
                         'removed_vs_preexport_blender_pairs':[list(p) for p in sorted(same-new)],
                         'seam_gap_max':max(float(np.linalg.norm(ps[aliases]-ps[aliases[0]],axis=1).max()) for aliases in sources.values())}
            positions[(model,case)]=ps;print(model,case,len(new),float(error.max()),flush=True)
        outcomes[model]=cases
    comparison={}
    ids=set(report['changed_source_vertex_ids']);outside=[i for i in range(len(next(iter(positions.values())))) if i not in ids]
    for case in report['trial']:
        a=outcomes['v6_export'][case];b=outcomes['c2_export'][case]
        before={tuple(x) for x in a['new_source_face_pairs']};after={tuple(x) for x in b['new_source_face_pairs']}
        difference=np.linalg.norm(positions[('v6_export',case)]-positions[('c2_export',case)],axis=1)
        comparison[case]={'v6_export_new_pairs':a['new_pairs'],'c2_export_new_pairs':b['new_pairs'],
                          'added_pairs':[list(p) for p in sorted(after-before)],'removed_pairs':[list(p) for p in sorted(before-after)],
                          'max_displacement_between_exports':float(difference.max()),'outside_approved_ids_error_max':float(difference[outside].max()),
                          'C1_vertex_displacement':float(difference[[3789,3791,3793,4258,4260,4261]].max())}
    output.write_text(json.dumps({'status':'ACTUAL_PANDA3D_EXPORTED_SKIN_DEFORMATION_AUDITED','baseline_pairs':sorted(baseline),'models':outcomes,
                                  'comparisons':comparison,'limits':'Same strict crossing detector as Blender. Panda floats, bind matrices and exporter cutoff may change marginal pair membership; reported explicitly.'},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','report','capture','work','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.report,a.capture,a.work,a.output)
