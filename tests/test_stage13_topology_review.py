"""Verify defect coverage, exact provenance and the no-application boundary."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/model-reports/stage13'
spec = importlib.util.spec_from_file_location('clusters', ROOT / 'tools/topology_defect_clusters.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_clusters_do_not_merge_by_context_or_spatial_proximity():
    events = [
        {'proxy_vertices': [1, 2], 'source_faces': [10], 'context_source_face_ids': [99]},
        {'proxy_vertices': [3, 4], 'source_faces': [11], 'context_source_face_ids': [99]},
        {'proxy_vertices': [4, 5], 'source_faces': [12]},
    ]
    assert module.cluster_defect_events(events) == [[0], [1, 2]]


def test_every_prior_c0_defect_is_covered_once():
    r = json.loads((REPORT / 'defect_register.json').read_text())
    coverage = [i for c in r['clusters'] for i in c['event_ids']]
    assert sorted(coverage) == list(range(137))
    assert len(set(coverage)) == 137
    assert r['counts'] == {'boundary': 87, 'nonmanifold': 42, 'fan': 8, 'clusters': 24}
    for c in r['clusters']:
        assert set(c['source_face_ids']) == {fi for i in c['event_ids'] for fi in r['events'][i]['source_faces']}
    assert not any(r['operations_performed'].values())


def test_proposal_has_no_hole_fill_or_application_and_exact_t_junctions():
    p = json.loads((REPORT / 'solver_edit_proposal.json').read_text())
    assert p['decision'] == 'C'
    assert p['authorized_operations_performed'] == 0
    assert len(p['proposals']) == 24
    for c in p['proposals']:
        assert c['status'] == 'PROPOSAL_ONLY_NOT_APPLIED'
        assert c['proved_body_hole'] is False
    loops = {c['cluster']: c for c in json.loads((REPORT / 'closed_contour_evidence.json').read_text())}
    for name, parent_face in [('D05',3003),('D07',6329),('D15',14146),('D18',14078)]:
        evidence = loops[name]['t_junction_evidence']
        assert evidence['exact_collinear']
        assert evidence['max_collinear_residual'] == 0
        assert evidence['long_edge_source_faces'] == [parent_face]
        assert all(0 < t < 1 for t in evidence['intermediate_proxy_parameters'].values())
        assert loops[name]['triangle_cap_area_if_triangular'] == 0


def test_all_source_assets_and_previous_reports_are_unchanged():
    frozen = json.loads((REPORT / 'preserved_manifest.json').read_text())
    assert 'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend' in frozen
    for name, expected in frozen.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
