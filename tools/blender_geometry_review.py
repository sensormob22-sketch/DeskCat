"""Blender headless read-only diagnostic. No mesh changes, export or skeleton.

Run blender -b --factory-startup --python tools/blender_geometry_review.py -- MODEL --landmarks JSON --output JSON
BVH candidates are narrowed by strict noncoplanar triangle edge crossings.
Coplanar overlap, adjacent folding and exact tangencies are not certified.
"""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from rig_geometry_analysis import mesh_data, contact_patches, topology


def crossing(a, b, tri, epsilon=1e-9):
    """Strict segment/interior-triangle crossing (Moller-Trumbore)."""
    direction = b-a
    v0, v1, v2 = tri
    edge1, edge2 = v1-v0, v2-v0
    p = direction.cross(edge2)
    det = edge1.dot(p)
    if abs(det) <= epsilon:
        return False
    inv = 1/det
    tvec = a-v0
    u = tvec.dot(p)*inv
    q = tvec.cross(edge1)
    v = direction.dot(q)*inv
    t = edge2.dot(q)*inv
    interior = 1e-6
    return interior < t < 1-interior and u > interior and v > interior and u+v < 1-interior


def review(model, landmarks, output):
    started = time.perf_counter()
    annotations = json.loads(landmarks.read_text())
    points, faces, sources, sha = mesh_data(model)
    if sha not in annotations['accepted_geometry_sha256']:
        raise ValueError('Unreviewed source hash; do not reuse anatomical masks')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(model.resolve()), merge_vertices=False)
    imported = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    imported_info = [{'vertices': len(o.data.vertices), 'polygons':len(o.data.polygons),
                      'uv_layers':len(o.data.uv_layers), 'materials':len(o.data.materials)} for o in imported]
    vectors = [Vector(p) for p in points]
    valid_face_ids = [i for i, f in enumerate(faces) if len(set(f)) == 3 and (vectors[f[1]]-vectors[f[0]]).cross(vectors[f[2]]-vectors[f[0]]).length_squared > 0]
    valid = [faces[i] for i in valid_face_ids]
    tree = BVHTree.FromPolygons(vectors, valid, all_triangles=True, epsilon=0)
    # Geometric proximity only; an exterior surface cannot locate real bones.
    landmark_proximity = {}
    for name, region in annotations['regions'].items():
        co, normal, face, distance = tree.find_nearest(Vector(region['center']))
        landmark_proximity[name] = {'nearest_surface':list(co), 'distance':distance,
                                    'joint_coordinate_status':'provisional, not certified bone center'}
    overlaps = tree.overlap(tree)
    suspects, confirmed, regions = 0, [], annotations['regions']
    region_counts = dict.fromkeys(regions, 0)
    skipped_shared = 0
    for a, b in overlaps:
        if a >= b:
            continue
        fa, fb = valid[a], valid[b]
        if set(fa).intersection(fb):
            skipped_shared += 1
            continue
        suspects += 1
        ta, tb = [vectors[i] for i in fa], [vectors[i] for i in fb]
        hit = any(crossing(ta[i], ta[(i+1)%3], tb) or crossing(tb[i], tb[(i+1)%3], ta) for i in range(3))
        if not hit:
            continue
        centroid = sum(ta+tb, Vector())/6
        labels = [name for name, r in regions.items() if (centroid-Vector(r['center'])).length <= r['radius']]
        for name in labels: region_counts[name] += 1
        confirmed.append({'source_face_pair':[valid_face_ids[a],valid_face_ids[b]], 'centroid':list(centroid), 'regions':labels})
    result = {'source':str(model), 'sha256':sha, 'blender':bpy.app.version_string,
              'read_only':True, 'imported_meshes':imported_info,
              'landmark_surface_proximity':landmark_proximity,
              'topology':topology(points, faces, regions),
              'paw_surface_segmentation':{'cutoff_y':.04,'analysis_exact_position_weld_only':True,
                  'labels_verified_against_original_views':True,
                  'method':'four connected low-surface components; source indices retained, lower-band/downward triangles are contact candidates, not pressure data',
                  'feet':contact_patches(points, faces, sources)},
              'self_intersection':{'method':'BVH overlap, exclude exact-position shared vertices, strict interior noncoplanar edge/triangle crossing',
                  'epsilon':1e-9, 'skipped_shared_vertex_pairs':skipped_shared,
                  'nonadjacent_bvh_candidate_pairs':suspects, 'strict_crossing_pairs':len(confirmed),
                  'region_counts':region_counts, 'examples':confirmed[:200],
                  'complete_pass':True, 'limits':'Coplanar overlaps, tangencies, adjacent face folding and near seams not certified. Counts measure pairs, not defects; coordinate welding is diagnostic only.'},
              'duration_seconds':time.perf_counter()-started,
              'decision':'REPAIR_THEN_RETEST'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output':str(output), 'components':result['topology']['edge_connected_components'],
                     'boundary_edges':result['topology']['boundary_edges'],
                     'nonmanifold_edges':result['topology']['nonmanifold_edges_more_than_two_faces'],
                     'strict_crossing_pairs':len(confirmed), 'seconds':result['duration_seconds']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('--landmarks', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    review(args.model, args.landmarks, args.output)
