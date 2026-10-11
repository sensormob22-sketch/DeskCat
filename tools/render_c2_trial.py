"""Matched measured before/after views, including actual Panda-skinned exports."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QGuiApplication
from panda3d.core import OrthographicLens,Point3,Vec3,LineSegs
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from render_weight_handoff import CAMERAS
from rig_readiness_audit import read_glb,accessor

def render(source,report_path,panda_work,output):
    output.mkdir(parents=True,exist_ok=True);report=json.loads(report_path.read_text())
    d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0];ps=accessor(d,b,p['attributes']['POSITION'])
    idx=[i[0] for i in accessor(d,b,p['indices'])];faces=[idx[i:i+3] for i in range(0,len(idx),3)]
    low=[min(v[i] for v in ps) for i in range(3)];high=[max(v[i] for v in ps) for i in range(3)]
    scale=2/max(high[i]-low[i] for i in range(3));offset=(-(low[0]+high[0])/2*scale,(low[2]+high[2])/2*scale,-low[1]*scale)
    def world(pt):return Point3(pt[0]*scale+offset[0],-pt[2]*scale+offset[1],pt[1]*scale+offset[2])
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication.instance() or QGuiApplication([])
    renderer=PandaRenderer(source,width=400,height=320);metadata={'status':'ONE_REJECTED_C2_TRIAL_MATCHED_VIEWS','scale':scale,'offset':offset,'driver':renderer.driver,'sheets':{},'limits':'Base-color preview, not full PBR; red source triangles drawn through geometry to show exact C2 face IDs.'}
    def canvas(columns,width,height,title):
        image=QImage(columns*width,3*height+145,QImage.Format.Format_RGBA8888);image.fill(QColor('#eeeeee'))
        q=QPainter(image);q.setPen(QColor('#171717'));q.setFont(QFont('DejaVu Sans',15));q.drawText(15,28,title)
        q.setFont(QFont('DejaVu Sans',11));q.drawText(15,53,'Rows: base color | solid | wire. Same cameras and rest normalization. No silhouette improvement claimed.')
        return image,q
    try:
        for name,view,cases in (
          ('tail_blender_before_after','tail',['tail_plus10','tail_plus15','tail_minus15','hold_negative']),
          ('pelvis_hip_before_after','hip',['pelvis_plus5','hip_plus15','hip_minus15','hold_positive']),
          ('c2_closeup_before_after','close',['tail_plus15'])):
            width,height=(600,480) if view=='close' else (400,320)
            image,q=canvas(len(cases)*2,width,height,name+' — v6 / ONE C2 trial (not production)');col=0;columns=[]
            if view!='close':camera,target,film=CAMERAS[view]
            else:
                snap=Path(report['baseline']['tail_plus15']['snapshot']);sd,sb,_=read_glb(snap);sp=sd['meshes'][0]['primitives'][0];posed=accessor(sd,sb,sp['attributes']['POSITION'])
                verts={i for fid in (7323,7586) for i in faces[fid]};center=[sum(posed[i][k] for i in verts)/len(verts) for k in range(3)]
                target=tuple(world(center));camera=(target[0]+2,target[1]-3,target[2]+.6);film=(.055,.044)
            for case in cases:
                for label,key in (('v6','baseline'),('C2 trial','trial')):
                    record=report[key][case];snapshot=Path(record['snapshot']);renderer.load(snapshot)
                    sd,sb,_=read_glb(snapshot);sp=sd['meshes'][0]['primitives'][0];posed=accessor(sd,sb,sp['attributes']['POSITION'])
                    actor=renderer.actor;actor.setScale(scale);actor.setPos(*offset);state=actor.getState()
                    lens=OrthographicLens();lens.setFilmSize(*film);lens.setNearFar(.01,100);renderer.base.cam.node().setLens(lens)
                    renderer.base.camera.setPos(*camera);renderer.base.camera.lookAt(Point3(*target),Vec3(0,0,1));renderer.base.setBackgroundColor(.72,.72,.72,1)
                    q.setPen(QColor('#171717'));q.setFont(QFont('DejaVu Sans',10));q.drawText(col*width+8,78,case+' / '+label);q.drawText(col*width+8,97,f"New pairs {record['new_pairs']}; C2 {'YES' if record['C2_intersects'] else 'no'}")
                    for row,style in enumerate(('texture','solid','wire')):
                        actor.setState(state);overlay=None
                        if style!='texture':
                            actor.setTextureOff(30);actor.setMaterialOff(30);actor.setColor(.8,.8,.8,1,30)
                            if style=='wire':actor.setRenderModeWireframe();actor.setLightOff();actor.setColor(.1,.1,.1,1,30)
                            if view=='close':
                                lines=LineSegs();lines.setColor(1,.04,.04,1);lines.setThickness(2)
                                for fid in (7323,7586):
                                    triangle=[world(posed[i]) for i in faces[fid]];lines.moveTo(triangle[0]);lines.drawTo(triangle[1]);lines.drawTo(triangle[2]);lines.drawTo(triangle[0])
                                overlay=renderer.base.render.attachNewNode(lines.create());overlay.setDepthTest(False);overlay.setDepthWrite(False);overlay.setLightOff()
                        for _ in range(2):frame=renderer.frame(0,{State.IDLE:1},width,height)
                        q.drawImage(col*width,110+row*height,frame.copy())
                        if overlay:overlay.removeNode()
                    columns.append({'label':label,'case':case,'camera':camera,'target':target,'film':film,'snapshot':str(snapshot)});col+=1
            q.setPen(QColor('#171717'));q.drawText(15,3*height+132,'C2: source faces 7323 / 7586. C1 and every unapproved vertex stay unchanged in Blender; full pair sets and strain in report.')
            q.end();image.save(str(output/(name+'.png')));metadata['sheets'][name]=columns
        panda=json.loads((report_path.parent/'panda_deformation.json').read_text()) if (report_path.parent/'panda_deformation.json').exists() else None
        cases=['tail_plus15','hold_negative'];width,height=480,384;image,q=canvas(4,width,height,'ACTUAL exported skins in Panda3D — v6 / C2 trial')
        for index,(case,label) in enumerate((case,label) for case in cases for label in ('v6_export','c2_export')):
            q.setPen(QColor('#171717'));q.setFont(QFont('DejaVu Sans',11));q.drawText(index*width+8,79,case+' / '+label)
            if panda:q.drawText(index*width+8,98,'New pairs '+str(panda['models'][label][case]['new_pairs']))
            for row,style in enumerate(('texture','solid','wire')):
                frame=QImage(str(panda_work/f'{label}_{case}_tail_{style}.png'))
                if frame.isNull():raise ValueError('Missing actual-export Panda capture')
                q.drawImage(index*width,110+row*height,frame)
        q.setPen(QColor('#171717'));q.drawText(15,3*height+132,'Driven CharacterJoint skinning from actual GLB. Tiny-weight export cutoff and Panda float precision are reported separately.')
        q.end();image.save(str(output/'actual_export_before_after.png'))
        (output/'image_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    finally:renderer.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','report','panda-work','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();render(a.source,a.report,a.panda_work,a.output)
