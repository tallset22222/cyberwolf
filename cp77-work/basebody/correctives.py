"""Corrective shapes, stage 1 (shape authoring and validation; engine delivery is stage 2, OI-20).
Enabled with CW_CORRECTIVES=elbow,knee (any subset). Off by default: nothing changes without it.

Common method (per joint, per skinning method; authored on the left limb and mirrored exactly to the right):
  * at key flexion angles the joint is posed with the normal pose machinery and skinned WITHOUT correctives;
  * CONTACT: inner-crease skin that has crossed the plane bisecting the joint angle is moved back onto it, leaving GAP
    each side, so the two sides end in contact. Side membership comes from rest-pose anatomy (signed distance along the
    limb axis from the joint), with a CREASE_BAND that lands on the plane. Only the limb's own skin takes part (test-3
    region map). The displacement is smoothed over the surface and re-constrained (SMOOTH_ITERS).
  * knee only, optional components on the OUTER (front) side, selected with CW_KNEE_FRONT:
      'radial' - restore each front vertex's rest distance from the knee hinge axis where skinning shrank it
                 (LBS front-of-knee collapse; DQS keeps the radius, so it is ~0 there);
      'relax'  - tangential relaxation toward rest edge lengths (skin slides over the knee instead of one band
                 stretching), with the normal component removed so the silhouette is kept;
  * the displacement is converted to rest (bind) space through each vertex's own skinning map (exact for LBS and DQS)
    and applied before skinning, like a morph target;
  * activation by flexion only (swing of the distal segment relative to the proximal one; twist-free): 0 below START,
    smoothstep to the first key, keys interpolated, held beyond the last key.
Elbow decisions (17 Nov 2026): one 90 deg key; deep flexion (110-145 deg) contact accepted; volume bulge off.
Knee (stage 1): keys 90 and 135 deg (knee contact starts after 110 deg and is local enough to flatten at 135);
front components per method: LBS radial+relax, DQS none."""
import os, numpy as np
ENABLED = [s for s in os.environ.get('CW_CORRECTIVES', '').split(',') if s]
START = 30.0; GAP = 0.00075; CREASE_BAND = 0.005; SMOOTH_ITERS = 12
JOINTS = {
    'elbow': dict(parent='upperarm', mid='lowerarm', end='hand', bend=[0, 0, 1.0], REGION=0.25,
                  regions=('upperarm_upper', 'upperarm_lower', 'elbow', 'forearm'), keys=os.environ.get('CW_ELBOW_KEYS', '90'),
                  bulge=os.environ.get('CW_ELBOW_BULGE', '0') == '1', front=''),
    'knee':  dict(parent='thigh', mid='calf', end='foot', bend=[0, 0, -1.0], REGION=0.25,
                  regions=('thigh_upper', 'thigh_lower', 'knee', 'shin'), keys=os.environ.get('CW_KNEE_KEYS', '90,135'),
                  bulge=False, front=os.environ.get('CW_KNEE_FRONT', ''),
                  # per skinning method when CW_KNEE_FRONT is not set: LBS collapses at the front of the knee (restore the
                  # radius, then relax tangentially); DQS keeps the radius, and relaxing only adds area growth there
                  front_by_method={'LBS': os.environ.get('CW_KNEE_FRONT_LBS', 'radial,relax'), 'DQS': os.environ.get('CW_KNEE_FRONT_DQS', '')}),
}
FRONT_REGION = 0.10; RELAX_ITERS = 20; RADIAL_SMOOTH_ITERS = int(os.environ.get('CW_KNEE_RADIAL_SMOOTH', '12'))
BULGE_SIGMA = 0.02; BULGE_MAX = 0.015
_C = {'authoring': False}

def keys_of(j): return tuple(float(x) for x in JOINTS[j]['keys'].split(','))

def flex_angle(G, pos, j, s):
    """Flexion = swing of the distal segment's direction relative to the proximal bone (twist-free; exact for a hinge)."""
    J = JOINTS[j]; f0 = pos[f"{J['end']}_{s}"] - pos[f"{J['mid']}_{s}"]; f0 = f0 / np.linalg.norm(f0)
    Rrel = G[f"{J['parent']}_{s}"][:3, :3].T @ G[f"{J['mid']}_{s}"][:3, :3]
    return float(np.degrees(np.arccos(np.clip((Rrel @ f0) @ f0, -1, 1))))

def _flex_angle(G, pos, s): return flex_angle(G, pos, 'elbow', s)      # kept for the elbow evaluation script

