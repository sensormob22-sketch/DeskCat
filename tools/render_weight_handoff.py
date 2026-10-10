"""Six curated contact sheets from unchanged v6 diagnostic snapshots.
No image synthesis: Panda3D renders actual geometry; Qt composes annotated tables.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QGuiApplication
from panda3d.core import OrthographicLens,Point3,Point2,Vec3,LineSegs,TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State
from rig_readiness_audit import read_glb,accessor

CAMERAS={
 'tail':((2,-3,.60),(.62,-.02,.34),(.90,.72)),
 'thorax':((-1,3,-.3),(-.27,0,.49),(1.40,1.12)),
 'hip':((2,-3,.60),(.47,-.09,.50),(.90,.72)),
 'front':((-2,3,.75),(-.53,.10,.42),(1.10,.88)),
 'wrist':((-3,0,.10),(-.53,0,.11),(.75,.60)),
 'hock':((3,0,.16),(.30,0,.12),(.95,.76)),
}
LABELS={'tail_to_pelvis':'01 Tail / pelvis transition','thoracic_abdomen':'02 Thoracic / abdomen','left_hip':'03 Left hip (HL)','right_shoulder_paw':'04 Right shoulder / front paw (FR)','wrist_to_sole':'05 Wrists / soles (both front paws)','hock_to_sole':'06 Hocks / soles (both hind paws)'}


def posed_heatmap(snapshot,template,out):
    d,b,_=read_glb(snapshot);colors,cb,_=read_glb(template)
    p=colors['meshes'][0]['primitives'][0];a=colors['accessors'][p['attributes']['COLOR_0']];v=colors['bufferViews'][a['bufferView']]
    payload=cb[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']]
    data=bytearray(b[:d['buffers'][0]['byteLength']]);data+=b'\0'*(-len(data)%4);offset=len(data);data+=payload
    view=len(d['bufferViews']);d['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(payload),'target':34962})
    index=len(d['accessors']);d['accessors'].append({'bufferView':view,'componentType':5126,'count':a['count'],'type':'VEC4'})
    d['meshes'][0]['primitives'][0]['attributes']['COLOR_0']=index;d['materials']=colors['materials'];d['buffers'][0]['byteLength']=len(data)
    encoded=json.dumps(d,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);data+=b'\0'*(-len(data)%4)
    body=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(data),0x004e4942)+data
    out.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)



def caption(label,rotations):
    codes={'pelvis':'PE','lumbar':'LU','thoracic':'TH','tail_base':'TA'}
    def short(name):
        if name in codes:return codes[name]
        stem,side=name.rsplit('_',1)
        return {'shoulder':'SH','elbow':'EL','wrist':'WR','hip':'HI','stifle':'ST','hock':'HO'}[stem]+'.'+side
    return label.upper()+' '+(' '.join(short(n)+f'{v:+d}' for n,v in rotations.items()) or '(0)')


def relabel(data,output):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    app=QGuiApplication.instance() or QGuiApplication([])
    review=json.loads((data/'pose_review.json').read_text());metadata=json.loads((output/'sheet_metadata.json').read_text())
    width=400
    for zone,info in review['zones'].items():
        image=QImage(str(output/(zone+'.png')))
        if image.isNull():raise ValueError('Missing contact sheet')
        painter=QPainter(image);painter.fillRect(0,0,image.width(),100,QColor('#eeeeee'));painter.setPen(QColor('#171717'));painter.setFont(QFont('DejaVu Sans',15))
        painter.drawText(15,25,LABELS[zone]+' — UNEDITED v6; review before changes');painter.setFont(QFont('DejaVu Sans',11))
        painter.drawText(15,49,'Rows: texture | solid + red triangles | wire + red triangles | weight '+ '+'.join(info.get('heatmap_bones',[info['bone']]))+' (blue=0, green=.5, red=1)')
        for column,(label,name) in enumerate(info['poses'].items()):
            record=review['poses'][name];meta=metadata['sheets'][zone]['columns'][label];painter.save();painter.setClipRect(column*width,55,width,45);painter.setFont(QFont('DejaVu Sans',10))
            painter.drawText(column*width+8,75,caption(label,record['rotations']));painter.drawText(column*width+8,93,f"New pairs: global {record['new_pairs']}, in zone {meta['zone_new_pairs']}");painter.restore()
        painter.end()
        if not image.save(str(output/(zone+'.png'))):raise RuntimeError('Cannot save table header')
    metadata['caption_codes']='PE pelvis; LU lumbar; TH thoracic; TA tail_base; SH shoulder; EL elbow; WR wrist; HI hip; ST stifle; HO hock; FL/FR/HL/HR as anatomical labels. Complete rotations stored per column.'
    (output/'sheet_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')

def render(data,work,source,output):
    if output.exists():raise ValueError('New sheet directory required')
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    app=QGuiApplication.instance() or QGuiApplication([])
    output.mkdir(parents=True);review=json.loads((data/'pose_review.json').read_text());masks=json.loads((data/'region_masks.json').read_text())
    d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0];positions=accessor(d,b,p['attributes']['POSITION']);indices=[x[0] for x in accessor(d,b,p['indices'])];faces=[indices[i:i+3] for i in range(0,len(indices),3)]
    low=[min(v[i] for v in positions) for i in range(3)];high=[max(v[i] for v in positions) for i in range(3)];scale=2/max(high[i]-low[i] for i in range(3));offset=(-(low[0]+high[0])/2*scale,(low[2]+high[2])/2*scale,-low[1]*scale)
    width,height=400,320;renderer=PandaRenderer(source,width=width,height=height)
    metadata={'status':'UNCHANGED_V6_DIAGNOSTIC_TABLES','projection':'orthographic','tile_resolution':[width,height],'fixed_scale':scale,'fixed_offset':offset,'renderer':renderer.driver,'backend':renderer.backend,'rows':['texture','solid + new crossing triangles','wire + new crossing triangles','primary bone weight'],'columns':['rest','plus10','plus15','minus10','minus15','hold_positive','hold_negative'],'sheets':{},'legend':'Red outlines = new strict crossing triangles in selected zone; black C labels mark computed crossing points; full source face pairs in pose_review.json. Heatmap blue0, green.5, red1; original character textures untouched. All rows use same posed geometry and camera.'}
    def world(pt):return Point3(pt[0]*scale+offset[0],-pt[2]*scale+offset[1],pt[1]*scale+offset[2])
    def screen(pt,lens):
        q=Point2()
        if not lens.project(renderer.base.camera.getRelativePoint(renderer.base.render,world(pt)),q):return None
        return ((q.x+1)*width/2,(1-q.y)*height/2)
    try:
        for zone,info in review['zones'].items():
            camera,target,film=CAMERAS[info['view']];canvas=QImage(7*width,4*height+190,QImage.Format.Format_RGBA8888);canvas.fill(QColor('#eeeeee'))
            painter=QPainter(canvas);painter.setPen(QColor('#171717'));painter.setFont(QFont('DejaVu Sans',15));painter.drawText(15,25,LABELS[zone]+' — UNEDITED v6; review before changes')
            painter.setFont(QFont('DejaVu Sans',11));painter.drawText(15,49,'Rows: texture | solid + red problem triangles | wire + red triangles | weight '+info['bone']+' (blue=0, green=.5, red=1)')
            zone_faces=set(masks['zones'][zone]['observed_problem_source_face_ids']);sheet={'camera':camera,'target':target,'film_size':film,'primary_bone':info['bone'],'columns':{}}
            for column,(label,name) in enumerate(info['poses'].items()):
                record=review['poses'][name];snapshot=Path(record['snapshot']);sd,sb,_=read_glb(snapshot);sp=sd['meshes'][0]['primitives'][0];posed=accessor(sd,sb,sp['attributes']['POSITION'])
                visible=[x for x in record['new_crossings'] if any(f in zone_faces for f in x['source_face_pair'])]
                marked=[]
                for pair in visible:
                    for point in pair['cross_points_gltf']:
                        if not any(sum((point[i]-m['point'][i])**2 for i in range(3))<.0004 for m in marked):
                            marked.append({'label':'C'+str(len(marked)+1),'point':point,'source_face_pair':pair['source_face_pair']})
                        if len(marked)>=3:break
                    if len(marked)>=3:break
                colored=work/(zone+'_'+label+'_color.glb');posed_heatmap(snapshot,work/(zone+'_heatmap.glb'),colored)
                renderer.load(str(snapshot));base_state=renderer.actor.getState()
                for row,style in enumerate(('texture','solid','wire','weight')):
                    if style=='weight':renderer.load(str(colored))
                    else:renderer.actor.setState(base_state)
                    renderer.actor.setScale(scale);renderer.actor.setPos(*offset)
                    renderer.base.setBackgroundColor(.72,.72,.72,1);lens=OrthographicLens();lens.setNearFar(.01,100);lens.setFilmSize(*film);renderer.base.cam.node().setLens(lens);renderer.base.camera.setPos(*camera);renderer.base.camera.lookAt(Point3(*target),Vec3(0,0,1))
                    if style in ('solid','wire'):
                        renderer.actor.setTextureOff(20);renderer.actor.setMaterialOff(20);renderer.actor.setColor(.80,.80,.80,1,20)
                        if style=='wire':renderer.actor.setRenderModeWireframe();renderer.actor.setColor(.12,.12,.12,1,20);renderer.actor.setLightOff()
                    if style=='weight':renderer.actor.setLightOff();renderer.actor.setMaterialOff(20)
                    overlay=None
                    if style in ('solid','wire') and visible:
                        lines=LineSegs();lines.setThickness(1.5);lines.setColor(1,.07,.08,1)
                        for f in sorted({f for x in visible for f in x['source_face_pair']}):
                            triangle=[world(posed[v]) for v in faces[f]];lines.moveTo(triangle[0]);lines.drawTo(triangle[1]);lines.drawTo(triangle[2]);lines.drawTo(triangle[0])
                        overlay=renderer.base.render.attachNewNode(lines.create());overlay.setDepthTest(False);overlay.setDepthWrite(False);overlay.setLightOff()
                    for _ in range(2):frame=renderer.frame(0,{State.IDLE:1},width,height)
                    frame=frame.copy();annotation=QPainter(frame);annotation.setFont(QFont('DejaVu Sans',9))
                    for mark in marked:
                        xy=screen(mark['point'],lens)
                        if not xy or not (0<=xy[0]<width and 0<=xy[1]<height):continue
                        x,y=map(int,xy);annotation.fillRect(x-2,y-2,5,5,QColor('#000000'));annotation.fillRect(x+5,y-15,24,16,QColor('#ffffff'));annotation.setPen(QColor('#000000'));annotation.drawText(x+6,y-2,mark['label'])
                    annotation.end();painter.drawImage(column*width,100+row*height,frame)
                    if overlay:overlay.removeNode()
                painter.setFont(QFont('DejaVu Sans',10));painter.setPen(QColor('#171717'));painter.drawText(column*width+8,75,caption(label,record['rotations']))
                painter.drawText(column*width+8,93,f"New pairs: global {record['new_pairs']}, in zone {len(visible)}")
                for line,mark in enumerate(marked):painter.drawText(column*width+8,4*height+119+line*18,f"{mark['label']}: source faces {mark['source_face_pair'][0]}/{mark['source_face_pair'][1]}")
                sheet['columns'][label]={'pose':name,'rotations':record['rotations'],'global_new_pairs':record['new_pairs'],'zone_new_pairs':len(visible),'cross_point_markers':marked}
            painter.end()
            if not canvas.save(str(output/(zone+'.png'))):raise RuntimeError('Cannot save sheet')
            metadata['sheets'][zone]=sheet
        (output/'sheet_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(json.dumps({'sheets':6,'renderer':renderer.driver,'resolution':[7*width,4*height+190]}))
    finally:renderer.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('data','work','source','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--relabel-only',action='store_true',help='Recompose captions of generated tables from saved measurements; geometry tiles unchanged')
    a=p.parse_args()
    if a.relabel_only:relabel(a.data,a.output)
    else:render(a.data,a.work,a.source,a.output)
