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
KEY = CR.keys_of(JNAME)[0]
MODE = os.environ.get('CW_OI20_MODE', 'share')   # share: joint takes part of the weight (extra slot); replace: joint takes the parent's whole slot
NT = {'upperarm': 2, 'lowerarm': 2, 'thigh': 2, 'calf': 1}
group = lambda b: [b] + [f"{b[:-2]}_twist_0{k}_l" for k in range(1, NT[b[:-2]] + 1)]
UP, LO = group(Pn), group(Mn)
Wd = np.zeros((len(V), len(bones))); np.add.at(Wd, (np.repeat(np.arange(len(V)), top.shape[1]), top.ravel()), Wt.ravel())
mi = CR._C['mirror']; MIR = np.diag([-1.0, 1, 1])

def G_at(angle, s='l'):
    ops = CR.joint_pose(JNAME, angle, s); return T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
def activation(theta):
    if theta <= CR.START: return 0.0
    t = min(1.0, (theta - CR.START) / (KEY - CR.START)); return t * t * (3 - 2 * t)
def slerpR(R, a):
    ang = math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if ang < 1e-12: return np.eye(3)
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]); ax /= np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + math.sin(a * ang) * K + (1 - math.cos(a * ang)) * K @ K

def fit(method, n_per_side, iters=40):
    delta = CR.deltas(JNAME, method)[0][0]          # fill the cache first: building it resets the authoring flag
    G = G_at(KEY); CR._C['authoring'] = True
    X0 = T2.skin(V, bones, top, Wt, G, method)
    assert CR._C['authoring']
    Xt = T2.skin(V + delta, bones, top, Wt, G, method)
    CR._C['authoring'] = False
    D = Xt - X0; patch = (np.linalg.norm(D, axis=1) > 5e-5) & (V[:, 0] > 0)
    # side of each patch vertex (rest anatomy, as in authoring) and the bone that gives up weight
    f0 = pos[En] - pos[Mn]; f0 /= np.linalg.norm(f0); u0 = pos[Pn] - pos[Mn]; u0 /= np.linalg.norm(u0)
    ax = (f0 - u0) / np.linalg.norm(f0 - u0); srest = (V - pos[Mn]) @ ax
    joints = []
    for side_name, grp, sel in (('prox', UP, patch & (srest <= 0)), ('dist', LO, patch & (srest > 0))):
        idx = np.where(sel)[0]
        if len(idx) == 0: continue
        gi = [bones.index(b) for b in grp]; own = np.array(gi)[np.argmax(Wd[np.ix_(idx, gi)], 1)]
        v = V[idx]; Dv = D[idx]
        # init: k-means on rest positions; each joint is parented to the bone that dominates its cluster and takes
        # weight only from that bone (so in poses that don't bend the joint the vertex follows exactly the same bone)
        cen = v[np.linspace(0, len(v) - 1, n_per_side).astype(int)].copy()
        for _ in range(20):
            lab = np.argmin(np.linalg.norm(v[:, None] - cen[None], axis=2), 1)
            cen = np.array([v[lab == k].mean(0) if (lab == k).any() else cen[k] for k in range(n_per_side)])
        par = [int(np.bincount(own[lab == k], minlength=len(bones)).argmax()) if (lab == k).any() else int(own[0]) for k in range(n_per_side)]
        avail = [Wd[idx, p] for p in par]
        dl = [(G[bones[p]][:3, :3].T @ Dv.T).T for p in par]
        Rs = [np.eye(3)] * n_per_side; ts = [np.zeros(3)] * n_per_side
        asg = lab.copy(); a = np.array([avail[asg[i]][i] for i in range(len(v))])
        if MODE == 'replace': a = a.copy()
        for it in range(iters):
            for k in range(n_per_side):
                m = (asg == k) & (a > 1e-4)
                if m.sum() < 3: continue
                w = a[m] ** 2; o = cen[k]; src = v[m] - o; dst = v[m] + dl[k][m] / a[m][:, None] - o
                ms, md = (w[:, None] * src).sum(0) / w.sum(), (w[:, None] * dst).sum(0) / w.sum()
                H = ((src - ms) * w[:, None]).T @ (dst - md); U, S_, Vt = np.linalg.svd(H); dd = np.sign(np.linalg.det(Vt.T @ U.T))
                R = Vt.T @ np.diag([1, 1, dd]) @ U.T; Rs[k] = R; ts[k] = md - R @ ms
            best = np.linalg.norm(Dv, axis=1).copy(); asg_new = np.full(len(v), -1); a_new = np.zeros(len(v))
            for k in range(n_per_side):
                u = (v - cen[k]) @ (Rs[k] - np.eye(3)).T + ts[k]
                if MODE == 'replace': ak = avail[k].copy()          # whole slot: no extra influence
                else: ak = np.clip((u * dl[k]).sum(1) / np.maximum((u * u).sum(1), 1e-18), 0, avail[k])
                err = np.linalg.norm(ak[:, None] * u - dl[k], axis=1)
                bet = (err < best - 1e-12) & (ak > 0); best[bet] = err[bet]; asg_new[bet] = k; a_new[bet] = ak[bet]
            if it < iters - 1:   # keep unassigned vertices in their cluster for the next transform step
                keep = asg_new < 0; asg_new[keep] = asg[keep]; a_new[keep] = np.array([avail[asg[i]][i] for i in np.where(keep)[0]]) if MODE=='replace' else 0.0
            asg, a = asg_new, a_new
        for k in range(n_per_side):
            m = asg == k
            joints.append(dict(name=f'crj_{JNAME}_{side_name}{k}_l', parent=bones[par[k]], o=cen[k], R=Rs[k], t=ts[k],
                               verts=idx[m], give=np.full(int(m.sum()), par[k]), share=a[m]))
    return joints, D, patch

