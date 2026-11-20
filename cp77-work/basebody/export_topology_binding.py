"""Export the v0.2 topology binding for MakeHuman hm08: seam loops, region face assignment and drawn-boundary vertex
chains, all in ORIGINAL OBJ indices (0-based vertex index, 0-based index over all 'f' lines), bound to the master
file's SHA-256. Output: specs/character_standard/topology/hm08/{seams,regions,boundaries}.json"""
import sys, os, json, hashlib, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mhmesh, test2_deformation as T2, test3_regions as T3
OUT = os.path.join(HERE, '..', 'specs', 'character_standard', 'topology', 'hm08'); os.makedirs(OUT, exist_ok=True)
sha = hashlib.sha256(open(mhmesh.WORK, 'rb').read()).hexdigest()
V0, Q0, _, used = mhmesh.load()
fidx = []; gi = -1; cur = None
for line in open(mhmesh.WORK):
    if line.startswith('g '): cur = line.split(None, 1)[1].strip()
    elif line.startswith('f '):
        gi += 1
        if cur == 'body': fidx.append(gi)
fidx = np.array(fidx)
V, Q, pos, *_ = T2.build()
assert len(Q) == len(fidx) and (Q == Q0).all()
closed, S = T3.seam_loops(V, Q, pos)
cut = set(e for k, (_, li) in S.items() if li is not None for e in closed[li]['edges'])
comp, fe = T3.flood(Q, cut)
lab = T3.label_regions(V, Q, pos, closed, S, comp)
R = json.load(open(os.path.join(HERE, '..', 'specs', 'character_standard', 'hiding_regions.json')))['regions']
bit = {r['name']: r['bit'] for r in R}
head = lambda what: {'standard': 'cyberwolf_character', 'standard_version': '0.2-draft', 'content': what,
                     'mesh': {'name': 'MakeHuman hm08 base.obj', 'sha256': sha, 'group': 'body', 'obj_vertices_used': int(len(used)), 'body_faces': int(len(Q))},
                     'indexing': 'vertex ids: 0-based OBJ vertex index; face ids: 0-based index over all f lines of the OBJ',
                     'generator': 'basebody/export_topology_binding.py'}
ov = lambda vs: [int(used[v]) for v in vs]
# seams
seams = {}
for code, (kind, li) in S.items():
    lv = closed[li]['verts']
    seams[code] = {'role': {'A': 'seam ring (option A root loop)', 'moved': 'seam ring (moved to the measured loop)', 'region': 'region boundary only (not a seam ring)'}.get(kind, 'seam ring'),
                   'closed_loop': True, 'vertex_ids_in_order': ov(lv)}
json.dump({**head('seam rings and loop-based region boundaries, as closed edge loops'), 'seams': seams}, open(os.path.join(OUT, 'seams.json'), 'w'), indent=1)
# region face assignment (authoritative for hm08)
faces = collections.defaultdict(list)
for f, l in enumerate(lab): faces[l].append(int(fidx[f]))
assert set(faces) == set(bit), set(bit) ^ set(faces)
json.dump({**head('hide-region membership of every body face'), 'regions': {k: {'bit': bit[k], 'face_ids': sorted(v)} for k, v in sorted(faces.items(), key=lambda kv: bit[kv[0]])}},
          open(os.path.join(OUT, 'regions.json'), 'w'))
# drawn boundaries as ordered vertex chains
pairs = collections.defaultdict(list)
for e, fs in fe.items():
    if len(fs) == 2 and lab[fs[0]] != lab[fs[1]] and e not in cut:
        pairs[tuple(sorted((lab[fs[0]], lab[fs[1]])))].append(e)
def chains(es):
    nb = collections.defaultdict(list)
    for a, b in es: nb[a].append(b); nb[b].append(a)
    left = set(map(tuple, es)); out = []
    while left:
        ends = [v for v in nb if len(nb[v]) == 1 and any(v in e for e in left)]
        start = ends[0] if ends else next(iter(left))[0]
        ch = [start]; v = start
        while True:
            nx = [u for u in nb[v] if (min(u, v), max(u, v)) in left]
            if not nx: break
            u = nx[0]; left.discard((min(u, v), max(u, v))); ch.append(u); v = u
        out.append(ch)
    return out
STATUS = {'ears': 'placeholder: rule-generated box; must be authored (no edge loop at the ear root on hm08)'}
bnd = {}
for (a, b), es in sorted(pairs.items()):
    name = f'{a}|{b}'
    st = next((v for k, v in STATUS.items() if k in (a, b)), 'baseline: rule-generated, hand refinement pending')
    bnd[name] = {'between': [a, b], 'status': st, 'chains': [ov(c) for c in chains(es)]}
json.dump({**head('drawn (non-loop) region boundaries as ordered vertex chains'), 'boundaries': bnd}, open(os.path.join(OUT, 'boundaries.json'), 'w'), indent=1)
print(sha[:12], len(seams), 'seams/loops;', len(faces), 'regions;', len(bnd), 'drawn boundaries:', {k: len(v['chains']) for k, v in bnd.items()})
