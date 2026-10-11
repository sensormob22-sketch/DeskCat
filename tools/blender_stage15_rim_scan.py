"""Read-only ray scan and exact rim triangles; no geometry edits."""
import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_stage15_gap_diagnosis import OUT,cast,p,idx,uv
rays=json.loads((OUT/'rays_oblique.json').read_text());base=rays[0];direction=np.array(base['direction']);direction/=np.linalg.norm(direction)
# Exact camera plane basis from known pixel separations.
o0=np.array(rays[0]['origin']);ox=(np.array(rays[6]['origin'])-o0)/30;oy=(np.array(rays[1]['origin'])-o0-ox*10)/40
rows=[]
for yy in [185,210,235,260,285,310]:
 for xx in range(360,471,10):
  o=o0+(xx-410)*ox+(yy-200)*oy;hits=cast(o,direction);h=hits[0] if hits else None;rows.append({'pixel':[xx,yy],'hit':h})
(OUT/'gap_scan.json').write_text(json.dumps(rows,indent=2)+'\n')
for yy in [185,210,235,260,285,310]:print(yy,[(row['pixel'][0],row['hit']['source_face_id'],[round(x,4) for x in row['hit']['point']]) for row in rows if row['pixel'][1]==yy])
# Candidate rim triangles: exact coordinates and UV.
ids=sorted({row['hit']['source_face_id'] for row in rows if row['hit'] and row['hit']['point'][2]>.02})
(OUT/'rim_source_triangles.json').write_text(json.dumps({str(i):{'source_vertex_ids':idx[i].tolist(),'positions':p[idx[i]].tolist(),'uv':uv[idx[i]].tolist()} for i in ids},indent=2)+'\n')
