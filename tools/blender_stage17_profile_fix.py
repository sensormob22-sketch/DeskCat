"""Local curved belly replacement, original-rim constrained, static diagnostic.

Blender 4.3: blender -b --factory-startup --python-exit-code 1 --python tools/blender_stage17_profile_fix.py
No remesh, rig generation, skin evaluation, or source overwrite. Source IDs are
zero-based triangles of the original GLB. UV on retained triangles stays exact.
"""
import sys,json,hashlib,struct,io,copy
from pathlib import Path
from collections import defaultdict,Counter
import bpy,numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
from PIL import Image,ImageFilter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_readiness_audit import read_glb,accessor
from blender_deformation_probe import pair_set,convert
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage17';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb';SCENE=ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend'
GLB=ROOT/'assets/3d/retopo/deskcat_belly_profile_fix_01.glb';BLEND=ROOT/'assets/rigging/deskcat_belly_profile_fix_01.blend'
if (GLB.exists() or BLEND.exists()) and '--replace-stage17-diagnostic' not in sys.argv:
 raise FileExistsError('Stage17 outputs already exist. Use a separate checkout and --replace-stage17-diagnostic explicitly; source models are never overwritten.')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(SOURCE)=='834cf794f24fff93e549ab80dbd21218565862ed9209852e3d2a72869c4b303b'
assert sha(SCENE)=='844c4316dd841d4f943f80da7810d32abde64290c5f29b84e7ce4bfb3242667a'
d,b,_=read_glb(SOURCE);pr=d['meshes'][0]['primitives'][0];p=np.array(accessor(d,b,pr['attributes']['POSITION']));uv=np.array(accessor(d,b,pr['attributes']['TEXCOORD_0']));sn=np.array(accessor(d,b,pr['attributes']['NORMAL']));f=np.array(accessor(d,b,pr['indices']),int).reshape(-1,3)
source_points=p.copy();source_normals=sn.copy();source_uv=uv.copy();source_faces=f.copy()
m=json.loads((ROOT/'docs/model-reports/exact-weld-proxy/vertex_map.json').read_text());cf=np.array(m['proxy_faces_in_source_face_order'],int);aliases=m['proxy_to_sources'];cp=p[[a[0] for a in aliases]];cent=p[f].mean(1)
original_cp=cp.copy();original_cf=cf.copy()
from stage17_local_clip import clip_window
p,sn,uv,f,sel,face_owner,cp,cf,aliases,removed_source,clipped_source,cut_provenance=clip_window(p,sn,uv,f,[-.11,.05,.19,.31])
assert 5552 not in removed_source and 5552 not in clipped_source
removed=np.where(sel)[0];retained=np.where(~sel)[0];assert 5552 not in face_owner[sel]
edges=defaultdict(list)
for i,face in enumerate(cf):
 for a,z in zip(face,np.roll(face,-1)):edges[tuple(sorted((int(a),int(z))))].append(i)
rim=[e for e,fs in edges.items() if any(sel[i] for i in fs) and any(not sel[i] for i in fs)];adj=defaultdict(list)
for a,z in rim:adj[a].append(z);adj[z].append(a)
assert all(len(v)==2 for v in adj.values()),'Boundary must be a simple loop'
loop=[];last=None;cur=min(adj)
while cur not in loop:
 loop.append(cur);nxt=[a for a in adj[cur] if a!=last];last,cur=cur,nxt[0]
assert cur==loop[0] and len(loop)==len(adj),'Exactly one boundary component required'
old_boundary=cp[loop].copy();boundary=old_boundary.copy();changed_ids=[]
yc=.34;ry=.131;rz=.102
param=np.column_stack((boundary[:,0],np.arctan2(boundary[:,2],yc-boundary[:,1])*.095))
if np.sum(param[:,0]*np.roll(param[:,1],-1)-np.roll(param[:,0],-1)*param[:,1])<0:
 loop=loop[::-1];boundary=boundary[::-1].copy();old_boundary=old_boundary[::-1].copy();param=param[::-1].copy()
def inside_polygon(q):
 x,y=q;inside=False
 for a,z in zip(param,np.roll(param,-1,axis=0)):
  if (a[1]>y)!=(z[1]>y) and x<(z[0]-a[0])*(y-a[1])/(z[1]-a[1])+a[0]:inside=not inside
 return inside
coords=[Vector(v) for v in param];n_boundary=len(coords)
for x in np.linspace(-.106,.046,24):
 for t in np.linspace(param[:,1].min()+.004,param[:,1].max()-.004,31):
  if inside_polygon((x,t)):coords.append(Vector((float(x),float(t))))
