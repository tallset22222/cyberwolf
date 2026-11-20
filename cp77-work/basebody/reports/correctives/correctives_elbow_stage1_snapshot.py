"""Corrective shapes, stage 1 (shape authoring and validation; engine delivery is a separate later step).
Enabled with CW_CORRECTIVES=elbow (comma list for more). Off by default: nothing changes without it.

Elbow corrective (per skinning method; authored for the left arm and mirrored to the right):
  * at key flexion angles (KEYS) the elbow is posed with the normal pose machinery and skinned WITHOUT correctives;
  * inner-crease skin that has crossed the plane bisecting the elbow angle (forearm skin into the upper arm half and
    vice versa) is moved back onto that plane leaving GAP: contact flattening at authoring time, in place of a sculptor;
  * the displacement is smoothed over the surface and re-constrained (SMOOTH_ITERS), faded to zero within REGION;
  * it is converted to rest (bind) space through each vertex's own skinning linear map, so it is applied before
    skinning like any morph target;
  * activation by elbow FLEXION only (angle between upper-arm and forearm directions, minus the rest angle; twist does
    not trigger it): 0 below START, the 90 deg key ramps in with a smoothstep, keys interpolated linearly, held beyond
    the last key."""
import os, numpy as np
ENABLED = [s for s in os.environ.get('CW_CORRECTIVES', '').split(',') if s]
KEYS = tuple(float(x) for x in os.environ.get('CW_ELBOW_KEYS', '90').split(',')); START = 30.0; GAP = 0.00075; CREASE_BAND = 0.005; REGION = 0.25; SMOOTH_ITERS = 12; BULGE = os.environ.get('CW_ELBOW_BULGE', '0') == '1'; BULGE_SIGMA = 0.02; BULGE_MAX = 0.015
# REGION covers the forearm's overlap reach at deep flexion (~21 cm at 135 deg). A volume-conserving bulge was tried
# and removed (it displaced vertices by up to 290 mm: see reports/correctives/elbow_corrective.md).
# GAP per side: the two sides end 1.5 mm apart, i.e. in contact (the metric's contact range is 2 mm)
_C = {'authoring': False}

def _flex_angle(G, pos, s):
    """Elbow flexion = swing of the forearm direction relative to the upper arm (twist-free; exact for a hinge)."""
    f0 = pos[f'hand_{s}'] - pos[f'lowerarm_{s}']; f0 = f0 / np.linalg.norm(f0)
    Rrel = G[f'upperarm_{s}'][:3, :3].T @ G[f'lowerarm_{s}'][:3, :3]
    return float(np.degrees(np.arccos(np.clip((Rrel @ f0) @ f0, -1, 1))))

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
    return _C

def elbow_pose(angle, s='l'):
    """Pose ops for a pure elbow flexion of `angle` degrees (same construction as the test-2 elbow poses)."""
    d = _data(); T2 = d['T2']; pos = d['pos']
    dirn = (pos[f'hand_{s}'] - pos[f'lowerarm_{s}']); dirn /= np.linalg.norm(dirn)
    return [(f'lowerarm_{s}', T2.toward(dirn, np.array([0, 0, 1.0]), angle), 1.0)]

def _linear_map(G, method):
    """Per-vertex 3x3 linear part of the skinning map (exact for LBS and DQS: both are affine per vertex)."""
    d = _data(); T2 = d['T2']; V = d['V']; eps = 1e-3
    base = T2.skin(V, d['bones'], d['top'], d['Wt'], G, method)
    cols = [(T2.skin(V + eps * e, d['bones'], d['top'], d['Wt'], G, method) - base) / eps for e in np.eye(3)]
    return base, np.stack(cols, 2)                  # A[v] columns = images of the unit axes

