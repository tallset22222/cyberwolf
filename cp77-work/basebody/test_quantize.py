"""Validate pipeline/cyberwolf/quantize.py on the v3 weights (4 and 8 influences) and on edge cases."""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'pipeline'))
from cyberwolf.quantize import quantize, export_floats
import test2_deformation as T2
rep = {}
for k in ('4', '8'):
    os.environ['CW_INFLUENCES'] = k
    V, Q, pos, par, kids, bones, top, Wt = T2.build('v3')
    B, r = quantize(Wt, top, bones)
    key = {tuple(np.round(v * [-1, 1, 1], 6)): i for i, v in enumerate(V)}; mi = np.array([key[tuple(np.round(v, 6))] for v in V])
    sw = lambda n: (n[:-2] + ('_r' if n.endswith('_l') else '_l')) if n.endswith(('_l', '_r')) else n
    d = lambda v: {bones[j]: int(b) for j, b in zip(top[v], B[v]) if b}
    asym = [v for v in range(len(V)) if d(mi[v]) != {sw(n): b for n, b in d(v).items()}]
    mid = np.abs(V[:, 0]) < 1e-9
    err = np.abs(B / 255.0 - Wt).max()
    rt = np.round(export_floats(B).astype(np.float64) * 255).astype(int)          # WolvenKit's per-weight rounding
    rep[k] = {'vertices': len(V), 'sum_255_all': bool((B.astype(int).sum(1) == 255).all()), 'assignments_kept': bool(((B > 0) == (Wt > 0)).all()),
              'max_abs_error_vs_float': round(float(err), 5), 'max_error_in_units_of_1/255': round(float(err * 255), 3),
              'mirror_asymmetric_vertices': len(asym), 'of_which_on_midline': int(mid[asym].sum()) if asym else 0,
              'midline_last_resort': len(r['midline_last_resort_vertices']), 'wolvenkit_roundtrip_exact': bool((rt == B).all())}
    print(k, rep[k])
# edge cases
cases = {'8 equal (sentinel)': ([0.125] * 8, [f'b{i}' for i in range(8)]), 'mirror pair only (midline)': ([0.5, 0.5, 0, 0], ['thigh_l', 'thigh_r', 'x', 'y']),
         'mirror pair + centre bone': ([0.45, 0.45, 0.1, 0], ['thigh_l', 'thigh_r', 'pelvis', 'y']), 'tiny weight kept': ([0.999, 0.0005, 0.0005, 0], ['a', 'b', 'c', 'd'])}
for name, (w, nm) in cases.items():
    B, r = quantize(np.array([w]), np.array([list(range(len(w)))]), nm)
    print(f'{name:28s} -> {list(B[0])} sum {int(B[0].astype(int).sum())} last-resort {bool(r["midline_last_resort_vertices"])}')
    rep[name] = {'bytes': [int(x) for x in B[0]], 'last_resort': bool(r['midline_last_resort_vertices'])}
json.dump(rep, open(os.path.join(HERE, 'reports', 'quantize_validation.json'), 'w'), indent=1)