verts,es,tris,orig_v,orig_e,orig_f=delaunay_2d_cdt(coords,[(i,(i+1)%n_boundary) for i in range(n_boundary)],[list(range(n_boundary))],1,1e-9,True)
param_out=np.array([v[:] for v in verts]);tri=np.array([t for t in tris if inside_polygon(param_out[list(t)].mean(0))],int);assert all(len(t)==3 for t in tris)
used=sorted(set(tri.ravel()));remap={v:i for i,v in enumerate(used)};tri=np.array([[remap[v] for v in t] for t in tri]);params=param_out[used];originals=[orig_v[i] for i in used]
fixed={i:ids[0] for i,ids in enumerate(originals) if ids and ids[0]<n_boundary};assert len(fixed)==n_boundary
theta=params[:,1]/.095
# Anatomical base shape plus a harmonic residual constrained by the exact rim.
# All source-rim coordinates are fixed. Interior residual, not the cross-section
# itself, is smoothed so a minimal-surface solver cannot collapse belly volume.
base=np.column_stack((params[:,0],yc-ry*np.cos(theta),rz*np.sin(theta)))
neighbors=defaultdict(set)
for t in tri:
 for a,z in zip(t,np.roll(t,-1)):neighbors[int(a)].add(int(z));neighbors[int(z)].add(int(a))
free=[i for i in range(len(base)) if i not in fixed];lookup={v:i for i,v in enumerate(free)};matrix=np.zeros((len(free),len(free)));rhs=np.zeros((len(free),3));residual=np.zeros_like(base)
for i,j in fixed.items():residual[i]=boundary[j]-base[i]
for i in free:
 row=lookup[i];matrix[row,row]=len(neighbors[i])
 for j in neighbors[i]:
  if j in lookup:matrix[row,lookup[j]]-=1
  else:rhs[row]+=residual[j]
residual[free]=np.linalg.solve(matrix,rhs);patch=base+residual
for i,j in fixed.items():patch[i]=boundary[j]
for i,t in enumerate(tri):
 n=np.cross(patch[t[1]]-patch[t[0]],patch[t[2]]-patch[t[0]]);c=patch[t].mean(0);out=np.array([0,c[1]-.32,c[2]])
 if n@out<0:tri[i]=t[[0,2,1]]
pn=np.zeros_like(patch)
for t in tri:
 n=np.cross(patch[t[1]]-patch[t[0]],patch[t[2]]-patch[t[0]])
 for v in t:pn[v]+=n
pn/=np.linalg.norm(pn,axis=1)[:,None]
for i,j in fixed.items():
 vals=sn[aliases[loop[j]]];normal=vals.mean(0);pn[i]=normal/np.linalg.norm(normal)
# Continuous boundary-matched shading normals, interpolated over this patch.
# Geometry remains the curved fitted surface; this avoids a sharp lighting seam
# against the source's baked/smoothed normals at the retained boundary.
normal_rhs=np.zeros_like(rhs)
for i in free:
 for j in neighbors[i]:
  if j in fixed:normal_rhs[lookup[i]]+=pn[j]