MIDKEYS = [float(x) for x in os.environ.get('CW_OI20_MIDKEYS', '').split(',') if x]
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
            R = Vt.T @ np.diag([1, 1, dd]) @ U.T; J['keys'].append((ang, R, md - R @ ms))

def offset_at(J, th):
    """Piecewise interpolation I -> mid keys -> key, parametrised by the offline activation curve."""
    a = activation(th); pts = [(0.0, np.eye(3), np.zeros(3))] + [(activation(k), R, t) for k, R, t in J.get('keys', [])] + [(1.0, J['R'], J['t'])]
    for (a0, R0, t0), (a1, R1, t1) in zip(pts, pts[1:]):
        if a <= a1 + 1e-12:
            u = 0.0 if a1 - a0 < 1e-12 else (a - a0) / (a1 - a0)
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

def evaluate(method, joints, budget, sweep=(0, 15, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 105, 120, 135)):
    names, tp, Wt2, over = build(joints, budget)
    M = M2.Metric2(V, Q, T2.INTERIOR); res = {'influence_overflow_vertices': over, 'sweep': {}}
    patch_any = np.zeros(len(V), bool)
    for J in joints: patch_any[J['verts']] = True; patch_any[mi[J['verts']]] = True
    for th in sweep:
        G = G_at(th); Ge = G_ext(G, joints, CR.flex_angle(G, pos, JNAME, 'l'), CR.flex_angle(G, pos, JNAME, 'r'))
        X_off = T2.skin(V, bones, top, Wt, G, method)                     # offline corrective (CR enabled)
        CR._C['authoring'] = True
        X_base = T2.skin(V, bones, top, Wt, G, method); X_j = T2.skin(V, names, tp, Wt2, Ge, method)
        CR._C['authoring'] = False
        e = np.linalg.norm(X_j - X_off, axis=1) * 1000; corr = np.linalg.norm(X_off - X_base, axis=1) > 1e-6
        area = np.zeros(len(V), bool); area[np.where((np.linalg.norm(V - pos[Mn], axis=1) < 0.25))[0]] = True
        r = {'max_err_mm': round(float(e[area].max()), 2), 'p95_err_mm': round(float(np.percentile(e[corr | patch_any], 95)), 2) if (corr | patch_any).any() else 0.0,
             'mean_err_mm': round(float(e[corr | patch_any].mean()), 2) if (corr | patch_any).any() else 0.0,
             'max_move_outside_patch_mm': round(float((np.linalg.norm(X_j - X_base, axis=1) * 1000)[~patch_any & area].max()), 3),
             'offline_correction_max_mm': round(float(np.linalg.norm(X_off - X_base, axis=1).max() * 1000), 1)}
        if th in (0,): r['rest_exact_mm'] = float(np.abs(X_j - V).max() * 1000)
        if th in (60, 90, 135):
            for lab, X in (('joint', X_j), ('offline', X_off)):
                ev = M.measure(X, pos[Mn]); r[lab] = {k: ev[k] for k in ('intersection_vertices', 'pinch_length_mm', 'fold_over_edges')}
        res['sweep'][th] = r
    # right side check: mirrored pose
    G = G_at(KEY, 'r'); Ge = G_ext(G, joints, CR.flex_angle(G, pos, JNAME, 'l'), CR.flex_angle(G, pos, JNAME, 'r'))
    CR._C['authoring'] = True; Xr = T2.skin(V, names, tp, Wt2, Ge, method)
    Gl = G_at(KEY); Gle = G_ext(Gl, joints, CR.flex_angle(Gl, pos, JNAME, 'l'), CR.flex_angle(Gl, pos, JNAME, 'r')); Xl = T2.skin(V, names, tp, Wt2, Gle, method)
    CR._C['authoring'] = False
    res['mirror_error_mm'] = float(np.abs(Xr[mi] * [-1, 1, 1] - Xl).max() * 1000)
    # poses that don't bend the joint: compare against the uncorrected v3 result (budget trimming may change them)
    lib, _ = T2.pose_library(pos); worst = (0.0, '')
    for p, ops in lib.items():
        if p.startswith(('elbow', 'knee')): continue
        G = T2.twist_distribute(T2.global_transforms(pos, d['par'], d['kids'], ops), pos, ops, d['kids'])
        if CR.flex_angle(G, pos, JNAME, 'l') > CR.START or CR.flex_angle(G, pos, JNAME, 'r') > CR.START: continue
        Ge = G_ext(G, joints, 0.0, 0.0); CR._C['authoring'] = True
        dlt = np.abs(T2.skin(V, names, tp, Wt2, Ge, method) - T2.skin(V, bones, top, Wt, G, method)).max() * 1000; CR._C['authoring'] = False
        if dlt > worst[0]: worst = (float(dlt), p)
    res['other_poses_max_change_mm'] = {'value': round(worst[0], 3), 'pose': worst[1]}
    return res

