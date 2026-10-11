"""Triangle clipping with barycentric UV preservation, only at a belly window."""
from collections import defaultdict
import numpy as np

def clip_window(points,normals,uv,faces,bounds):
    pp=points.tolist();nn=normals.tolist();uu=uv.tolist();out=[];owners=[];inside=[]
    planes=[(0,bounds[0],1),(0,bounds[1],-1),(1,bounds[2],1),(1,bounds[3],-1)]
    clipped=[];removed=[];provenance=[]
    for fi,face in enumerate(faces):
        pos=points[face]
        if any(np.all(sign*(pos[:,axis]-limit)<-1e-10) for axis,limit,sign in planes):
            out.append(face.tolist());owners.append(fi);inside.append(False);continue
        cache={tuple(np.eye(3)[i]):int(v) for i,v in enumerate(face)}
        pieces=[]
        def emit(poly,is_inside):
            if len(poly)<3:return
            ids=[]
            for weights in poly:
                key=tuple(np.round(weights,12))
                if key not in cache:
                    cache[key]=len(pp);provenance.append({'vertex_id':len(pp),'source_face_id':fi,'barycentric':weights.tolist()});pp.append((weights@pos).tolist());normal=weights@normals[face];normal/=np.linalg.norm(normal);nn.append(normal.tolist());uu.append((weights@uv[face]).tolist())
                ids.append(cache[key])
            if len(ids)>3:
                weights=np.mean(poly,axis=0);center=len(pp);provenance.append({'vertex_id':center,'source_face_id':fi,'barycentric':weights.tolist()});pp.append((weights@pos).tolist());normal=weights@normals[face];normal/=np.linalg.norm(normal);nn.append(normal.tolist());uu.append((weights@uv[face]).tolist())
                triangles=[[center,ids[i],ids[(i+1)%len(ids)]] for i in range(len(ids))]
            else:triangles=[ids]
            for t in triangles:
                a=np.array([pp[v] for v in t])
                if np.linalg.norm(np.cross(a[1]-a[0],a[2]-a[0]))<1e-13:continue
                out.append(t);owners.append(fi);inside.append(is_inside)
        poly=list(np.eye(3));was_cut=False
        for axis,limit,sign in planes:
            if not poly:break
            good=[];bad=[]
            for a,z in zip(poly,poly[1:]+poly[:1]):
                da=sign*((a@pos)[axis]-limit);dz=sign*((z@pos)[axis]-limit)
                (good if da>=-1e-10 else bad).append(a)
                if (da>=-1e-10)!=(dz>=-1e-10):
                    q=a+(z-a)*da/(da-dz);good.append(q);bad.append(q);was_cut=True
            if len(bad)>=3:pieces.append((bad,False))
            poly=good
        if len(poly)>=3:pieces.append((poly,True))
        pool=[v for polygon,_ in pieces for v in polygon]
        for polygon,is_inside in pieces:
            expanded=[]
            for a,z in zip(polygon,polygon[1:]+polygon[:1]):
                expanded.append(a);ab=z-a;length=ab@ab
                if length<1e-20:continue
                splits=[]
                for q in pool:
                    t=(q-a)@ab/length
                    if 1e-9<t<1-1e-9 and np.linalg.norm(q-a-t*ab)<1e-9:splits.append((t,q))
                previous=None
                for t,q in sorted(splits,key=lambda item:item[0]):
                    if previous is None or abs(t-previous)>1e-9:expanded.append(q);previous=t
            emit(expanded,is_inside)
        if len(poly)>=3:removed.append(fi)
        if was_cut:clipped.append(fi)
    # Canonicalize in the actual GLB float32 representation. Source positions
    # were already float32, so this changes only newly interpolated cut points.
    pp=np.array(pp,dtype=np.float32).astype(float);nn=np.array(nn);uu=np.array(uu);out=np.array(out,int)
    # Share coordinate aliases for topological checks, keep UV aliases in export.
    _,first,inv=np.unique(pp,axis=0,return_index=True,return_inverse=True)
    aliases=defaultdict(list)
    for v,c in enumerate(inv):aliases[int(c)].append(v)
    return pp,nn,uu,out,np.array(inside,bool),np.array(owners),pp[first],inv[out],list(aliases[i] for i in range(len(first))),removed,clipped,provenance
