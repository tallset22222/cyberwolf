"""OI-20 stage 2: reproduce an offline corrective shape with corrective joints (REDengine's native mechanism is joint-based:
animAnimNode_ApplyCorrectivePoseRBF / SetDrivenKey). The offline shape stays the reference target.

Model. A corrective joint c rests at the centre o_c of a skin patch, parented to bone P_c (upper arm or forearm side),
with a local rigid offset L_c = (R_c about o_c, t_c), identity at rest. A patch vertex hands a share a_i of its weight
on its own side to one corrective joint, so at the key pose it moves by a_i * M_P (L_c - I) v (LBS). Offsets and shares
are fitted alternately (weighted Kabsch / clipped least squares) to the offline shape's posed displacement at the key
pose, separately per skinning method. Off the key the offset is interpolated with the same activation as the offline
shape (rotation slerp, translation linear); the engine's RBF curve is a separate open item.
Influence budget: corrective joints compete for the per-vertex limit; extra influences are trimmed to the budget
(smallest dropped, renormalised) and the cost is measured, including on poses that don't bend the joint."""
import os, sys, json, math, numpy as np
os.environ.setdefault('CW_WEIGHTS', 'v3')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['CW_CORRECTIVES'] = os.environ.get('CW_JOINT', 'elbow')
import correctives as CR, metrics2 as M2
JNAME = os.environ['CW_CORRECTIVES']; d = CR._data(); T2 = d['T2']
V, Q, pos, bones, top, Wt = d['V'], d['Q'], d['pos'], d['bones'], d['top'], d['Wt']
JS = CR.JOINTS[JNAME]; Pn, Mn, En = (f"{JS[k]}_l" for k in ('parent', 'mid', 'end'))
KEYS = CR.keys_of(JNAME); KEY = KEYS[-1]          # structure (clusters, shares) fitted at the deepest key
MODE = os.environ.get('CW_OI20_MODE', 'share')   # share: joint takes part of the weight (extra slot); replace: joint takes the parent's whole slot
NT = {'upperarm': 2, 'lowerarm': 2, 'thigh': 2, 'calf': 1}
group = lambda b: [b] + [f"{b[:-2]}_twist_0{k}_l" for k in range(1, NT[b[:-2]] + 1)]
UP, LO = group(Pn), group(Mn)
Wd = np.zeros((len(V), len(bones))); np.add.at(Wd, (np.repeat(np.arange(len(V)), top.shape[1]), top.ravel()), Wt.ravel())
mi = CR._C['mirror']; MIR = np.diag([-1.0, 1, 1])

def G_at(angle, s='l'):
    ops = CR.joint_pose(JNAME, angle, s); return T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
def activation(theta):
    """Offline activation parameter: 0 at START, smoothstep to 1 at the first key, then k (k = 1..) at later keys,
    linear in angle between them; held beyond the last key."""
    if theta <= CR.START: return 0.0
    if theta <= KEYS[0]:
        t = (theta - CR.START) / (KEYS[0] - CR.START); return t * t * (3 - 2 * t)
    for i in range(len(KEYS) - 1):
        if theta <= KEYS[i + 1]: return 1.0 + i + (theta - KEYS[i]) / (KEYS[i + 1] - KEYS[i])
    return float(len(KEYS))
def slerpR(R, a):
    ang = math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if ang < 1e-12: return np.eye(3)
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]); ax /= np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + math.sin(a * ang) * K + (1 - math.cos(a * ang)) * K @ K

JOINTFIT = os.environ.get('CW_OI20_JOINTFIT', '0') == '1'   # 1: shares fitted to ALL keys at once (one offset per key)

XFORM = os.environ.get('CW_OI20_XFORM', 'rigid')   # rigid: rotation + translation; scaled: + non-uniform scale (LBS only)

