"""Conservative separate-file cleanup: remove exact zero-area indexed triangles.

Does not weld, remesh, repose, change UVs, textures, normals or create bones.
"""
import argparse
import json
from pathlib import Path
import struct
if __package__:
    from .rig_readiness_audit import read_glb, accessor, audit
else:
    from rig_readiness_audit import read_glb, accessor, audit


def clean(source, output):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Output must be a new separate file')
    audit(source)  # Reject unsupported/nonstatic geometry before any write.
    doc, binary, _ = read_glb(source)
    binary = bytearray(binary[:doc['buffers'][0]['byteLength']])
    removed = 0
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            if 'indices' not in primitive:
                raise ValueError('Cleanup requires indexed triangles')
            points = accessor(doc, binary, primitive['attributes']['POSITION'])
            indices = [v[0] for v in accessor(doc, binary, primitive['indices'])]
            keep = []
            for i in range(0, len(indices), 3):
                a, b, c = (points[indices[i+k]] for k in range(3))
                u = [b[k]-a[k] for k in range(3)]
                v = [c[k]-a[k] for k in range(3)]
                cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
                if cross == (0, 0, 0):
                    removed += 1
                else:
                    keep.extend(indices[i:i+3])
            if len(keep) == len(indices):
                continue
            if not keep:
                raise ValueError('Cleanup would remove all primitive geometry')
            binary.extend(b'\0' * (-len(binary) % 4))
            offset = len(binary)
            chunk = struct.pack('<' + 'I'*len(keep), *keep)
            binary.extend(chunk)
            view = len(doc['bufferViews'])
            doc['bufferViews'].append({'buffer': 0, 'byteOffset': offset,
                                      'byteLength': len(chunk), 'target': 34963})
            primitive['indices'] = len(doc['accessors'])
            doc['accessors'].append({'bufferView': view, 'componentType': 5125,
                                    'count': len(keep), 'type': 'SCALAR',
                                    'min': [min(keep)], 'max': [max(keep)]})
    doc['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(doc, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    binary.extend(b'\0' * (-len(binary) % 4))
    body = struct.pack('<II', len(encoded), 0x4E4F534A) + encoded
    body += struct.pack('<II', len(binary), 0x004E4942) + binary
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(struct.pack('<4sII', b'glTF', 2, len(body)+12) + body)
    return {'removed_exact_degenerate_triangles': removed,
            'source': str(source), 'output': str(output)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(clean(args.source, args.output), indent=2))
