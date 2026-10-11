"""Contact masks, topology guards and microscopic repair verification."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tools.rig_geometry_analysis import contact_patches, topology, mesh_data
from tools.rig_readiness_audit import audit, read_glb, accessor
from tools.local_boundary_repair import repair

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets/3d/tripo'
SHA='cab5d4a2205c644bdbb24a340777cf172e80969515290ae441bb78a29ce4df2c'


def test_four_connected_support_surfaces():
    points=[]
    for x,z,y in [(-.3,.1,.001),(-.3,-.1,.002),(.2,.1,0),(.2,-.1,.003)]:
        points.extend([(x,y,z),(x+.01,y,z),(x,y,z+.01)])
    faces=[(0,1,2),(3,4,5),(6,7,8),(9,10,11)]
    r=contact_patches(points,faces,{i:[i] for i in range(12)},band=.001)
    assert set(r)=={'front_left','front_right','hind_left','hind_right'}
    assert r['front_left']['min_y']==.001
    assert r['hind_right']['min_y']==.003
    assert all(f['downward_bottom_band_face_count']==1 for f in r.values())
    # Connected masks, not a sector-based inference: joining low surfaces fails.
    with pytest.raises(ValueError,match='Expected 4'):
        contact_patches(points,faces+[(0,3,6)],{i:[i] for i in range(12)})


def test_edge_manifold_and_roi_counts():
    pts=[(0,0,0),(1,0,0),(0,1,0),(0,0,1)]
    faces=[(0,1,2),(0,3,1),(1,3,2),(0,2,3)]
    region={'tip':{'center':[0,0,0],'radius':.1}}
    closed=topology(pts,faces,region)
    assert closed['boundary_edges']==closed['nonmanifold_edges_more_than_two_faces']==0
    assert closed['edge_connected_components']==1
    opened=topology(pts,faces[1:],region)
    assert opened['boundary_edges']==3
    assert opened['regions']['tip']['global_boundary_edges_touching_region']==2
    duplicate=topology(pts,faces+[faces[0]],region)
    assert duplicate['duplicate_faces_by_exact_position']==1
    assert duplicate['nonmanifold_edges_more_than_two_faces']==3


def test_original_contact_masks_match_anatomical_labels():
    points,faces,sources,sha=mesh_data(ASSETS/'deskcat_calico_h25_v1.glb')
    r=contact_patches(points,faces,sources)
    assert sha=='ff2a9e1d7280e4784913413fb45b10a2bdeadc125c80791a50f918a3ae646150'
    assert r['front_left']['min_y']==pytest.approx(.0001220703125)
    assert r['front_right']['min_y']==pytest.approx(.001007080078125)
    assert r['hind_left']['min_y']==0
    assert r['hind_right']['min_y']==pytest.approx(.000640869140625)
    masks=[set(f['source_vertex_ids']) for f in r.values()]
    assert all(not a.intersection(b) for i,a in enumerate(masks) for b in masks[i+1:])
    assert all(f['downward_bottom_band_face_count']>0 for f in r.values())


def test_micro_repair_only_changes_reviewed_position(tmp_path):
    source=ASSETS/'deskcat_calico_h25_v1_rigprep.glb'
    before=source.read_bytes()
    out=tmp_path/'candidate.glb'
    result=repair(source,out,SHA)
    assert source.read_bytes()==before
    assert result['changed_source_vertex_ids']==[5276]
    assert result['maximum_displacement']==pytest.approx(9.5367431640625e-7)
    assert result['retained_incident_normal_angle_max_degrees']<1
    assert audit(out)['degenerate_triangles_exact']==0
    assert audit(out)['triangles']==100790
    a,ab,_=read_glb(source);b,bb,_=read_glb(out)
    pa=a['meshes'][0]['primitives'][0];pb=b['meshes'][0]['primitives'][0]
    assert a['materials']==b['materials'] and a['images']==b['images'] and a['textures']==b['textures']
    for name in ('NORMAL','TEXCOORD_0'):
        assert accessor(a,ab,pa['attributes'][name])==accessor(b,bb,pb['attributes'][name])
    old=accessor(a,ab,pa['attributes']['POSITION']);new=accessor(b,bb,pb['attributes']['POSITION'])
    assert [i for i,(x,y) in enumerate(zip(old,new)) if x!=y]==[5276]
    points,faces,_,_=mesh_data(out)
    t=topology(points,faces,{})
    assert t['boundary_edges']==t['nonmanifold_edges_more_than_two_faces']==0
    for image in a['images']:
        v=a['bufferViews'][image['bufferView']];start=v.get('byteOffset',0);end=start+v['byteLength']
        assert ab[start:end]==bb[start:end]
    with pytest.raises(ValueError,match='separate'):
        repair(source,source,SHA)
    with pytest.raises(ValueError,match='separate'):
        repair(source,out,SHA)


@pytest.mark.parametrize('kwargs,match',[
    ({'expected_sha':'wrong'},'SHA'),
    ({'expected_sha':SHA,'limit':1e-8},'limit'),
    ({'expected_sha':SHA,'vertex':0},'boundary'),
])
def test_unreviewed_edits_rejected_without_output(tmp_path,kwargs,match):
    out=tmp_path/'forbidden.glb'
    with pytest.raises(ValueError,match=match):
        repair(ASSETS/'deskcat_calico_h25_v1_rigprep.glb',out,**kwargs)
    assert not out.exists()


def test_blender_strict_crossing_semantics():
    blender=shutil.which('blender')
    if blender is None:
        pytest.skip('Blender-specific geometric predicate requires Blender')
    script=f"""
import runpy
from mathutils import Vector
m=runpy.run_path({str(ROOT/'tools/blender_geometry_review.py')!r})
f=m['crossing'];t=[Vector((0,0,0)),Vector((1,0,0)),Vector((0,1,0))]
assert f(Vector((.2,.2,-1)),Vector((.2,.2,1)),t)
assert not f(Vector((2,2,-1)),Vector((2,2,1)),t)
assert not f(Vector((.2,.2,0)),Vector((.3,.3,0)),t)
assert not f(Vector((0,0,-1)),Vector((0,0,1)),t)
print('CROSSING_TEST_PASSED')
"""
    r=subprocess.run([blender,'-b','--factory-startup','--python-expr',script],capture_output=True,text=True,timeout=30)
    assert r.returncode==0 and 'CROSSING_TEST_PASSED' in r.stdout, r.stdout+r.stderr


def test_vertex_pinch_is_not_mistaken_for_safe_edge_manifold():
    # Two otherwise closed tetrahedra touch only at vertex 0.
    points=[(0,0,0),(1,0,0),(0,1,0),(0,0,1),(-1,0,0),(0,-1,0),(0,0,-1)]
    faces=[(0,1,2),(0,3,1),(1,3,2),(0,2,3),
           (0,4,5),(0,6,4),(4,6,5),(0,5,6)]
    r=topology(points,faces,{})
    assert r['boundary_edges']==r['nonmanifold_edges_more_than_two_faces']==0
    assert r['inconsistent_two_face_edge_winding']==0
    assert r['disconnected_vertex_fans']==1
    assert r['disconnected_vertex_fan_ids']==[0]