def _data():
    if 'V' not in _C:
        import test2_deformation as T2
        V, Q, pos, par, kids, bones, top, Wt = T2.build()
        _C.update(V=V, Q=Q, pos=pos, par=par, kids=kids, bones=bones, top=top, Wt=Wt, T2=T2)
        nb = [set() for _ in range(len(V))]
        for q in Q:
            for k in range(4): nb[q[k]].update((q[(k + 1) % 4], q[(k + 3) % 4]))
        _C['rows'] = np.concatenate([[i] * len(n) for i, n in enumerate(nb)]); _C['cols'] = np.concatenate([list(n) for n in nb])
        key = {tuple(np.round(v * [-1, 1, 1], 6)): i for i, v in enumerate(V)}
        _C['mirror'] = np.array([key[tuple(np.round(v, 6))] for v in V])
        _C['lab'] = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_test3_lab.npy'), allow_pickle=True)
    return _C

def joint_pose(j, angle, s='l'):
    """Pose ops for a pure flexion of `angle` degrees (same construction as the test-2 elbow / knee poses)."""
    d = _data(); T2 = d['T2']; pos = d['pos']; J = JOINTS[j]
    dirn = pos[f"{J['end']}_{s}"] - pos[f"{J['mid']}_{s}"]; dirn /= np.linalg.norm(dirn)
    return [(f"{J['mid']}_{s}", T2.toward(dirn, np.array(J['bend']), angle), 1.0)]

def elbow_pose(angle, s='l'): return joint_pose('elbow', angle, s)

def _linear_map(G, method):
    """Per-vertex 3x3 linear part of the skinning map (exact for LBS and DQS: both are affine per vertex)."""
    d = _data(); T2 = d['T2']; V = d['V']; eps = 1e-3
    base = T2.skin(V, d['bones'], d['top'], d['Wt'], G, method)
    cols = [(T2.skin(V + eps * e, d['bones'], d['top'], d['Wt'], G, method) - base) / eps for e in np.eye(3)]
    return base, np.stack(cols, 2)

def _smooth(D, mask_or_moved, fade, rows, cols, cnt):
    acc = np.zeros_like(D); np.add.at(acc, rows, D[cols])
    return np.where(mask_or_moved[:, None], 0.5 * D + 0.5 * acc / cnt, D) * fade[:, None]

def front_of(j, method):
    J = JOINTS[j]
    if J['front'] or 'front_by_method' not in J: return J['front']
    return J['front_by_method'].get(method, '')

