"""Interpolation tolerance for an OI-20 corrective-joint fit, either joint, BOTH limbs tested independently.
Fit unchanged (deterministic refit of the accepted configuration). Variants: as fitted; nlerp; matrix blend; linear
activation; no intermediate keys (90-degree key only); activation threshold shifted to 25/35 degrees (runtime vs
authoring mismatch); inverse-distance RBF over key angles (powers 1, 2, 4).
Usage: CW_JOINT=elbow CW_METHOD=DQS CW_NJ=3 CW_OI20_MIDKEYS=50,70 python3 oi20_interp_check.py"""
import os, sys, json, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import oi20_joints as O
METHOD, N = os.environ.get('CW_METHOD', 'DQS'), int(os.environ.get('CW_NJ', '3'))
V, pos, T2, CR, JN = O.V, O.pos, O.T2, O.CR, O.JNAME
import pickle
_cache = os.path.join(HERE, 'reports', 'correctives', f'_fitcache_{JN}_{METHOD}_n{N}_mk{"-".join(str(int(k)) for k in O.MIDKEYS)}.pkl')
if os.path.exists(_cache): joints = pickle.load(open(_cache, 'rb'))
else:
    joints, _, _ = O.fit(METHOD, N); O.fit_midkeys(joints, METHOD); pickle.dump(joints, open(_cache, 'wb'))
names, tp, Wt2, over = O.build(joints, 8)
assert over == 0
SWEEP = list(range(0, 151, 5)); fitted_off, fitted_act = O.offset_at, O.activation
areas = {s: (np.linalg.norm(V - pos[O.Mn[:-2] + '_' + s], axis=1) < 0.25) for s in 'lr'}
M = O.M2.Metric2(V, O.Q, T2.INTERIOR)
def sweep():
    res = {}
    for s in 'lr':
        per = {}; worst = rest = 0.0
        for th in SWEEP:
            G = O.G_at(th, s); Ge = O.G_ext(G, joints, CR.flex_angle(G, pos, JN, 'l'), CR.flex_angle(G, pos, JN, 'r'))
            X_off = T2.skin(V, O.bones, O.top, O.Wt, G, METHOD); CR._C['authoring'] = True
            X_j = T2.skin(V, names, tp, Wt2, Ge, METHOD); CR._C['authoring'] = False
            e = float(np.linalg.norm(X_j - X_off, axis=1)[areas[s]].max() * 1000); per[th] = round(e, 2)
            if th <= CR.START: rest = max(rest, e)
            if th <= O.KEY: worst = max(worst, e)
            if th in (60, 90):
                ev = M.measure(X_j, pos[O.Mn[:-2] + '_' + s]); per[f'{th}_X_fold'] = [ev['intersection_vertices'], ev['fold_over_edges']]
        res[s] = {'max_err_to_key_mm': round(worst, 2), 'max_err_up_to_30_mm': round(rest, 4),
                  'max_err_35_85_mm': max(per[a] for a in range(35, 90, 5)), 'per_angle': per}
    return res
def quat(R):
    w = math.sqrt(max(0.0, 1 + np.trace(R))) / 2; x = math.copysign(math.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0]); z = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    return np.array([w, x, y, z])
def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)], [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)], [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]])
def keys(J, mid=True):
    ks = [(CR.START, np.eye(3), np.zeros(3))] + (list(J.get('keys', [])) if mid else []) + [(O.KEY, J['R'], J['t'])]
    return ks
def blend(ks, w, how):
    if how == 'matrix': return sum(wi * R for wi, (_, R, _) in zip(w, ks)), sum(wi * t for wi, (_, _, t) in zip(w, ks))
    q0 = quat(ks[0][1]); qs = [quat(R) for _, R, _ in ks]; qs = [q if q @ q0 >= 0 else -q for q in qs]
    return qmat(sum(wi * q for wi, q in zip(w, qs))), sum(wi * t for wi, (_, _, t) in zip(w, ks))
def act_smooth(th, start=CR.START):
    if th <= start: return 0.0
    t = min(1.0, (th - start) / (O.KEY - start)); return t * t * (3 - 2 * t)
def piecewise(ks, th, act):
    a = act(th); pa = [act(k[0]) for k in ks]; w = np.zeros(len(ks))
    if a <= 0: w[0] = 1; return w
    for i in range(len(ks) - 1):
        if a <= pa[i + 1] + 1e-12: u = (a - pa[i]) / max(pa[i + 1] - pa[i], 1e-12); w[i], w[i + 1] = 1 - u, u; return w
    w[-1] = 1; return w
def variant(kind, arg=None):
    def off(J, th):
        if kind == 'fitted': return fitted_off(J, th)
        if kind == 'nlerp': ks = keys(J); return blend(ks, piecewise(ks, th, act_smooth), 'nlerp')
        if kind == 'matrix': ks = keys(J); return blend(ks, piecewise(ks, th, act_smooth), 'matrix')
        if kind == 'linear': ks = keys(J); lin = lambda t: 0.0 if t <= CR.START else min(1.0, (t - CR.START) / (O.KEY - CR.START)); return blend(ks, piecewise(ks, th, lin), 'nlerp')
        if kind == 'no_mid': ks = keys(J, mid=False); return blend(ks, piecewise(ks, th, act_smooth), 'nlerp')
        if kind == 'threshold':   # runtime starts at `arg` degrees; keys keep their angles
            ks = keys(J); ks = [(arg, ks[0][1], ks[0][2])] + ks[1:]; return blend(ks, piecewise(ks, th, lambda t: act_smooth(t, arg)), 'nlerp')
        if kind == 'rbf':
            ks = [(0.0, np.eye(3), np.zeros(3))] + keys(J); d = np.array([abs(th - k[0]) for k in ks])
            w = (d < 1e-9).astype(float) if d.min() < 1e-9 else 1 / d ** arg; return blend(ks, w / w.sum(), 'nlerp')
    return off
out = {'joint': JN, 'method': METHOD, 'joints_per_limb': len(joints), 'keys': list(O.KEYS), 'intermediate_keys': O.MIDKEYS, 'variants': {}}
ALL = (('fitted', None), ('nlerp', None), ('matrix', None), ('linear', None), ('no_mid', None), ('threshold', 25.0), ('threshold', 35.0), ('rbf', 1.0), ('rbf', 2.0), ('rbf', 4.0))
SEL = os.environ.get('CW_VARIANTS', '')
_outp = os.path.join(HERE, 'reports', 'correctives', f'oi20_{JN}_interp_{METHOD}.json')
if os.path.exists(_outp): out = json.load(open(_outp))
for kind, arg in [v for v in ALL if not SEL or (v[0] + ('' if v[1] is None else f'_{v[1]:g}')) in SEL.split(',')]:
    O.offset_at = variant(kind, arg); name = kind + ('' if arg is None else f'_{arg:g}')
    r = sweep(); out['variants'][name] = r; json.dump(out, open(_outp, 'w'), indent=1)
    print(name, {s: {k: v for k, v in r[s].items() if k != 'per_angle'} | {'X_fold@60,90': [r[s]['per_angle']['60_X_fold'], r[s]['per_angle']['90_X_fold']]} for s in 'lr'}, flush=True)
O.offset_at = fitted_off