pn[free]=np.linalg.solve(matrix,normal_rhs);pn/=np.linalg.norm(pn,axis=1)[:,None]
# Pure profile (X/Y) UV for the new polygons; two independent anatomical sides.
uv_bounds=[-.14,.10,.16,.34];puv=np.column_stack(((patch[:,0]+.14)/.24,1-(patch[:,1]-.16)/.18))
view=d['bufferViews'][d['images'][0]['bufferView']];src_img=Image.open(io.BytesIO(b[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']])).convert('RGB');tex=np.array(src_img)
mv=d['bufferViews'][d['images'][1]['bufferView']];mr_tex=np.array(Image.open(io.BytesIO(b[mv.get('byteOffset',0):mv.get('byteOffset',0)+mv['byteLength']])).convert('RGB'))
textures=[];texture_metrics=[];N=768
for sign,name in [(1,'left'),(-1,'right')]:
 pixels=np.full((N,N,3),[231,228,222],dtype=np.uint8);mr_pixels=np.full((N,N,3),[255,190,0],dtype=np.uint8);depth=np.full((N,N),-np.inf);valid=np.zeros((N,N),bool)
 for face in source_faces:
  pts=source_points[face]
  if np.mean(pts[:,2])*sign<0:continue
  q=np.column_stack(((pts[:,0]+.14)/.24*(N-1),(1-(pts[:,1]-.16)/.18)*(N-1)))
  lo=np.maximum(np.floor(q.min(0)).astype(int),0);hi=np.minimum(np.ceil(q.max(0)).astype(int),N-1)
  if np.any(lo>hi):continue
  a,c,e=q;det=(c[0]-a[0])*(e[1]-a[1])-(c[1]-a[1])*(e[0]-a[0])
  if abs(det)<1e-10:continue
  xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1));dx=xx-a[0];dy=yy-a[1]
  v=(dx*(e[1]-a[1])-dy*(e[0]-a[0]))/det;w=((c[0]-a[0])*dy-(c[1]-a[1])*dx)/det;u=1-v-w;z=(u*pts[0,2]+v*pts[1,2]+w*pts[2,2])*sign
  dst=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1];hit=(u>=-1e-6)&(v>=-1e-6)&(w>=-1e-6)&(z>dst)
  tuv=u[:,:,None]*source_uv[face[0]]+v[:,:,None]*source_uv[face[1]]+w[:,:,None]*source_uv[face[2]];tx=np.clip((tuv[:,:,0]*(tex.shape[1]-1)).astype(int),0,tex.shape[1]-1);ty=np.clip((tuv[:,:,1]*(tex.shape[0]-1)).astype(int),0,tex.shape[0]-1)
  mx=np.clip((tuv[:,:,0]*(mr_tex.shape[1]-1)).astype(int),0,mr_tex.shape[1]-1);my=np.clip((tuv[:,:,1]*(mr_tex.shape[0]-1)).astype(int),0,mr_tex.shape[0]-1);mr_pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][hit]=mr_tex[my,mx][hit]
  pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][hit]=tex[ty,tx][hit];dst[hit]=z[hit];valid[lo[1]:hi[1]+1,lo[0]:hi[0]+1][hit]=True
 # The lowest fringe is deliberately replaced by white belly texture cloned
 # from the central underside. Feather upward into the independently projected calico map.
 y=.34-np.arange(N)/(N-1)*.18
 # Clone the source's central white underside (both maps share this color).
 sample=(abs(source_points[:,0])<.12)&(source_points[:,1]>.20)&(source_points[:,1]<.235)&(abs(source_points[:,2])<.03)
 samples=(source_uv[sample]*np.array([tex.shape[1]-1,tex.shape[0]-1])).astype(int);clone=np.median(tex[samples[:,1],samples[:,0]],axis=0)
 alpha=np.clip((y-.240)/.045,0,1);alpha=alpha*alpha*(3-2*alpha)
 projected=np.array(Image.fromarray(pixels).filter(ImageFilter.GaussianBlur(1.5)))
 pixels=np.clip(projected*alpha[:,None,None]+clone*(1-alpha[:,None,None]),0,255).astype(np.uint8)
 # Match the retained source UV exactly along the geometric cut, with a local
 # profile-atlas color correction that fades into the cloned white interior.
 total=np.zeros((N,N));delta=np.zeros((N,N,3));nearest=np.full((N,N),np.inf)
 for ca,cb in rim:
  a,bp=cp[ca],cp[cb]
  if (a[2]+bp[2])*sign<-.001:continue
  outside=[i for i in edges[tuple(sorted((ca,cb)))] if not sel[i]]
  if not outside:continue
  fi=outside[0];va=next(int(f[fi,k]) for k in range(3) if cf[fi,k]==ca);vb=next(int(f[fi,k]) for k in range(3) if cf[fi,k]==cb)
  qa=np.array([(a[0]+.14)/.24,1-(a[1]-.16)/.18])*(N-1);qb=np.array([(bp[0]+.14)/.24,1-(bp[1]-.16)/.18])*(N-1)
  steps=max(2,int(np.linalg.norm(qb-qa)/1.5)+1)
  for t in np.linspace(0,1,steps):
   px,py=(1-t)*qa+t*qb;u=(1-t)*uv[va]+t*uv[vb];tx,ty=(u*np.array([tex.shape[1]-1,tex.shape[0]-1])).astype(int);target=tex[ty,tx].astype(float)
   ix=int(np.clip(round(px),0,N-1));iy=int(np.clip(round(py),0,N-1));error=target-pixels[iy,ix]
   x0=max(0,ix-20);x1=min(N,ix+21);y0=max(0,iy-20);y1=min(N,iy+21);gy,gx=np.mgrid[y0:y1,x0:x1];distance=(gx-px)**2+(gy-py)**2;weight=np.exp(-distance/(2*4**2));total[y0:y1,x0:x1]+=weight;delta[y0:y1,x0:x1]+=weight[:,:,None]*error;nearest[y0:y1,x0:x1]=np.minimum(nearest[y0:y1,x0:x1],distance)
 correction=delta/np.maximum(total[:,:,None],1e-12)*np.exp(-nearest[:,:,None]/(2*18**2))
 pixels=np.clip(pixels.astype(float)+correction,0,255).astype(np.uint8)
 # Eight pixels of dilation into invalid profile areas; no original atlas edits.
 for _ in range(8):
  old=valid.copy();pp=pixels.copy()
  for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
   mask=(~old)&np.roll(old,(dy,dx),(0,1));pixels[mask]=np.roll(pp,(dy,dx),(0,1))[mask];valid[mask]=True
 muv=(source_uv[sample]*np.array([mr_tex.shape[1]-1,mr_tex.shape[0]-1])).astype(int);mr_clone=np.median(mr_tex[muv[:,1],muv[:,0]],axis=0);mr_pixels=np.clip(mr_pixels*alpha[:,None,None]+mr_clone*(1-alpha[:,None,None]),0,255).astype(np.uint8);Image.fromarray(mr_pixels).save(OUT/f'belly_profile_{name}_mr.png')
 filename=OUT/f'belly_profile_{name}.png';Image.fromarray(pixels).save(filename);textures.append(filename);texture_metrics.append({'side':name,'projection':'orthographic X/Y profile, glTF V down','clone_source':'median original central white underside vertices, abs(Z)<0.03, Y=0.20..0.235','white_clone_rgb':clone.tolist(),'resolution':[N,N],'dilation_pixels':8})
