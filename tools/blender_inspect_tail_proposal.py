"""Read original scene and evaluate its existing +15 pose, never apply the proposal."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from blender_deformation_probe import inverse, pair_set
from rig_geometry_analysis import mesh_data


def inspect(root, output, points_output):
    data = root / 'docs/model-reports/stage9/data'
    masks = json.loads((data / 'region_masks.json').read_text())
    scene = root / 'assets/rigging/deskcat_v6_weight_handoff.blend'
    scene_sha = hashlib.sha256(scene.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    mesh = bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS']
    rig = bpy.data.objects['V6_17_BONES_UNVERIFIED']
    names = [bone.name for bone in rig.data.bones]
    def weights():
        result = np.zeros((len(mesh.data.vertices), len(names)), dtype='<f4')
        for v in mesh.data.vertices:
            for group in v.groups:
                name = mesh.vertex_groups[group.group].name
                if name in names:
                    result[v.index, names.index(name)] = group.weight
        return result
    before = weights()
    digest = hashlib.sha256(before.tobytes()).hexdigest()
    if digest != masks['bone_weight_sha256_float32']:
        raise ValueError('Unexpected pre-export Blender weights')
    for key, row in masks['baseline_vertex_weights'].items():
        if any(before[int(key), names.index(n)] != w for n, w in row.items()):
            raise ValueError('JSON baseline does not match actual scene')
    rest = np.array([inverse(mesh.matrix_world @ v.co) for v in mesh.data.vertices])
    faces = np.array([poly.vertices[:] for poly in mesh.data.polygons])
    # Reuse the existing diagnostic operator: no vertex group additions or changes.
    exec(compile(bpy.data.texts['DESKCAT_REVIEW_UI.py'].as_string(), 'review_ui', 'exec'), {'__name__': '__main__'})
    bpy.context.scene.deskcat_zone = 'tail_to_pelvis'
    bpy.context.scene.deskcat_pose = 'plus15'
    bpy.ops.deskcat.review_pose()
    evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    temporary = evaluated.to_mesh()
    posed = np.array([inverse(evaluated.matrix_world @ v.co) for v in temporary.vertices])
    evaluated.to_mesh_clear()
    source = root / 'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
    canonical, canonical_faces, sources, _ = mesh_data(source)
    first = [sources[i][0] for i in range(len(canonical))]
    baseline = {tuple(p) for p in json.loads((data / 'pose_review.json').read_text())['baseline_pairs']}
    new_pairs = pair_set(posed[first], canonical_faces) - baseline
    if len(new_pairs) != 44:
        raise ValueError('Unchanged +15 baseline does not reproduce 44 new pairs')
    problem_faces = {}
    for fid in (6971, 7816, 7323, 7586):
        ids = faces[fid]
        def area(ps):
            a, b, c = ps[ids]
            return float(np.linalg.norm(np.cross(b-a, c-a)) / 2)
        problem_faces[str(fid)] = {'source_vertex_ids': ids.tolist(), 'rest_area': area(rest),
                                   'current_plus15_area': area(posed), 'current_area_ratio': area(posed) / area(rest)}
    bpy.context.scene.deskcat_pose = 'rest'
    bpy.ops.deskcat.review_pose()
    after = weights()
    if not np.array_equal(before, after) or hashlib.sha256(scene.read_bytes()).hexdigest() != scene_sha:
        raise ValueError('Inspection changed weights or scene file')
    result = {'status': 'ORIGINAL_SCENE_INSPECTED_NO_PROPOSAL_APPLIED', 'blender': bpy.app.version_string,
              'scene_sha256': scene_sha, 'bone_weight_sha256_float32': digest,
              'all_5330_baseline_rows_match_actual_blender': True, 'all_weights_unchanged_in_memory': True,
              'scene_file_unchanged': True, 'current_plus15_new_pairs': len(new_pairs),
              'C1_present': [6971, 7816] in [list(p) for p in new_pairs],
              'C2_present': [7323, 7586] in [list(p) for p in new_pairs], 'problem_faces': problem_faces,
              'bone_pivots_gltf': {n: {'head': inverse(rig.matrix_world @ rig.data.bones[n].head_local),
                                       'tail': inverse(rig.matrix_world @ rig.data.bones[n].tail_local),
                                       'parent': rig.data.bones[n].parent.name} for n in ('pelvis', 'tail_base')},
              'animation_actions': len(bpy.data.actions), 'new_glb_exported': False,
              'limits': 'Only existing v6 +15 deformation was evaluated; proposed weights never installed or evaluated.'}
    output.write_text(json.dumps(result, indent=2) + '\n')
    points_output.write_text(json.dumps({'rest': rest.tolist(), 'current_plus15': posed.tolist()}) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--points-output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    inspect(args.root, args.output, args.points_output)
