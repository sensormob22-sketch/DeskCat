"""Read-only correspondence and proposal validation; deliberately has no apply/export API."""
import argparse
import hashlib
import json
import math
from pathlib import Path
if __package__:
    from .rig_readiness_audit import read_glb,accessor
else:
    from rig_readiness_audit import read_glb,accessor


def source_skin_weights(source,skin):
    a,ab,_=read_glb(source);b,bb,_=read_glb(skin)
    def arrays(d,bin):
        p=d['meshes'][0]['primitives'][0]
        return p,accessor(d,bin,p['attributes']['POSITION']),accessor(d,bin,p['attributes']['TEXCOORD_0'])
    _,ps,uv=arrays(a,ab);p,newps,newuv=arrays(b,bb)
    names=[b['nodes'][i]['name'] for i in b['skins'][0]['joints']]
    joints=accessor(b,bb,p['attributes']['JOINTS_0']);weights=accessor(b,bb,p['attributes']['WEIGHTS_0'])
    lookup={}
    for position,texcoord,js,ws in zip(newps,newuv,joints,weights):
        key=(*position,*texcoord);row={n:0. for n in names}
        for j,w in zip(js,ws):row[names[j]]+=w
        if key in lookup and any(abs(row[n]-lookup[key][n])>1e-7 for n in names):raise ValueError('Exporter split has conflicting weights')
        lookup[key]=row
    rows=[]
    for position,texcoord in zip(ps,uv):
        key=(*position,*texcoord)
        if key not in lookup:raise ValueError('Original source position/UV missing in skin')
        rows.append(lookup[key])
    return names,rows,ps


def validate_proposal(proposal,masks,source,skin,scene=None):
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest();skin_sha=hashlib.sha256(skin.read_bytes()).hexdigest()
    if proposal.get('baseline_source_sha256')!=source_sha or masks['source_sha256']!=source_sha:raise ValueError('Source hash mismatch')
    if proposal.get('baseline_skin_sha256')!=skin_sha:raise ValueError('Skin hash mismatch')
    if proposal.get('baseline_bone_weights_sha256_float32')!=masks['bone_weight_sha256_float32']:raise ValueError('Blender weight baseline mismatch')
    if scene is not None and proposal.get('baseline_scene_sha256')!=hashlib.sha256(scene.read_bytes()).hexdigest():raise ValueError('Scene hash mismatch')
    if proposal.get('region') not in masks['zones']:raise ValueError('Unknown region')
    names,rows,positions=source_skin_weights(source,skin);zone=masks['zones'][proposal['region']]
    allowed=set(zone['editable_source_vertex_ids']);protected=set(masks['protected_source_vertex_ids'])
    bones={zone['primary_bone'],*zone['suggested_adjacent_bones']};changes={}
    for entry in proposal.get('changes',[]):
        row=entry['weights']
        if not row or set(row)-set(names):raise ValueError('Unknown bone influence')
        if any(isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or w<0 or w>1 for w in row.values()):raise ValueError('Weights must be finite in [0,1]')
        if sum(w>0 for w in row.values())>4 or abs(sum(row.values())-1)>1e-6:raise ValueError('Max four normalized influences required')
        for i in entry['source_vertex_ids']:
            if isinstance(i,bool) or not isinstance(i,int) or i not in allowed or i in protected:raise ValueError('Outside editable region or protected vertex')
            allowed_changes=bones
            if zone.get('subregions'):
                owner=next((r for r in zone['subregions'].values() if i in r['editable_source_vertex_ids']),None)
                if owner is None:raise ValueError('Ambiguous foot ownership')
                allowed_changes=set(owner['allowed_bones'])
            baseline_row=masks['baseline_vertex_weights'].get(str(i))
            if baseline_row is None:raise ValueError('Missing Blender baseline row')
            if any(abs(row.get(n,0)-baseline_row.get(n,0))>1e-7 for n in set(names)-allowed_changes):
                raise ValueError('Forbidden cross-foot influence' if zone.get('subregions') else 'Forbidden bone influence change')
            if i in changes:raise ValueError('Duplicate vertex proposal')
            changes[i]=row
    seams={}
    for i,p in enumerate(positions):seams.setdefault(tuple(p),[]).append(i)
    for i,row in changes.items():
        for j in seams[tuple(positions[i])]:
            if j not in changes or any(abs(changes[j].get(n,0)-row.get(n,0))>1e-7 for n in names):raise ValueError('All exact-position seam copies need identical proposed weights')
    return {'valid_for_review':True,'changed_source_vertices_proposed':len(changes),'weights_applied':False,'new_skinprobe_exported':False,'status':'DRAFT_ONLY_REQUIRES_HUMAN_REVIEW','limits':'Validation checks scope, bone names, normalized values and seam identity. It does not certify visual deformation or authorize applying weights.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('proposal','masks','source','skin'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--scene',type=Path)
    a=p.parse_args();r=validate_proposal(json.loads(a.proposal.read_text()),json.loads(a.masks.read_text()),a.source,a.skin,a.scene);print(json.dumps(r))
