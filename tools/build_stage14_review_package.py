"""Build a review-only packet from existing Stage 13 evidence; no Blender edits."""
import csv
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QGuiApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from rig_readiness_audit import read_glb, accessor
OUT = ROOT / 'docs/model-reports/stage14'
BASE = 'https://github.com/sensormob22-sketch/DeskCat'
REF = '74199b9'
AMBIGUOUS = ['D04','D06','D09','D14','D17','D24']
TJ = ['D05','D07','D15','D18']

def topology_hash(faces):
    return hashlib.sha256(json.dumps(faces, separators=(',', ':')).encode()).hexdigest()

def build():
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    app = QGuiApplication.instance() or QGuiApplication([])
    OUT.mkdir(exist_ok=True)
    (OUT / 'images').mkdir(exist_ok=True)
    register = json.loads((ROOT / 'docs/model-reports/stage13/defect_register.json').read_text())
    mapping = json.loads((ROOT / 'docs/model-reports/exact-weld-proxy/vertex_map.json').read_text())
    loops = {c['cluster']: c for c in json.loads((ROOT / 'docs/model-reports/stage13/closed_contour_evidence.json').read_text())}
    model = ROOT / 'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
    d,b,_ = read_glb(model)
    primitive = d['meshes'][0]['primitives'][0]
    indices = [v[0] for v in accessor(d,b,primitive['indices'])]
    original_faces = [indices[i:i+3] for i in range(0,len(indices),3)]
    proxy_faces = mapping['proxy_faces_in_source_face_order']
    selected = []
    for c in register['clusters']:
        if c['id'] not in AMBIGUOUS + TJ:
            continue
        item = {k:c[k] for k in ['id','region','counts','source_face_ids','context_source_face_ids','fan_groups','confidence']}
        item['review_kind'] = 'AMBIGUOUS' if c['id'] in AMBIGUOUS else 'T_JUNCTION_PROPOSAL'
        verts = sorted({v for fi in c['source_face_ids'] + c['context_source_face_ids'] for v in proxy_faces[fi]})
        item['source_vertex_aliases'] = {str(v):mapping['proxy_to_sources'][v] for v in verts}
        if c['id'] in loops:
            item['contour_evidence'] = loops[c['id']]
        selected.append(item)
        n = int(c['id'][1:])-1
        sheet = QImage(str(ROOT / f'docs/model-reports/stage13/images/clusters_{n//8+1}.png'))
        assert not sheet.isNull()
        # Preserve existing textured/solid paired cameras and colored overlays.
        image = sheet.copy(0,50+(n%8)*310,1100,300)
        painter = QPainter(image)
        painter.fillRect(0,0,1100,28,QColor("#eeeeee"))
        painter.setFont(QFont("DejaVu Sans",10))
        painter.setPen(QColor("#151515"))
        painter.drawText(10,20,c["id"]+" / "+c["region"]+" / "+item["review_kind"]+" / "+str(c["counts"]))
        painter.end()
        assert image.save(str(OUT / f'images/{c["id"]}.png'))
    frozen = json.loads((ROOT / 'docs/model-reports/stage13/preserved_manifest.json').read_text())
    scene = 'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend'
    manifest = {'base_commit':REF,'source_scene':scene,'source_scene_sha256':frozen[scene],
        'objects':{
            'EXACT_WELD_PROXY_NO_WEIGHTS':{'vertices':8253,'faces':16460,'face_order_sha256':topology_hash(proxy_faces)},
            'RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE':{'vertices':19464,'faces':16460,'face_order_sha256':topology_hash(original_faces)}},
        'rig':'CAT_RIGIFY_TRIAL_02','deform_bones':46,'clusters':selected,
        'decisions':['BODY','COSMETIC','KEEP SEPARATE','UNCERTAIN'],
        'id_convention':'Zero-based source triangle IDs. Both object face orders must validate before selection. Context is not an approved repair mask.',
        'operations':'Selection and viewport visibility only; no topology/weights/export or automatic save.'}
    (OUT / 'review_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    files = [scene, 'assets/3d/retopo/deskcat_calico_retopo_16460.glb',
             'docs/model-reports/exact-weld-proxy/vertex_map.json',
             'docs/model-reports/exact-weld-proxy/preflight.json',
             'docs/model-reports/stage13/solver_edit_proposal.json',
             'docs/model-reports/stage13/preserved_manifest.json']
    links = []
    for name in files:
        path = ROOT / name
        links.append({'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                      'view':f'{BASE}/blob/{REF}/{name}',
                      'download':f'https://raw.githubusercontent.com/sensormob22-sketch/DeskCat/{REF}/{name}'})
    (OUT / 'source_links.json').write_text(json.dumps(links,indent=2)+'\n')
    with (OUT / 'face_decisions.csv').open('w',newline='') as stream:
        w=csv.writer(stream,lineterminator="\n")
        w.writerow(['cluster','source_face_id','decision','reason','reviewer','scope'])
        for c in selected:
            for fi in c['source_face_ids']:
                w.writerow([c['id'],fi,'','','',c['review_kind']])
    with (OUT / 'fan_decisions.csv').open('w',newline='') as stream:
        w=csv.writer(stream,lineterminator="\n")
        w.writerow(['cluster','proxy_vertex_id','fan_index','source_face_ids','decision','reason','reviewer'])
        for c in selected:
            for fan in c['fan_groups']:
                for i,faces in enumerate(fan['fan_source_face_groups']):
                    w.writerow([c['id'],fan['proxy_vertex'],i,' '.join(map(str,faces)),'','',''])
    (OUT / 'package_checksums.json').write_text(json.dumps({str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['DeskCat_Topology_Review.zip','package_checksums.json','verification.json','test-results.txt']},indent=2)+'\n')
    with zipfile.ZipFile(OUT / 'DeskCat_Topology_Review.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file() and p.name not in ['DeskCat_Topology_Review.zip','verification.json','test-results.txt']:
                z.write(p, 'DeskCat_Topology_Review/' + str(p.relative_to(OUT)))
    print(json.dumps({'clusters':len(selected),'archive_bytes':(OUT / 'DeskCat_Topology_Review.zip').stat().st_size,'scene_copied':False}))

if __name__ == '__main__':
    build()
