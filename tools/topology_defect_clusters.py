"""Read-only deterministic clustering of defect records; no geometric mutation."""
from collections import defaultdict

def connected_groups(count, links):
    parent=list(range(count))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for a,b in links:parent[root(a)]=root(b)
    groups=defaultdict(list)
    for i in range(count):groups[root(i)].append(i)
    return sorted(groups.values(),key=lambda ids:min(ids))

def cluster_defect_events(events):
    """Join events sharing a defect vertex or an incident source face.

    Context one-rings are excluded: ordinary surface adjacency must not merge
    every defect on the connected animal into one cluster.
    """
    seen_vertex={};seen_face={};links=[]
    for i,event in enumerate(events):
        for key in event['proxy_vertices']:
            if key in seen_vertex:links.append((i,seen_vertex[key]))
            seen_vertex[key]=i
        for key in event['source_faces']:
            if key in seen_face:links.append((i,seen_face[key]))
            seen_face[key]=i
    return connected_groups(len(events),links)