def _author_key(angle, method):
    d = _data(); T2 = d['T2']; V, pos, bones, top, Wt = d['V'], d['pos'], d['bones'], d['top'], d['Wt']
    ops = elbow_pose(angle, 'l'); G = T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
    _C['authoring'] = True
    try: X, A = _linear_map(G, method)
    finally: _C['authoring'] = False
    p = (G['lowerarm_l'] @ np.append(pos['lowerarm_l'], 1))[:3]
    u = (G['upperarm_l'] @ np.append(pos['upperarm_l'], 1))[:3] - p; u /= np.linalg.norm(u)
    f = (G['hand_l'] @ np.append(pos['hand_l'], 1))[:3] - p; f /= np.linalg.norm(f)
    b = (u + f) / np.linalg.norm(u + f); n = (u - f) / np.linalg.norm(u - f)          # inner-crease axis; bisector-plane normal
    # anatomical side at rest: signed distance along the forearm axis from the elbow joint
    f0 = pos['hand_l'] - pos['lowerarm_l']; f0 /= np.linalg.norm(f0); u0 = pos['upperarm_l'] - pos['lowerarm_l']; u0 /= np.linalg.norm(u0)
    ax = (f0 - u0) / np.linalg.norm(f0 - u0)                         # rest limb axis through the elbow
    srest = (V - pos['lowerarm_l']) @ ax
    fore_side = srest > CREASE_BAND; upper_side = srest < -CREASE_BAND; crease = ~fore_side & ~upper_side
    dist = np.linalg.norm(X - p, axis=1); inner = (X - p) @ b > -0.01
    # only the arm's own skin takes part (validated region map, test 3): never torso, hand or head
    lab = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_test3_lab.npy'), allow_pickle=True)
    arm = np.zeros(len(V), bool)
    for fi, q in enumerate(d['Q']):
        if lab[fi] in ('upperarm_upper_l', 'upperarm_lower_l', 'elbow_l', 'forearm_l'): arm[q] = True
    reg = (dist < REGION) & inner & arm
    fade = np.clip((REGION - dist) / (0.3 * REGION), 0, 1)
    def violation(Y):
        s_ = (Y - p) @ n; out = np.zeros_like(Y)
        mf = reg & fore_side & (s_ > -GAP); out[mf] = -(s_[mf] + GAP)[:, None] * n
        mu = reg & upper_side & (s_ < GAP); out[mu] = (GAP - s_[mu])[:, None] * n
        mc = reg & crease & (np.abs(s_) > GAP); out[mc] = -(s_[mc] - np.sign(s_[mc]) * GAP)[:, None] * n   # crease line onto the plane
        return out
    D = violation(X)
    rows, cols = _C['rows'], _C['cols']; cnt = np.bincount(rows, minlength=len(V))[:, None]
    for _ in range(SMOOTH_ITERS):
        acc = np.zeros_like(D); np.add.at(acc, rows, D[cols]); D = np.where(reg[:, None] | (np.linalg.norm(D, axis=1) > 0)[:, None], 0.5 * D + 0.5 * acc / cnt, D)
        D *= fade[:, None]
        D += violation(X + D)                         # re-constrain after smoothing
    if BULGE:
        # volume conservation: volume removed by flattening (inward displacement x vertex area) returned as a smooth
        # outward bulge on the same limb's skin around its contact patch (arm skin only), along posed normals
        Qm = d['Q']; nq = np.cross(X[Qm[:, 2]] - X[Qm[:, 0]], X[Qm[:, 3]] - X[Qm[:, 1]]); fa = 0.5 * np.linalg.norm(nq, axis=1)
        va = np.zeros(len(V)); np.add.at(va, Qm.ravel(), np.repeat(fa / 4, 4))
        vn = np.zeros_like(X); np.add.at(vn, Qm.ravel(), np.repeat(nq, 4, 0)); vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-15
        patch = np.linalg.norm(D, axis=1) > 1e-5
        for side in (fore_side | crease, upper_side):
            P_ = patch & side & reg
            if not P_.any(): continue
            removed = float((np.maximum(-(D[P_] * vn[P_]).sum(1), 0) * va[P_]).sum())
            pts = X[P_]; cand = np.where(side & reg & ~P_)[0]
            if not len(cand): continue
            dd = np.min(np.linalg.norm(X[cand][:, None, :] - pts[None, :, :], axis=2), axis=1)
            w = np.zeros(len(V)); w[cand] = np.where(dd < 3 * BULGE_SIGMA, np.exp(-(dd / BULGE_SIGMA) ** 2), 0.0)
            denom = float((w * va).sum())
            if denom > 1e-9:
                h = min(removed / denom, BULGE_MAX)
                D = D + (h * w)[:, None] * vn
                _C.setdefault('bulge_log', []).append({'angle': angle, 'removed_cm3': removed * 1e6, 'band_area_cm2': denom * 1e4, 'h_mm': h * 1000})
        D += violation(X + D)
    delta = np.einsum('vij,vj->vi', np.linalg.inv(A), D)   # posed displacement -> rest space
    delta[~((np.linalg.norm(D, axis=1) > 1e-7))] = 0
    # mirror to the right arm
    mi = _C['mirror']; dr = delta[mi] * [-1, 1, 1]
    return delta + dr, {'angle': angle, 'vertices_moved': int((np.linalg.norm(D, axis=1) > 1e-5).sum()), 'max_mm': float(np.linalg.norm(D, axis=1).max() * 1000)}

def elbow_deltas(method):
    k = ('elbow', method)
    if k not in _C:
        _C[k] = [_author_key(a, method) for a in KEYS]
    return _C[k]

def activation_delta(theta, keys):
    """keys: [(delta, info)] for KEYS. Returns the blended rest-space delta for flexion theta (deg)."""
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
    if 'elbow' in ENABLED:
        keys = elbow_deltas(method)
        for s in 'lr':
            th = _flex_angle(G, d['pos'], s)
            dl = activation_delta(th, keys)
            if dl is None: continue
            side = (d['V'][:, 0] > 0) if s == 'l' else (d['V'][:, 0] < 0)
            out = out + np.where(side[:, None], dl, 0.0)
    return out
