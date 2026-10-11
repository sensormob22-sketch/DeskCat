"""Read-only importer explanation and prospective Cat hierarchy check; never generates."""
import bpy,json,sys,math
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor
root=Path.cwd();out=root/'docs/model-reports/existing-retopo-skin';source=root/'assets/3d/retopo/deskcat_calico_retopo_16460.glb'
bpy.ops.import_scene.gltf(filepath=str(source),merge_vertices=False)
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
audit=json.loads((out/'skin_audit.json').read_text());d,b,_=read_glb(source);p=d['meshes'][0]['primitives'][0];js=np.array(accessor(d,b,p['attributes']['JOINTS_0']));ws=np.array(accessor(d,b,p['attributes']['WEIGHTS_0']));ref=np.load(root/'artifacts/existing_retopo_skin/reference.npz')['primitive'];bl=np.load(root/'artifacts/existing_retopo_skin/blender.npz')['disabled'];C=np.array([[1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]]);prediction=np.zeros_like(ref);h=np.column_stack([ref,np.ones(len(ref))])
for k,j in enumerate(audit['joints']):
 rest=np.array(rig.data.bones[j['name']].matrix_local);matrix=np.linalg.inv(C)@rest@C@np.array(j['inverse_bind_matrix']);prediction+=(h@matrix.T)[:,:3]*np.where(js==k,ws,0).sum(1)[:,None]
error=float(np.linalg.norm(prediction-bl,axis=1).max());
(out/'blender_importer_explanation.json').write_text(json.dumps({'simple_bone_matrix_local_times_IBM_hypothesis_error':error,'simple_hypothesis_rejected':error>2e-6,'explanation':'Blender mesh skin_into_bind_pose multiplies weighted bind_arma_mat @ inverseBindMatrix before Armature modifier. Disabling modifier reveals this baked mesh, not raw POSITION. Importer bind_arma_mat includes adjustments which must not be substituted with final bone.matrix_local; the simple substitution was tested and rejected.','source':'Blender 4.3.2 io_scene_gltf2/blender/imp/mesh.py:633-685'},indent=2)+'\n')
bpy.ops.wm.open_mainfile(filepath=str(root/'assets/rigging/deskcat_retopo_rigify_trial_01.blend'))
bpy.ops.preferences.addon_enable(module='rigify');r=bpy.data.objects['CAT_METARIG_TRIAL_01'];bones={x.name:{'parent':x.parent.name if x.parent else None,'head':list(x.head_local),'tail':list(x.tail_local),'use_connect':x.use_connect,'rigify_type':r.pose.bones[x.name].rigify_type,'connect_chain':bool(getattr(r.pose.bones[x.name].rigify_parameters,'connect_chain',False))} for x in r.data.bones}
def check(rows):
 errors=[]
 for name,v in rows.items():
  if not all(math.isfinite(x) for x in v['head']+v['tail']) or math.dist(v['head'],v['tail'])<1e-6:errors.append(name+': invalid endpoints')
  seen={name};par=v['parent']
  while par:
   if par not in rows or par in seen:errors.append(name+': invalid parent cycle');break
   seen.add(par);par=rows[par]['parent']
  if v['use_connect'] and v['parent'] and math.dist(v['head'],rows[v['parent']]['tail'])>1e-5:errors.append(name+': connected endpoint gap')
 return errors
proposed=json.loads(json.dumps(bones));proposed['spine']['head']=list(proposed['tail.001']['head'])
def chains(rows):
 checks=[]
 for name,v in rows.items():
  if not v['rigify_type'] or not v['connect_chain']:continue
  ancestor=v['parent']
  while ancestor and not rows[ancestor]['rigify_type']:ancestor=rows[ancestor]['parent']
  if not ancestor:checks.append({'bone':name,'pass':False,'reason':'no parent rig'});continue
  last=ancestor
  while True:
   children=[k for k,x in rows.items() if x['parent']==last and x['use_connect'] and not x['rigify_type']]
   if len(children)!=1:break
   last=children[0]
  reverse=math.dist(rows[ancestor]['head'],v['head']);direct=math.dist(rows[last]['tail'],v['head'])
  checks.append({'bone':name,'parent_rig':ancestor,'parent_chain_last':last,'reverse_gap':reverse,'direct_gap':direct,'pass':min(reverse,direct)<1e-5})
 return checks
report={'applied':False,'generation_calls':0,'chain_checks_before':chains(bones),'chain_checks_proposed':chains(proposed),'bone_count':len(bones),'all_bones':bones,'baseline_structural_errors':check(bones),'proposal_structural_errors':check(proposed),'proposal':{'bone':'spine','field':'head','before':bones['spine']['head'],'after':proposed['spine']['head'],'coordinate_system':'Blender Z-up','tail_head_preserved':True,'reverse_connection_gap_before':math.dist(bones['spine']['head'],bones['tail.001']['head']),'reverse_connection_gap_after':math.dist(proposed['spine']['head'],proposed['tail.001']['head'])},'limitations':'Structural endpoint/acyclicity check only. Moving pelvis/spine root needs anatomical review. All Rigify component configuration and generation remain untested. No scene saved or changed.'}
(out/'rigify_connection_preflight.json').write_text(json.dumps(report,indent=2)+'\n');print(error,report['baseline_structural_errors'],report['proposal_structural_errors'])
