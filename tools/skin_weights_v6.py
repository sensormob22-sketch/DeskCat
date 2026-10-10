"""One controlled, asset-specific weight experiment; no mesh modification."""
import heapq
import numpy as np

def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)

def build_weights(points, faces, names, specs, distance):
    p=np.asarray(points);n=len(p);w=np.zeros((n,len(names)))
    edges=set(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    adj=[[] for _ in range(n)]
    for a,b in edges:
        length=float(np.linalg.norm(p[a]-p[b]));adj[a].append((b,length));adj[b].append((a,length))
    eligible=(p[:,0]>.27)&(p[:,1]<.285)&(abs(p[:,2])<.085)
    seed=int(np.argmax(p[:,0]));tail=np.zeros(n,dtype=bool);stack=[seed]
    while stack:
        a=stack.pop()
        if tail[a] or not eligible[a]:continue
        tail[a]=True;stack.extend(b for b,_ in adj[a] if eligible[b] and not tail[b])
    d=np.full(n,np.inf);queue=[]
    for a in np.flatnonzero(tail):
        if any(not tail[b] for b,_ in adj[a]):d[a]=0;heapq.heappush(queue,(0,int(a)))
    while queue:
        length,a=heapq.heappop(queue)
        if length!=d[a]:continue
        for b,cost in adj[a]:
            new=length+cost
            if tail[b] and new<d[b]:d[b]=new;heapq.heappush(queue,(new,b))
    # Partition of unity along the torso; posterior surface inherits pelvis.
    neck=smooth((p[:,0]+.35)/.13)
    posterior=smooth((p[:,0]-.045)/.16)
    lumbar=smooth((p[:,0]+.13)/.15)*(1-posterior)
    w[:,names.index('root')]=1-neck
    w[:,names.index('thoracic')]=neck*(1-lumbar-posterior)
    w[:,names.index('lumbar')]=neck*lumbar
    w[:,names.index('pelvis')]=neck*posterior
    for label in ('FL','FR','HL','HR'):
        front=label.startswith('F');side=1 if label.endswith('L') else -1
        chain=[x for x in names if x.endswith('_'+label)]
        distances=np.array([distance(p,specs[x]['head_gltf'],specs[x]['tail_gltf']) for x in chain]).T
        gate=smooth((.125-distances.min(1))/.065)*smooth((.41-p[:,1])/.20)*smooth((side*p[:,2]+.005)/.035)
        gate*=smooth((-.075-p[:,0])/.10) if front else smooth((p[:,0]-.02)/.07)
        gate[tail]=0
        raw=np.exp(-(distances/.07)**2);raw/=np.maximum(raw.sum(1,keepdims=True),1e-30)
        w*=1-gate[:,None]
        for j,x in enumerate(chain):w[:,names.index(x)]+=gate*raw[:,j]
    # Connected local tail surface, geodesic blend from its pelvis boundary.
    tw=smooth(d[tail]/.09)
    w[tail]=0;w[tail,names.index('pelvis')]=1-tw;w[tail,names.index('tail_base')]=tw
    return w,tail,d
