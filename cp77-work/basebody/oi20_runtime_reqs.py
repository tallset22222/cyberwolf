"""OI-20 runtime requirements of the two knee candidates (approved 17 Nov 2026; technical scope only).
Candidates (unchanged, refitted deterministically): DQS + 8 rigid joints/leg; LBS + 6 scaled joints/leg.
  A. Interpolation tolerance: error vs the offline prototype when the runtime interpolates differently from the fit.
  B. Influence budget: exact influence counts per vertex with the corrective joints; exact data and arithmetic cost.
  C. Scale feasibility (LBS): one fixed scale frame per joint across keys; normals under non-uniform scale.
Usage: CW_CAND=DQS|LBS python3 oi20_runtime_reqs.py  -> reports/correctives/oi20_knee_runtime_<cand>.json"""
import os, sys, json, math, numpy as np
CAND = os.environ.get('CW_CAND', 'DQS')
os.environ.update(CW_JOINT='knee', CW_OI20_JOINTFIT='1', CW_OI20_MODE='share', CW_OI20_XFORM='rigid' if CAND == 'DQS' else 'scaled')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import oi20_joints as O
METHOD, N = ('DQS', 4) if CAND == 'DQS' else ('LBS', 3)
V, pos, T2, CR = O.V, O.pos, O.T2, O.CR
joints, _, _ = O.fit(METHOD, N); O.fit_midkeys(joints, METHOD); names, tp, Wt2, over = O.build(joints, 8)
area = (np.linalg.norm(V - pos['calf_l'], axis=1) < 0.25) & (V[:, 0] > 0)
SWEEP = list(range(0, 151, 5)); out = {'candidate': f'{METHOD} {len(joints)} joints/leg ({os.environ["CW_OI20_XFORM"]})'}
_fitted_offset, _fitted_act = O.offset_at, O.activation

def sweep_err(metric_at=(110, 135)):
    worst, rest = 0.0, 0.0; per = {}
    M = O.M2.Metric2(V, O.Q, T2.INTERIOR) if metric_at else None
    for th in SWEEP:
        G = O.G_at(th); Ge = O.G_ext(G, joints, CR.flex_angle(G, pos, 'knee', 'l'), CR.flex_angle(G, pos, 'knee', 'r'))
        X_off = T2.skin(V, O.bones, O.top, O.Wt, G, METHOD); CR._C['authoring'] = True
        X_j = T2.skin(V, names, tp, Wt2, Ge, METHOD); CR._C['authoring'] = False
        e = float(np.linalg.norm(X_j - X_off, axis=1)[area].max() * 1000); per[th] = round(e, 2)
        if th <= CR.START: rest = max(rest, e)
        worst = max(worst, e)
        if th in metric_at:
            ev = M.measure(X_j, pos['calf_l']); per[f'{th}_intersections_folds'] = [ev['intersection_vertices'], ev['fold_over_edges']]
    return {'max_err_mm': round(worst, 2), 'max_err_at_or_below_30deg_mm': round(rest, 4), 'per_angle': per}

# ---------- A. interpolation variants ----------
def quat(R):
    w = math.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2; x = math.copysign(math.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0]); z = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    return np.array([w, x, y, z])
def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)], [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)], [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]])
def polar(A):
    U, s, Vt = np.linalg.svd(A); return U @ Vt, Vt.T @ np.diag(s) @ Vt
def key_list(J):   # (angle, rotation, stretch, translation) including rest at START
    ks = [(CR.START, np.eye(3), np.eye(3), np.zeros(3))]
    for ang, A, t in J.get('keys', []) + [(O.KEY, J['R'], J['t'])]:
        R, S = polar(A); ks.append((ang, R, S, t))
    return ks
def blend(ks, wts, rot):
    """weighted blend of key transforms: rot = 'nlerp' (normalised quaternion sum) or 'matrix' (component-wise)"""
    if rot == 'matrix': A = sum(w * (R @ S) for w, (_, R, S, _) in zip(wts, ks))
    else:
        q0 = quat(ks[0][1]); qs = [quat(R) for _, R, _, _ in ks]; qs = [q if q @ q0 >= 0 else -q for q in qs]
        A = qmat(sum(w * q for w, q in zip(wts, qs))) @ sum(w * S for w, (_, _, S, _) in zip(wts, ks))
    return A, sum(w * t for w, (_, _, _, t) in zip(wts, ks))
