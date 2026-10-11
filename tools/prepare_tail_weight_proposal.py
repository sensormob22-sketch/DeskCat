"""Prepare a single-zone, review-only JSON diff. No Blender mutation or export."""
import argparse
import hashlib
import json
import math
from pathlib import Path

if __package__:
    from .rig_readiness_audit import read_glb, accessor
    from .weight_handoff_contract import validate_proposal, source_skin_weights
else:
    from rig_readiness_audit import read_glb, accessor
    from weight_handoff_contract import validate_proposal, source_skin_weights

PAIRS = {'C1': [6971, 7816], 'C2': [7323, 7586]}


def prepare(root, output):
    if output.exists():
        raise ValueError('Use a new output directory')
    data = root / 'docs/model-reports/stage9/data'
    masks = json.loads((data / 'region_masks.json').read_text())
    source = root / 'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
    skin = root / 'assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb'
    scene = root / 'assets/rigging/deskcat_v6_weight_handoff.blend'
    doc, binary, _ = read_glb(source)
    prim = doc['meshes'][0]['primitives'][0]
    positions = accessor(doc, binary, prim['attributes']['POSITION'])
    flat = [x[0] for x in accessor(doc, binary, prim['indices'])]
    faces = [flat[i:i+3] for i in range(0, len(flat), 3)]
    adjacent = [set() for _ in positions]
    seams = {}
    for i, point in enumerate(positions):
        seams.setdefault(tuple(point), []).append(i)
    for face in faces:
        for i in face:
            adjacent[i].update(set(face) - {i})
    other = set().union(*(set(z['editable_source_vertex_ids'])
                        for n, z in masks['zones'].items() if n != 'tail_to_pelvis'))
    protected = set(masks['protected_source_vertex_ids'])
    allowed = set(masks['zones']['tail_to_pelvis']['editable_source_vertex_ids']) - other - protected
    core = {i for f in PAIRS['C2'] for i in faces[f]}
    support = core | set().union(*(adjacent[i] for i in core))
    # Frozen context contributes to the desired gradient, but is never selected.
    eligible = {i for i in support if set(seams[tuple(positions[i])]) <= allowed}
    names, _, _ = source_skin_weights(source, skin)
    baseline = masks['baseline_vertex_weights']
    changes, measurements = [], []
    handled = set()
    for i in sorted(eligible):
        if i in handled:
            continue
        copies = seams[tuple(positions[i])]
        row = baseline[str(i)]
        if any(any(abs(baseline[str(j)].get(n, 0)-row.get(n, 0)) > 1e-7 for n in names) for j in copies):
            raise ValueError('Baseline seam disagreement; requires a separate decision')
        neighbors = sorted(set().union(*(adjacent[j] for j in copies)) - set(copies))
        if any(str(j) not in baseline for j in neighbors):
            raise ValueError('Neighbor missing original Blender baseline')
        influence = [1 / max(math.dist(positions[i], positions[j]), 1e-8) for j in neighbors]
        target = sum(a * baseline[str(j)].get('tail_base', 0) for a, j in zip(influence, neighbors)) / sum(influence)
        rate, cap = (.25, .015) if set(copies) & core else (.125, .0075)
        delta = max(-cap, min(cap, rate * (target - row.get('tail_base', 0))))
        if abs(delta) < 1e-7:
            continue
        full = {n: row.get(n, 0.) for n in names}
        full['tail_base'] += delta
        # Only pelvis absorbs both the transfer and float32 normalization residue.
        full['pelvis'] = 1 - sum(w for n, w in full.items() if n != 'pelvis')
        changes.append({'source_vertex_ids': sorted(copies), 'weights': full})
        measurements.append({'source_vertex_ids': sorted(copies), 'support': 'C2_core' if set(copies) & core else 'one_edge_transition',
                             'position_gltf': positions[i], 'neighbor_ids': neighbors,
                             'baseline_weights': row, 'local_tail_weight_target': target,
                             'tail_weight_delta': delta, 'proposal_weights': full})
        handled.update(copies)
    proposal = json.loads((root / 'docs/model-reports/stage9/proposal_template.json').read_text())
    proposal.update(human_annotation='Stage10 review-only C2 proximal surface patch; C1 frozen because all six vertices overlap other region masks.',
                    changes=changes, approval_reference=None,
                    limits='Not applied. Proposed influence diagrams are not deformed output. Requires approval of this exact JSON before any application/export.')
    validation = validate_proposal(proposal, masks, source, skin, scene)
    ids = {i for e in changes for i in e['source_vertex_ids']}
    if ids & (other | protected) or not ids <= allowed:
        raise ValueError('Frozen region violation')
    # Source graph connectivity across exact-position seam aliases.
    visited = set()
    pending = [min(ids)]
    while pending:
        i = pending.pop()
        if i in visited:
            continue
        visited.add(i)
        pending.extend((adjacent[i] | set(seams[tuple(positions[i])])) & ids - visited)
    if visited != ids:
        raise ValueError('Selected patch is not contiguous')
    report = {'status': 'PROPOSAL_ONLY_NOT_APPLIED', 'changed_source_vertex_ids': sorted(ids),
              'changed_vertex_count': len(ids), 'weight_rows': len(changes),
              'max_absolute_weight_delta': max(abs(e['weights'][n] - baseline[str(i)].get(n, 0)) for e in changes for i in e['source_vertex_ids'] for n in names),
              'protected_vertex_overlap': sorted(ids & protected), 'other_five_edit_masks_overlap': sorted(ids & other),
              'protected_vertex_count': len(protected), 'patch_connected': visited == ids,
              'source_vertex_ids_basis': 'Unmodified localprep source order; matches delivered Blender vertex IDs, not exported v6 GLB order.',
              'C1_C2': {label: {'source_face_pair': pair, 'vertices': [
                  {'source_face_id': f, 'source_vertex_ids': faces[f],
                   'weights': {str(i): baseline[str(i)] for i in faces[f]},
                   'frozen_other_region_vertices': sorted(set(faces[f]) & other)} for f in pair],
                  'one_edge_neighbors': [{'source_vertex_id': i, 'position_gltf': positions[i],
                    'baseline_weights': baseline.get(str(i)),
                    'other_edit_regions': [n for n,z in masks['zones'].items() if n != 'tail_to_pelvis' and i in z['editable_source_vertex_ids']],
                    'proposed': i in ids} for i in sorted(set().union(*(adjacent[i] for f in pair for i in faces[f])) - {i for f in pair for i in faces[f]})]}
                  for label, pair in PAIRS.items()},
              'excluded_support_vertices': sorted(support - eligible), 'algorithm': {
                  'scope': 'C2 six core vertices + eligible one-edge neighbors; no global mask or iteration',
                  'target': 'inverse-edge-length weighted mean of unchanged Blender tail_base neighbor weights',
                  'core_step': .25, 'core_delta_cap': .015, 'transition_step': .125, 'transition_delta_cap': .0075,
                  'other_bones': 'All except pelvis/tail_base frozen. All 17 bone columns provided; pelvis is normalization residual.',
                  'anatomy_limit': 'Small contiguous surface patch, not a complete circumferential ring or anatomically certified boundary. Other-zone overlap clips its boundary.'},
              'measurements': measurements, 'validation': validation,
              'weights_applied': False, 'deformation_improvement_tested': False, 'new_glb_exported': False}
    # Compare scalar influence continuity only; never evaluate a proposed skin.
    edges = {tuple(sorted((i,j))) for i in ids for j in adjacent[i]}
    new_rows = {i: e['weights'] for e in changes for i in e['source_vertex_ids']}
    continuity = {}
    for label in ('baseline', 'proposed'):
        differences = []
        for i,j in edges:
            left = new_rows.get(i, baseline[str(i)]) if label == 'proposed' else baseline[str(i)]
            right = new_rows.get(j, baseline[str(j)]) if label == 'proposed' else baseline[str(j)]
            differences.append((abs(left.get('tail_base',0)-right.get('tail_base',0)),math.dist(positions[i],positions[j])))
        continuity[label] = {'max_adjacent_tail_weight_jump': max(v for v,d in differences),
                             'sum_squared_tail_weight_jumps': sum(v*v for v,d in differences),
                             'inverse_edge_length_weighted_squared_jumps': sum(v*v/max(d,1e-8) for v,d in differences)}
    report['influence_continuity'] = {'incident_edge_count': len(edges), 'metrics': continuity,
                                     'limits': 'Scalar weight differences only, not deformed geometry, anatomy or intersection improvement.'}
    report['scope_summary'] = {
        'current_tail_edit_mask_vertices': len(masks['zones']['tail_to_pelvis']['editable_source_vertex_ids']),
        'exclusive_tail_edit_mask_vertices': len(allowed), 'proposal_vertices': len(ids),
        'unlisted_vertices_frozen': len(positions)-len(ids),
        'coincident_position_copy_count_selected': sum(len(seams[tuple(positions[i])])-1 for i in ids),
        'protected_head_and_four_sole_vertices_frozen': True,
        'other_five_edit_masks_frozen': True,
        'C1_frozen_reason': 'All six C1 vertices also belong to EDIT_left_hip; current approval scope forbids their modification.',
        'no_global_weights_modified': True}
    output.mkdir(parents=True)
    (output / 'tail_to_pelvis_proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')
    report['proposal_sha256'] = hashlib.sha256((output / 'tail_to_pelvis_proposal.json').read_bytes()).hexdigest()
    (output / 'proposal_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('changed_vertex_count', 'max_absolute_weight_delta', 'proposal_sha256')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.output)
