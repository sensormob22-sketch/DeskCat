"""Asset-specific non-production quadruped deformation experiment. No Tripo.
Run with Blender --background --factory-startup --python this.py -- --output DIR.
Creates a separate skin GLB; never overwrites reviewed input or output files.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree
from blender_geometry_review import crossing
from rig_geometry_analysis import mesh_data
from rig_readiness_audit import read_glb, accessor

SOURCE_SHA = '0e98d05ce6184779a1cac655474f7e3738c2dedb46824f72fc93a46163082bc6'

def convert(p):
    return Vector((p[0], -p[2], p[1]))

def inverse(p):
    return (p[0], p[2], -p[1])

def segment_distances(points, a, b):
    a, b = np.array(a), np.array(b)
    ab = b-a
    t = np.clip((points-a) @ ab / (ab @ ab), 0, 1)
    return np.linalg.norm(points-(a+t[:,None]*ab), axis=1)

def pair_set(points, faces):
    vectors = [Vector(p) for p in points]
    tree = BVHTree.FromPolygons(vectors, faces, all_triangles=True, epsilon=0)
    hits = set()
    for a,b in tree.overlap(tree):
        if a >= b or set(faces[a]).intersection(faces[b]): continue
        ta,tb = [vectors[i] for i in faces[a]], [vectors[i] for i in faces[b]]
        if any(crossing(ta[i],ta[(i+1)%3],tb) or crossing(tb[i],tb[(i+1)%3],ta) for i in range(3)):
            hits.add((a,b))
    return hits

def write_snapshot(source, out, positions, normals):
    if out.exists() or out.resolve()==source.resolve(): raise ValueError('Output must be new')
    doc, binary, raw = read_glb(source)
    data = bytearray(binary[:doc['buffers'][0]['byteLength']])
    primitive = doc['meshes'][0]['primitives'][0]
    for attr, vals in [('POSITION',positions),('NORMAL',normals)]:
        acc = doc['accessors'][primitive['attributes'][attr]]
        view = doc['bufferViews'][acc['bufferView']]
        if acc['componentType']!=5126 or acc['type']!='VEC3': raise ValueError('Unexpected float layout')
        offset=view.get('byteOffset',0)+acc.get('byteOffset',0)
        for i,v in enumerate(vals): struct.pack_into('<3f',data,offset+i*view.get('byteStride',12),*v)
        if attr=='POSITION':
            acc['min']=np.min(vals,axis=0).tolist();acc['max']=np.max(vals,axis=0).tolist()
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4)
    data+=b'\0'*(-len(data)%4)
    body=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(data),0x004e4942)+data
    out.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)


def main(source, landmarks, output, export, legacy_root_competition=False, weight_version="v5", holdouts=False):
    if hashlib.sha256(source.read_bytes()).hexdigest()!=SOURCE_SHA: raise ValueError('Unreviewed input')
    if export.exists() or output.exists(): raise ValueError('Use new output paths')
    output.mkdir(parents=True);export.parent.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(landmarks.read_text());regions=cfg['regions']
    doc,binary,_=read_glb(source);prim=doc['meshes'][0]['primitives'][0]
    original=np.array(accessor(doc,binary,prim['attributes']['POSITION']))
    original_norm=np.array(accessor(doc,binary,prim['attributes']['NORMAL']))
    canonical,faces,sources,_=mesh_data(source)
    ids=[sources[i][0] for i in range(len(canonical))]
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source.resolve()),merge_vertices=False)
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    imported=np.array([inverse(mesh.matrix_world @ v.co) for v in mesh.data.vertices])
    if imported.shape!=original.shape or np.max(np.abs(imported-original))>1e-7: raise ValueError('Import vertex order/coordinates differ')
    # Bone heads are joint pivots, local Y follows distal segment. Knees forward,
    # hocks backward in sagittal plane, not a human heel-on-floor chain.
    specs={}
    def add(name,a,b,parent='root'):
        specs[name]={'head_gltf':list(a),'tail_gltf':list(b),'parent':parent,'verified':False}
    add('root',(0,.35,0),(0,.45,0),None)
    add('pelvis',regions['spine_pelvis']['center'],regions['spine_lumbar']['center'])
    add('lumbar',regions['spine_lumbar']['center'],regions['spine_thoracic']['center'])
    add('thoracic',regions['spine_thoracic']['center'],regions['spine_chest']['center'])
    for label in ('FL','FR','HL','HR'):
        front=label.startswith('F')
        joint_names=('shoulder','elbow','wrist') if front else ('hip','stifle','hock')
        centers=[regions[f'{j}_{label}']['center'] for j in joint_names]
        # Distal end from actual low paw center; elevated metacarpal/metatarsal chain.
        footname=('front' if front else 'hind')+('_left' if label.endswith('L') else '_right')
        report=json.loads(Path('docs/model-reports/stage6/localprep_geometry_review.json').read_text())
        end=list(report['paw_surface_segmentation']['feet'][footname]['downward_bottom_band_area_centroid']);end[1]=.012
        add(f'{joint_names[0]}_{label}',centers[0],centers[1], 'root' if front else 'pelvis')
        add(f'{joint_names[1]}_{label}',centers[1],centers[2],f'{joint_names[0]}_{label}')
        add(f'{joint_names[2]}_{label}',centers[2],end,f'{joint_names[1]}_{label}')
    add('tail_base',regions['tail_base']['center'],cfg.get('probe_tail_end_gltf',(.44,.24,0)),'pelvis')
    if weight_version=='v6':
        specs['lumbar']['parent']='thoracic';specs['pelvis']['parent']='lumbar'
        specs['shoulder_FL']['parent']='thoracic';specs['shoulder_FR']['parent']='thoracic'
    rigdata=bpy.data.armatures.new('EXPERIMENTAL_UNVERIFIED');rig=bpy.data.objects.new('EXPERIMENTAL_UNVERIFIED',rigdata)
    bpy.context.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True);mesh.select_set(False)
    bpy.ops.object.mode_set(mode='EDIT')
    for name,spec in specs.items():
        bone=rigdata.edit_bones.new(name);bone.head=convert(spec['head_gltf']);bone.tail=convert(spec['tail_gltf'])
        bone.align_roll(Vector((0,1,0)))
    for name,spec in specs.items():
        if spec['parent']: rigdata.edit_bones[name].parent=rigdata.edit_bones[spec['parent']]
    bpy.ops.object.mode_set(mode='OBJECT')
    names=list(specs);weights=np.zeros((len(canonical),len(names)))
    pts=np.array(canonical)
    weights[:,0]=1
    # Smooth distance-to-chain envelope. Soft tissue region gates avoid opposite
    # limbs and abdomen. Same exact-position seam copies receive same weights.
    for label in ('FL','FR','HL','HR'):
        front=label.startswith('F');side=1 if label.endswith('L') else -1
        chain=[n for n in names if n.endswith('_'+label)]
        dist=np.array([segment_distances(pts,specs[n]['head_gltf'],specs[n]['tail_gltf']) for n in chain]).T
        raw=np.exp(-np.square(dist/.048)*2)
        # limb gate fades towards chest/hip; no inferred rigid leg partition.
        height=np.clip((.38-pts[:,1])/.12,0,1)
        sidegate=np.clip((pts[:,2]*side+.008)/.04,0,1)
        gate=np.clip((.13-dist.min(axis=1))/.07,0,1)*height*sidegate
        if front: gate*=np.clip((-.08-pts[:,0])/.10,0,1)
        else: gate*=np.clip((pts[:,0]-.015)/.07,0,1)
        share=raw/np.maximum(raw.sum(axis=1,keepdims=True),1e-30)
        for j,n in enumerate(chain): weights[:,names.index(n)]+=gate*share[:,j]
    body=np.clip((pts[:,1]-.22)/.12,0,1)
    for name,center,width in [('pelvis',.23,.15),('lumbar',.095,.12),('thoracic',-.06,.14)]:
        weights[:,names.index(name)]=body*np.exp(-((pts[:,0]-center)/width)**2)*.7
    weights[:,names.index('tail_base')]=np.clip((pts[:,0]-.32)/.07,0,1)*2
    tail_mask=None
    if weight_version=='v6':
        from skin_weights_v6 import build_weights
        weights,tail_mask,tail_distance=build_weights(pts,faces,names,specs,segment_distances)
    # Paws are rigid distal blocks below measured cutoff; no toe rig in this probe.
    review=json.loads(Path('docs/model-reports/stage6/localprep_geometry_review.json').read_text())
    for foot,info in review['paw_surface_segmentation']['feet'].items():
        label=cfg['foot_labels'][foot];distal=('wrist_' if label.startswith('F') else 'hock_')+label
        sourceids=set(info['source_vertex_ids'])
        mask=[i for i,v in enumerate(ids) if v in sourceids]
        weights[mask,:]=0;weights[mask,names.index(distal)]=1
    head=(pts[:,0]<-.35)&(pts[:,1]>.30)
    weights[head,:]=0;weights[head,0]=1
    # Root receives the residual, not a competing constant 50% contribution.
    # The first probe showed that constant root influence sheared wrist envelopes.
    if not legacy_root_competition and weight_version=='v5':
        weights[:,0]=np.maximum(0,1-weights[:,1:].sum(axis=1))
    # At most four influences, preserving identical seam coordinates.
    order=np.argsort(weights,axis=1)
    weights[np.arange(len(weights))[:,None],order[:,:-4]]=0
    weights/=weights.sum(axis=1,keepdims=True)
    expanded=np.zeros((len(original),len(names)))
    for i,entries in sources.items(): expanded[entries]=weights[i]
    for j,name in enumerate(names):
        group=mesh.vertex_groups.new(name=name)
        for i,w in enumerate(expanded[:,j]):
            if w>0: group.add([i],float(w),'REPLACE')
    mod=mesh.modifiers.new('Experimental linear skinning','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=False
    # No keyframes or animation clips exported. Test poses remain diagnostics only.
    joint_cases={f'isolated_{name}':{name:15 if not name.startswith(('wrist','hock')) else 10} for name in names if name!='root'}
    poses={'rest':{},'front_bend':{'elbow_FL':15,'elbow_FR':15,'wrist_FL':-10,'wrist_FR':-10},
           'hind_bend':{'stifle_HL':-15,'stifle_HR':-15,'hock_HL':15,'hock_HR':15},
           'pelvis_spine':{'pelvis':5,'lumbar':-5,'thoracic':5},'tail_bend':{'tail_base':15}}
    cases={**poses,**joint_cases}
    if holdouts:
        cases.update({name+'_opposite':{bone:-angle for bone,angle in rotations.items()} for name,rotations in list(cases.items()) if rotations})
        cases['combined_holdout']={'pelvis':5,'lumbar':-5,'tail_base':-15,'elbow_FR':-15,'stifle_HL':15}
        cases['combined_holdout_opposite']={n:-v for n,v in cases['combined_holdout'].items()}
    np.savez_compressed(output/'weights.npz',weights=expanded,bone_names=np.array(names),tail_mask=np.array([]) if tail_mask is None else tail_mask,source_positions=original)
    baseline=pair_set(canonical,faces)
    arrays=np.array(faces);resttris=pts[arrays];restareas=np.linalg.norm(np.cross(resttris[:,1]-resttris[:,0],resttris[:,2]-resttris[:,0]),axis=1)/2
    edgeids=np.unique(np.sort(np.concatenate([arrays[:,[0,1]],arrays[:,[1,2]],arrays[:,[2,0]]]),axis=1),axis=0)
    oldlength=np.linalg.norm(pts[edgeids[:,0]]-pts[edgeids[:,1]],axis=1)
    outcomes={}
    normals_bl=np.array([convert(n) for n in original_norm])
    for pose,rotations in cases.items():
        for pb in rig.pose.bones: pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion()
        for name,degrees in rotations.items():
            pb=rig.pose.bones[name]
            # Rotation about global Blender Y (glTF -Z), mapped to local bone axes.
            axis=pb.bone.matrix_local.to_3x3().inverted() @ Vector((0,1,0))
            pb.rotation_quaternion=Quaternion(axis,math.radians(degrees))
        bpy.context.view_layer.update()
        deps=bpy.context.evaluated_depsgraph_get();evaluated=mesh.evaluated_get(deps);evmesh=evaluated.to_mesh()
        evaluated_positions=np.array([inverse(evaluated.matrix_world @ v.co) for v in evmesh.vertices]);evaluated.to_mesh_clear()
        cp=evaluated_positions[ids];pairs=pair_set(cp,faces)
        tris=cp[arrays];areas=np.linalg.norm(np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]),axis=1)/2
        lengths=np.linalg.norm(cp[edgeids[:,0]]-cp[edgeids[:,1]],axis=1)
        ratio=np.divide(lengths,oldlength,out=np.ones_like(lengths),where=oldlength>1e-10)
        aratio=np.divide(areas,restareas,out=np.ones_like(areas),where=restareas>1e-14)
        delta=np.linalg.norm(cp-pts,axis=1)
        regional={}
        for name,r in regions.items():
            vm=np.linalg.norm(pts-np.array(r['center']),axis=1)<=r['radius'];em=vm[edgeids].any(axis=1);fm=vm[arrays].any(axis=1)
            regional[name]={'vertices':int(vm.sum()),'max_displacement':float(delta[vm].max(initial=0)),
                'edge_ratio_min':float(ratio[em].min(initial=1)), 'edge_ratio_max':float(ratio[em].max(initial=1)),
                'faces_area_below_half':int((aratio[fm]<.5).sum()),'faces_area_above_double':int((aratio[fm]>2).sum()),
                'new_crossing_pairs_touching_roi':sum(any(vm[v] for f in pair for v in faces[f]) for pair in pairs-baseline)}
        outcomes[pose]={'rotations_degrees_about_blender_world_y':rotations,'strict_crossing_pairs':len(pairs),
            'retained_baseline_pairs':len(pairs&baseline),'new_pairs':len(pairs-baseline),'resolved_baseline_pairs':len(baseline-pairs),
            'new_source_face_pairs':[list(p) for p in sorted(pairs-baseline)],
            'retained_source_face_pairs':[list(p) for p in sorted(pairs&baseline)],
            'zero_area_faces':int((areas==0).sum()),'area_below_half_faces':int((aratio<.5).sum()),
            'edge_ratio_min':float(ratio.min()),'edge_ratio_max':float(ratio.max()),
            'edge_ratio_percentiles':np.percentile(ratio,[1,5,50,95,99]).tolist(),
            'area_ratio_percentiles':np.percentile(aratio,[1,5,50,95,99]).tolist(),
            'seam_gap_max':max(float(np.linalg.norm(evaluated_positions[entries]-evaluated_positions[entries[0]],axis=1).max()) for entries in sources.values()),
            'protected_head_max_displacement':float(delta[head].max(initial=0)),'regions':regional}
        if pose in poses or (holdouts and pose in ('isolated_pelvis','isolated_shoulder_FR','tail_bend_opposite','front_bend_opposite','hind_bend_opposite','pelvis_spine_opposite','isolated_pelvis_opposite','isolated_shoulder_FR_opposite','combined_holdout','combined_holdout_opposite')):
            # Transformed original split normals, not destructive recalculation.
            blended=np.zeros_like(normals_bl)
            for j,name in enumerate(names):
                pb=rig.pose.bones[name];transform=(pb.matrix @ pb.bone.matrix_local.inverted()).to_3x3()
                transformed=normals_bl @ np.array(transform).T
                blended+=expanded[:,j,None]*transformed
            blended/=np.maximum(np.linalg.norm(blended,axis=1,keepdims=True),1e-20)
            posednorm=np.array([inverse(n) for n in blended])
            write_snapshot(source,output/f'{pose}.glb',evaluated_positions,posednorm)
            # Small diagnostic geometry arrays permit repeatable metrics, not a new animation.
    for pb in rig.pose.bones: pb.rotation_quaternion=Quaternion()
    bpy.context.view_layer.update()
    boneinfo={n:{**s,'matrix_local_blender':[list(row) for row in rig.data.bones[n].matrix_local]} for n,s in specs.items()}
    bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.wm.save_as_mainfile(filepath=str((output/'experimental_probe.blend').resolve()))
    bpy.ops.export_scene.gltf(filepath=str(export.resolve()),export_format='GLB',use_selection=True,
        export_animations=False,export_skins=True,export_all_influences=False,export_texcoords=True,
        export_normals=True,export_materials='EXPORT',export_yup=True)
    report={'status':'EXPERIMENTAL_UNVERIFIED_NOT_PRODUCTION_RIG','source_sha256':SOURCE_SHA,
        'export':str(export),'export_sha256':hashlib.sha256(export.read_bytes()).hexdigest(),'blender':bpy.app.version_string,
        'coordinate_conversion':'glTF (x,y,z) -> Blender (x,-z,y); sagittal bend about Blender +Y = glTF -Z; local quaternion axis computed from rest bone matrix',
        'anatomical_limits':'Small ±10/15 degree relative probes, pelvis ±5; not certified feline ROM or neutral anatomy. No 30/45 degree stress until small probes accepted.',
        'weight_version':weight_version,'controlled_adjustment_cycles':1 if weight_version=='v6' else 0,
        'bones':boneinfo,'weights':{'method':('v6 connected 3D tail branch and geodesic boundary smoothstep, torso partition of unity, broader asymmetric limb falloff' if weight_version=='v6' else 'v5 segment-distance envelopes and coordinate gates')+'; rigid measured paw patches; head locked to root; top four normalized; identical seam-copy weights',
            'root_rule':('partition of unity neck-to-torso' if weight_version=='v6' else ('competing constant root (rejected v1)' if legacy_root_competition else 'residual normalized root (v2)')),
            'max_influences':int((weights>0).sum(axis=1).max()),'sum_error_max':float(np.abs(weights.sum(axis=1)-1).max()),
            'unweighted_vertices':int((weights.sum(axis=1)==0).sum()),'vertex_count':len(original),'bone_count':len(names),'protected_head_rule':'glTF x < -0.35 and y > 0.30; lower muzzle included','protected_head_canonical_vertices':int(head.sum())},
        'baseline_pairs':[list(p) for p in sorted(baseline)],'baseline_count':len(baseline),'poses':outcomes,
        'limits':'Strict noncoplanar nonadjacent crossing only; excludes shared rest positions. Coplanar contacts, tangencies and adjacent folding not certified. No gait, IK, floor constraint, full PBR or Windows check.'}
    (output/'deformation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'export':str(export),'baseline':len(baseline),'poses':{n:(r['new_pairs'],r['strict_crossing_pairs']) for n,r in outcomes.items()}}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb'))
    p.add_argument('--landmarks',type=Path,default=Path('docs/model-reports/stage7/provisional_landmarks.json'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--export',type=Path,required=True)
    p.add_argument('--legacy-root-competition',action='store_true',help='Compare rejected constant root weighting; historical probes also used older centers/head mask')
    p.add_argument('--weight-version',choices=['v5','v6'],default='v5')
    p.add_argument('--holdouts',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);main(a.source,a.landmarks,a.output,a.export,a.legacy_root_competition,a.weight_version,a.holdouts)
