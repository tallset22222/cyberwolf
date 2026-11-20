"""Verify a WolvenKit import of tests_assets/infl8_import/l1_003_ma_pants__jeans.glb.
Usage: verify_infl8_import.py <imported .mesh (with its .buffer files beside it)>
Checks: layout carries 8 influences; every vertex found by position; per-vertex bone NAMES and weight BYTES equal
the expected table (exact vertices), nothing silently dropped or renormalised; sentinel sums reported; bind
matrices unchanged vs the vanilla template. Writes <mesh>.infl8_report.json."""
import sys, os, json, numpy as np
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
from cyberwolf.mesh import Mesh
E = json.load(open(os.path.join(ROOT, 'tests_assets', 'infl8_import', 'expected.json')))
path = sys.argv[1]; M = Mesh(path); T = Mesh(os.path.join(ROOT, E['template']))
rep = {'mesh': path, 'checks': {}}
lod0 = [c for c in M.chunks if c.lod_mask & 1]
rep['checks']['lod0_chunks'] = len(lod0)
c = lod0[0]
rep['checks']['layout_has_8_influences'] = ('PS_SkinIndices1:PT_UByte4@s0' in c.layout) and ('PS_SkinWeights1:PT_UByte4N@s0' in c.layout)
rep['layout'] = c.layout
X = np.vstack([ch.position for ch in lod0]); Jm = np.vstack([ch.joints for ch in lod0]); Wm = np.vstack([ch.weights_raw for ch in lod0])
exp_pos = np.array(E['positions_red'])
# nearest imported vertex for every expected vertex (simple grid hash)
cell = 0.002; key = lambda p: tuple(np.floor(p / cell).astype(int))
grid = {}
for i, p in enumerate(X): grid.setdefault(key(p), []).append(i)
match = np.full(len(exp_pos), -1); dist = np.full(len(exp_pos), np.inf)
for v, p in enumerate(exp_pos):
    k = np.array(key(p))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for i in grid.get(tuple(k + [dx, dy, dz]), []):
                    d = np.linalg.norm(X[i] - p)
                    if d < dist[v]: dist[v], match[v] = d, i
found = (match >= 0) & (dist < 0.0005)
rep['checks']['vertices_found'] = f'{int(found.sum())}/{len(exp_pos)}'; rep['max_position_error_mm'] = float(dist[found].max() * 1000) if found.any() else None
rep['imported_vertex_count'] = int(len(X))
names = M.bone_names; res = {'exact_ok': 0, 'exact_bad': 0, 'dropped_influences': 0, 'byte_mismatch': 0, 'bone_mismatch': 0}; sent = {}; bad = []
for v, e in enumerate(E['expected']):
    if not found[v]: continue
    i = match[v]; got = {names[j]: int(w) for j, w in zip(Jm[i], Wm[i]) if w > 0}
    if e['kind'] == 'sentinel_equal_8':
        s = int(Wm[i].sum()); sent[s] = sent.get(s, 0) + 1
        res['dropped_influences'] += 8 - len(got); continue
    want = dict(zip(e['bones'], e['bytes']))
    if got == want: res['exact_ok'] += 1; continue
    res['exact_bad'] += 1
    res['dropped_influences'] += len(set(want) - set(got)); res['bone_mismatch'] += len(set(got) - set(want))
    res['byte_mismatch'] += sum(1 for b in want if b in got and got[b] != want[b])
    if len(bad) < 10: bad.append({'vertex': v, 'expected': want, 'got': got})
rep['weights'] = res; rep['sentinel_byte_sums'] = sent; rep['examples_of_mismatch'] = bad
# bind matrices: imported vs vanilla template, by bone name
ti = {n: k for k, n in enumerate(T.bone_names)}
dm = [float(np.abs(M.ibm_rowvec[k] - T.ibm_rowvec[ti[n]]).max()) for k, n in enumerate(M.bone_names) if n in ti]
rep['checks']['bind_matrices_max_abs_diff_vs_template'] = max(dm) if dm else None
rep['checks']['bones_added_by_import'] = [n for n in M.bone_names if n not in ti]
rep['verdict'] = {'eight_influences_survive': bool(rep['checks']['layout_has_8_influences'] and res['exact_bad'] == 0 and res['dropped_influences'] == 0 and found.all()),
                  'sentinel_sum_256_observed': 256 in sent}
json.dump(rep, open(path + '.infl8_report.json', 'w'), indent=1)
print(json.dumps({k: rep[k] for k in ('checks', 'weights', 'sentinel_byte_sums', 'verdict')}, indent=1))