def _kabsch(v, a, dl, o):
    w = a ** 2; src = v - o; dst = v + dl / a[:, None] - o
    ms, md = (w[:, None] * src).sum(0) / w.sum(), (w[:, None] * dst).sum(0) / w.sum()
    if XFORM == 'scaled':
        # weighted least-squares linear map, kept to positive determinant and scale within [0.7, 1.4] per axis; a joint
        # with a suitable bind orientation realises R*S (rotation + non-uniform scale in its own frame) under LBS
        Sx = ((src - ms) * w[:, None]).T @ (src - ms); Sxy = ((src - ms) * w[:, None]).T @ (dst - md)
        A = np.linalg.solve(Sx + 1e-9 * np.eye(3), Sxy).T
        U, sv, Vt = np.linalg.svd(A); R = U @ Vt
        if np.linalg.det(R) < 0: U[:, -1] *= -1; R = U @ Vt
        A = R @ (Vt.T @ np.diag(np.clip(sv, 0.7, 1.4)) @ Vt)
        return A, md - A @ ms
    H = ((src - ms) * w[:, None]).T @ (dst - md); U, S_, Vt = np.linalg.svd(H); dd = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, dd]) @ U.T; return R, md - R @ ms

def fit(method, n_per_side, iters=40):
    dlts = CR.deltas(JNAME, method)                 # fill the cache first: building it resets the authoring flag
    fitkeys = list(KEYS) if JOINTFIT else [KEY]
    Gs, Ds = {}, {}
    for ang in fitkeys:
        G = G_at(ang); CR._C['authoring'] = True
        X0 = T2.skin(V, bones, top, Wt, G, method); assert CR._C['authoring']
        Xt = T2.skin(V + dlts[KEYS.index(ang)][0], bones, top, Wt, G, method)   # the key's full shape at its own angle
        CR._C['authoring'] = False
        Gs[ang], Ds[ang] = G, Xt - X0
    D = Ds[KEY]; patch = np.zeros(len(V), bool)
    for ang in fitkeys: patch |= np.linalg.norm(Ds[ang], axis=1) > 5e-5
    patch &= V[:, 0] > 0
    # side of each patch vertex (rest anatomy, as in authoring) and the bone that gives up weight
    f0 = pos[En] - pos[Mn]; f0 /= np.linalg.norm(f0); u0 = pos[Pn] - pos[Mn]; u0 /= np.linalg.norm(u0)
    ax = (f0 - u0) / np.linalg.norm(f0 - u0); srest = (V - pos[Mn]) @ ax
    joints = []
    for side_name, grp, sel in (('prox', UP, patch & (srest <= 0)), ('dist', LO, patch & (srest > 0))):
        idx = np.where(sel)[0]
        if len(idx) == 0: continue
        gi = [bones.index(b) for b in grp]; own = np.array(gi)[np.argmax(Wd[np.ix_(idx, gi)], 1)]
        v = V[idx]
        # init: k-means on rest positions; each joint is parented to the bone that dominates its cluster and takes
        # weight only from that bone (so in poses that don't bend the joint the vertex follows exactly the same bone)
        cen = v[np.linspace(0, len(v) - 1, n_per_side).astype(int)].copy()
        for _ in range(20):
            lab = np.argmin(np.linalg.norm(v[:, None] - cen[None], axis=2), 1)
            cen = np.array([v[lab == k].mean(0) if (lab == k).any() else cen[k] for k in range(n_per_side)])
        par = [int(np.bincount(own[lab == k], minlength=len(bones)).argmax()) if (lab == k).any() else int(own[0]) for k in range(n_per_side)]
        avail = [Wd[idx, p] for p in par]
        dl = [{ang: (Gs[ang][bones[p]][:3, :3].T @ Ds[ang][idx].T).T for ang in fitkeys} for p in par]   # per joint, per key
        RT = [{ang: (np.eye(3), np.zeros(3)) for ang in fitkeys} for _ in range(n_per_side)]
        asg = lab.copy(); a = np.array([avail[asg[i]][i] for i in range(len(v))])
        base_err = np.sqrt(sum((np.linalg.norm(Ds[ang][idx], axis=1) ** 2) for ang in fitkeys))
        for it in range(iters):
            for k in range(n_per_side):
                m = (asg == k) & (a > 1e-4)
                if m.sum() < 3: continue
                for ang in fitkeys: RT[k][ang] = _kabsch(v[m], a[m], dl[k][ang][m], cen[k])
            best = base_err.copy(); asg_new = np.full(len(v), -1); a_new = np.zeros(len(v))
            for k in range(n_per_side):
                us = {ang: (v - cen[k]) @ (RT[k][ang][0] - np.eye(3)).T + RT[k][ang][1] for ang in fitkeys}
                if MODE == 'replace': ak = avail[k].copy()          # whole slot: no extra influence
                else:
                    num = sum((us[g] * dl[k][g]).sum(1) for g in fitkeys); den = sum((us[g] * us[g]).sum(1) for g in fitkeys)
                    ak = np.clip(num / np.maximum(den, 1e-18), 0, avail[k])
                err = np.sqrt(sum(np.linalg.norm(ak[:, None] * us[g] - dl[k][g], axis=1) ** 2 for g in fitkeys))
                bet = (err < best - 1e-12) & (ak > 0); best[bet] = err[bet]; asg_new[bet] = k; a_new[bet] = ak[bet]
            if it < iters - 1:   # keep unassigned vertices in their cluster for the next transform step
                keep = asg_new < 0; asg_new[keep] = asg[keep]; a_new[keep] = np.array([avail[asg[i]][i] for i in np.where(keep)[0]]) if MODE=='replace' else 0.0
            asg, a = asg_new, a_new
        for k in range(n_per_side):
            m = asg == k
            joints.append(dict(name=f'crj_{JNAME}_{side_name}{k}_l', parent=bones[par[k]], o=cen[k], R=RT[k][KEY][0], t=RT[k][KEY][1],
                               verts=idx[m], give=np.full(int(m.sum()), par[k]), share=a[m]))
    return joints, D, patch

