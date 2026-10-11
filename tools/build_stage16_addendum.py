"""Build a cosmetic handoff from existing evidence. No mesh or Blender writes."""
import csv,hashlib,json,os,sys,zipfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont,QPen
from PySide6.QtCore import QPointF
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/model-reports/stage16';REF='8e0c36e'
sys.path.insert(0,str(ROOT/'tools'))
from rig_readiness_audit import read_glb,accessor
BASE=f'https://github.com/sensormob22-sketch/DeskCat/blob/{REF}/'
RAW=f'https://raw.githubusercontent.com/sensormob22-sketch/DeskCat/{REF}/'
app=QGuiApplication.instance() or QGuiApplication([])

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')

def build():
    OUT.mkdir(exist_ok=True);(OUT/'images').mkdir(exist_ok=True)
    old=json.loads((ROOT/'docs/model-reports/stage14/review_manifest.json').read_text());register=json.loads((ROOT/'docs/model-reports/stage13/defect_register.json').read_text());mapping=json.loads((ROOT/'docs/model-reports/exact-weld-proxy/vertex_map.json').read_text())
    d,b,_=read_glb(ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb');pr=d['meshes'][0]['primitives'][0];points=accessor(d,b,pr['attributes']['POSITION']);ids=[x[0] for x in accessor(d,b,pr['indices'])];faces=[ids[i:i+3] for i in range(0,len(ids),3)]
    near=[12122,12146,12149,12150,12159,12160,12162];far=[5552];d14=next(c for c in register['clusters'] if c['id']=='D14')
    groups=[]
    for name,region,selected,context,fans in [('D14_FULL','Source D14 core',d14['source_face_ids'],d14['context_source_face_ids'],d14['fan_groups']),('D14_NEAR_WHITE','Near white rim, ray-proven example',near,[],[]),('FAR_5552','Distant colored surface, not a repair target',far,[],[])]:
        vertices=sorted({mapping['source_to_proxy'][v] for fi in selected+context for v in faces[fi]})
        groups.append({'id':name,'region':region,'review_kind':'COSMETIC_EVIDENCE_ONLY','source_face_ids':selected,'context_source_face_ids':context,'fan_groups':fans,'source_vertex_aliases':{str(v):mapping['proxy_to_sources'][v] for v in vertices}})
    manifest={k:old[k] for k in ['source_scene','source_scene_sha256','objects','rig','deform_bones']};manifest.update(base_commit=REF,clusters=groups,scope='Selection only. No geometry edits authorized. Cosmetic coverage is separate from Bone Heat.',id_convention='0-based original primitive triangle IDs. Both face-order hashes checked before selection.')
    write('review_manifest.json',manifest)
    (OUT/'blender_review_selector.py').write_bytes((ROOT/'docs/model-reports/stage14/blender_review_selector.py').read_bytes())
    rays=json.loads((ROOT/'docs/model-reports/stage15/ray_diagnosis.json').read_text())['oblique'];target=next(r for r in rays if r['pixel']==[420,240]);assert target['hits'][0]['source_face_id']==5552
    write('exact_gap_evidence.json',{'source_commit':REF,'camera_source':'docs/model-reports/stage15/camera_initial.json','pixel_oblique':[420,240],'ray':target,'near_white_source_face_ids':near,'near_triangles':{str(fi):{'source_vertex_ids':faces[fi],'positions_gltf':[points[v] for v in faces[fi]]} for fi in near},'far_face_5552':{'source_vertex_ids':faces[5552],'positions_gltf':[points[v] for v in faces[5552]]},'video_scope':'Two lateral regions visually evidenced; exact source IDs of every video slit not established.'})
    # Project unchanged original triangles into the existing oblique camera image.
    rr=json.loads((ROOT/'docs/model-reports/stage15/rays_oblique.json').read_text());origin=rr[0]['origin'];dx=[(rr[6]['origin'][i]-origin[i])/30 for i in range(3)];dy=[(rr[1]['origin'][i]-origin[i]-dx[i]*10)/40 for i in range(3)]
    def project(p):
        v=[p[i]-origin[i] for i in range(3)];dot=lambda a,b:sum(x*y for x,y in zip(a,b))
        return QPointF((410+dot(v,dx)/dot(dx,dx)-280)*1.5,(200+dot(v,dy)/dot(dy,dy)-110)*1.5+65)
    source=QImage(str(ROOT/'docs/model-reports/stage15/images/before_oblique.png'));assert not source.isNull();crop=source.copy(280,110,320,290).scaled(480,435)
    image=QImage(1440,500,QImage.Format.Format_RGBA8888);image.fill(QColor('#eeeeee'));q=QPainter(image);q.setFont(QFont('DejaVu Sans',10));q.setPen(QColor('#151515'))
    panels=[('Exact ray at pixel 420/240','Original unchanged image',[],None),('Nearest white source faces','Green: rim, not a delete mask',near,QColor('#39ed76')),('Far colored source face 5552','Red: through-depth overlay, behind fur',far,QColor('#ff6659'))]
    for col,(title,note,selected,color) in enumerate(panels):
        q.save();q.translate(col*480,0);q.setPen(QColor('#151515'));q.drawText(8,22,title);q.drawText(8,45,note);q.drawImage(0,65,crop)
        if selected:
            q.setPen(QPen(color,2))
            for fi in selected:
                ps=[project(points[v]) for v in faces[fi]]
                for i in range(3):q.drawLine(ps[i],ps[(i+1)%3])
        q.setPen(QPen(QColor('#00d9ff'),2));pos=QPointF((420-280)*1.5,(240-110)*1.5+65);q.drawEllipse(pos,6,6);q.restore()
    q.end();assert image.save(str(OUT/'images/exact_gap_layers.png'))
    # Four small stills instead of copying all original full-size video artifacts.
    image=QImage(1340,910,QImage.Format.Format_RGBA8888);image.fill(QColor('#eeeeee'));q=QPainter(image);q.setFont(QFont('DejaVu Sans',12));q.setPen(QColor('#151515'))
    for i,(sec,label) in enumerate([(6,'one flank'),(12,'opposite flank'),(20,'underside: BOTH lateral rows'),(31,'lower closeup')]):
        x=(i%2)*670;y=(i//2)*455;q.drawText(x+8,y+23,f'{sec} s / {label}');im=QImage(str(ROOT/f'docs/model-reports/stage15/additional-video/view_{sec:02d}.png'));assert not im.isNull();q.drawImage(x,y+30,im.scaled(670,425))
    q.end();assert image.save(str(OUT/'images/two_sided_video.png'))
    image=QImage(900,1080,QImage.Format.Format_RGBA8888);image.fill(QColor('#eeeeee'));q=QPainter(image)
    for i,name in enumerate(['side','below','oblique']):
        im=QImage(str(ROOT/f'docs/model-reports/stage15/images/comparison_{name}.png'));assert not im.isNull();q.drawImage(0,i*360,im.scaled(900,323))
    q.end();assert image.save(str(OUT/'images/rejected_views.png'))
    files=['docs/model-reports/stage14/DeskCat_Topology_Review.zip','assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend','assets/3d/retopo/deskcat_calico_retopo_16460.glb','docs/model-reports/exact-weld-proxy/vertex_map.json','docs/model-reports/stage15/README.md','docs/model-reports/stage15/patch_trial.json','docs/model-reports/stage15/ray_diagnosis.json','docs/model-reports/stage15/rim_source_triangles.json','docs/model-reports/stage15/camera_initial.json','docs/model-reports/stage15/additional-video/provenance.json']
    files += [f'docs/model-reports/stage15/additional-video/view_{s:02d}.png' for s in [6,12,20,31]]+[f'docs/model-reports/stage15/images/comparison_{name}.png' for name in ['side','below','oblique']]
    write('source_links.json',[{'path':n,'sha256':sha(ROOT/n),'view':BASE+n,'download':RAW+n} for n in files])
    with (OUT/'return_checklist.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['region_or_view','decision_or_result','source_face_ids','new_face_ids','reason','reviewer'])
        for region in ['D14 confirmed representative slit','Other lateral row (identify actual source IDs)','Both sides camera sweep','Underside','Positive oblique','Opposite oblique','Original geometry UV texture preservation','New intersections vs baseline 81','Silhouette and feathered edge','Texture UV normals depth acceptance']:
            w.writerow([region,'','','','',''])
    # Compact archive contains only addon resources; all large historical files are links.
    packed=[p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['DeskCat_Belly_Coat_Addendum.zip','package_checksums.json','verification.json']]
    write('package_checksums.json',{str(p.relative_to(OUT)):sha(p) for p in sorted(packed)})
    with zipfile.ZipFile(OUT/'DeskCat_Belly_Coat_Addendum.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(packed)+[OUT/'package_checksums.json']:z.write(p,'DeskCat_Belly_Coat_Addendum/'+str(p.relative_to(OUT)))
    print(json.dumps({'bytes':(OUT/'DeskCat_Belly_Coat_Addendum.zip').stat().st_size,'selection_sets':len(groups),'new_meshes':0}))

if __name__=='__main__':build()
