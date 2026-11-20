"""Flexion sweep for one corrective joint (base vs corrected, LBS and DQS). Usage: CW_JOINT=knee [CW_KNEE_FRONT=..] corrective_sweep.py <tag>
Writes reports/correctives/<joint>_sweep_<tag>.json and saves posed arrays for renders."""
import os, sys, json, numpy as np
os.environ.setdefault('CW_WEIGHTS', 'v3'); J = os.environ.get('CW_JOINT', 'knee'); os.environ['CW_CORRECTIVES'] = J
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import correctives as CR, metrics2 as M2
tag = sys.argv[1] if len(sys.argv) > 1 else 'default'
d = CR._data(); T2 = d['T2']; V, Q, pos = d['V'], d['Q'], d['pos']; mid = CR.JOINTS[J]['mid'] + '_l'
M = M2.Metric2(V, Q, T2.INTERIOR); out = {}
for m in ('LBS', 'DQS'):
    keys = CR.deltas(J, m); mi = CR._C['mirror']
    out[m] = {'keys': [k[1] for k in keys], 'delta_mirror_error': float(np.abs(keys[0][0][mi] * [-1, 1, 1] - keys[0][0]).max()), 'sweep': {}}
    for a in (0, 30, 60, 90, 110, 135, 150):
        ops = CR.joint_pose(J, a); G = T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
        CR._C['authoring'] = True; Xb = T2.skin(V, d['bones'], d['top'], d['Wt'], G, m); CR._C['authoring'] = False
        Xc = T2.skin(V, d['bones'], d['top'], d['Wt'], G, m)
        r = {}
        for lab, X in (('base', Xb), ('corrective', Xc)):
            e = M.measure(X, pos[mid]); leg = T2.metrics(V, X, Q, pos, G, mid, d['bones'], d['top'], d['Wt'])
            r[lab] = {**{k: e[k] for k in ('intersection_vertices', 'intersection_max_depth_mm', 'pinch_length_mm', 'fold_over_edges', 'area_grow_pct', 'area_shrink_pct', 'strain_p95')},
                      'volume_ratio': leg['volume_ratio'], 'legacy_s95': leg['strain_p95'], 'legacy_s5': leg['strain_p5']}
        r['max_displacement_mm'] = float(np.linalg.norm(Xc - Xb, axis=1).max() * 1000); r['flexion_measured'] = round(CR.flex_angle(G, pos, J, 'l'), 1)
        out[m]['sweep'][a] = r
        np.save(os.path.join(HERE, 'reports', 'correctives', f'_{J}_{tag}_{m}_{a}.npy'), np.stack([Xb, Xc]))
json.dump(out, open(os.path.join(HERE, 'reports', 'correctives', f'{J}_sweep_{tag}.json'), 'w'), indent=1)
for m in out:
    print(m, [{k: round(v, 1) if isinstance(v, float) else v for k, v in kk.items()} for kk in out[m]['keys']], 'mirror err', out[m]['delta_mirror_error'])
    for a, r in out[m]['sweep'].items():
        if a in (0, 30): 
            if r['max_displacement_mm'] > 0: print('   !! moved at', a)
            continue
        b, c = r['base'], r['corrective']
        print(f"  {a:3d} (meas {r['flexion_measured']:5.1f}) inter {b['intersection_vertices']:3d}/{b['intersection_max_depth_mm']:2.0f}->{c['intersection_vertices']:3d}/{c['intersection_max_depth_mm']:2.0f} | pinch {b['pinch_length_mm']:3.0f}->{c['pinch_length_mm']:3.0f} | fold {b['fold_over_edges']}->{c['fold_over_edges']} | vol {b['volume_ratio']:.2f}->{c['volume_ratio']:.2f} | s95(13cm) {b['legacy_s95']:.2f}->{c['legacy_s95']:.2f} s5 {b['legacy_s5']:.2f}->{c['legacy_s5']:.2f} | grow {b['area_grow_pct']:.1f}->{c['area_grow_pct']:.1f}% | move {r['max_displacement_mm']:.0f}mm")