MIDKEYS = sorted(set([float(x) for x in os.environ.get('CW_OI20_MIDKEYS', '').split(',') if x] + list(KEYS[:-1])))
def fit_midkeys(joints, method):
    """Same joints and weights; one extra offset per intermediate key, fitted to the offline shape at that angle."""
    for J in joints: J['keys'] = []
    for ang in MIDKEYS:
        G = G_at(ang); X_off = T2.skin(V, bones, top, Wt, G, method)
        CR._C['authoring'] = True; X_b = T2.skin(V, bones, top, Wt, G, method); CR._C['authoring'] = False
        D = X_off - X_b
        for J in joints:
            m = J['share'] > 1e-4
            if m.sum() < 3: J['keys'].append((ang, np.eye(3), np.zeros(3))); continue
            v = V[J['verts']][m]; a = J['share'][m]; dl = (G[J['parent']][:3, :3].T @ D[J['verts']][m].T).T
            w = a ** 2; o = J['o']; src = v - o; dst = v + dl / a[:, None] - o
            ms, md = (w[:, None] * src).sum(0) / w.sum(), (w[:, None] * dst).sum(0) / w.sum()
            H = ((src - ms) * w[:, None]).T @ (dst - md); U, S_, Vt = np.linalg.svd(H); dd = np.sign(np.linalg.det(Vt.T @ U.T))
            R, t = _kabsch(v, a, dl, o); J['keys'].append((ang, R, t))

def offset_at(J, th):
    """Piecewise interpolation I -> mid keys -> key, parametrised by the offline activation curve."""
    a = activation(th); pts = [(0.0, np.eye(3), np.zeros(3))] + [(activation(k), R, t) for k, R, t in J.get('keys', [])] + [(activation(KEY), J['R'], J['t'])]
    for (a0, R0, t0), (a1, R1, t1) in zip(pts, pts[1:]):
        if a <= a1 + 1e-12:
            u = 0.0 if a1 - a0 < 1e-12 else (a - a0) / (a1 - a0)
            if XFORM == 'scaled':        # polar split: rotation slerped, stretch blended linearly
                def polar(A):
                    U_, s_, Vt_ = np.linalg.svd(A); return U_ @ Vt_, Vt_.T @ np.diag(s_) @ Vt_
                P0, S0 = polar(R0); P1, S1 = polar(R1)
                return P0 @ slerpR(P0.T @ P1, u) @ ((1 - u) * S0 + u * S1), (1 - u) * t0 + u * t1
            return R0 @ slerpR(R0.T @ R1, u), (1 - u) * t0 + u * t1
    return J['R'], J['t']