# Write static GLB directly: retained attribute/image bytes remain exactly the
# original bytes. Drop unusable old skin only in this standalone static copy.
doc=copy.deepcopy(d);binary=bytearray(b[:d['buffers'][0]['byteLength']]);doc['nodes']=[{'mesh':0,'name':'DeskCat local belly profile repair STATIC'}];doc['scenes']=[{'nodes':[0]}];doc['scene']=0;doc.pop('skins',None);doc.pop('animations',None)
def append_view(data,target=None):
 binary.extend(b'\0'*(-len(binary)%4));idx=len(doc['bufferViews']);v={'buffer':0,'byteOffset':len(binary),'byteLength':len(data)}
 if target:v['target']=target
 doc['bufferViews'].append(v);binary.extend(data);return idx
def add_accessor(data,typ,ctype=5126,target=34962):
 arr=np.asarray(data,dtype=np.float32 if ctype==5126 else np.uint32);idx=len(doc['accessors']);a={'bufferView':append_view(arr.tobytes(),target),'componentType':ctype,'count':len(arr),'type':typ}
 if typ=='VEC3':a['min']=arr.min(0).tolist();a['max']=arr.max(0).tolist()
 doc['accessors'].append(a);return idx
kept=copy.deepcopy(pr);kept['attributes']={k:v for k,v in pr['attributes'].items() if k not in ['JOINTS_0','WEIGHTS_0']};kept['attributes']={'POSITION':add_accessor(p,'VEC3'),'NORMAL':add_accessor(sn,'VEC3'),'TEXCOORD_0':add_accessor(uv,'VEC2')};kept['indices']=add_accessor(f[retained].reshape(-1),'SCALAR',5125,34963);primitives=[kept]
pa={'POSITION':add_accessor(patch,'VEC3'),'NORMAL':add_accessor(pn,'VEC3'),'TEXCOORD_0':add_accessor(puv,'VEC2')};patch_sides=[]
for sign,path in zip([1,-1],textures):
 image_idx=len(doc['images']);doc['images'].append({'bufferView':append_view(path.read_bytes()),'mimeType':'image/png','name':path.stem});tx=len(doc['textures']);doc['textures'].append({'source':image_idx,'sampler':d['textures'][0].get('sampler',0)});mr_image=len(doc['images']);doc['images'].append({'bufferView':append_view(path.with_name(path.stem+'_mr.png').read_bytes()),'mimeType':'image/png','name':path.stem+'_mr'});mr_tx=len(doc['textures']);doc['textures'].append({'source':mr_image,'sampler':0});material=len(doc['materials']);doc['materials'].append({'name':path.stem,'doubleSided':False,'pbrMetallicRoughness':{'baseColorTexture':{'index':tx},'metallicRoughnessTexture':{'index':mr_tx}}})
 tids=np.where((patch[tri].mean(1)[:,2]>=0)==(sign>0))[0];patch_sides.append(tids);primitives.append({'attributes':pa,'indices':add_accessor(tri[tids].reshape(-1),'SCALAR',5125,34963),'material':material,'mode':4})
