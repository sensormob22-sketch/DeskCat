"""Actually evaluate all baked cage morphs with Panda3D; compare source-order data.
Also produce matched base-color/solid/wire images. No animations authored.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont
from panda3d.core import OrthographicLens,Point3,Vec3,LineSegs,GeomVertexReader,Thread,TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor

def main():
    root=Path.cwd();out=root/'docs/model-reports/stage12';report=json.loads((out/'comparison.json').read_text());images=out/'images';images.mkdir(exist_ok=True)
    glb=root/'assets/3d/tripo/deskcat_cage_trial_01_baked_poses.glb';source=root/'assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'
    d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0];rest=accessor(d,b,p['attributes']['POSITION']);indices=[v[0] for v in accessor(d,b,p['indices'])];faces=[indices[i:i+3] for i in range(0,len(indices),3)]
    gd,gb,_=read_glb(glb);names=gd['meshes'][0]['extras']['targetNames']
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication.instance() or QGuiApplication([])
    renderer=PandaRenderer(glb,width=360,height=300);actor=renderer.actor;geompath=actor.find('**/+GeomNode');vd=geompath.node().getGeom(0).getVertexData();bundle=actor.getPartBundle('modelRoot')
    measured={}
    work=root/'artifacts/stage12_panda';work.mkdir(exist_ok=True)
    for case in ['rest',*names]:
        for name in names:
            if not bundle.freezeJoint(name,1.0 if name==case else 0.0):raise ValueError('Panda failed to drive baked morph '+name)
        bundle.forceUpdate();animated=vd.animateVertices(True,Thread.getCurrentThread());reader=GeomVertexReader(animated,'vertex');positions=[]
        while not reader.isAtEnd():
            q=actor.getRelativePoint(geompath,reader.getData3());positions.append((q.x,q.z,-q.y))
        sd,sb,_=read_glb(root/report['models']['cage'][case]['snapshot']);sp=sd['meshes'][0]['primitives'][0];expected=accessor(sd,sb,sp['attributes']['POSITION']) if case!='rest' else rest
        if len(positions)!=len(rest):raise ValueError('Panda changed vertex order/count')
        error=max(sum((a-b)**2 for a,b in zip(actual,wanted))**.5 for actual,wanted in zip(positions,expected))
        if error>2e-6:raise ValueError('Actual morph positions disagree: '+str(error))
        (work/f'{case}.f32').write_bytes(b''.join(struct.pack('<3f',*pt) for pt in positions))
        measured[case]={'max_position_error':error,'vertices':len(positions),'morph_driver':'PartBundle.freezeJoint scalar / GeomVertexData.animateVertices'}
    driver=renderer.driver
    # Rest normalization and camera fixed across every before/after pair.
    lo=[min(v[i] for v in rest) for i in range(3)];hi=[max(v[i] for v in rest) for i in range(3)];scale=2/max(hi[i]-lo[i] for i in range(3));offset=(-(lo[0]+hi[0])/2*scale,(lo[2]+hi[2])/2*scale,-lo[1]*scale)
    def world(pt):return Point3(pt[0]*scale+offset[0],-pt[2]*scale+offset[1],pt[1]*scale+offset[2])
    camera_records={}
    for label,zone,cases in [('tail','tail_to_pelvis',['tail_plus10','tail_minus10','tail_plus15','tail_minus15']),('hip','left_hip',['hip_plus10','hip_minus10','hip_plus15','hip_minus15']),('combined','tail_to_pelvis',['rest','combined_positive','combined_negative'])]:
        ids=set(map(int,next(c['source_mask'] for c in json.loads((out/'cage_definitions.json').read_text())['cages'] if c['zone']==zone)))
        bounds=report['models']['v6']['rest']['regions'][zone]['bounds'];center=[(a+b)/2 for a,b in zip(bounds['min'],bounds['max'])];target=world(center);camera=Point3(target.x+2,target.y-3,target.z+.6);film=(.85,.71) if label=='combined' else (.60,.50)
        canvas=QImage(len(cases)*2*360,3*300+100,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'));q=QPainter(canvas);q.setPen(QColor('#111111'));q.setFont(QFont('DejaVu Sans',12));q.drawText(10,23,label+' — v6 / single REJECTED cage trial; matched cameras. Rows: base color / solid / wire + red new crossings')
        for j,case in enumerate(cases):
            for k,model in enumerate(['v6','cage']):
                col=j*2+k;record=report['models'][model][case]
                # Cage images use the actual baked GLB and runtime morph deformation.
                renderer.load(glb if model=='cage' else root/record['snapshot']);actor=renderer.actor
                if model=='cage':
                    bundle=actor.getPartBundle('modelRoot')
                    for name in names:bundle.freezeJoint(name,1.0 if name==case else 0.0)
                    bundle.forceUpdate()
                actor.setScale(scale);actor.setPos(*offset);actor.setMaterialOff(20)
                for stage in actor.findAllTextureStages():
                    if stage.getMode()!=TextureStage.MModulate:actor.setTextureOff(stage,20)
                originalstate=actor.getState()
                lens=OrthographicLens();lens.setFilmSize(*film);lens.setNearFar(.01,100);renderer.base.cam.node().setLens(lens);renderer.base.camera.setPos(camera);renderer.base.camera.lookAt(target,Vec3(0,0,1));renderer.base.setBackgroundColor(.72,.72,.72,1)
                sd,sb,_=read_glb(root/record['snapshot']);sp=sd['meshes'][0]['primitives'][0];ps=accessor(sd,sb,sp['attributes']['POSITION'])
                q.setPen(QColor('#111111'));q.setFont(QFont('DejaVu Sans',10));q.drawText(col*360+8,48,case+' / '+model);q.drawText(col*360+8,68,'New crossing pairs: '+str(record['new_pairs']))
                for row,style in enumerate(['texture','solid','wire']):
                    actor.setState(originalstate);overlay=None
                    if style!='texture':
                        actor.setTextureOff(30);actor.setMaterialOff(30);actor.setColor(.8,.8,.8,1,30)
                    if style=='wire':
                        actor.setRenderModeWireframe();actor.setLightOff();actor.setColor(.15,.15,.15,1,30)
                        lines=LineSegs();lines.setColor(1,.03,.03,1);lines.setThickness(1.5)
                        for pair in record['new_source_face_pairs']:
                            for fid in pair:
                                if not any(v in ids for v in faces[fid]):continue
                                tri=[world(ps[v]) for v in faces[fid]];lines.moveTo(tri[0]);lines.drawTo(tri[1]);lines.drawTo(tri[2]);lines.drawTo(tri[0])
                        overlay=renderer.base.render.attachNewNode(lines.create());overlay.setDepthTest(False);overlay.setDepthWrite(False);overlay.setLightOff()
                    frame=renderer.frame(0,{State.IDLE:1},360,300);q.drawImage(col*360,80+row*300,frame.copy())
                    if overlay:overlay.removeNode()
        q.end();canvas.save(str(images/(label+'_matched.png')));camera_records[label]={'camera':list(camera),'target':list(target),'film':film,'scale':scale,'offset':offset,'cage_views':'Actual baked morph GLB driven in Panda3D','red_overlay':'Exact new source triangle IDs, drawn through depth for location only'}
    renderer.close()
    (out/'panda_morph.json').write_text(json.dumps({'environment':'Linux Panda3D 1.10.15 / panda3d-gltf 1.3.0','driver':driver,'cases':measured,'cameras':camera_records,'glb_sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'limitation':'10 discrete measured morph poses, no animation clips. Interpolation between poses and arbitrary combined motion are unverified; rest normals retained, not final lighting.'},indent=2)+'\n')

if __name__=='__main__':main()
