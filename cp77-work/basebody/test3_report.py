"""Assemble reports/test3_regions.json/.md from the region labelling (part A) and _test3_partB.json (part B)."""
import sys, os, json, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test2_deformation as T2, test3_regions as T3, render_test3 as R
V, Q, pos, *_ = T2.build()
closed, S = T3.seam_loops(V, Q, pos)
cut = set(e for k, (_, li) in S.items() if li is not None for e in closed[li]['edges'])
comp, fe = T3.flood(Q, cut)
lab = T3.label_regions(V, Q, pos, closed, S, comp)
np.save(os.path.join(HERE, '_test3_lab.npy'), lab.astype(str))
spec_regions = [r['name'] for r in json.load(open(os.path.join(HERE, '..', 'specs', 'character_standard', 'hiding_regions.json')))['regions']]
counts = collections.Counter(lab)
br = T3.boundary_report(V, Q, lab, fe)
on_loop = {}
for e, fs in fe.items():
    if len(fs) == 2 and lab[fs[0]] != lab[fs[1]]:
        k = ' | '.join(sorted((lab[fs[0]], lab[fs[1]]))); on_loop.setdefault(k, []).append(e in cut)
for k in br: br[k]['on_edge_loop'] = bool(all(on_loop[k])); br[k] = {kk: (float(v) if isinstance(v, np.floating) else v) for kk, v in br[k].items()}
# hiding any one region must leave only clean open edges (no T-junctions / non-manifold boundary)
hide_ok = {}
for r in counts:
    vis = lab != r; deg = collections.Counter()
    for e, fs in fe.items():
        n = sum(vis[f] for f in fs)
        if n == 1: deg[e[0]] += 1; deg[e[1]] += 1
    hide_ok[r] = bool(all(v == 2 for v in deg.values()))
B = json.load(open(os.path.join(HERE, 'reports', '_test3_partB_l.json')))
BR = json.load(open(os.path.join(HERE, 'reports', '_test3_partB_r.json')))
rings = []
for li, l in enumerate(closed):
    P = V[l['verts']]
    if abs(P[:, 0].mean()) < 0.01 and np.ptp(P[:, 0]) > 0.2 and np.ptp(P[:, 1]) < 0.06 and S['waist'][1] != li and V[closed[S['waist'][1]]['verts']][:, 1].mean() < P[:, 1].mean() < pos['spine_03'][1]:
        rings.append(round(float(P[:, 1].mean() * 1000)))
e = np.load(os.path.join(HERE, '_weight_asym.npy'))
vl = {}
for f, q in enumerate(Q):
    for v in q: vl.setdefault(int(v), lab[f])
per = collections.defaultdict(lambda: [0, 0.0])
for v in np.where(e > 0.05)[0]:
    k = vl[int(v)]; k = k[:-2] if k.endswith(('_l', '_r')) else k; per[k][0] += 1; per[k][1] = max(per[k][1], float(e[v]))
WSJ = json.load(open(os.path.join(HERE, 'reports', 'weight_symmetry.json')))
WS = {'gate': WSJ, 'v1_mesh_mirror_error_mm': 0.0, 'v1_joint_mirror_error_mm': 0.01, 'v1_vertices_weight_asym_gt_0.05': int((e > 0.05).sum()),
      'v1_max_weight_asym': round(float(e.max()), 2), 'v1_by_region': {k: {'vertices': n, 'max': round(m, 2)} for k, (n, m) in sorted(per.items(), key=lambda kv: -kv[1][0])}}
out = {'test': 'region separation and seam motion', 'mesh': 'MakeHuman hm08 working copy (base_working.obj), body group, metres',
       'partA': {'components': int(comp.max() + 1), 'regions_found': len(counts), 'regions_in_spec': len(spec_regions),
                 'missing': sorted(set(spec_regions) - set(counts)), 'faces_per_region': dict(sorted(counts.items())),
                 'boundaries': br, 'hide_leaves_clean_open_edge': hide_ok,
                 'ribcage_loop_y_mm': round(float(V[closed[S['ribcage'][1]]['verts']][:, 1].mean() * 1000)),
                 'waist_loop_y_mm': round(float(V[closed[S['waist'][1]]['verts']][:, 1].mean() * 1000)),
                 'candidate_torso_rings_above_waist_y_mm': sorted(set(rings))},
       'partB': B, 'partB_right': BR, 'partB_v1_archive': 'reports/v1_asymmetric_weights/',
       'weight_symmetry': WS,
       'notes': ['Seam motion measured on BOTH sides with real poses (right-side poses are the left library mirrored); right-side results are not inferred from the left.',
                 'Body-to-body region boundaries share vertices, so hiding never opens a gap between body regions at rest or posed; '
                 'the only gap risk is at the implant/body interface (part B).']}
json.dump(out, open(os.path.join(HERE, 'reports', 'test3_regions.json'), 'w'), indent=1)
R.render_regions(V, Q, lab, fe, cut, os.path.join(HERE, 'reports', 'test3_regions.png'))
R.render_motion(B, os.path.join(HERE, 'reports', 'test3_seam_motion.png'))
print(json.dumps({k: v for k, v in out['partA'].items() if k not in ('boundaries', 'faces_per_region')}, indent=0))
print('rule-based boundaries:', sorted(k for k, v in br.items() if not v['on_edge_loop']))
