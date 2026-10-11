"""Evaluate actual exported trial skin with Panda CharacterJoint transforms; no clips/assets written."""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QGuiApplication
from panda3d.core import LMatrix4, CS_yup_right, CS_default, Thread, GeomVertexReader, OrthographicLens, Point3, Vec3, TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor
from render_weight_handoff import CAMERAS

def run(report_path,source,output,work):
    if work.exists():raise ValueError('New evidence directory required')
    work.mkdir(parents=True);output.mkdir(parents=True,exist_ok=True)
    report=json.loads(report_path.read_text())
    models={'v6_export':Path('assets/3d/tripo/deskcat_calico_h25_v1_skinprobe_v6.glb'),'c2_export':Path(report['export'])}
    d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0];ps=accessor(d,b,p['attributes']['POSITION']);uv=accessor(d,b,p['attributes']['TEXCOORD_0'])
    low=[min(v[i] for v in ps) for i in range(3)];high=[max(v[i] for v in ps) for i in range(3)]
    scale=2/max(high[i]-low[i] for i in range(3));offset=(-(low[0]+high[0])/2*scale,(low[2]+high[2])/2*scale,-low[1]*scale)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen');app=QGuiApplication.instance() or QGuiApplication([])
    renderer=PandaRenderer(models['v6_export'],width=480,height=384)
    cs=LMatrix4.convertMat(CS_yup_right,CS_default);inv=LMatrix4.convertMat(CS_default,CS_yup_right)
    results={'status':'ACTUAL_GLBS_EVALUATED_BY_PANDA3D_CHARACTER_JOINTS','driver':renderer.driver,'backend':renderer.backend,'models':{},
             'limits':'Actual exported joints and transform blends; no generated animation clips. Base-color preview, not full PBR. Geometry errors/crossings audited separately from binary captures.'}
    try:
        for label,path in models.items():
            renderer.load(path);a=renderer.actor
            if not renderer.has_skeleton or a.getAnimNames():raise ValueError('Expected skinned model without animation clips')
            ed,eb,_=read_glb(path);ep=ed['meshes'][0]['primitives'][0]
            eps=accessor(ed,eb,ep['attributes']['POSITION']);euv=accessor(ed,eb,ep['attributes']['TEXCOORD_0'])
            lookup={}
            for i,(point,tex) in enumerate(zip(eps,euv)):lookup.setdefault((*point,*tex),[]).append(i)
            remap=[lookup[(*point,*tex)][0] for point,tex in zip(ps,uv)]
            geoms=a.findAllMatches('**/+GeomNode')
            if len(geoms)!=1 or geoms[0].node().getNumGeoms()!=1:raise ValueError('Single geometry required')
            geom_path=geoms[0];vd=geom_path.node().getGeom(0).getVertexData()
            if vd.getNumRows()!=len(eps):raise ValueError('Unexpected Panda source order')
            reader=GeomVertexReader(vd,'vertex');order_error=0
            for point in eps:
                q=a.getRelativePoint(geom_path,reader.getData3f());order_error=max(order_error,math.dist((q.x,q.z,-q.y),point))
            if order_error>1e-6:raise ValueError('Panda vertex order/space does not match exported GLB')
            controls={bone.getName():a.controlJoint(None,'modelRoot',bone.getName()) for bone in a.getJoints()}
            defaults={bone.getName():LMatrix4(bone.getDefaultValue()) for bone in a.getJoints()}
            parent_index={child:i for i,node in enumerate(ed['nodes']) for child in node.get('children',[])}
            parents={ed['nodes'][j]['name']:ed['nodes'][parent_index[j]]['name'] if j in parent_index else None for j in ed['skins'][0]['joints']}
            world={}
            def rest_world(n):
                if n not in world:world[n]=defaults[n]*rest_world(parents[n]) if parents.get(n) in defaults else defaults[n]
                return world[n]
            axes={}
            for n in defaults:
                inverse=LMatrix4(rest_world(n));inverse.invertInPlace();axes[n]=inverse.xformVec(Vec3(0,1,0))
            poses={};baseline_error=None
            for case,entry in report['trial'].items():
                for name in controls:
                    angle=entry['rotations'].get(name,0)
                    # Blender exporter changes bone-local basis. Use actual Panda bind
                    # axes, with the same rest-world Blender/Panda +Y sagittal axis.
                    controls[name].setMat(LMatrix4.rotateMat(angle,axes[name])*defaults[name])
                a.getPartBundle('modelRoot').forceUpdate()
                animated=vd.animateVertices(True,Thread.getCurrentThread());reader=GeomVertexReader(animated,'vertex');values=[]
                for i in range(len(eps)):
                    q=a.getRelativePoint(geom_path,reader.getData3f());values.append((q.x,q.z,-q.y))
                capture=work/f'{label}_{case}.f32';array('f',(v for i in remap for v in values[i])).tofile(capture.open('wb'))
                if case=='rest':
                    baseline_error=max(math.dist(ps[i],values[j]) for i,j in enumerate(remap))
                    if baseline_error>2e-6:raise ValueError('Controlled Panda rest/bind mismatch')
                poses[case]={'positions_f32':str(capture),'source_vertex_count':len(ps)}
                # Actual-export base-color frames at matched cameras for the report.
                a.setScale(scale);a.setPos(*offset);a.setMaterialOff(20)
                for stage in a.findAllTextureStages():
                    if stage.getMode()!=TextureStage.MModulate:a.setTextureOff(stage,20)
                state=a.getState()
                for view in ('tail','hip'):
                    camera,target,film=CAMERAS[view];lens=OrthographicLens();lens.setNearFar(.01,100);lens.setFilmSize(*film)
                    renderer.base.cam.node().setLens(lens);renderer.base.camera.setPos(*camera);renderer.base.camera.lookAt(Point3(*target),Vec3(0,0,1))
                    renderer.base.setBackgroundColor(.72,.72,.72,1)
                    for style in ('texture','solid','wire'):
                        a.setState(state)
                        if style!='texture':
                            a.setTextureOff(30);a.setMaterialOff(30);a.setColor(.8,.8,.8,1,30)
                            if style=='wire':a.setRenderModeWireframe();a.setLightOff();a.setColor(.1,.1,.1,1,30)
                        for _ in range(2):frame=renderer.frame(0,{State.IDLE:1},480,384)
                        frame.copy().save(str(work/f'{label}_{case}_{view}_{style}.png'))
                a.setState(state);print(label,case,flush=True)
            results['models'][label]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'panda_original_vertex_order_error':order_error,'rest_bind_error':baseline_error,
                                     'controlled_joints':sorted(controls),'poses':poses}
        (output/'panda_capture.json').write_text(json.dumps(results,indent=2)+'\n')
    finally:renderer.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('report','source','output','work'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.report,a.source,a.output,a.work)
