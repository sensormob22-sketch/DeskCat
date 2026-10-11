"""Exact-coordinate alias map for a separate solver mesh; never edits render data."""
import math

def build_exact_proxy(points, faces):
    canonical=[];lookup={};source_to_proxy=[];proxy_to_sources=[]
    for source_id,point in enumerate(points):
        key=tuple(float(x) for x in point)
        if len(key)!=3 or not all(math.isfinite(x) for x in key):
            raise ValueError('Finite XYZ coordinates required')
        if key not in lookup:
            lookup[key]=len(canonical);canonical.append(key);proxy_to_sources.append([])
        proxy_id=lookup[key];source_to_proxy.append(proxy_id);proxy_to_sources[proxy_id].append(source_id)
    proxy_faces=[]
    for face in faces:
        if len(face)!=3 or any(not isinstance(i,int) or not 0<=i<len(points) for i in face):
            raise ValueError('Valid triangle indices required')
        proxy_faces.append(tuple(source_to_proxy[i] for i in face))
    return canonical,proxy_faces,source_to_proxy,proxy_to_sources
