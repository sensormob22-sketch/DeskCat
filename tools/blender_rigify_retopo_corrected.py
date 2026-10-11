"""Second, separately authorized Cat attempt after mandatory preflight. No fitting retries or production clips.
blender -b --factory-startup --python-exit-code 1 --python tools/blender_rigify_retopo_corrected.py
"""
import hashlib,json,math,struct,sys,time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector,Quaternion,Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor
from blender_deformation_probe import pair_set,convert,inverse

ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/rigify-corrected';WORK=ROOT/'artifacts/rigify_corrected'
SRC=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
SCENE=ROOT/'assets/rigging/deskcat_retopo_rigify_trial_02.blend'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,default=lambda o:o.item() if isinstance(o,np.generic) else o)+'\n')

def main():
    execute='--execute' in sys.argv
    if execute:
        gate=json.loads((OUT/'preflight.json').read_text())
        if not gate['structural_pass'] or not gate.get('visual_anatomy_review_pass') or (OUT/'attempt_started.json').exists():raise ValueError('Preflight failed/unreviewed or attempt already used')
        if sha(SCENE)!=gate['prepared_scene_sha256']:raise ValueError('Prepared scene changed')
    elif SCENE.exists() or WORK.exists():raise ValueError('New output names required')
    OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=execute)
    frozen=json.loads((OUT/'preserved_manifest.json').read_text()) if execute else {str(p.relative_to(ROOT)):sha(p) for folder in ['assets/3d','assets/rigging'] for p in (ROOT/folder).rglob('*') if p.is_file()}
    assert all(sha(ROOT/p)==h for p,h in frozen.items())
    write(OUT/'preserved_manifest.json',frozen)
    d,buf,_=read_glb(SRC);prim=d['meshes'][0]['primitives'][0];original=np.array(accessor(d,buf,prim['attributes']['POSITION']));indices=np.array(accessor(d,buf,prim['indices'])).reshape(-1,3)
    uv=np.array(accessor(d,buf,prim['attributes']['TEXCOORD_0']));assert np.isfinite(uv).all()
    def texture_hashes(doc,binary):
        result=[]
        for image in doc['images']:
            v=doc['bufferViews'][image['bufferView']];start=v.get('byteOffset',0);result.append(hashlib.sha256(binary[start:start+v['byteLength']]).hexdigest())
        return result
    od,ob,_=read_glb(ROOT/'assets/3d/tripo/deskcat_calico_h25_v1.glb')
    preflight={'sha256':sha(SRC),'triangles':len(indices),'source_vertices':len(original),'input_skin_joints':len(d['skins'][0]['joints']),'animations':len(d.get('animations',[])),'uv_finite':True,'uv_bounds':[uv.min(0).tolist(),uv.max(0).tolist()],'texture_sha256':texture_hashes(d,buf),'textures_match_highres_original':texture_hashes(d,buf)==texture_hashes(od,ob),'material_count':len(d['materials']),'materials':d['materials'],'uv_limit':'Topology differs from original; equality of UV arrays cannot establish retopology appearance. Check mapped appearance in images.'}
    write(OUT/'input_audit.json',preflight)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(SRC),merge_vertices=False)
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');oldrig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    bpy.context.view_layer.update()
    def evaluated():
        ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();ps=np.array([inverse(ev.matrix_world@v.co) for v in m.vertices]);ev.to_mesh_clear();return ps
    baseline=evaluated()
    if len(baseline)!=len(original):raise ValueError('Importer changed source vertex count')
    # Keep the imported baseline surface. Only detached experiment loses the supplied skin.
    transform=mesh.matrix_world.copy();mesh.parent=None;mesh.matrix_world=transform
    for mod in list(mesh.modifiers):
        if mod.type=='ARMATURE':mesh.modifiers.remove(mod)
    detached=evaluated();rest_delta=float(abs(detached-baseline).max())
    # Supplied skin is not a neutral rest reference: import incorporates inverse-bind
    # transforms. New rigging copy uses the intact primitive in its documented Y-up
    # geometry frame, NOT the supplied skin's already-deformed default pose.
    preflight['input_imported_skin_difference_after_detach']=rest_delta
    preflight['rigging_geometry_basis']='Original POSITION primitive, upright glTF frame. Supplied 21-joint skin discarded only in new copy; not copied as neutral skeleton.'
    mesh.matrix_world=Matrix.Identity(4)
    for v,pt in zip(mesh.data.vertices,original):v.co=convert(pt)
    normal_values=accessor(d,buf,prim['attributes']['NORMAL'])
    mesh.data.normals_split_custom_set_from_vertices([convert(n) for n in normal_values]);mesh.data.update();bpy.context.view_layer.update()
    baseline=evaluated()
    if float(abs(baseline-original).max())>1e-7:raise ValueError('Working copy does not match original primitive')
    write(OUT/'input_audit.json',preflight)
    mesh.vertex_groups.clear();mesh.name='RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'
    bpy.data.objects.remove(oldrig,do_unlink=True)  # Never use the rejected 21-joint skin.
    source_faces=np.array([p.vertices[:] for p in mesh.data.polygons]);assert np.array_equal(source_faces,indices)
    canonical,rev=np.unique(baseline,axis=0,return_inverse=True);faces=rev[indices];first=np.array([np.where(rev==i)[0][0] for i in range(len(canonical))])
    aliases=[np.where(rev==i)[0] for i in range(len(canonical))]
    oldpairs=pair_set(canonical,faces.tolist());tri=canonical[faces];oldareas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0);oldlength=np.linalg.norm(canonical[edges[:,0]]-canonical[edges[:,1]],axis=1)
    frozen_mesh={'positions':sha_bytes(np.array([v.co[:] for v in mesh.data.vertices],dtype='<f4')),'uv':sha_bytes(np.array([v.uv[:] for v in mesh.data.uv_layers.active.data],dtype='<f4'))}
    # Static snapshots retain source buffer/UV/images. Skin is explicitly removed; not rig exports.
    def snapshot(path,ps):
        doc=json.loads(json.dumps(d));data=bytearray(buf[:doc['buffers'][0]['byteLength']]);pr=doc['meshes'][0]['primitives'][0]
        for key in ['JOINTS_0','WEIGHTS_0']:pr['attributes'].pop(key,None)
        doc.pop('skins',None);doc.pop('animations',None);doc['nodes']=[{'mesh':0}];doc['scenes']=[{'nodes':[0]}];doc['scene']=0
        acc=doc['accessors'][pr['attributes']['POSITION']];view=doc['bufferViews'][acc['bufferView']];off=view.get('byteOffset',0)+acc.get('byteOffset',0)
        for i,pt in enumerate(ps):struct.pack_into('<3f',data,off+i*view.get('byteStride',12),*pt)
        acc['min']=ps.min(0).tolist();acc['max']=ps.max(0).tolist();j=json.dumps(doc,separators=(',',':')).encode();j+=b' '*(-len(j)%4);data+=b'\0'*(-len(data)%4)
        body=struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(data),0x004e4942)+data;path.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
    snapshot(WORK/'input_rest.glb',baseline)
    bpy.ops.preferences.addon_enable(module='rigify');import rigify.metarigs.Animals.cat as cat
    bpy.ops.object.armature_add();meta=bpy.context.object;meta.name='CAT_METARIG_TRIAL_02';cat.create(meta)
    bpy.ops.object.mode_set(mode='EDIT')
    remove={b.name for b in meta.data.edit_bones if b.name=='Bone' or b.name=='face' or b.name.startswith(('f_palm','f_index','f_middle','f_ring','f_pinky','r_palm','r_index','r_middle','r_ring','r_pinky'))}
    for b in meta.data.edit_bones:
        if any(a.name=='face' for a in b.parent_recursive):remove.add(b.name)
    for name in remove:
        if name in meta.data.edit_bones:meta.data.edit_bones.remove(meta.data.edit_bones[name])
    transform=Matrix(((0,1.4,0,0),(-2.1,0,0,0),(0,0,1.65,0),(0,0,0,1)))
    for b in meta.data.edit_bones:b.transform(transform)
    def setbone(name,a,b):
        bone=meta.data.edit_bones[name];bone.head=convert(a);bone.tail=convert(b);bone.align_roll(Vector((0,1,0)))
    spine=[(.19,.35,0),(.10,.375,0),(-.05,.385,0),(-.20,.385,0),(-.25,.40,0),(-.29,.435,0),(-.33,.47,0),(-.405,.49,0)]
    spine[0]=tails_root=(.315,.30,0) # Preserve tail pivot; lengthen posterior spine into pelvis.
    for i in range(7):setbone('spine'+(f'.{i:03}' if i else ''),spine[i],spine[i+1])
    tails=[(.315,.30,0),(.36,.235,.004),(.395,.15,.012),(.44,.085,.022),(.485,.075,.03)]
    for i in range(4):setbone(f'tail.{i+1:03}',tails[i],tails[i+1])
    landmarks=json.loads((ROOT/'docs/model-reports/stage6/anatomical_landmarks.json').read_text())['regions']
    limb_anchors={};contacts={}
    for side,suffix in [('L','L'),('R','R')]:
        fl='F'+side;hl='H'+side
        shoulder=landmarks['shoulder_'+fl]['center'];elbow=landmarks['elbow_'+fl]['center'];wrist=landmarks['wrist_'+fl]['center']
        hip=landmarks['hip_'+hl]['center'];knee=landmarks['stifle_'+hl]['center'];hock=landmarks['hock_'+hl]['center']
        def contact(anchor):
            mask=(np.linalg.norm(baseline[:,[0,2]]-np.array(anchor)[[0,2]],axis=1)<.07)&(baseline[:,1]<.035)
            ids=np.where(mask)[0]
            if not len(ids):raise ValueError('No observed paw below provisional anchor')
            p=np.median(baseline[ids],axis=0);p[1]=float(baseline[ids,1].min())+.012
            return p.tolist(),ids
        fp,fids=contact(wrist);hp,hids=contact(hock);contacts[fl]=fids.tolist();contacts[hl]=hids.tolist()
        ftoe=[fp[0]-.035,fp[1]-.006,fp[2]];htoe=[hp[0]-.035,hp[1]-.006,hp[2]]
        setbone('shoulder.'+suffix,[-.19,.405,shoulder[2]*.5],shoulder)
        for name,a,b in [('upper_arm',shoulder,elbow),('forearm',elbow,wrist),('hand',wrist,fp),('f_toe',fp,ftoe),('thigh',hip,knee),('shin',knee,hock),('foot',hock,hp),('r_toe',hp,htoe)]:setbone(name+'.'+suffix,a,b)
        setbone('pelvis.'+suffix,(.19,.35,0),hip)
        limb_anchors[fl]=[shoulder,elbow,wrist,fp,ftoe];limb_anchors[hl]=[hip,knee,hock,hp,htoe]
    bpy.ops.object.mode_set(mode='OBJECT');meta.show_in_front=True
    layout={b.name:{'head_gltf':inverse(b.head_local),'tail_gltf':inverse(b.tail_local),'parent':b.parent.name if b.parent else None,'rigify_type':meta.pose.bones[b.name].rigify_type} for b in meta.data.bones}
    write(OUT/'metarig_layout.json',{'template':'Rigify built-in Animals/cat.py','removed_face_and_digit_bones':sorted(remove),'bones':layout,'limb_anchors':limb_anchors,'status':'Provisional anatomical placement, not specialist-certified. Prior highres landmarks reused only because orientation/scale inspected; retopo source IDs differ.'})
    bpy.context.view_layer.objects.active=meta;meta.select_set(True)
    rows={b.name:{'parent':b.parent.name if b.parent else None,'head':list(b.head_local),'tail':list(b.tail_local),'use_connect':b.use_connect,'rigify_type':meta.pose.bones[b.name].rigify_type,'connect_chain':bool(getattr(meta.pose.bones[b.name].rigify_parameters,'connect_chain',False))} for b in meta.data.bones}
    errors=[];connections=[]
    for name,v in rows.items():
        if not all(math.isfinite(x) for x in v['head']+v['tail']) or math.dist(v['head'],v['tail'])<1e-5:errors.append(name+': invalid endpoints')
        seen={name};par=v['parent']
        while par:
            if par not in rows or par in seen:errors.append(name+': parent cycle');break
            seen.add(par);par=rows[par]['parent']
        if v['use_connect'] and v['parent'] and math.dist(v['head'],rows[v['parent']]['tail'])>1e-5:errors.append(name+': connected bone gap')
        if v['rigify_type'] and v['connect_chain']:
            ancestor=v['parent']
            while ancestor and not rows[ancestor]['rigify_type']:ancestor=rows[ancestor]['parent']
            if not ancestor:errors.append(name+': no parent component');continue
            last=ancestor
            while True:
                children=[n for n,x in rows.items() if x['parent']==last and x['use_connect'] and not x['rigify_type']]
                if len(children)!=1:break
                last=children[0]
            reverse=math.dist(rows[ancestor]['head'],v['head']);direct=math.dist(rows[last]['tail'],v['head']);ok=min(reverse,direct)<1e-5
            connections.append({'bone':name,'parent':ancestor,'last':last,'reverse_gap':reverse,'direct_gap':direct,'pass':ok})
            if not ok:errors.append(name+': Rigify chain gap')
    anatomy={}
    for limb,anchors in limb_anchors.items():
        a=np.array(anchors);segments=a[1:]-a[:-1];length=np.linalg.norm(segments,axis=1);angle=math.degrees(math.acos(float(np.clip(np.dot(segments[0],segments[1])/(length[0]*length[1]),-1,1))))
        side_ok=all(p[2]>0 for p in a) if limb.endswith('L') else all(p[2]<0 for p in a)
        descent=all(segments[:,1]<0)
        front_ok=bool(np.all(a[:3,0]<-.15)) if limb.startswith('F') else bool(np.all(a[:3,0]>.03))
        anatomy[limb]={'anchors_gltf':anchors,'segment_lengths':length.tolist(),'joint_direction_angle_degrees':angle,'side_correct':side_ok,'distal_height_descending':descent,'longitudinal_region_correct':front_ok,'paw_vertices':contacts[limb],'paw_min_y':float(baseline[contacts[limb],1].min()),'nearest_surface_distances':[float(np.linalg.norm(baseline-p,axis=1).min()) for p in a]}
        if not side_ok or not descent or not front_ok:errors.append(limb+': misplaced limb chain')
    if not np.all(np.diff(np.array(spine)[:,0])<0):errors.append('spine does not follow tail-to-head direction')
    if math.dist(tails[0],inverse(meta.data.bones['spine'].head_local))>1e-6:errors.append('tail pivot changed')
    pre={'structural_pass':not errors,'errors':errors,'chains':connections,'all_bones':rows,'anatomy':anatomy,'spine_points_gltf':spine,'tail_points_gltf':tails,'pelvis_branch_heads_gltf':[.19,.35,0],'notes':'Posterior spine starts at preserved tail base, runs forward through pelvis; pelvis side branches remain body-centered with intentionally unconnected offsets. Limb pivots are provisional surface-derived, not medical anatomy. Generation blocked until visual review of matched overlay.','visual_anatomy_review_pass':False}
    if not execute:
        bpy.ops.wm.save_as_mainfile(filepath=str(SCENE),compress=True);pre['prepared_scene_sha256']=sha(SCENE);write(OUT/'preflight.json',pre);return
    if errors:write(OUT/'execution_preflight_failure.json',pre);return
    write(OUT/'attempt_started.json',{'generation_attempts_allowed':1,'timestamp':time.time(),'prepared_scene_sha256':gate['prepared_scene_sha256']})
    generation={'attempts':1,'auto_weight_attempts':0}
    try:
        bpy.ops.pose.rigify_generate();rig=bpy.context.object;rig.name='CAT_RIGIFY_TRIAL_02'
        generation.update(generated=True,bones=len(rig.data.bones),deform_bones=sum(b.use_deform for b in rig.data.bones))
        bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
        generation['auto_weight_attempts']=1;bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        deform={b.name for b in rig.data.bones if b.use_deform};covered=[];influences=[]
        for v in mesh.data.vertices:
            row=[g.weight for g in v.groups if mesh.vertex_groups[g.group].name in deform and g.weight>0];covered.append(bool(row));influences.append(len(row))
        generation.update(auto_weighted_vertices=sum(covered),unweighted_vertices=len(covered)-sum(covered),max_influences=max(influences),vertex_groups=len(mesh.vertex_groups))
        write(OUT/'generation.json',generation)
        weight_rows=[];contributions={n:[] for n in sorted(deform)}
        for v in mesh.data.vertices:
            row={mesh.vertex_groups[g.group].name:float(g.weight) for g in v.groups if mesh.vertex_groups[g.group].name in deform and g.weight>0}
            weight_rows.append(row)
            for n in row:contributions[n].append(v.index)
        write(OUT/'weights.json',{'rows':weight_rows,'bone_source_vertex_ids':contributions,'unweighted_vertices':generation['unweighted_vertices'],'sum_error_max':max(abs(sum(v.values())-1) for v in weight_rows),'positive_influence_histogram':{str(n):influences.count(n) for n in sorted(set(influences))}})
        neutral=evaluated();delta=float(np.linalg.norm(neutral-baseline,axis=1).max())
        local_limb={}
        for limb,anchors in limb_anchors.items():
            suffix=limb[-1];names=[n for n in deform if any(part in n for part in (['upper_arm','forearm','hand'] if limb.startswith('F') else ['thigh','shin','foot'])) and n.endswith('.'+suffix)]
            local_limb[limb]={'deform_groups':names,'positive_vertices':len(set(i for n in names for i in contributions[n])),'contact_patch_mean_limb_weight':float(np.mean([sum(weight_rows[i].get(n,0) for n in names) for i in contacts[limb]]))}
        good=all(covered) and delta<1e-6 and all(v['positive_vertices']>0 and v['contact_patch_mean_limb_weight']>.5 for v in local_limb.values())
        write(OUT/'neutral_gate.json',{'blender_max_rest_error':delta,'limbs':local_limb,'blender_and_local_weight_gate_pass':good,'panda_neutral_gate_tested':False,'panda_note':'Final deform-only export is conditional on acceptable deformation; runtime neutral checked separately if an export is produced.'})
        if not good:raise ValueError('Neutral or limb weight gate failed; no bends, no retry')
    except Exception as e:
        generation.update(error=str(e),accepted=False,failure_stage='heat_weight_or_neutral_gate' if generation['auto_weight_attempts'] else 'generation');write(OUT/'generation.json',generation)
        bpy.ops.wm.save_as_mainfile(filepath=str(SCENE),compress=True)
        assert all(sha(ROOT/p)==h for p,h in frozen.items())
        write(OUT/'preserved_manifest.json',frozen);return
    bpy.ops.wm.save_as_mainfile(filepath=str(SCENE),compress=True)
    assert all(sha(ROOT/p)==h for p,h in frozen.items())
    generation['scene_sha256']=sha(SCENE);generation['accepted']=False;generation['status']='Generation and bind completed; neutral runtime and deformation tests pending'
    write(OUT/'generation.json',generation)

def sha_bytes(a):return hashlib.sha256(a.tobytes()).hexdigest()
if __name__=='__main__':main()
