"""Evaluate the elbow corrective across a flexion sweep (base vs corrected, LBS and DQS). Writes reports/correctives/elbow_sweep.json"""
import os, sys, json, numpy as np
os.environ.setdefault('CW_WEIGHTS', 'v3'); os.environ['CW_CORRECTIVES'] = 'elbow'
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import correctives as CR, metrics2 as M2
d = CR._data(); T2 = d['T2']; V, Q, pos = d['V'], d['Q'], d['pos']
M = M2.Metric2(V, Q, T2.INTERIOR); out = {}
ANG = [0, 30, 60, 90, 110, 135, 150]
for m in ('LBS', 'DQS'):
    keys = CR.elbow_deltas(m)
    out[m] = {'keys': [k[1] for k in keys], 'sweep': {}}
    dl = keys[0][0]; mi = CR._C['mirror']
    out[m]['delta_mirror_error'] = float(np.abs(dl[mi] * [-1, 1, 1] - dl).max())
    for a in ANG:
        ops = CR.elbow_pose(a); G = T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
        CR._C['authoring'] = True; Xb = T2.skin(V, d['bones'], d['top'], d['Wt'], G, m); CR._C['authoring'] = False
        Xc = T2.skin(V, d['bones'], d['top'], d['Wt'], G, m)
        c = pos['lowerarm_l']; r = {}
        for lab, X in (('base', Xb), ('corrective', Xc)):
            e = M.measure(X, c); leg = T2.metrics(V, X, Q, pos, G, 'lowerarm_l', d['bones'], d['top'], d['Wt'])
            r[lab] = {**{k: e[k] for k in ('intersection_vertices', 'intersection_max_depth_mm', 'pinch_length_mm', 'fold_over_edges', 'crease_line_edges', 'area_shrink_pct', 'area_grow_pct')},
                      'volume_ratio': leg['volume_ratio'], 'strain_p95': leg['strain_p95'], 'strain_p5': leg['strain_p5']}
        r['max_displacement_mm'] = float(np.linalg.norm(Xc - Xb, axis=1).max() * 1000); r['flexion_measured'] = round(CR._flex_angle(G, pos, 'l'), 1)
        out[m]['sweep'][a] = r
        np.save(os.path.join(HERE, 'reports', 'correctives', f'_elbow_{m}_{a}.npy'), np.stack([Xb, Xc]))
json.dump(out, open(os.path.join(HERE, 'reports', 'correctives', 'elbow_sweep' + os.environ.get('CW_SWEEP_TAG', '') + '.json'), 'w'), indent=1)
for m in out:
    print(m, 'keys', out[m]['keys'], 'mirror err', out[m]['delta_mirror_error'])
    for a, r in out[m]['sweep'].items():
        b, c = r['base'], r['corrective']
        print(f"  {a:3d}deg (meas {r['flexion_measured']:5.1f}) inter {b['intersection_vertices']:3d}/{b['intersection_max_depth_mm']:4.0f}mm -> {c['intersection_vertices']:3d}/{c['intersection_max_depth_mm']:4.0f}mm | pinch {b['pinch_length_mm']:4.0f}->{c['pinch_length_mm']:4.0f} | fold {b['fold_over_edges']}->{c['fold_over_edges']} | vol {b['volume_ratio']:.2f}->{c['volume_ratio']:.2f} | s95 {b['strain_p95']:.2f}->{c['strain_p95']:.2f} s5 {b['strain_p5']:.2f}->{c['strain_p5']:.2f} | max move {r['max_displacement_mm']:.1f}mm")