def build(joints, budget):
    """Extended bone list and weights (left + mirrored right), trimmed to the influence budget."""
    names = list(bones); Wx = np.zeros((len(V), len(bones) + 2 * len(joints))); Wx[:, :len(bones)] = Wd
    for j_i, J in enumerate(joints):
        cl, cr = len(bones) + 2 * j_i, len(bones) + 2 * j_i + 1
        names += [J['name'], J['name'][:-2] + '_r']
        for vv, gb, sh in zip(J['verts'], J['give'], J['share']):
            Wx[vv, gb] -= sh; Wx[vv, cl] += sh
            gr = bones.index(bones[gb][:-2] + '_r'); vr = mi[vv]; Wx[vr, gr] -= sh; Wx[vr, cr] += sh
    nz = (Wx > 1e-12).sum(1)
    over = int((nz > budget).sum())
    tp = np.argsort(-Wx, 1, kind='stable')[:, :budget]; Wt2 = np.take_along_axis(Wx, tp, 1); Wt2 /= Wt2.sum(1, keepdims=True)
    return names, tp, Wt2, over

def G_ext(G, joints, theta_l, theta_r):
    G = dict(G)
    for J in joints:
        for s, th in (('l', theta_l), ('r', theta_r)):
            Ra, ta = offset_at(J, th); o = J['o']
            if s == 'r': Ra, ta, o = MIR @ Ra @ MIR, MIR @ ta, MIR @ o
            L = np.eye(4); L[:3, :3] = Ra; L[:3, 3] = o + ta - Ra @ o
            P = J['parent'] if s == 'l' else J['parent'][:-2] + '_r'
            G[J['name'][:-2] + '_' + s] = G[P] @ L
    return G

# umbrella Laplacian (surface roughness) on the quad mesh, for the bump check
_nb = [set() for _ in range(len(V))]
for q in Q:
    for k in range(4): _nb[q[k]].update((q[(k + 1) % 4], q[(k + 3) % 4]))
_nbr = np.array([i for i, n in enumerate(_nb) for _ in n]); _nbc = np.array([j for n in _nb for j in n]); _deg = np.array([len(n) for n in _nb], float)
def lap(X):
    m = np.zeros_like(X); np.add.at(m, _nbr, X[_nbc]); return m / np.maximum(_deg, 1)[:, None] - X

SWEEP = tuple(range(0, 30, 15)) + tuple(range(30, 151, 5))
METRIC_AT = (60, 90, 110, 135)

