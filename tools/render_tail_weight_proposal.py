"""Draw review-only source-mesh influence diagrams; never render proposed deformation."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont, QPen, QPolygonF
from rig_readiness_audit import read_glb, accessor


def render(root, output):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QGuiApplication.instance() or QGuiApplication([])
    report = json.loads((output / 'proposal_audit.json').read_text())
    masks = json.loads((root / 'docs/model-reports/stage9/data/region_masks.json').read_text())
    data = json.loads((root / 'docs/model-reports/stage9/data/pose_review.json').read_text())
    doc, binary, _ = read_glb(root / 'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb')
    prim = doc['meshes'][0]['primitives'][0]
    points = accessor(doc, binary, prim['attributes']['POSITION'])
    flat = [x[0] for x in accessor(doc, binary, prim['indices'])]
    faces = [flat[i:i+3] for i in range(0, len(flat), 3)]
    baseline = masks['baseline_vertex_weights']
    proposed = {i: e['proposal_weights'] for e in report['measurements'] for i in e['source_vertex_ids']}
    core = {i for f in (7323, 7586) for i in faces[f]}
    changed = set(proposed)
    def canvas(w, h, title, subtitle):
        image = QImage(w, h, QImage.Format.Format_RGBA8888); image.fill(QColor('#f5f5f5'))
        painter = QPainter(image); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor('#171717')); painter.setFont(QFont('DejaVu Sans', 16)); painter.drawText(20, 30, title)
        painter.setFont(QFont('DejaVu Sans', 11)); painter.drawText(20, 57, subtitle)
        return image, painter
    def save(image, painter, name):
        painter.end()
        if not image.save(str(output / name)):
            raise ValueError('Image save failed')
    old = QImage(str(root / 'docs/model-reports/stage9/sheets/tail_to_pelvis.png'))
    if old.isNull():
        raise ValueError('Missing original stage9 sheet')
    image, painter = canvas(1800, 700, 'TAIL REVIEW: current v6 only — no new weights applied',
                            'C1 frozen (overlap with other masks). Only the small C2 surface patch is proposed.')
    for col, (x, y, label) in enumerate(((0,100,'REST / original texture'), (800,100,'CURRENT +15 / original texture'), (800,420,'CURRENT +15 / crossing faces'))):
        painter.drawImage(QRectF(col*600,110,600,480), old.copy(x,y,400,320))
        painter.setPen(QColor('#171717'));painter.drawText(col*600+18,92,label)
    painter.drawText(20,620,'C1: source faces 6971 / 7816; six vertices frozen. C2: 7323 / 7586; six core vertices + 15 transition vertices.')
    painter.drawText(20,650,'+15 baseline: 44 new crossing pairs. No proposed deformed geometry exists; no improvement has been tested.')
    save(image,painter,'tail_context.png')

    # Same orthographic projection and source positions for all three panels.
    context_faces = [i for i,f in enumerate(faces) if set(f) & (changed | set(report['excluded_support_vertices']))]
    context_ids = {i for f in context_faces for i in faces[f]}
    projected = {i:(points[i][0]+.2*points[i][2],points[i][1]+.2*points[i][2]) for i in context_ids}
    lo = [min(p[k] for p in projected.values()) for k in (0,1)]
    hi = [max(p[k] for p in projected.values()) for k in (0,1)]
    scale = min(480/(hi[0]-lo[0]),480/(hi[1]-lo[1]))
    def pt(i,col):
        x,y=projected[i];return QPointF(col*600+55+(x-lo[0])*scale,630-(y-lo[1])*scale)
    def weight(i,mode):
        before=baseline.get(str(i),{}).get('tail_base',0)
        after=proposed.get(i,baseline.get(str(i),{})).get('tail_base',0)
        return before if mode==0 else after if mode==1 else after-before
    def color(value,mode):
        if mode==2:
            t=min(1,abs(value)/.005)
            return QColor.fromRgbF(1,1-t,1-t) if value>=0 else QColor.fromRgbF(1-t,1-t,1)
        t=max(0,min(1,value/.25))
        return QColor.fromRgbF(max(0,2*t-1),1-abs(2*t-1),max(0,1-2*t))
    image,painter=canvas(1800,850,'C2: proposed influence map on identical REST geometry',
                         'Surface diagram, not a corrected model. X+0.2Z / Y+0.2Z projection; triangles flat-colored by mean vertex weight.')
    for col, title in enumerate(('BASELINE tail_base (0 to 0.25)','PROPOSED tail_base (0 to 0.25)','PROPOSED delta (-0.005 to +0.005)')):
        painter.setPen(QColor('#171717'));painter.drawText(col*600+20,96,title)
        # Depth ordering is for a diagram only; wire and vertex annotations show all local context.
        for f in sorted(context_faces,key=lambda f:sum(points[i][2] for i in faces[f])):
            vertices=faces[f]
            painter.setBrush(color(sum(weight(i,col) for i in vertices)/3,col))
            painter.setPen(QPen(QColor('#777777'),.6))
            painter.drawPolygon(QPolygonF([pt(i,col) for i in vertices]))
        for f in (7323,7586):
            painter.setBrush(QColor(0,0,0,0));painter.setPen(QPen(QColor('#111111'),3))
            painter.drawPolygon(QPolygonF([pt(i,col) for i in faces[f]]))
        for i in sorted(context_ids):
            if i in changed:
                painter.setBrush(color(weight(i,col),col));painter.setPen(QPen(QColor('#111111'),1.5));painter.drawEllipse(pt(i,col),4,4)
            if i in core or i in report['excluded_support_vertices']:
                painter.setPen(QColor('#a000a0') if i in report['excluded_support_vertices'] else QColor('#111111'))
                painter.setFont(QFont('DejaVu Sans',9));painter.drawText(pt(i,col)+QPointF(5,-5),str(i))
    painter.setPen(QColor('#171717'));painter.setFont(QFont('DejaVu Sans',11))
    painter.drawText(20,710,'Black circles: 21 proposed vertices. Black thick triangles: source faces 7323 and 7586 (C2).')
    painter.drawText(20,738,'Magenta IDs: 4001, 4005, 4152, 4155 — frozen neighbors in other edit masks; no seam copy crosses a frozen boundary.')
    painter.drawText(20,766,'Weights: blue 0, green 0.125, red 0.25. Delta: blue decrease, white unchanged, red increase; display range amplified.')
    painter.drawText(20,798,'Small open transition patch, NOT a complete anatomical ring. Proposed weights do not imply fewer intersections.')
    save(image,painter,'proposed_transition.png')

    image,painter=canvas(1600,950,'Exact proposed tail_base changes — all other bones frozen except pelvis',
                         '21 source vertices; each complete normalized 17-bone row is in tail_to_pelvis_proposal.json.')
    painter.setPen(QColor('#171717'));painter.drawText(20,98,'ID       support      before       proposed        delta                     blue = baseline; orange = proposed')
    for index,entry in enumerate(report['measurements']):
        y=130+index*32;i=entry['source_vertex_ids'][0];b=entry['baseline_weights']['tail_base'];a=entry['proposal_weights']['tail_base']
        painter.setPen(QColor('#171717'));painter.setFont(QFont('DejaVu Sans Mono',11))
        painter.drawText(20,y,f'{i:<8} {"core" if i in core else "edge":<8} {b:.7f}    {a:.7f}    {a-b:+.7f}')
        x0=740;x1=x0+b/.25*600;x2=x0+a/.25*600
        painter.setPen(QPen(QColor('#999999'),1));painter.drawLine(QPointF(x0,y-5),QPointF(x0+600,y-5))
        painter.setPen(QPen(QColor('#1b65b9'),2));painter.drawEllipse(QPointF(x1,y-5),3,3)
        painter.setPen(QPen(QColor('#d55a00'),2));painter.drawEllipse(QPointF(x2,y-5),3,3)
    painter.setPen(QColor('#171717'));painter.setFont(QFont('DejaVu Sans',11))
    painter.drawText(20,840,'Maximum change: 0.004256759 (0.425676 percentage points). Pelvis receives the opposite transfer + float32 normalization residue.')
    painter.drawText(20,874,'C1 unchanged: tail weights 3789=.7721604, 3791=.7557423, 3793=.7139621, 4258=.7116715, 4260=.6849859, 4261=.6688845.')
    painter.drawText(20,910,'No weights written to Blender. No new GLB. Exact JSON approval is required before any deformation experiment.')
    save(image,painter,'vertex_weight_plan.png')
    metadata={'status':'PROPOSED_INFLUENCE_DIAGRAMS_NOT_APPLIED_DEFORMATION','source_geometry':'localprep unchanged',
              'context_source':'stage9 fixed-camera baseline sheet; +15 reproduced from the delivered .blend',
              'projection':{'axes':['X+0.2Z','Y+0.2Z'],'bounds':[lo,hi],'same_geometry_all_columns':True},
              'proposal_sha256':report['proposal_sha256'],'deformation_improvement_tested':False,
              'C1_C2_cross_points':json.loads((root/'docs/model-reports/stage9/sheets/sheet_metadata.json').read_text())['sheets']['tail_to_pelvis']['columns']['plus15']['cross_point_markers']}
    (output/'image_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'));parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();render(args.root,args.output)