def piecewise_weights(ks, th, act):
    a = act(th); pa = [act(k[0]) for k in ks]; w = np.zeros(len(ks))
    if a <= pa[0]: w[0] = 1; return w
    for i in range(len(ks) - 1):
        if a <= pa[i + 1] + 1e-12:
            u = (a - pa[i]) / max(pa[i + 1] - pa[i], 1e-12); w[i], w[i + 1] = 1 - u, u; return w
    w[-1] = 1; return w
def make_offset(kind, p=2.0):
    def off(J, th):
        ks = key_list(J)
        if kind == 'fitted': return _fitted_offset(J, th)
        if kind == 'linear_activation':
            lin = lambda t: 0.0 if t <= CR.START else (min(1.0, (t - CR.START) / (O.KEYS[0] - CR.START)) if t <= O.KEYS[0] else _fitted_act(t))
            return blend(ks, piecewise_weights(ks, th, lin), 'nlerp')
        if kind == 'nlerp': return blend(ks, piecewise_weights(ks, th, _fitted_act), 'nlerp')
        if kind == 'matrix_lerp': return blend(ks, piecewise_weights(ks, th, _fitted_act), 'matrix')
        if kind.startswith('rbf'):
            # RBF-style: inverse-distance weights over the key angles (rest key at 0 AND at START, both identity), normalised
            allk = [(0.0, np.eye(3), np.eye(3), np.zeros(3))] + ks; d = np.array([abs(th - k[0]) for k in allk])
            if d.min() < 1e-9: w = (d < 1e-9).astype(float)
            else: w = 1 / d ** p
            return blend(allk, w / w.sum(), 'nlerp')
    return off
out['interpolation'] = {}
for kind, p in (('fitted', 0), ('nlerp', 0), ('matrix_lerp', 0), ('linear_activation', 0), ('rbf', 1.0), ('rbf', 2.0), ('rbf', 4.0)):
    O.offset_at = make_offset(kind, p); key = kind if kind != 'rbf' else f'rbf_inverse_distance_p{p:g}'
    out['interpolation'][key] = sweep_err(); print(key, {k: v for k, v in out['interpolation'][key].items() if k != 'per_angle'}, flush=True)
O.offset_at = _fitted_offset

# ---------- B. influence budget and cost ----------
Wx = np.zeros((len(V), len(O.bones) + 2 * len(joints))); Wx[:, :len(O.bones)] = O.Wd
for j_i, J in enumerate(joints):
    for vv, gb, sh in zip(J['verts'], J['give'], J['share']):
        Wx[vv, gb] -= sh; Wx[vv, len(O.bones) + 2 * j_i] += sh
        gr = O.bones.index(O.bones[gb][:-2] + '_r'); vr = O.mi[vv]; Wx[vr, gr] -= sh; Wx[vr, len(O.bones) + 2 * j_i + 1] += sh
nz = (Wx > 1e-12).sum(1); base_nz = (O.Wd > 1e-12).sum(1)
out['influences'] = {'vertices_total': int(len(V)), 'histogram_with_correctives': {int(k): int((nz == k).sum()) for k in range(1, nz.max() + 1)},
    'vertices_over_4': int((nz > 4).sum()), 'vertices_over_8': int((nz > 8).sum()), 'max_influences': int(nz.max()),
    'vertices_gaining_an_influence': int((nz > base_nz).sum()),
    'note': 'v3 base weights are top-4 (CW_INFLUENCES=4); every vertex that receives a corrective joint goes over 4'}
nv8 = int((nz > 4).sum())
out['cost_exact'] = {
    'extra_joints_both_legs': 2 * len(joints),
    'vertex_data_per_vertex_bytes': {'4_influences': 8, '8_influences': 16, 'note': 'UByte4 indices + UByte4N weights per set of 4'},
    'extra_vertex_bytes_if_only_vertices_over_4_carry_8': nv8 * 8,
    'extra_vertex_bytes_if_whole_mesh_carries_8': int(len(V)) * 8,
    'skinning_multiply_adds_per_vertex': {
        'LBS': {'4': 4 * 12 + 9 + 9, '8': 8 * 12 + 9 + 9, 'formula': '12 per influence to blend a 3x4 matrix + 9 position + 9 normal'},
        'DQS': {'4': 4 * 8 + 30, '8': 8 * 8 + 30, 'formula': '8 per influence to blend a dual quaternion + ~30 normalise and apply (approx.)'}},
    'per_frame_joint_work': f'{2 * len(joints)} corrective joints: one key interpolation (slerp + lerp) and one 4x4 multiply each',
    'not_measured': 'GPU/CPU time: depends on the runtime, which does not exist yet'}
