"""Read-only, conservative GLB preflight. Never modifies the source model.

This is a geometric diagnostic, *not* an automatic riggability validator.
Run: python tools/rig_readiness_audit.py assets/3d/tripo/deskcat_calico_h25_v1.glb --output diagnostics/rig-readiness.json
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

_COMPONENT = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2),
              5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
_DIMS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def read_glb(path):
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != b'glTF':
        raise ValueError('Not a GLB file')
    version, length = struct.unpack_from('<II', data, 4)
    if version != 2 or length != len(data):
        raise ValueError('Invalid GLB version or declared byte length')
    offset, doc, binary = 12, None, None
    while offset + 8 <= len(data):
        size, kind = struct.unpack_from('<II', data, offset)
        if size % 4 or (offset == 12 and kind != 0x4E4F534A):
            raise ValueError('Invalid GLB chunk order/alignment')
        offset += 8
        if offset + size > len(data):
            raise ValueError('Truncated GLB chunk')
        chunk = data[offset:offset + size]
        offset += size
        if kind == 0x4E4F534A:
            if doc is not None:
                raise ValueError('Multiple JSON chunks')
            doc = json.loads(chunk.decode('utf-8').rstrip(' \t\r\n\x00'))
        elif kind == 0x004E4942:
            if binary is not None:
                raise ValueError('Multiple BIN chunks')
            binary = chunk
    if offset != len(data) or doc is None:
        raise ValueError('Invalid GLB chunks')
    if len(doc.get('buffers', [])) != 1 or 'uri' in doc['buffers'][0]:
        raise ValueError('Only self-contained GLB buffers are supported')
    if binary is None or len(binary) < doc['buffers'][0]['byteLength']:
        raise ValueError('Truncated binary buffer')
    return doc, binary, data


def accessor(doc, binary, number):
    a = doc['accessors'][number]
    if 'sparse' in a:
        raise ValueError('Sparse accessors require a separate inspection tool')
    if a.get('normalized'):
        raise ValueError('Normalized accessors require a separate inspection tool')
    if 'bufferView' not in a:
        raise ValueError('Accessor without bufferView cannot be inspected')
    if a['type'] not in _DIMS or a['componentType'] not in _COMPONENT:
        raise ValueError('Unsupported accessor encoding')
    view = doc['bufferViews'][a['bufferView']]
    if view.get('buffer', 0) != 0:
        raise ValueError('External buffers not supported')
    fmt, width = _COMPONENT[a['componentType']]
    count = _DIMS[a['type']]
    if a['count'] <= 0:
        raise ValueError('Accessor count must be positive')
    size = width * count
    stride = view.get('byteStride', size)
    if stride < size:
        raise ValueError('Invalid accessor stride')
    start = view.get('byteOffset', 0) + a.get('byteOffset', 0)
    end = view.get('byteOffset', 0) + view['byteLength']
    if start + max(0, a['count'] - 1) * stride + size > end:
        raise ValueError('Accessor exceeds its bufferView')
    result = []
    for i in range(a['count']):
        pos = start + i * stride
        if pos + size > len(binary):
            raise ValueError('Accessor exceeds BIN chunk')
        result.append(struct.unpack_from('<' + fmt * count, binary, pos))
    return result


def identity():
    return (1., 0., 0., 0., 0., 1., 0., 0.,
            0., 0., 1., 0., 0., 0., 0., 1.)


def product(a, b):
    # Column-major 4x4 matrices as used by glTF.
    return tuple(sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
                 for col in range(4) for row in range(4))


def node_transform(node):
    if 'matrix' in node:
        m = tuple(float(x) for x in node['matrix'])
        if len(m) != 16 or not all(math.isfinite(x) for x in m):
            raise ValueError('Invalid node matrix')
        if any(key in node for key in ('translation', 'rotation', 'scale')):
            raise ValueError('Node cannot combine matrix and TRS')
        if (m[3], m[7], m[11], m[15]) != (0, 0, 0, 1):
            raise ValueError('Node matrix must be affine')
        return m
    tx, ty, tz = node.get('translation', (0, 0, 0))
    sx, sy, sz = node.get('scale', (1, 1, 1))
    x, y, z, w = node.get('rotation', (0, 0, 0, 1))
    if not all(math.isfinite(v) for v in (tx, ty, tz, sx, sy, sz, x, y, z, w)):
        raise ValueError('Non-finite node transform')
    if not math.isclose(x*x + y*y + z*z + w*w, 1, abs_tol=1e-5):
        raise ValueError('Node quaternion must have unit length')
    r = (1 - 2 * (y*y + z*z), 2 * (x*y + z*w), 2 * (x*z - y*w), 0,
         2 * (x*y - z*w), 1 - 2 * (x*x + z*z), 2 * (y*z + x*w), 0,
         2 * (x*z + y*w), 2 * (y*z - x*w), 1 - 2 * (x*x + y*y), 0,
         0, 0, 0, 1)
    s = (sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sz, 0, 0, 0, 0, 1)
    t = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, tx, ty, tz, 1)
    return product(t, product(r, s))


def transform(p, m):
    x, y, z = p[:3]
    return (m[0]*x + m[4]*y + m[8]*z + m[12],
            m[1]*x + m[5]*y + m[9]*z + m[13],
            m[2]*x + m[6]*y + m[10]*z + m[14])


def audit(path):
    doc, binary, raw = read_glb(path)
    scenes = doc.get('scenes', [])
    if not scenes:
        raise ValueError('GLB has no scenes')
    nodes = doc.get('nodes', [])
    scene = scenes[doc.get('scene', 0)]
    primitives = []
    visited = set()

    def walk(i, parent, ancestry):
        if i in ancestry:
            raise ValueError('Cycle in scene graph')
        if i in visited:
            raise ValueError('Node has multiple parents or repeated scene roots')
        visited.add(i)
        node = nodes[i]
        if 'skin' in node:
            raise ValueError('Skinned geometry needs bind-pose inspection, not this static audit')
        world = product(parent, node_transform(node))
        if 'mesh' in node:
            for prim in doc['meshes'][node['mesh']]['primitives']:
                primitives.append((prim, world))
        for j in node.get('children', []):
            walk(j, world, ancestry | {i})

    for i in scene.get('nodes', []):
        walk(i, identity(), set())
    if not primitives:
        raise ValueError('No renderable mesh in active scene')
    verts, total_triangles, degenerate, missing_tangents = [], 0, 0, 0
    degenerate_examples = []
    for primitive_number, (prim, world) in enumerate(primitives):
        if prim.get('mode', 4) != 4:
            raise ValueError('Only TRIANGLES primitives supported for topology audit')
        attrs = prim['attributes']
        position = doc['accessors'][attrs['POSITION']]
        if position['type'] != 'VEC3' or position['componentType'] != 5126:
            raise ValueError('POSITION must be a float VEC3')
        if 'targets' in prim:
            raise ValueError('Morph geometry needs a separate inspection tool')
        points = [transform(p, world) for p in accessor(doc, binary, attrs['POSITION'])]
        if not all(math.isfinite(v) for p in points for v in p):
            raise ValueError('Non-finite POSITION values')
        verts.extend(points)
        if 'indices' in prim:
            index_accessor = doc['accessors'][prim['indices']]
            if index_accessor['type'] != 'SCALAR' or index_accessor['componentType'] not in (5121, 5123, 5125):
                raise ValueError('Indices must be unsigned SCALAR')
        indexes = ([v[0] for v in accessor(doc, binary, prim['indices'])]
                   if 'indices' in prim else list(range(len(points))))
        if len(indexes) % 3:
            raise ValueError('Triangle index count not divisible by 3')
        if any(i < 0 or i >= len(points) for i in indexes):
            raise ValueError('Triangle index out of bounds')
        total_triangles += len(indexes) // 3
        for i in range(0, len(indexes), 3):
            a, b, c = (points[indexes[i + k]] for k in range(3))
            u = [b[k] - a[k] for k in range(3)]
            v = [c[k] - a[k] for k in range(3)]
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            if cross == (0.0, 0.0, 0.0):
                degenerate += 1
                if len(degenerate_examples) < 10:
                    degenerate_examples.append({'scene_primitive': primitive_number,
                                                'triangle': i // 3,
                                                'scene_positions': [list(a), list(b), list(c)]})
        material_index = prim.get('material')
        if material_index is not None and 'normalTexture' in doc['materials'][material_index] and 'TANGENT' not in attrs:
            missing_tangents += 1
    lows = [min(p[i] for p in verts) for i in range(3)]
    highs = [max(p[i] for p in verts) for i in range(3)]
    height = highs[1] - lows[1]  # glTF Y up, before Panda's axis conversion.
    ground = lows[1] + height * .025
    center_x, center_z = (lows[0]+highs[0])/2, (lows[2]+highs[2])/2
    quarters = {}
    for a in ('-', '+'):
        for b in ('-', '+'):
            group = [p for p in verts if (p[0] < center_x) == (a == '-') and
                     (p[2] < center_z) == (b == '-')]
            quarters[f'X{a} Z{b}'] = {'points_below_lower_2_5pct':
                                    sum(p[1] <= ground for p in group),
                                    'min_y': round(min(p[1] for p in group), 6) if group else None}
    notes = ['LOWER 2.5% vertex counts are only rough contact candidates, not identified paws.',
             'Coordinate sectors X±/Z± do not establish anatomical front/back or left/right.',
             'This tool cannot establish joint placement, manifold topology, weight painting, or animation quality.']
    if not doc.get('skins'):
        notes.append('No skeleton: rigging must be planned and validated separately.')
    if missing_tangents:
        notes.append('Normal-mapped primitives without TANGENT: shader tangent-space appearance may differ.')
    return {
        'source': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
        'bytes': len(raw), 'coordinate_system': 'glTF Y-up (scene-space)',
        'scene_primitives': len(primitives), 'vertices_with_instances': len(verts),
        'triangles': total_triangles, 'degenerate_triangles_exact': degenerate,
        'degenerate_triangle_examples': degenerate_examples,
        'skins': len(doc.get('skins', [])), 'animations': len(doc.get('animations', [])),
        'materials': len(doc.get('materials', [])),
        'normal_mapped_primitives_without_tangents': missing_tangents,
        'bounding_box': {'min': [round(v, 6) for v in lows], 'max': [round(v, 6) for v in highs]},
        'ground_candidate_y': round(ground, 6), 'ground_quadrants': quarters,
        'decision': 'MANUAL_REVIEW_REQUIRED', 'notes': notes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('glb', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.glb)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')


if __name__ == '__main__':
    main()