def _author_key(j, angle, method):
    d = _data(); T2 = d['T2']; V, pos, Q = d['V'], d['pos'], d['Q']; J = dict(JOINTS[j]); R = J['REGION']; J['front'] = front_of(j, method)
    P, Mi, E = (f"{J[k]}_l" for k in ('parent', 'mid', 'end'))
    ops = joint_pose(j, angle, 'l'); G = T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
    _C['authoring'] = True
    try: X, A = _linear_map(G, method)
    finally: _C['authoring'] = False
    tp = lambda n: (G[n] @ np.append(pos[n], 1))[:3]
    p = tp(Mi); u = tp(P) - p; u /= np.linalg.norm(u); f = tp(E) - p; f /= np.linalg.norm(f)
    b = (u + f) / np.linalg.norm(u + f); n = (u - f) / np.linalg.norm(u - f)          # inner-crease axis; bisector-plane normal
    f0 = pos[E] - pos[Mi]; f0 /= np.linalg.norm(f0); u0 = pos[P] - pos[Mi]; u0 /= np.linalg.norm(u0)
    ax = (f0 - u0) / np.linalg.norm(f0 - u0); srest = (V - pos[Mi]) @ ax
    distal = srest > CREASE_BAND; proximal = srest < -CREASE_BAND; crease = ~distal & ~proximal
    dist = np.linalg.norm(X - p, axis=1); inner = (X - p) @ b > -0.01
    limb = np.zeros(len(V), bool)
    for fi, q in enumerate(Q):
        if d['lab'][fi] in tuple(r + '_l' for r in J['regions']): limb[q] = True
    reg = (dist < R) & inner & limb
    fade = np.clip((R - dist) / (0.3 * R), 0, 1)
    def violation(Y):
        s_ = (Y - p) @ n; out = np.zeros_like(Y)
        mf = reg & distal & (s_ > -GAP); out[mf] = -(s_[mf] + GAP)[:, None] * n
        mu = reg & proximal & (s_ < GAP); out[mu] = (GAP - s_[mu])[:, None] * n
        mc = reg & crease & (np.abs(s_) > GAP); out[mc] = -(s_[mc] - np.sign(s_[mc]) * GAP)[:, None] * n
        return out
    D = violation(X)
    rows, cols = _C['rows'], _C['cols']; cnt = np.bincount(rows, minlength=len(V))[:, None]
    for _ in range(SMOOTH_ITERS):
        D = _smooth(D, reg | (np.linalg.norm(D, axis=1) > 0), fade, rows, cols, cnt)
        D += violation(X + D)
    info = {'joint': j, 'angle': angle, 'contact_vertices_moved': int((np.linalg.norm(D, axis=1) > 1e-5).sum())}
    if J['front']:
        # outer (front) side of the bend, limb skin within FRONT_REGION of the joint
        front = limb & ((X - p) @ b < 0) & (dist < FRONT_REGION)
        ffade = np.clip((FRONT_REGION - dist) / (0.4 * FRONT_REGION), 0, 1)
        h = np.cross(u, f); h /= np.linalg.norm(h)                                    # hinge axis (posed)
        Rp = G[P][:3, :3]; h0 = Rp.T @ h; p0 = pos[Mi]
        F = np.zeros_like(X)
        if 'radial' in J['front']:
            rel = X - p; rv = rel - np.outer(rel @ h, h); r = np.linalg.norm(rv, axis=1)
            rel0 = V - p0; r0 = np.linalg.norm(rel0 - np.outer(rel0 @ h0, h0), axis=1)
            grow = np.where(front & (r < r0), (r0 - r) * ffade, 0.0)
            F += (grow / np.maximum(r, 1e-9))[:, None] * rv
            # smooth the radial field over the surface (a per-vertex push leaves a step where it fades out)
            mask = front | (np.linalg.norm(F, axis=1) > 0); ones = np.ones(len(V))
            for _ in range(RADIAL_SMOOTH_ITERS):
                F = _smooth(F, mask, ones, rows, cols, cnt)            # no repeated fade: it compounds without a re-constraint
            F *= ffade[:, None]
            info['radial_max_mm'] = float(np.linalg.norm(F, axis=1).max() * 1000)
        if 'relax' in J['front']:
            Ee = np.array(sorted({(min(a, c), max(a, c)) for q in Q for a, c in zip(q, np.roll(q, -1))}))
            L0 = np.linalg.norm(V[Ee[:, 0]] - V[Ee[:, 1]], axis=1)
            Y = X + D + F
            nq = np.cross(Y[Q[:, 2]] - Y[Q[:, 0]], Y[Q[:, 3]] - Y[Q[:, 1]]); vn = np.zeros_like(Y); np.add.at(vn, Q.ravel(), np.repeat(nq, 4, 0))
            vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-15
            act = front.astype(float) * ffade
            for _ in range(RELAX_ITERS):
                e = Y[Ee[:, 1]] - Y[Ee[:, 0]]; L = np.linalg.norm(e, axis=1); corr = ((L - L0) / np.maximum(L, 1e-12))[:, None] * e * 0.5
                g = np.zeros_like(Y); np.add.at(g, Ee[:, 0], corr); np.add.at(g, Ee[:, 1], -corr)
                deg = np.bincount(Ee.ravel(), minlength=len(Y))[:, None]
                step = g / deg; step -= (step * vn).sum(1, keepdims=True) * vn            # tangential only
                Y = Y + 0.5 * step * act[:, None]
            F = Y - (X + D)
            info['relax_max_mm'] = float(np.linalg.norm(F, axis=1).max() * 1000)
        D = D + F
        D += violation(X + D)
    delta = np.einsum('vij,vj->vi', np.linalg.inv(A), D)
    delta[~(np.linalg.norm(D, axis=1) > 1e-7)] = 0
    info.update(vertices_moved=int((np.linalg.norm(D, axis=1) > 1e-5).sum()), max_mm=float(np.linalg.norm(D, axis=1).max() * 1000))
    mi = _C['mirror']; return delta + delta[mi] * [-1, 1, 1], info

def deltas(j, method):
    k = (j, method, JOINTS[j]['keys'], front_of(j, method))
    if k not in _C: _C[k] = [_author_key(j, a, method) for a in keys_of(j)]
    return _C[k]

def elbow_deltas(method): return deltas('elbow', method)

def activation_delta(theta, keys, KEYS=None):
    KEYS = KEYS or tuple(k[1]['angle'] for k in keys)
    if theta <= START: return None
    if theta <= KEYS[0]:
        t = (theta - START) / (KEYS[0] - START); t = t * t * (3 - 2 * t); return t * keys[0][0]
    for i in range(len(KEYS) - 1):
        if theta <= KEYS[i + 1]:
            t = (theta - KEYS[i]) / (KEYS[i + 1] - KEYS[i]); return (1 - t) * keys[i][0] + t * keys[i + 1][0]
    return keys[-1][0]

def apply(V, G, method):
    """Called by test2_deformation.skin before skinning. Returns V (+ corrective deltas when active)."""
    if not ENABLED or _C['authoring']: return V
    d = _data()
    if len(V) != len(d['V']): return V
    out = V
    for j in ENABLED:
        if j not in JOINTS: continue
        keys = deltas(j, method)
        for s in 'lr':
            dl = activation_delta(flex_angle(G, d['pos'], j, s), keys)
            if dl is None: continue
            side = (d['V'][:, 0] > 0) if s == 'l' else (d['V'][:, 0] < 0)
            out = out + np.where(side[:, None], dl, 0.0)
    return out
