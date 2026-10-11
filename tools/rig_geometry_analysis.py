"""Read-only asset-specific paw segmentation and topology review helpers.

Canonical positions are welded EXACTLY for analysis only, never in a GLB.
Foot masks are connected surface components below a measured Y height, not
unlabelled quadrants. Annotation maps declare the anatomical interpretation.
"""
from collections import Counter, defaultdict
import hashlib
import math
from pathlib import Path

if __package__:
    from .rig_readiness_audit import read_glb, accessor
else:
    from rig_readiness_audit import read_glb, accessor


def mesh_data(path):
    d, b, raw = read_glb(path)
    roots = d['scenes'][d.get('scene', 0)]['nodes']
    if len(roots) != 1:
        raise ValueError('This review requires a single scene root')
    n = d['nodes'][roots[0]]
    if any(k in n for k in ('matrix', 'translation', 'rotation', 'scale', 'children', 'skin')):
        raise ValueError('Review requires untransformed static single-mesh root')
    if len(d['meshes'][n['mesh']]['primitives']) != 1:
        raise ValueError('Review requires one primitive')
    p = d['meshes'][n['mesh']]['primitives'][0]
    if p.get('mode', 4) != 4:
        raise ValueError('TRIANGLES required')
    points = accessor(d, b, p['attributes']['POSITION'])
    indices = [v[0] for v in accessor(d, b, p['indices'])]
    lookup, remap, sources = {}, [], defaultdict(list)
    for i, v in enumerate(points):
        if v not in lookup:
            lookup[v] = len(lookup)
        j = lookup[v]
        remap.append(j)
        sources[j].append(i)
    return list(lookup), [tuple(remap[v] for v in indices[i:i+3]) for i in range(0, len(indices), 3)], sources, hashlib.sha256(raw).hexdigest()


def components(vertex_ids, edges):
    vertex_ids = set(vertex_ids)
    parent = {v: v for v in vertex_ids}
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in edges:
        if a in vertex_ids and b in vertex_ids:
            parent[root(a)] = root(b)
    groups = defaultdict(list)
    for i in sorted(vertex_ids):
        groups[root(i)].append(i)
    return sorted(groups.values(), key=lambda g: (-len(g), min(g)))


def edge_faces(faces):
    edges = defaultdict(list)
    for i, f in enumerate(faces):
        if len(set(f)) != 3:
            continue
        for a, b in zip(f, f[1:]+f[:1]):
            edges[tuple(sorted((a, b)))].append(i)
    return edges


def bounds(points):
    return {'min': [min(v[k] for v in points) for k in range(3)],
            'max': [max(v[k] for v in points) for k in range(3)]}


def contact_patches(points, faces, sources, cutoff=.04, band=.0015654754638671875):
    edges = edge_faces(faces)
    patches = components((i for i, p in enumerate(points) if p[1] < cutoff), edges)
    if len(patches) != 4:
        raise ValueError(f'Expected 4 anatomically reviewed low-surface components, got {len(patches)}; stop instead of guessing')
    result = {}
    for ids in patches:
        ps = [points[i] for i in ids]
        center = [sum(p[k] for p in ps)/len(ps) for k in range(3)]
        # Mapping verified on side/front/underside images: head -X, up +Y,
        # anatomical left +Z. Do not generalize this map to arbitrary assets.
        name = ('front' if center[0] < 0 else 'hind') + ('_left' if center[2] > 0 else '_right')
        if name in result:
            raise ValueError('Ambiguous anatomical component assignment')
        idset = set(ids)
        bottom = min(p[1] for p in ps)
        surface = [i for i in ids if points[i][1] <= bottom + band]
        downward = []
        area = 0.
        weighted = [0., 0., 0.]
        for fi, f in enumerate(faces):
            if not all(v in idset for v in f):
                continue
            a, b, c = (points[i] for i in f)
            u, v = ([b[k]-a[k] for k in range(3)], [c[k]-a[k] for k in range(3)])
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            length = math.sqrt(sum(x*x for x in cross))
            centroid = [(a[k]+b[k]+c[k])/3 for k in range(3)]
            if length and cross[1]/length < -.3 and max(a[1],b[1],c[1]) <= bottom + band:
                downward.append(fi)
                area += length/2
                for k in range(3): weighted[k] += centroid[k]*length/2
        result[name] = {'component_unique_vertices': len(ids), 'low_patch_aabb': bounds(ps),
                        'min_y': bottom, 'max_y': max(p[1] for p in ps),
                        'low_patch_vertex_mean': center,
                        'bottom_band_width': band, 'bottom_band_vertex_count': len(surface),
                        'bottom_band_aabb': bounds([points[i] for i in surface]),
                        'downward_bottom_band_face_count': len(downward),
                        'downward_bottom_band_area': area,
                        'downward_bottom_band_area_centroid': [x/area for x in weighted] if area else None,
                        'source_vertex_ids': sorted(j for i in ids for j in sources[i]),
                        'support_candidate_source_vertex_ids': sorted(j for i in surface for j in sources[i]),
                        'support_candidate_face_ids': downward}
    return result


def topology(points, faces, regions):
    edges = edge_faces(faces)
    groups = components({v for f in faces for v in f}, edges)
    boundaries = {e for e, fs in edges.items() if len(fs) == 1}
    nonmanifold = {e for e, fs in edges.items() if len(fs) > 2}
    duplicates = sum(n-1 for n in Counter(tuple(sorted(f)) for f in faces).values() if n > 1)
    winding = defaultdict(list)
    links = defaultdict(list)
    for f in faces:
        if len(set(f)) != 3:
            continue
        for a, b in zip(f, f[1:]+f[:1]):
            winding[tuple(sorted((a,b)))].append(1 if a < b else -1)
        for k, vertex in enumerate(f):
            links[vertex].append((f[(k+1)%3], f[(k+2)%3]))
    split_fans = []
    for vertex, link_edges in links.items():
        neighbors = {v for edge in link_edges for v in edge}
        if len(components(neighbors, link_edges)) > 1:
            split_fans.append(vertex)
    results = {}
    for name, region in regions.items():
        center, radius = region['center'], region['radius']
        ids = {i for i, p in enumerate(points) if sum((p[k]-center[k])**2 for k in range(3)) <= radius**2}
        region_faces = [i for i, f in enumerate(faces) if any(v in ids for v in f)]
        results[name] = {'vertices_in_sphere': len(ids), 'incident_faces': len(region_faces),
                         'global_boundary_edges_touching_region': sum(bool(ids.intersection(e)) for e in boundaries),
                         'global_nonmanifold_edges_touching_region': sum(bool(ids.intersection(e)) for e in nonmanifold),
                         'component_ids_touching_region': [i for i, g in enumerate(groups) if ids.intersection(g)]}
    return {'analysis_exact_position_weld_only': True, 'unique_positions': len(points),
            'edge_connected_components': len(groups), 'component_sizes': [len(g) for g in groups],
            'boundary_edges': len(boundaries), 'nonmanifold_edges_more_than_two_faces': len(nonmanifold),
            'disconnected_vertex_fans': len(split_fans), 'disconnected_vertex_fan_ids': split_fans,
            'inconsistent_two_face_edge_winding':sum(len(signs)==2 and sum(signs)!=0 for signs in winding.values()),
            'duplicate_faces_by_exact_position': duplicates, 'regions': results}
