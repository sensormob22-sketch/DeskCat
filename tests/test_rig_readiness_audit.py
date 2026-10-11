"""Synthetic tests: never change the Tripo asset in-place."""
import json
import struct

import pytest

from tools.rig_readiness_audit import audit, accessor, node_transform, transform


def sample_glb(path):
    vertices = [(-1., 0., -1.), (-1., 0., 1.), (1., 0., -1.),
                (1., 0., 1.), (0., 2., 0.)]
    indices = [0, 1, 4, 1, 3, 4, 3, 2, 4, 2, 0, 4]
    packed = b''.join(struct.pack('<3f', *p) for p in vertices) + struct.pack('<12H', *indices)
    doc = {'asset': {'version': '2.0'},
           'buffers': [{'byteLength': len(packed)}],
           'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 60},
                           {'buffer': 0, 'byteOffset': 60, 'byteLength': 24}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 5, 'type': 'VEC3'},
                         {'bufferView': 1, 'componentType': 5123, 'count': 12, 'type': 'SCALAR'}],
           'materials': [{}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1, 'material': 0}]}],
           'nodes': [{'mesh': 0, 'translation': [0, 1, 0]}],
           'scenes': [{'nodes': [0]}], 'scene': 0}
    header = json.dumps(doc).encode('utf-8')
    header += b' ' * ((-len(header)) % 4)
    packed += b'\0' * ((-len(packed)) % 4)
    length = 12 + 8 + len(header) + 8 + len(packed)
    path.write_bytes(struct.pack('<4sII', b'glTF', 2, length) +
                     struct.pack('<II', len(header), 0x4E4F534A) + header +
                     struct.pack('<II', len(packed), 0x004E4942) + packed)


def test_audit_geometry_and_ground_sectors(tmp_path):
    p = tmp_path/'synthetic.glb'
    sample_glb(p)
    result = audit(p)
    assert result['triangles'] == 4
    assert result['degenerate_triangles_exact'] == 0
    assert result['skins'] == 0 and result['animations'] == 0
    assert result['bounding_box']['min'] == [-1., 1., -1.]
    assert result['bounding_box']['max'] == [1., 3., 1.]
    assert sum(x['points_below_lower_2_5pct'] for x in result['ground_quadrants'].values()) == 4
    assert result['decision'] == 'MANUAL_REVIEW_REQUIRED'


def test_reject_invalid_header(tmp_path):
    p = tmp_path/'bad.glb'
    p.write_bytes(b'not a GLB')
    with pytest.raises(ValueError, match='Not a GLB'):
        audit(p)


def test_quaternion_node_transform():
    m = node_transform({'translation': [1, 2, 3], 'scale': [2, 2, 2]})
    assert transform((.5, .5, .5), m) == pytest.approx((2, 3, 4))


def rewrite_sample(path, mutate):
    from tools.rig_readiness_audit import read_glb
    doc, binary, _ = read_glb(path)
    mutate(doc)
    encoded = json.dumps(doc).encode()
    encoded += b' ' * (-len(encoded) % 4)
    body = struct.pack('<II', len(encoded), 0x4E4F534A) + encoded
    body += struct.pack('<II', len(binary), 0x004E4942) + binary
    path.write_bytes(struct.pack('<4sII', b'glTF', 2, len(body) + 12) + body)


def test_original_asset_read_only_and_measured():
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / 'assets/3d/tripo/deskcat_calico_h25_v1.glb'
    before = p.read_bytes()
    r = audit(p)
    assert r['sha256'] == 'ff2a9e1d7280e4784913413fb45b10a2bdeadc125c80791a50f918a3ae646150'
    assert (r['triangles'], r['vertices_with_instances']) == (100796, 58450)
    assert r['degenerate_triangles_exact'] == 5
    assert r['skins'] == r['animations'] == 0
    assert p.read_bytes() == before


@pytest.mark.parametrize('change,match', [
    (lambda d: d['accessors'][0].update(sparse={}), 'Sparse'),
    (lambda d: d['accessors'][0].update(normalized=True), 'Normalized'),
    (lambda d: d['accessors'][0].update(componentType=5123), 'float VEC3'),
    (lambda d: d['accessors'][1].update(componentType=5126), 'unsigned SCALAR'),
    (lambda d: d['bufferViews'][0].update(byteLength=4), 'bufferView'),
    (lambda d: d['nodes'][0].update(children=[0]), 'Cycle'),
    (lambda d: d['scenes'][0].update(nodes=[0, 0]), 'multiple parents'),
    (lambda d: d['nodes'][0].update(skin=0), 'bind-pose'),
])
def test_reject_unsupported_and_malformed_geometry(tmp_path, change, match):
    p = tmp_path / 'case.glb'
    sample_glb(p)
    rewrite_sample(p, change)
    with pytest.raises(ValueError, match=match):
        audit(p)


def test_empty_quadrant_serializes_as_null(tmp_path):
    p = tmp_path / 'flat.glb'
    sample_glb(p)
    rewrite_sample(p, lambda d: d['nodes'][0].update(scale=[0, 1, 0]))
    r = audit(p)
    assert r['ground_quadrants']['X- Z-']['min_y'] is None
    json.dumps(r, allow_nan=False)


def test_rotated_parent_and_nonuniform_scale(tmp_path):
    import math
    p = tmp_path / 'transformed.glb'
    sample_glb(p)
    def change(d):
        d['nodes'].append({'children': [0], 'translation': [5, 0, 0],
                           'rotation': [0, 0, math.sqrt(.5), math.sqrt(.5)], 'scale': [2, 3, 1]})
        d['scenes'][0]['nodes'] = [1]
    rewrite_sample(p, change)
    r = audit(p)
    assert r['bounding_box']['min'] == [-4, -2, -1]
    assert r['bounding_box']['max'] == [2, 2, 1]


def test_separate_cleanup_preserves_original_and_vertex_buffer(tmp_path):
    from tools.remove_exact_degenerate_triangles import clean
    from tools.rig_readiness_audit import read_glb
    source = tmp_path / 'source.glb'
    output = tmp_path / 'clean.glb'
    sample_glb(source)
    # Degenerate first triangle by repeating its first index; keep others.
    doc, binary, raw = read_glb(source)
    binary = bytearray(binary)
    struct.pack_into('<H', binary, 62, 0)
    start = len(raw) - len(binary)
    source.write_bytes(raw[:start] + binary)
    before = source.read_bytes()
    result = clean(source, output)
    assert result['removed_exact_degenerate_triangles'] == 1
    assert source.read_bytes() == before
    assert audit(output)['degenerate_triangles_exact'] == 0
    assert audit(output)['triangles'] == 3
    _, new_binary, _ = read_glb(output)
    assert new_binary[:len(binary)] == binary
    with pytest.raises(ValueError, match='new separate'):
        clean(source, source)
    with pytest.raises(ValueError, match='new separate'):
        clean(source, output)