doc['meshes']=[{'name':'Local continuous lower abdomen','primitives':primitives}]
# Correct inherited inaccurate accessor bounds, without changing stored data.
for ai,a in enumerate(doc['accessors']):
 if 'min' in a or 'max' in a:
  if a['type']=='MAT4':
   a.pop('min',None);a.pop('max',None);continue
  vals=np.array(accessor(doc,binary,ai));a['min']=vals.min(0).tolist();a['max']=vals.max(0).tolist()
doc['buffers'][0]['byteLength']=len(binary);encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4);body=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary;GLB.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
# Source scene is preserved in a separate saved scene; original objects hidden,
# existing Rigify untouched. Editable replacement has per-loop local profile UV.
bpy.ops.wm.open_mainfile(filepath=str(SCENE));original=bpy.data.objects['RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE'];allpoints=np.vstack([p,patch]);unwelded_faces=f[retained].tolist()+(tri+len(p)).tolist();local_weld={}
for i,j in fixed.items():
 anchor=aliases[loop[j]][0]
 for v in aliases[loop[j]]:local_weld[v]=anchor
 local_weld[len(p)+i]=anchor
allfaces=[[local_weld.get(v,v) for v in face] for face in unwelded_faces];edit_vertex_ids=sorted(set(v for face in allfaces for v in face));edit_vertex_map={v:i for i,v in enumerate(edit_vertex_ids)};edit_faces=[[edit_vertex_map[v] for v in face] for face in allfaces];mesh=bpy.data.meshes.new('STAGE17_EDITABLE_STATIC_REPAIR');mesh.from_pydata([convert(allpoints[v]) for v in edit_vertex_ids],[],edit_faces);mesh.update();mesh.materials.append(original.data.materials[0]);layer=mesh.uv_layers.new(name='UVMap')
for path in textures:
 mat=bpy.data.materials.new(path.stem);mat.use_nodes=True;bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.9;image=bpy.data.images.load(str(path));image.pack();node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color']);mr_image=bpy.data.images.load(str(path.with_name(path.stem+'_mr.png')));mr_image.colorspace_settings.name='Non-Color';mr_image.pack();mr_node=mat.node_tree.nodes.new('ShaderNodeTexImage');mr_node.image=mr_image;separate=mat.node_tree.nodes.new('ShaderNodeSeparateColor');mat.node_tree.links.new(mr_node.outputs['Color'],separate.inputs['Color']);mat.node_tree.links.new(separate.outputs['Green'],bsdf.inputs['Roughness']);mat.node_tree.links.new(separate.outputs['Blue'],bsdf.inputs['Metallic']);mesh.materials.append(mat)
for i,poly in enumerate(mesh.polygons):
 poly.use_smooth=True
 if i>=len(retained):poly.material_index=1 if patch[tri[i-len(retained)]].mean(0)[2]>=0 else 2
 for corner,li in enumerate(poly.loop_indices):
  vi=unwelded_faces[i][corner];u=uv[vi] if i<len(retained) else puv[vi-len(p)];layer.data[li].uv=(float(u[0]),float(1-u[1]))
mesh.normals_split_custom_set([tuple(convert(sn[v] if v<len(p) else pn[v-len(p)])) for face in unwelded_faces for v in face])
for obj in bpy.context.scene.objects:obj.hide_render=True
for obj in bpy.context.view_layer.objects:obj.hide_set(True)
obj=bpy.data.objects.new('DeskCat belly profile fix 01 STATIC',mesh);bpy.context.scene.collection.objects.link(obj);obj.hide_render=False;obj.hide_set(False);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
vg=obj.vertex_groups.new(name='STAGE17_NEW_BELLY');vg.add(sorted(set(edit_vertex_map[v] for face in allfaces[len(retained):] for v in face)),1,'REPLACE');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
# Exact-position alias topology for comparable strict crossing counts.
baseline=pair_set(original_cp,original_cf.tolist());combined=np.vstack([cp,patch]);nf=(tri+len(cp)).tolist();allcf=cf[retained].tolist()+nf
for i,j in fixed.items():
 old=len(cp)+i;new=loop[j];allcf=[[new if v==old else v for v in t] for t in allcf]