def evaluate(method, joints, budget, sweep=SWEEP):
    names, tp, Wt2, over = build(joints, budget)
    M = M2.Metric2(V, Q, T2.INTERIOR); res = {'influence_overflow_vertices': over, 'sides': {}}
    patch = {'l': np.zeros(len(V), bool), 'r': np.zeros(len(V), bool)}
    for J in joints: patch['l'][J['verts']] = True; patch['r'][mi[J['verts']]] = True
    area = np.linalg.norm(V - pos[Mn], axis=1) < 0.25; area_r = np.linalg.norm(V - pos[Mn[:-2] + '_r'], axis=1) < 0.25
    for s in 'lr':                                       # each side bent ALONE; the other leg stays at rest
        o = 'r' if s == 'l' else 'l'; ar = area if s == 'l' else area_r; side = (V[:, 0] > 0) if s == 'l' else (V[:, 0] < 0)
        out = {}
        for th in sweep:
            G = G_at(th, s); Ge = G_ext(G, joints, CR.flex_angle(G, pos, JNAME, 'l'), CR.flex_angle(G, pos, JNAME, 'r'))
            X_off = T2.skin(V, bones, top, Wt, G, method)
            CR._C['authoring'] = True
            X_base = T2.skin(V, bones, top, Wt, G, method); X_j = T2.skin(V, names, tp, Wt2, Ge, method)
            CR._C['authoring'] = False
            e = np.linalg.norm(X_j - X_off, axis=1) * 1000; corr = (np.linalg.norm(X_off - X_base, axis=1) > 1e-6) | patch[s]
            bump = (np.linalg.norm(lap(X_j), axis=1) - np.linalg.norm(lap(X_off), axis=1)) * 1000
            r = {'max_err_mm': round(float(e[ar].max()), 2), 'p95_err_mm': round(float(np.percentile(e[corr], 95)), 2) if corr.any() else 0.0,
                 'mean_err_mm': round(float(e[corr].mean()), 2) if corr.any() else 0.0,
                 'offline_correction_max_mm': round(float(np.linalg.norm(X_off - X_base, axis=1).max() * 1000), 1),
                 'max_move_outside_patch_mm': round(float((np.linalg.norm(X_j - X_base, axis=1) * 1000)[~patch[s] & ar].max()), 3),
                 'other_leg_change_mm': round(float((np.linalg.norm(X_j - X_base, axis=1) * 1000)[~side].max()), 4),
                 'bump_vs_offline_mm': round(float(bump[ar].max()), 3)}
            if th == 0: r['rest_exact_mm'] = float(np.abs(X_j - V).max() * 1000)
            if th in METRIC_AT:
                for lab, X in (('joint', X_j), ('offline', X_off), ('baseline', X_base)):
                    ev = M.measure(X, pos[Mn[:-2] + '_' + s]); r[lab] = {k: ev[k] for k in ('intersection_vertices', 'pinch_length_mm', 'fold_over_edges')}
            out[th] = r
        res['sides'][s] = out
    # left vs right: the right sweep must mirror the left sweep
    G = G_at(KEY, 'r'); Ge = G_ext(G, joints, CR.flex_angle(G, pos, JNAME, 'l'), CR.flex_angle(G, pos, JNAME, 'r'))
    CR._C['authoring'] = True; Xr = T2.skin(V, names, tp, Wt2, Ge, method)
    Gl = G_at(KEY); Gle = G_ext(Gl, joints, CR.flex_angle(Gl, pos, JNAME, 'l'), CR.flex_angle(Gl, pos, JNAME, 'r')); Xl = T2.skin(V, names, tp, Wt2, Gle, method)
    CR._C['authoring'] = False
    res['mirror_error_mm'] = float(np.abs(Xr[mi] * [-1, 1, 1] - Xl).max() * 1000)
    # the whole 22-pose library: inactive poses must be unchanged; poses that bend the joint are compared with the prototype
    lib, _ = T2.pose_library(pos); worst = (0.0, ''); active = {}
    for p, ops in lib.items():
        G = T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
        fl, fr = CR.flex_angle(G, pos, JNAME, 'l'), CR.flex_angle(G, pos, JNAME, 'r'); Ge = G_ext(G, joints, fl, fr)
        X_off = T2.skin(V, bones, top, Wt, G, method)
        CR._C['authoring'] = True; X_j = T2.skin(V, names, tp, Wt2, Ge, method); X_b = T2.skin(V, bones, top, Wt, G, method); CR._C['authoring'] = False
        if fl > CR.START or fr > CR.START:
            ev_j, ev_o = M.measure(X_j, pos[Mn]), M.measure(X_off, pos[Mn])
            active[p] = {'flex_deg': [round(fl, 1), round(fr, 1)], 'max_err_mm': round(float(np.linalg.norm(X_j - X_off, axis=1).max() * 1000), 2),
                         'intersections_joint_vs_offline': [ev_j['intersection_vertices'], ev_o['intersection_vertices']]}
        else:
            dlt = float(np.abs(X_j - X_b).max() * 1000)
            if dlt > worst[0]: worst = (dlt, p)
    res['other_poses_max_change_mm'] = {'value': round(worst[0], 4), 'pose': worst[1]}; res['library_active_poses'] = active
    return res

