"""Read-only skin forensics + metadata-only new GLB. No weights/poses/rig generation.
blender -b --factory-startup --python-exit-code 1 --python tools/blender_audit_existing_retopo_skin.py
"""
import hashlib,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from rig_readiness_audit import read_glb,accessor,node_transform
from blender_deformation_probe import inverse
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/existing-retopo-skin';WORK=ROOT/'artifacts/existing_retopo_skin'
SRC=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
COPY=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460_metadata_diag.glb'
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def mat(flat):return np.array(flat).reshape(4,4,order='F')

def main():
    if OUT.exists() or WORK.exists() or COPY.exists():raise ValueError('New diagnostic paths only')
    OUT.mkdir(parents=True);WORK.mkdir(parents=True)
    frozen={str(p.relative_to(ROOT)):sha(p.read_bytes()) for folder in ['assets/3d','assets/rigging'] for p in (ROOT/folder).rglob('*') if p.is_file()}
    d,b,_=read_glb(SRC);skin=d['skins'][0];prim=d['meshes'][0]['primitives'][0]
    ps=np.array(accessor(d,b,prim['attributes']['POSITION']));js=np.array(accessor(d,b,prim['attributes']['JOINTS_0']),dtype=int);ws=np.array(accessor(d,b,prim['attributes']['WEIGHTS_0']))
    assert np.isfinite(ps).all() and np.isfinite(ws).all()
    parents={c:i for i,n in enumerate(d['nodes']) for c in n.get('children',[])};worlds={}
    def world(i):
        if i not in worlds:worlds[i]=(world(parents[i]) if i in parents else np.eye(4))@mat(node_transform(d['nodes'][i]))
        return worlds[i]
    for i in range(len(d['nodes'])):world(i)
    mesh_node=next(i for i,n in enumerate(d['nodes']) if 'skin' in n)
    def rows(accid):
        a=d['accessors'][accid];v=d['bufferViews'][a['bufferView']];size={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        fmt={5126:'f',5125:'I',5123:'H',5121:'B',5122:'h',5120:'b'}[a['componentType']];length=struct.calcsize('<'+fmt)*size;start=v.get('byteOffset',0)+a.get('byteOffset',0)
        return np.array([struct.unpack_from('<'+fmt*size,b,start+i*v.get('byteStride',length)) for i in range(a['count'])])
    ibms=np.array([mat(r) for r in rows(skin['inverseBindMatrices'])]);transforms=np.array([worlds[n]@ib for n,ib in zip(skin['joints'],ibms)])
    predicted=np.zeros_like(ps);homo=np.column_stack([ps,np.ones(len(ps))]);contributions=[]
    for k in range(len(skin['joints'])):
        weight=np.where(js==k,ws,0).sum(1);predicted+=(homo@transforms[k].T)[:,:3]*weight[:,None]
        ids=np.where(weight>0)[0];contributions.append({'skin_joint_index':k,'node_index':skin['joints'][k],'name':d['nodes'][skin['joints'][k]]['name'],'positive_vertices':len(ids),'weight_mass':float(weight.sum()),'source_vertex_ids':ids.tolist() if len(ids)<100 else 'bulk; see JOINTS_0 binary','geometry_bounds_if_used':[ps[ids].min(0).tolist(),ps[ids].max(0).tolist()] if len(ids) else None})
    expected=(homo@worlds[mesh_node].T)[:,:3];diff=np.linalg.norm(predicted-expected,axis=1)
    joint_rows=[]
    for k,node in enumerate(skin['joints']):
        bind=np.linalg.inv(ibms[k]);rotation=bind[:3,:3];axes=[rotation[:,i]/np.linalg.norm(rotation[:,i]) for i in range(3)]
        joint_rows.append({'skin_joint_index':k,'node_index':node,'name':d['nodes'][node]['name'],'parent_node':parents.get(node),'parent_name':d['nodes'][parents[node]]['name'] if node in parents else None,'children':d['nodes'][node].get('children',[]),'default_local_matrix':mat(node_transform(d['nodes'][node])).tolist(),'default_world_matrix':worlds[node].tolist(),'default_world_head':worlds[node][:3,3].tolist(),'default_world_axes':worlds[node][:3,:3].T.tolist(),'inverse_bind_matrix':ibms[k].tolist(),'inverse_bind_determinant':float(np.linalg.det(ibms[k])),'inferred_bind_world_matrix':bind.tolist(),'inferred_bind_head':bind[:3,3].tolist(),'inferred_bind_axes':np.array(axes).tolist(),'default_skin_matrix_identity_error':float(abs(transforms[k]-worlds[mesh_node]).max())})
    node_report=[{'node_index':i,'name':n.get('name'),'parent_node':parents.get(i),'children':n.get('children',[]),'is_skin_joint':i in skin['joints'],'has_explicit_transform':any(key in n for key in ['matrix','translation','rotation','scale']),'local_matrix':mat(node_transform(n)).tolist()} for i,n in enumerate(d['nodes'])]
    distribution={str(i):int(np.count_nonzero((ws>0).sum(1)==i)) for i in range(5)}
    report={'source_sha256':sha(SRC.read_bytes()),'vertices':len(ps),'triangles':d['accessors'][prim['indices']]['count']//3,'skin_joint_count':len(skin['joints']),'scene_nodes':node_report,'joints':joint_rows,'weights':{'min':float(ws.min()),'max':float(ws.max()),'max_sum_error':float(abs(ws.sum(1)-1).max()),'zero_sum_vertices':int((ws.sum(1)==0).sum()),'positive_influence_distribution':distribution,'joint_index_min':int(js.min()),'joint_index_max':int(js.max()),'joint_indices_in_range':bool((js>=0).all() and (js<len(skin['joints'])).all()),'joint_contributions':contributions,'bone0_fraction':contributions[0]['positive_vertices']/len(ps),'all_rows_are_1_0_0_0':bool(np.array_equal(ws,np.tile([1,0,0,0],(len(ps),1))))},'default_bind':{'mesh_node_index':mesh_node,'mesh_parent_node':parents.get(mesh_node),'mesh_world_matrix':worlds[mesh_node].tolist(),'all_node_local_transforms_identity':all(np.array_equal(mat(node_transform(n)),np.eye(4)) for n in d['nodes']),'max_displacement_from_primitive':float(diff.max()),'p50_p95_p99_displacement':np.percentile(diff,[50,95,99]).tolist(),'primitive_bounds':[ps.min(0).tolist(),ps.max(0).tolist()],'gltf_default_skinned_bounds':[predicted.min(0).tolist(),predicted.max(0).tolist()]},'anatomy_limit':'Inferred bind heads/axes come from inverse IBMs only; actual default node pivots are all zero. Missing non-joint ancestor rest transforms and original bone names/roles are not established. No anatomical certification.'}
    write(OUT/'skin_audit.json',report)
    np.savez_compressed(WORK/'reference.npz',primitive=ps,gltf_default=predicted)
    # Fix actual extrema only; no node, matrix, attribute, image, buffer or weight edits.
    corrected=json.loads(json.dumps(d));changes=[]
    for i,a in enumerate(d['accessors']):
        values=rows(i)
        for key,fn in [('min',np.min),('max',np.max)]:
            if key not in a:continue
            actual=fn(values,axis=0).tolist()
            if a[key]!=actual:
                changes.append({'accessor':i,'field':key,'before':a[key],'after':actual,'changed_components':[k for k,(old,new) in enumerate(zip(a[key],actual)) if old!=new]});corrected['accessors'][i][key]=actual
    j=json.dumps(corrected,separators=(',',':')).encode();j+=b' '*(-len(j)%4)
    body=struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(b),0x004e4942)+b;COPY.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
    nd,nb,_=read_glb(COPY);assert nb==b
    unchanged=json.loads(json.dumps(nd))
    for c in changes:unchanged['accessors'][c['accessor']][c['field']]=c['before']
    assert unchanged==d
    write(OUT/'metadata_fix.json',{'source_sha256':sha(SRC.read_bytes()),'copy_sha256':sha(COPY.read_bytes()),'source_bin_sha256':sha(b),'copy_bin_sha256':sha(nb),'bin_bit_identical':True,'only_accessor_extrema_changed':True,'changes':changes,'transforms_geometry_uv_weights_ibm_images_materials_unchanged':True})
    # Capture actual Blender default/rest and Armature-disabled result without saving scene.
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.import_scene.gltf(filepath=str(SRC),merge_vertices=False)
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.context.view_layer.update()
    def evaluated():
        ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());tmp=ev.to_mesh();result=np.array([inverse(ev.matrix_world@v.co) for v in tmp.vertices]);ev.to_mesh_clear();return result
    imported=evaluated()
    for mod in mesh.modifiers:
        if mod.type=='ARMATURE':mod.show_viewport=False
    bpy.context.view_layer.update();disabled=evaluated()
    np.savez_compressed(WORK/'blender.npz',enabled=imported,disabled=disabled)
    write(OUT/'blender_default.json',{'version':bpy.app.version_string,'imported_armature_world':np.array(rig.matrix_world).tolist(),'mesh_world_matrix':np.array(mesh.matrix_world).tolist(),'max_enabled_vs_disabled_distance':float(np.linalg.norm(imported-disabled,axis=1).max()),'max_enabled_vs_gltf_formula_distance':float(np.linalg.norm(imported-predicted,axis=1).max()),'max_disabled_vs_primitive_distance':float(np.linalg.norm(disabled-ps,axis=1).max()),'max_disabled_vs_gltf_formula_distance':float(np.linalg.norm(disabled-predicted,axis=1).max()),'bounds_enabled':[imported.min(0).tolist(),imported.max(0).tolist()],'bounds_disabled':[disabled.min(0).tolist(),disabled.max(0).tolist()],'imported_bones':[{'name':bone.name,'head_world_gltf':inverse(rig.matrix_world@bone.head_local),'tail_world_gltf':inverse(rig.matrix_world@bone.tail_local)} for bone in rig.data.bones],'note':'Actual loaded default pose, no pose edits. Blender reconstructs bone rest frames and bakes importer adjustments into mesh. Compare numerical arrays; do not equate Armature-disabled mesh with raw source POSITION.'})
    # Static visual forensic snapshots only; omit all skins and flatten node transforms.
    def snapshot(name,positions):
        doc=json.loads(json.dumps(d));data=bytearray(b);p=doc['meshes'][0]['primitives'][0]
        p['attributes'].pop('JOINTS_0');p['attributes'].pop('WEIGHTS_0');doc.pop('skins');doc['nodes']=[{'mesh':0}];doc['scenes']=[{'nodes':[0]}];doc['scene']=0
        a=doc['accessors'][p['attributes']['POSITION']];v=doc['bufferViews'][a['bufferView']];start=v.get('byteOffset',0)+a.get('byteOffset',0)
        for i,point in enumerate(positions):struct.pack_into('<3f',data,start+i*v.get('byteStride',12),*point)
        a['min']=positions.min(0).tolist();a['max']=positions.max(0).tolist();j=json.dumps(doc,separators=(',',':')).encode();j+=b' '*(-len(j)%4);body=struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(data),0x004e4942)+data;(WORK/(name+'.glb')).write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
    for name,positions in [('primitive',ps),('gltf_formula',predicted),('blender_enabled',imported),('blender_disabled',disabled)]:snapshot(name,positions)
    assert all(sha((ROOT/p).read_bytes())==h for p,h in frozen.items());write(OUT/'preserved_manifest.json',frozen)

if __name__=='__main__':main()
