"""Stage10 review proposal must remain small, reproducible and outside frozen masks."""
import hashlib
import json
from pathlib import Path
import pytest
from tools.prepare_tail_weight_proposal import prepare
from tools.weight_handoff_contract import validate_proposal, source_skin_weights

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'docs/model-reports/stage10'
SOURCE = ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
SKIN = ROOT/'assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb'
SCENE = ROOT/'assets/rigging/deskcat_v6_weight_handoff.blend'

def load(name):
    return json.loads((PACKAGE/name).read_text())

@pytest.fixture(scope='module')
def context():
    return json.loads((ROOT/'docs/model-reports/stage9/data/region_masks.json').read_text()), source_skin_weights(SOURCE,SKIN)


def test_concrete_tail_proposal_passes_read_only_validator(context):
    masks,_=context
    result=validate_proposal(load('tail_to_pelvis_proposal.json'),masks,SOURCE,SKIN,SCENE)
    assert result['valid_for_review'] and result['changed_source_vertices_proposed']==21
    assert not result['weights_applied'] and not result['new_skinprobe_exported']


def test_other_five_masks_protected_points_and_c1_remain_frozen(context):
    masks,_=context;proposal=load('tail_to_pelvis_proposal.json')
    ids={i for row in proposal['changes'] for i in row['source_vertex_ids']}
    other=set().union(*(set(z['editable_source_vertex_ids']) for n,z in masks['zones'].items() if n!='tail_to_pelvis'))
    assert not ids & (other|set(masks['protected_source_vertex_ids']))
    assert not ids & {3789,3791,3793,4258,4260,4261}
    assert proposal['status']=='DRAFT_NOT_AUTHORIZED' and proposal['approval_reference'] is None
    assert proposal['geometry_uv_texture_changes_allowed'] is False


def test_full_rows_small_two_bone_transfer_and_all_seam_copies(context):
    masks,(names,_,positions)=context;proposal=load('tail_to_pelvis_proposal.json');changes={}
    maximum=0
    for entry in proposal['changes']:
        row=entry['weights'];assert set(row)==set(names)
        assert sum(row.values())==pytest.approx(1,abs=1e-12)
        for i in entry['source_vertex_ids']:
            base=masks['baseline_vertex_weights'][str(i)]
            for name in names:
                delta=abs(row[name]-base.get(name,0));maximum=max(maximum,delta)
                if name not in ('pelvis','tail_base'):assert delta==0
            changes[i]=row
    assert maximum==pytest.approx(.004256758696091545,abs=1e-12)
    seams={}
    for i,p in enumerate(positions):seams.setdefault(tuple(p),[]).append(i)
    for i,row in changes.items():
        assert all(j in changes and changes[j]==row for j in seams[tuple(positions[i])])


def test_preparation_is_reproducible_and_does_not_touch_scene(tmp_path):
    before=hashlib.sha256(SCENE.read_bytes()).hexdigest()
    out=tmp_path/'proposal';prepare(ROOT,out)
    for name in ('tail_to_pelvis_proposal.json','proposal_audit.json'):
        assert (out/name).read_bytes()==(PACKAGE/name).read_bytes()
    assert hashlib.sha256(SCENE.read_bytes()).hexdigest()==before


def test_blender_inspection_did_not_install_proposed_weights(context):
    masks,_=context;r=load('blender_inspection.json')
    assert r['bone_weight_sha256_float32']==masks['bone_weight_sha256_float32']
    assert r['all_weights_unchanged_in_memory'] and r['scene_file_unchanged']
    assert r['all_5330_baseline_rows_match_actual_blender']
    assert r['current_plus15_new_pairs']==44 and r['C1_present'] and r['C2_present']
    assert r['animation_actions']==0 and not r['new_glb_exported']
