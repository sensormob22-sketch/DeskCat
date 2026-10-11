"""Read-only UV-seam and actual Panda morph crossing audit of fixed outputs."""
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from blender_deformation_probe import pair_set
from rig_geometry_analysis import mesh_data

root=Path.cwd();out=root/'docs/model-reports/stage12';r=json.loads((out/'comparison.json').read_text())
_,faces,aliases,_=mesh_data(root/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb');first=[aliases[i][0] for i in range(len(aliases))];old={tuple(x) for x in r['baseline_pairs']}
definitions=json.loads((out/'cage_definitions.json').read_text())
mask={c['zone']:{int(i):v for i,v in c['source_mask'].items()} for c in definitions['cages']}
mask_mismatches=[]
for entries in aliases.values():
    if len(entries)<2:continue
    spread={n:max(m.get(i,0) for i in entries)-min(m.get(i,0) for i in entries) for n,m in mask.items()}
    if max(spread.values())>1e-12:mask_mismatches.append({'source_vertex_ids':entries,'mask_weights':{n:[m.get(i,0) for i in entries] for n,m in mask.items()}})
cases={};actual={}
for case in r['cases']:
    ps=np.load(root/f'artifacts/stage12_cage/cage_{case}.npz')['positions'];bad=[]
    for entries in aliases.values():
        if len(entries)<2:continue
        gap=float(np.linalg.norm(ps[entries]-ps[entries[0]],axis=1).max())
        if gap>1e-6:bad.append({'source_vertex_ids':entries,'gap':gap,'position_gltf':ps[entries[0]].tolist(),'mask_weights':{n:[m.get(i,0) for i in entries] for n,m in mask.items()}})
    cases[case]={'split_exact_position_alias_sets_above_1e6':len(bad),'largest_20':sorted(bad,key=lambda x:-x['gap'])[:20]}
    raw=(root/f'artifacts/stage12_panda/{case}.f32').read_bytes();points=np.array(list(struct.iter_unpack('<3f',raw)))
    pairs=pair_set(points[first],faces);new=pairs-old;reference={tuple(p) for p in r['models']['cage'][case]['new_source_face_pairs']}
    actual[case]={'new_pairs':len(new),'same_pair_set_as_blender_snapshot':new==reference,'only_in_panda':sorted(new-reference),'only_in_snapshot':sorted(reference-new)}
(out/'seam_and_runtime_audit.json').write_text(json.dumps({'mask_alias_mismatches':mask_mismatches,'cases':cases,'actual_panda_crossings':actual,'diagnosis':'Fixed boundary feather masks were not collapsed to canonical exact-position aliases. Different local modifier/complement values split some UV aliases. This trial fails continuity; no corrective second cycle was applied.'},indent=2)+'\n')