after=pair_set(combined,allcf);new_pairs=[];surviving=[]
for a,z in after:
 if z<len(retained):surviving.append([int(face_owner[retained[a]]),int(face_owner[retained[z]])])
 else:new_pairs.append([int(face_owner[retained[a]]) if a<len(retained) else 'patch_'+str(a-len(retained)), 'patch_'+str(z-len(retained))])
counts=Counter(tuple(sorted((a,z))) for face in allcf for a,z in zip(face,face[1:]+face[:1]));new_edge_counts=Counter(v for e,v in counts.items() if any(a>=len(cp) for a in e));area=np.linalg.norm(np.cross(patch[tri[:,1]]-patch[tri[:,0]],patch[tri[:,2]]-patch[tri[:,0]]),axis=1)/2
register=json.loads((ROOT/'docs/model-reports/stage13/defect_register.json').read_text());regions={c['id']:{'core_faces':c['source_face_ids'],'removed_core_faces':sorted(set(c['source_face_ids'])&set(removed_source))} for c in register['clusters'] if c['id'] in ['D06','D14','D17']}
result={'source_sha256':sha(SOURCE),'source_scene_sha256':sha(SCENE),'output_glb_sha256':sha(GLB),'output_blend_sha256':sha(BLEND),'selection':'exact triangle clipping at -0.11<X<0.05, 0.19<Y<0.31; both flanks and connecting underside; glTF Y-up','removed_source_face_ids':sorted(set(removed_source)-set(clipped_source)),'clipped_source_face_ids':clipped_source,'source_faces_with_removed_portions':removed_source,'retained_source_face_ids':sorted(set(face_owner[retained].tolist())),'retained_output_face_source_ids':face_owner[retained].tolist(),'removed_source_faces':len(set(removed_source)-set(clipped_source)),'retained_source_faces':len(retained),'new_patch_vertices':len(patch),'new_patch_triangles':len(tri),'rim_vertices':len(loop),'fixed_rim_proxy_ids':loop,'fixed_rim_output_vertex_aliases':[aliases[v] for v in loop],'fixed_rim_source_aliases':[[i for i in aliases[v] if i<len(source_points)] for v in loop],'regions':regions,'protected_face_5552_preserved':True,'unchanged_source_positions':len(source_points),'new_cut_vertices':len(p)-len(source_points),'changed_source_vertex_ids':sorted(changed_ids),'rim_displacement_max':float(np.linalg.norm(boundary-old_boundary,axis=1).max()),'changed_retained_source_face_ids':clipped_source,'unchanged_retained_loop_uv':True,'original_three_images_byte_identical':True,'rig_def_bones_in_scene':sum(b.use_deform for b in bpy.data.objects['CAT_RIGIFY_TRIAL_02'].data.bones),'blender_used_glb_geometry_vertex_ids':edit_vertex_ids,'blender_boundary_weld_coordinates':len(fixed),'blender_weld_scope':'rim aliases and new patch boundary only; per-loop UV and split normals preserved; no global weld','skin':'static output, no automatic weights or evaluated source skin','baseline_strict_crossings':len(baseline),'surviving_original_crossings':surviving,'new_strict_crossings':new_pairs,'patch_edge_incidence_counts':dict(new_edge_counts),'new_triangle_area_min':float(area.min()),'patch_bounds_gltf':[patch.min(0).tolist(),patch.max(0).tolist()],'texture_projection':texture_metrics,'acceptance':'requires multi-view visual review; no deformation/rig certification'}
(OUT/'cut_vertex_provenance.json').write_text(json.dumps(cut_provenance,indent=2)+'\n')
(OUT/'patch_export_map.json').write_text(json.dumps({'blender_patch_polygon_ids':[len(retained)+i for i in range(len(tri))],'glb_primitive_1_patch_triangle_ids':patch_sides[0].tolist(),'glb_primitive_2_patch_triangle_ids':patch_sides[1].tolist()},indent=2)+'\n')
(OUT/'geometry_audit.json').write_text(json.dumps(result,indent=2)+'\n');np.savez(ROOT/'artifacts/stage17/patch.npz',points=patch,faces=tri,uv=puv,removed=removed,retained=retained)
print(json.dumps({k:result[k] for k in ['removed_source_faces','new_patch_triangles','baseline_strict_crossings','new_strict_crossings','patch_edge_incidence_counts']}))
