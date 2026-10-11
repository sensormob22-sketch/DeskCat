"""Add four editable foot submasks; preserve all actual v6 bone groups and geometry."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from rig_geometry_analysis import mesh_data



def align_axis_guides(rig):
    for bone in rig.data.bones:
        guide=bpy.data.objects['AXIS_'+bone.name];guide.parent=None
        for constraint in list(guide.constraints):guide.constraints.remove(constraint)
        constraint=guide.constraints.new('COPY_TRANSFORMS');constraint.name='Exact bone-head axes';constraint.target=rig;constraint.subtarget=bone.name;constraint.target_space='WORLD';constraint.owner_space='WORLD'
    bpy.context.view_layer.update()
    return max((bpy.data.objects['AXIS_'+bone.name].matrix_world.translation-(rig.matrix_world@rig.pose.bones[bone.name].matrix).translation).length for bone in rig.data.bones)

def finalize(scene,source,data,output):
    if output.exists() or output.resolve()==scene.resolve():raise ValueError('Separate new scene required')
    masks=json.loads((data/'region_masks.json').read_text());points,faces,sources,_=mesh_data(source);reverse={v:i for i,entries in sources.items() for v in entries}
    adj=[set() for _ in points]
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):adj[a].add(b);adj[b].add(a)
    feet=json.loads(Path('docs/model-reports/stage6/localprep_geometry_review.json').read_text())['paw_surface_segmentation']['feet']
    bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()));mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS']
    for zone,foot_names,labels in [('wrist_to_sole',('front_left','front_right'),('FL','FR')),('hock_to_sole',('hind_left','hind_right'),('HL','HR'))]:
        region=masks['zones'][zone];distances=[]
        for foot in foot_names:
            distance=[10**9]*len(points);queue=deque()
            for v in feet[foot]['source_vertex_ids']:distance[reverse[v]]=0;queue.append(reverse[v])
            while queue:
                a=queue.popleft()
                for b in adj[a]:
                    if distance[b]>distance[a]+1:distance[b]=distance[a]+1;queue.append(b)
            distances.append(distance)
        subregions={};all_bones=[];ambiguous=[]
        for side,label in enumerate(labels):
            selected=[v for v in region['editable_source_vertex_ids'] if distances[side][reverse[v]]<distances[1-side][reverse[v]]]
            bones=[stem+'_'+label for stem in (('shoulder','elbow','wrist') if zone.startswith('wrist') else ('hip','stifle','hock'))]
            group=mesh.vertex_groups.new(name='EDIT_'+('wrist_' if zone.startswith('wrist') else 'hock_')+label)
            if selected:group.add(selected,1,'REPLACE')
            subregions[label]={'vertex_group':group.name,'editable_source_vertex_ids':selected,'allowed_bones':bones,'basis':'nearest reviewed connected sole by graph edge distance, not mirrored coordinates'};all_bones+=bones
        ambiguous=[v for v in region['editable_source_vertex_ids'] if distances[0][reverse[v]]==distances[1][reverse[v]]]
        region['subregions']=subregions;region['ambiguous_source_vertex_ids_do_not_edit']=ambiguous
        region['suggested_adjacent_bones']=[bone for bone in all_bones if bone!=region['primary_bone']]
    axis_error=align_axis_guides(bpy.data.objects['V6_17_BONES_UNVERIFIED'])
    if axis_error>1e-7:raise ValueError('Bone guide head mismatch')
    # Only annotation groups/Text are updated, not deforming groups or materials.
    text=bpy.data.texts['REGION_MASKS.json'];text.clear();text.write(json.dumps(masks,indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(output.resolve()),compress=True)
    (data/'region_masks.json').write_text(json.dumps(masks,indent=2)+'\n');audit=json.loads((data/'scene_audit.json').read_text());audit['scene']=str(output);audit['scene_sha256']=hashlib.sha256(output.read_bytes()).hexdigest();audit['foot_submasks']={zone:{label:len(x['editable_source_vertex_ids']) for label,x in masks['zones'][zone]['subregions'].items()} for zone in ('wrist_to_sole','hock_to_sole')};audit['axis_guide_head_error_max']=axis_error;audit['finalization']='Four foot graph-distance review submasks added. Actual v6 deforming groups unchanged.';(data/'scene_audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit['foot_submasks']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('scene','source','data','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);finalize(a.scene,a.source,a.data,a.output)