if __name__ == '__main__':
    out = {}; method = os.environ.get('CW_METHOD', 'LBS'); budgets = [int(b) for b in os.environ.get('CW_BUDGETS', '4,8').split(',')]
    for n in [int(x) for x in os.environ.get('CW_NJ', '1,2,3').split(',')]:
        joints, D, patch = fit(method, n); fit_midkeys(joints, method)
        for budget in budgets:
            r = evaluate(method, joints, budget); r['joints_per_arm'] = 2 * n; r['mode'] = MODE; r['midkeys'] = MIDKEYS
            r['joints'] = [{'name': J['name'], 'parent': J['parent'], 'vertices': int(len(J['verts'])), 'rot_deg': round(math.degrees(math.acos(np.clip((np.trace(J['R']) - 1) / 2, -1, 1))), 2),
                            't_mm': round(float(np.linalg.norm(J['t']) * 1000), 2)} for J in joints]
            out[f'{method}_{MODE}_n{n}_k{budget}'] = r; s_ = r['sweep']
            band = max(s_[a]['max_err_mm'] for a in range(35, 90, 5))
            print(f"{method} {MODE} mid{MIDKEYS} joints/arm {2*n} budget {budget}: overflow {r['influence_overflow_vertices']:4d} | @90 mean/p95/max {s_[90]['mean_err_mm']}/{s_[90]['p95_err_mm']}/{s_[90]['max_err_mm']} | 35-85 max {band} | @135 max {s_[135]['max_err_mm']} | rest {s_[0]['rest_exact_mm']:.2g} | outside {max(v['max_move_outside_patch_mm'] for v in s_.values())} | mirror {r['mirror_error_mm']:.2g} | other poses {r['other_poses_max_change_mm']} | @90 joint {s_[90]['joint']} offline {s_[90]['offline']}", flush=True)
    json.dump(out, open(os.path.join(HERE, 'reports', 'correctives', f'oi20_{JNAME}_{method}_{MODE}' + ('_mk' + '-'.join(str(int(k)) for k in MIDKEYS) if MIDKEYS else '') + '.json'), 'w'), indent=1)