if __name__ == '__main__':
    out = {}; method = os.environ.get('CW_METHOD', 'LBS'); budgets = [int(b) for b in os.environ.get('CW_BUDGETS', '4,8').split(',')]
    for n in [int(x) for x in os.environ.get('CW_NJ', '1,2,3').split(',')]:
        joints, D, patch = fit(method, n); fit_midkeys(joints, method)
        for budget in budgets:
            r = evaluate(method, joints, budget); r['joints_per_limb'] = 2 * n; r['mode'] = MODE; r['keys'] = list(KEYS); r['midkeys'] = MIDKEYS
            r['joints'] = [{'name': J['name'], 'parent': J['parent'], 'vertices': int(len(J['verts'])), 'rot_deg': round(math.degrees(math.acos(np.clip((np.trace(np.linalg.svd(J['R'])[0] @ np.linalg.svd(J['R'])[2]) - 1) / 2, -1, 1))), 2), 'scale': [round(float(x), 3) for x in np.linalg.svd(J['R'])[1]],
                            't_mm': round(float(np.linalg.norm(J['t']) * 1000), 2)} for J in joints]
            tag = f'{method}_{MODE}_n{n}_k{budget}'; out[tag] = r
            for sd, S in r['sides'].items():
                band = max(S[a]['max_err_mm'] for a in S if 35 <= a <= 85); band2 = max(S[a]['max_err_mm'] for a in S if 95 <= a <= 130)
                print(f"{tag} side {sd}: overflow {r['influence_overflow_vertices']} | max err @90 {S[90]['max_err_mm']} @135 {S[135]['max_err_mm']} @150 {S[150]['max_err_mm']} | 35-85 {band} | 95-130 {band2} | bump max {max(v['bump_vs_offline_mm'] for v in S.values())} | rest {S[0]['rest_exact_mm']:.2g} | outside {max(v['max_move_outside_patch_mm'] for v in S.values())} | other leg {max(v['other_leg_change_mm'] for v in S.values())} | X@90 j/o/b {S[90]['joint']['intersection_vertices']}/{S[90]['offline']['intersection_vertices']}/{S[90]['baseline']['intersection_vertices']} X@135 {S[135]['joint']['intersection_vertices']}/{S[135]['offline']['intersection_vertices']}/{S[135]['baseline']['intersection_vertices']}", flush=True)
            print(f"{tag}: mirror {r['mirror_error_mm']:.2g} | inactive poses {r['other_poses_max_change_mm']} | active poses {r['library_active_poses']}", flush=True)
    json.dump(out, open(os.path.join(HERE, 'reports', 'correctives', f'oi20_{JNAME}_{method}_{MODE}' + ('_mk' + '-'.join(str(int(k)) for k in MIDKEYS) if MIDKEYS else '') + ('_jf' if JOINTFIT else '') + ('_scaled' if XFORM == 'scaled' else '') + '_nj' + os.environ.get('CW_NJ', '1,2,3').replace(',', '-') + '_b' + os.environ.get('CW_BUDGETS', '4,8').replace(',', '-') + '.json'), 'w'), indent=1)

def error_map(method, n, budget=8, angles=(90, 135)):
    """Where the residual sits: error per vertex vs the offline prototype, split front/back of the knee and by region."""
    joints, D, patch = fit(method, n); fit_midkeys(joints, method); names, tp, Wt2, over = build(joints, budget)
    f0 = pos[En] - pos[Mn]; f0 /= np.linalg.norm(f0); u0 = pos[Pn] - pos[Mn]; u0 /= np.linalg.norm(u0)
    ax = (f0 + u0); ax /= np.linalg.norm(ax)            # points into the flexion crease (back of the knee)
    out = {}
    for th in angles:
        G = G_at(th); Ge = G_ext(G, joints, CR.flex_angle(G, pos, JNAME, 'l'), CR.flex_angle(G, pos, JNAME, 'r'))
        X_off = T2.skin(V, bones, top, Wt, G, method); CR._C['authoring'] = True
        X_b = T2.skin(V, bones, top, Wt, G, method); X_j = T2.skin(V, names, tp, Wt2, Ge, method); CR._C['authoring'] = False
        e = np.linalg.norm(X_j - X_off, axis=1) * 1000; c = np.linalg.norm(X_off - X_b, axis=1) * 1000
        near = (np.linalg.norm(V - pos[Mn], axis=1) < 0.25) & (V[:, 0] > 0); back = ((V - pos[Mn]) @ ax) > 0
        out[th] = {'front': {'max_err': round(float(e[near & ~back].max()), 2), 'max_correction': round(float(c[near & ~back].max()), 1)},
                   'back': {'max_err': round(float(e[near & back].max()), 2), 'max_correction': round(float(c[near & back].max()), 1)},
                   'n_vertices_err_over_1mm': int((e[near] > 1).sum()), 'n_vertices_corrected_over_1mm': int((c[near] > 1).sum())}
    return out
