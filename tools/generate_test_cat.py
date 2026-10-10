"""Generate an original CC0, untextured glTF 2.0 skinned cat fixture.

No external assets, services, or generation credits. Coordinates: glTF Y-up.
"""
import json
import math
import struct
from pathlib import Path


def generate(destination):
    blob = bytearray()
    views, accessors = [], []

    def accessor(rows, fmt, component, kind, bounds=False):
        while len(blob) % 4:
            blob.append(0)
        offset = len(blob)
        for row in rows:
            blob.extend(struct.pack('<' + fmt, *row))
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(blob) - offset})
        item = {'bufferView': len(views) - 1, 'componentType': component,
                'count': len(rows), 'type': kind}
        if bounds:
            item['min'] = [min(r[i] for r in rows) for i in range(len(rows[0]))]
            item['max'] = [max(r[i] for r in rows) for i in range(len(rows[0]))]
        accessors.append(item)
        return len(accessors) - 1

    pivots = [(0, 0, 0), (-0.6, 0.65, 0), (0.42, 0.48, 0.22),
              (0.42, 0.48, -0.22), (-0.42, 0.48, 0.22), (-0.42, 0.48, -0.22)]
    names = ['root', 'tail', 'front_left', 'front_right', 'back_left', 'back_right']
    positions, normals, joints, weights, indices = [], [], [], [], []

    def box(center, size, joint=0):
        # Face corner order yields outward-facing counterclockwise triangles.
        faces = [((1,0,0), [(1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1)]),
                 ((-1,0,0), [(-1,-1,1),(-1,1,1),(-1,1,-1),(-1,-1,-1)]),
                 ((0,1,0), [(-1,1,-1),(-1,1,1),(1,1,1),(1,1,-1)]),
                 ((0,-1,0), [(-1,-1,1),(-1,-1,-1),(1,-1,-1),(1,-1,1)]),
                 ((0,0,1), [(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]),
                 ((0,0,-1), [(1,-1,-1),(-1,-1,-1),(-1,1,-1),(1,1,-1)])]
        for normal, corners in faces:
            start = len(positions)
            for corner in corners:
                positions.append(tuple(center[i] + corner[i] * size[i] / 2 for i in range(3)))
                normals.append(normal)
                joints.append((joint, 0, 0, 0))
                weights.append((1, 0, 0, 0))
            indices.extend([(start,), (start+1,), (start+2,),
                            (start,), (start+2,), (start+3,)])

    box((0, .6, 0), (1.2, .45, .5))
    box((.58, .88, 0), (.42, .42, .43))
    box((.62, 1.14, .15), (.14, .22, .13))
    box((.62, 1.14, -.15), (.14, .22, .13))
    box((-.92, .68, 0), (.7, .12, .12), 1)
    for index, pivot in enumerate(pivots[2:], 2):
        box((pivot[0], .24, pivot[2]), (.15, .48, .15), index)
    attributes = {'POSITION': accessor(positions, '3f', 5126, 'VEC3', True),
                  'NORMAL': accessor(normals, '3f', 5126, 'VEC3'),
                  'JOINTS_0': accessor(joints, '4H', 5123, 'VEC4'),
                  'WEIGHTS_0': accessor(weights, '4f', 5126, 'VEC4')}
    triangles = accessor(indices, 'H', 5123, 'SCALAR')
    for item in attributes.values():
        views[accessors[item]['bufferView']]['target'] = 34962
    views[accessors[triangles]['bufferView']]['target'] = 34963
    matrices = []
    for x,y,z in pivots:
        matrices.append((1,0,0,0, 0,1,0,0, 0,0,1,0, -x,-y,-z,1))
    inverse_bind = accessor(matrices, '16f', 5126, 'MAT4')
    nodes = [{'name': name, 'translation': list(pivot)} for name,pivot in zip(names,pivots)]
    nodes[0]['children'] = list(range(1,6))
    nodes.append({'name': 'CatMesh', 'mesh': 0, 'skin': 0})
    animations = []
    for name, amplitude in [('idle', .12), ('walk', .6), ('sit', .2),
                            ('stand_up', .3), ('groom', .45), ('sleep', .03), ('drag', .25)]:
        times = [(i/15,) for i in range(31)]
        timeline = accessor(times, 'f', 5126, 'SCALAR', True)
        samplers, channels = [], []
        for joint in range(1,6):
            rotations = []
            for i in range(31):
                angle = amplitude * math.sin(i / 30 * math.tau + (joint % 2) * math.pi)
                # Tail swings around Y, limbs swing around Z.
                axis = (0,1,0) if joint == 1 else (0,0,1)
                rotations.append(tuple(v * math.sin(angle/2) for v in axis) + (math.cos(angle/2),))
            output = accessor(rotations, '4f', 5126, 'VEC4')
            samplers.append({'input': timeline, 'output': output, 'interpolation': 'LINEAR'})
            channels.append({'sampler': len(samplers)-1, 'target': {'node': joint, 'path': 'rotation'}})
        animations.append({'name': name, 'samplers': samplers, 'channels': channels})
    document = {'asset': {'version': '2.0', 'generator': 'DeskCat CC0 fixture generator'},
                'scene': 0, 'scenes': [{'nodes': [0,6]}], 'nodes': nodes,
                'meshes': [{'primitives': [{'attributes': attributes, 'indices': triangles, 'material': 0}]}],
                'materials': [{'name': 'test-gray', 'pbrMetallicRoughness':
                               {'baseColorFactor': [.55,.42,.3,1], 'metallicFactor': 0, 'roughnessFactor': .85}}],
                'skins': [{'joints': list(range(6)), 'skeleton': 0, 'inverseBindMatrices': inverse_bind}],
                'animations': animations, 'buffers': [{'byteLength': len(blob)}],
                'bufferViews': views, 'accessors': accessors}
    raw = json.dumps(document, separators=(',', ':')).encode()
    raw += b' ' * (-len(raw) % 4)
    blob.extend(b'\0' * (-len(blob) % 4))
    glb = struct.pack('<III', 0x46546c67, 2, 12 + 8 + len(raw) + 8 + len(blob))
    glb += struct.pack('<II', len(raw), 0x4e4f534a) + raw
    glb += struct.pack('<II', len(blob), 0x004e4942) + blob
    Path(destination).write_bytes(glb)


if __name__ == '__main__':
    generate(Path(__file__).resolve().parents[1] / 'assets/3d/test_cat.glb')