print('influences', out['influences'], flush=True)

# ---------- C. scale (LBS candidate) and normals ----------
if CAND == 'LBS':
    fr = []
    for J in joints:
        Ss = [polar(A)[1] for _, A, _ in J.get('keys', [])] + [polar(J['R'])[1]]
        w, Qf = np.linalg.eigh(Ss[-1])                     # deepest key's stretch frame = the joint's fixed scale frame
        mis = [float(np.linalg.norm(Qf.T @ S @ Qf - np.diag(np.diag(Qf.T @ S @ Qf))) / np.linalg.norm(S - np.eye(3)) if np.linalg.norm(S - np.eye(3)) > 1e-9 else 0) for S in Ss]
        fr.append({'joint': J['name'], 'scale_at_keys': [np.round(np.linalg.eigvalsh(S), 3).tolist() for S in Ss], 'off_frame_fraction_per_key': [round(m, 3) for m in mis]})
    out['scale_frames'] = fr
    # constrained: every key's stretch re-expressed as axis-aligned scale in the deepest key's frame
    saved = [(J['R'], J['t'], list(J.get('keys', []))) for J in joints]
    for J in joints:
        Qf = np.linalg.eigh(polar(J['R'])[1])[1]
        def fix(A, Qf=Qf):
            R, S = polar(A); return R @ (Qf @ np.diag(np.diag(Qf.T @ S @ Qf)) @ Qf.T)
        J['R'] = fix(J['R']); J['keys'] = [(a, fix(A), t) for a, A, t in J.get('keys', [])]
    out['fixed_scale_frame'] = sweep_err(); print('fixed_scale_frame', {k: v for k, v in out['fixed_scale_frame'].items() if k != 'per_angle'}, flush=True)
    for J, (R, t, k) in zip(joints, saved): J['R'], J['t'], J['keys'] = R, t, k
    # normals: plain blended 3x3 vs inverse-transpose
    fn = np.cross(V[O.Q[:, 1]] - V[O.Q[:, 0]], V[O.Q[:, 2]] - V[O.Q[:, 0]]) + np.cross(V[O.Q[:, 3]] - V[O.Q[:, 2]], V[O.Q[:, 0]] - V[O.Q[:, 2]])
    vn = np.zeros_like(V); [np.add.at(vn, O.Q[:, k], fn) for k in range(4)]; vn /= np.linalg.norm(vn, axis=1, keepdims=True)
    nres = {}
    for th in (90, 135):
        G = O.G_at(th); Ge = O.G_ext(G, joints, CR.flex_angle(G, pos, 'knee', 'l'), CR.flex_angle(G, pos, 'knee', 'r'))
        def blended(names_, tp_, W_, GG):
            Mx = np.array([GG[b] for b in names_]); return np.einsum('vk,vkij->vij', W_, Mx[tp_])[:, :3, :3]
        for lab, Mv in (('with_corrective_joints', blended(names, tp, Wt2, Ge)), ('base_weights_only', blended(O.bones, O.top, O.Wt, G))):
            a = np.einsum('vij,vj->vi', Mv, vn); b = np.einsum('vji,vj->vi', np.linalg.inv(Mv), vn)
            a /= np.linalg.norm(a, axis=1, keepdims=True); b /= np.linalg.norm(b, axis=1, keepdims=True)
            ang = np.degrees(np.arccos(np.clip((a * b).sum(1), -1, 1)))[area]
            nres[f'{th}_{lab}'] = {'max_deg': round(float(ang.max()), 2), 'p95_deg': round(float(np.percentile(ang, 95)), 2)}
    out['normals_plain_vs_inverse_transpose'] = nres; print('normals', nres, flush=True)
json.dump(out, open(os.path.join(HERE, 'reports', 'correctives', f'oi20_knee_runtime_{CAND}.json'), 'w'), indent=1)
