"""Load the MakeHuman hm08 base mesh (working copy), the body group only, plus MakeHuman's joint markers.
Units converted to metres (source is decimetres). Axes kept: +Y up, +Z forward, +X character-left."""
import numpy as np, collections, os
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'concepts', 'base_mesh_work', 'base_working.obj')

def load(path=WORK):
    V, F, G = [], [], []; cur = None
    for line in open(path):
        if line.startswith('v '): V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('g '): cur = line.split(None, 1)[1].strip()
        elif line.startswith('f '): F.append([int(t.split('/')[0]) - 1 for t in line.split()[1:]]); G.append(cur)
    V = np.array(V) * 0.1
    joints = {}
    for f, g in zip(F, G):
        if g and g.startswith('joint-'): joints.setdefault(g, set()).update(f)
    joints = {k[6:]: V[list(v)].mean(0) for k, v in joints.items()}
    body = [f for f, g in zip(F, G) if g == 'body']
    used = sorted({i for f in body for i in f}); remap = {o: n for n, o in enumerate(used)}
    Q = np.array([[remap[i] for i in f] for f in body])
    return V[used], Q, joints, np.array(used)

def edge_loops(Q):
    """All edge loops of a quad mesh (traversal continues straight through valence-4 vertices)."""
    faces_of_edge = collections.defaultdict(list); vedges = collections.defaultdict(set)
    for fi, q in enumerate(Q):
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]; e = (min(a, b), max(a, b))
            faces_of_edge[e].append(fi); vedges[a].add(e); vedges[b].add(e)
    def nxt(e, v):
        es = vedges[v]
        if len(es) != 4: return None
        shared = set(faces_of_edge[e])
        cands = [x for x in es if x != e and not (set(faces_of_edge[x]) & shared)]
        return cands[0] if len(cands) == 1 else None
    seen, loops = set(), []
    for e0 in faces_of_edge:
        if e0 in seen: continue
        path = [e0]; closed = False
        for direction in (1, 0):  # walk both ways from e0
            e, v = e0, e0[direction]
            while True:
                n = nxt(e, v)
                if n is None: break
                if n == e0: closed = True; break
                path.append(n) if direction == 1 else path.insert(0, n)
                v = n[0] if n[1] == v else n[1]; e = n
            if closed: break
        for e in path: seen.add(e)
        verts = []
        for e in path:
            for x in e:
                if x not in verts: verts.append(x)
        loops.append({'edges': path, 'verts': verts, 'closed': closed})
    return loops, faces_of_edge
