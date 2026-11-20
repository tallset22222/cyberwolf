"""TEST 2 (independent of the seam definitions): does the Cyberwolf skeleton deform the MakeHuman body acceptably?

Skinning is deliberately simple and FIXED (not tuned per joint): inverse-distance weights to bone segments
(core + twist), 4 influences, smoothed on the mesh, so results reflect skeleton placement and joint design, not
weight painting. Helper joints are NOT used (their drivers are not defined yet), so this is the baseline before
corrective deformation. Two blend methods are compared: linear (LBS) and dual-quaternion (DQS).

Metrics per pose, in the neighbourhood of the posed joint:
  volume ratio (signed tetra volume about the joint, posed/rest), edge strain p5/p95, folded faces (normal flip
  relative to the rigidly transformed rest normal of the face's dominant bone). Thresholds: THRESH (configurable).
"""
import json, os, sys, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from fit_skeleton import fitted
THRESH = {'vol_min': 0.85, 'vol_max': 1.10, 'strain_p95_max': 1.35, 'strain_p5_min': 0.70, 'folded_max': 0}
TWIST_CHILD = {'upperarm': 'lowerarm', 'lowerarm': 'hand', 'thigh': 'calf', 'calf': 'foot'}

_DBG = {}
PACED_RULE = {}
CAVITY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'face_cavities_hm08.json')
def _cavities(V, Q, pos, rule_set):
    """Vertices excluded from the body metrics because they line enclosed head cavities owned by the face rig.
    Frozen as an explicit list on first use (from the grid rule, minus connected patches whose centre lies more than
    90 mm below the jaw joint: those are external under-chin skin, not a cavity). Never re-derived silently."""
    import json, hashlib, collections
    import mhmesh
    sha = hashlib.sha256(open(mhmesh.WORK, 'rb').read()).hexdigest()
    if os.path.exists(CAVITY_FILE):
        d = json.load(open(CAVITY_FILE)); assert d['mesh_sha256'] == sha, 'cavity list belongs to another mesh'
        out = np.zeros(len(V), bool); out[d['body_vertex_ids']] = True; return out
    adj = collections.defaultdict(set)
    for q in Q:
        for k in range(4): adj[q[k]].add(q[(k + 1) % 4]); adj[q[(k + 1) % 4]].add(q[k])
    seen, keep, dropped = set(), np.zeros(len(V), bool), []
    for s0 in np.where(rule_set)[0]:
        if s0 in seen: continue
        st, c = [s0], []; seen.add(s0)
        while st:
            x = st.pop(); c.append(x)
            for y in adj[x]:
                if rule_set[y] and y not in seen: seen.add(y); st.append(y)
        if V[c][:, 1].mean() < pos['jaw'][1] - 0.09: dropped.append(len(c))
        else: keep[c] = True
    json.dump({'content': 'body-group vertex ids (0-based, body group order) lining enclosed head cavities: mouth, eye sockets, ear canals, nostrils; excluded from body deformation metrics, owned by the face rig',
               'mesh_sha256': sha, 'derived_from': 'test2 v2 grid rule (inside the closed head solid 4 mm both ways, above neck_01, |x| < 80 mm)',
               'dropped_patches_vertices': dropped, 'count': int(keep.sum()), 'body_vertex_ids': [int(i) for i in np.where(keep)[0]]}, open(CAVITY_FILE, 'w'))
    return keep
WEIGHTS = os.environ.get('CW_WEIGHTS', 'v2')   # 'v1' = original (asymmetric); 'v2' = mirror-exact (default); 'v3' = v2 + anatomical rules (candidate)

# ---- v3 anatomical rules: smooth ramps, applied before and after the smoothing passes (no hard cut-offs) ----
LAT_RAMP = 0.04                                   # m: opposite-side influence fades to 0 over 4 cm from the midline
THIGH_FADE_FRONT = (0.08, 0.14)                   # m above the hip joint: from the inguinal ligament's upper end (ASIS level) to just below the navel (+0.15)
THIGH_FADE_BACK = (0.10, 0.18)                    # m above the hip joint: the buttock moves with the thigh up to the iliac crest
OLECRANON = None   # dropped: v2 already gives the elbow tip 0.93 forearm; the rule only added a hard edge (see weights_v3.md)
def _smoothstep(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)
def _anatomical_rules(V, pos, bones, W):
    W = W.copy(); x = V[:, 0]
    side = np.array([1 if b.endswith('_l') else (-1 if b.endswith('_r') else 0) for b in bones])
    # 1. laterality: a side bone fades out on the opposite side of the body (midline shared equally)
    for s in (1, -1):
        opp = np.clip(-s * x / LAT_RAMP, 0, 1)                 # 0 on own side and midline, 1 beyond 3 cm on the other side
        W[:, side == s] *= (1 - _smoothstep(opp))[:, None]
    # 2. thigh boundary on the torso: front (inguinal ligament) lower than back (gluteal region)
    y0 = pos['thigh_l'][1]; z0 = pos['thigh_l'][2]
    wf = _smoothstep((V[:, 2] - z0) / 0.06 + 0.5)                # 1 = front, 0 = back
    lo = wf * THIGH_FADE_FRONT[0] + (1 - wf) * THIGH_FADE_BACK[0]; hi = wf * THIGH_FADE_FRONT[1] + (1 - wf) * THIGH_FADE_BACK[1]
    f = 1 - _smoothstep((V[:, 1] - y0 - lo) / (hi - lo))
    W[:, [i for i, b in enumerate(bones) if b.startswith('thigh')]] *= f[:, None]
    s_ = W.sum(1, keepdims=True); W = W / np.maximum(s_, 1e-15)
    return W
MIRROR = np.array([-1.0, 1, 1])
def _side_swap(n): return (n[:-2] + ('_r' if n.endswith('_l') else '_l')) if n.endswith(('_l', '_r')) else n

def build(weights=None):
    """weights 'v2' (default): mirror-exact recipe. v1 had three sources of left/right asymmetry, fixed here:
      1. voxel grid not centred on x = 0          -> voxelize(mirror_x=True)
      2. quads split along an order-dependent diagonal (mirrored quads triangulated differently)
                                                  -> centroid-fan split for voxelisation and normals
      3. midline vertices: left/right bone ties broken by bone order, then spread by smoothing
                                                  -> midline visibility made pair-symmetric; top-4 never splits a pair
      plus: fitted joints/tips symmetrised exactly (they were within 0.005 mm)."""
    weights = weights or WEIGHTS
    V, Q, joints, tips = fitted()
    pos = {j['name']: np.array(j['rest_position_m']) for j in joints}
    if weights in ('v2', 'v3'):
        sym = {}
        for n, p in pos.items():
            m = _side_swap(n)
            sym[n] = p * [0, 1, 1] if m == n else (p + pos[m] * MIRROR) / 2
        pos = sym
        tips = {n: (p * [0, 1, 1] if _side_swap(n) == n else (p + tips[_side_swap(n)] * MIRROR) / 2) for n, p in tips.items()}
    par = {j['name']: j['parent'] for j in joints}
    kids = {}
    for n, p in par.items(): kids.setdefault(p, []).append(n)
    # skinning segments: bone -> (start, end)
    seg = {}
    for n in pos:
        if n == 'root' or n.startswith('eye'): continue
        if '_twist_' in n:
            base = n.split('_twist_')[0]; side = n[-1]; ch = f'{TWIST_CHILD[base]}_{side}'
            sibs = sorted([k for k in kids[f'{base}_{side}'] if '_twist_' in k])
            i = sibs.index(n); ends = [pos[k] for k in sibs] + [pos[ch]]
            seg[n] = (pos[n], ends[i + 1]); continue
        cs = [k for k in kids.get(n, []) if '_twist_' not in k and not k.startswith(('eye', 'jaw'))]
        if n.startswith(('upperarm', 'lowerarm', 'thigh', 'calf')):
            first = sorted([k for k in kids[n] if '_twist_' in k])[0]; seg[n] = (pos[n], pos[first]); continue
        if n in tips: seg[n] = (pos[n], tips[n]); continue
        if n == 'pelvis': seg[n] = (pos['thigh_l'], pos['thigh_r']); continue      # pelvis spans the hip joints
        if n.startswith('hand'): seg[n] = (pos[n], pos[f'middle_01_{n[-1]}']); continue
        if n.startswith('foot'): seg[n] = (pos[n], pos[f'ball_{n[-1]}']); continue
        if n.startswith('clavicle'): seg[n] = (pos[n], pos[f'upperarm_{n[-1]}']); continue
        if len(cs) == 1: seg[n] = (pos[n], pos[cs[0]]); continue
        if n == 'spine_03': seg[n] = (pos[n], pos['neck_01']); continue
        seg[n] = (pos[n], pos[cs[0]])
    bones = list(seg)
    A = np.array([seg[b][0] for b in bones]); B = np.array([seg[b][1] for b in bones])
    d = B - A; L2 = np.maximum((d * d).sum(1), 1e-12)
    t = np.clip(((V[:, None, :] - A[None]) * d[None]).sum(2) / L2, 0, 1)
    C = A[None] + t[..., None] * d[None]
    D = np.linalg.norm(V[:, None, :] - C, axis=2)
    # visibility (fixed rule, same for every joint): a bone may influence a vertex only if the straight path from the
    # vertex (3 mm inside the surface) to the bone's nearest point stays inside the body (>= 7 of 8 samples)
    from voxel import voxelize, is_inside, close
    if weights in ('v2', 'v3'):
        Vx = np.vstack([V, V[Q].mean(1)]); cidx = len(V) + np.arange(len(Q))
        T = np.concatenate([np.stack([Q[:, k], Q[:, (k + 1) % 4], cidx], 1) for k in range(4)])
    else:
        Vx = V; T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    vn = np.zeros_like(Vx)
    fn = np.cross(Vx[T[:, 1]] - Vx[T[:, 0]], Vx[T[:, 2]] - Vx[T[:, 0]])
    for k in range(3): np.add.at(vn, T[:, k], fn)
    vn = vn[:len(V)]; vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    raw = voxelize(Vx, T, h=0.005, mirror_x=(weights in ('v2', 'v3')))
    vox = close(raw, iters=2)   # closes holes up to ~2 cm (eye sockets, toe and finger gaps)
    # the head is treated as solid for visibility: MakeHuman's body has an open oral cavity (~4-5 cm) that belongs to
    # the face rig, not the body skeleton. Closing radius 6 voxels (3 cm) applied above the neck joint only.
    hv = close(raw, iters=6)[0]
    ys = vox[1][1] + (np.arange(vox[0].shape[1]) + 0.5) * vox[2]
    head_rows = ys > pos['neck_01'][1] - 0.01
    filled = vox[0].copy(); filled[:, head_rows, :] |= hv[:, head_rows, :]
    vox = (filled, vox[1], vox[2])
    start = V - 0.003 * vn
    if weights in ('v2', 'v3'):   # tie-aware candidate set: every bone at or within 1e-9 m of the 6th distance (shared joint ends tie exactly)
        order = np.argsort(D, 1, kind='stable')[:, :10]; d6 = np.take_along_axis(D, order[:, 5:6], 1)
        cmask = np.take_along_axis(D, order, 1) <= d6 + 1e-9; cand = order
    else:
        cand = np.argsort(D, 1)[:, :6]; cmask = np.ones(cand.shape, bool)
    vis = np.zeros(D.shape, bool)
    ss = np.linspace(0.12, 1.0, 8)
    for kk in range(cand.shape[1]):
        b = cand[:, kk]; tgt = C[np.arange(len(V)), b]
        pts = start[:, None, :] + ss[None, :, None] * (tgt - start)[:, None, :]
        vis[np.arange(len(V)), b] = (is_inside(pts, vox).sum(1) >= 7) & cmask[:, kk]
    perm = np.array([bones.index(_side_swap(b)) for b in bones])
    midline = np.abs(V[:, 0]) < 1e-9
    if weights in ('v2', 'v3'):   # a midline vertex is its own mirror: a bone is visible iff its mirror bone is
        vis[midline] = vis[midline] | vis[midline][:, perm]
    none = ~vis.any(1); vis[none] = True     # parts thinner than the voxels (toes, lips): keep plain distance weights
    _DBG.update(D=D, vis=vis.copy(), V=V, bones=bones, perm=perm, cand=cand)
    W = np.where(vis, 1.0 / np.maximum(D, 1e-3) ** 4, 0.0)
    # smooth on the mesh graph (fixed recipe: 8 Jacobi iterations, then top-4 and normalise)
    nb = [set() for _ in range(len(V))]
    for q in Q:
        for k in range(4): nb[q[k]].update((q[(k + 1) % 4], q[(k + 3) % 4]))
    rows = np.concatenate([[i] * len(n) for i, n in enumerate(nb)]); cols = np.concatenate([list(n) for n in nb])
    W = W / W.sum(1, keepdims=True)
    if weights == 'v3': W = _anatomical_rules(V, pos, bones, W)
    for _ in range(8):
        acc = np.zeros_like(W); np.add.at(acc, rows, W[cols]); cnt = np.bincount(rows, minlength=len(V))[:, None]
        W = 0.5 * W + 0.5 * acc / cnt
    if weights == 'v3': W = _anatomical_rules(V, pos, bones, W)     # re-applied after smoothing (rules are smooth ramps)
    _DBG['Wsmooth'] = W.copy()
    if weights in ('v2', 'v3'):
        W[midline] = (W[midline] + W[midline][:, perm]) / 2          # removes floating-point residue only
    K = int(os.environ.get('CW_INFLUENCES', '4'))   # influences per vertex (4 default; 8 = Cyberpunk LOD0 practice, OI-19)
    top = np.argsort(-W, 1, kind='stable')[:, :K]; Wt = np.take_along_axis(W, top, 1)
    if weights in ('v2', 'v3'):   # never keep one bone of an exactly tied mirror pair while dropping the other (midline only)
        for v in np.where(midline)[0]:
            kept = set(top[v])
            for k in range(K):
                b = top[v, k]
                if perm[b] != b and perm[b] not in kept and np.isclose(W[v, perm[b]], W[v, b], rtol=1e-9, atol=0): Wt[v, k] = 0.0
    Wt /= Wt.sum(1, keepdims=True)
    global INTERIOR
    # mouth lining only: surface buried in the closed solid AND inside the head. (Toe and finger gaps also read as
    # 'buried' after closing; they are deliberately kept in the metrics.)
    INTERIOR = is_inside(V - 0.004 * vn, vox) & is_inside(V + 0.004 * vn, vox) & (V[:, 1] > pos['neck_01'][1]) & (np.abs(V[:, 0]) < 0.08)
    if weights in ('v2', 'v3'):   # explicit, frozen cavity list (mouth, eye sockets, ear canals, nostrils); see make_cavity_list()
        INTERIOR = _cavities(V, Q, pos, INTERIOR)
    import helpers as H
    if H.ENABLED: bones, top, Wt = H.add_weights(V, pos, bones, top, Wt, Q)
    return V, Q, pos, par, kids, bones, top, Wt

def descendants(kids, n):
    out, st = [], [n]
    while st:
        x = st.pop(); out.append(x); st += kids.get(x, [])
    return out

def rot(axis, ang):
    a = axis / np.linalg.norm(axis); c, s = math.cos(ang), math.sin(ang); x, y, z = a
    return np.array([[c + x*x*(1-c), x*y*(1-c) - z*s, x*z*(1-c) + y*s], [y*x*(1-c) + z*s, c + y*y*(1-c), y*z*(1-c) - x*s], [z*x*(1-c) - y*s, z*y*(1-c) + x*s, c + z*z*(1-c)]])

def aim_rotation(d, target):
    d = d / np.linalg.norm(d); t = target / np.linalg.norm(target); ax = np.cross(d, t)
    if np.linalg.norm(ax) < 1e-9: return np.eye(3)
    return rot(ax, math.acos(np.clip(d @ t, -1, 1)))

def toward(d, toward_dir, deg):
    ax = np.cross(d, toward_dir)
    return rot(ax, math.radians(deg))

def pose_library(pos):
    P = lambda n: pos[n]
    dirn = lambda a, b: (P(b) - P(a)) / np.linalg.norm(P(b) - P(a))
    up, fwd, lat = np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), np.array([1.0, 0, 0])
    lib = {
        'shoulder_abduct_to_horizontal': [('upperarm_l', aim_rotation(dirn('upperarm_l', 'lowerarm_l'), np.array([1, 0, 0.05])), 1.0)],
        'shoulder_abduct_overhead': [('clavicle_l', rot(fwd, math.radians(20)), 1.0), ('upperarm_l', aim_rotation(dirn('upperarm_l', 'lowerarm_l'), np.array([0.35, 1, 0.05])), 1.0)],
        'shoulder_flex_forward': [('upperarm_l', aim_rotation(dirn('upperarm_l', 'lowerarm_l'), np.array([0.25, 0, 1])), 1.0)],
        'shoulder_adduct_across_chest': [('upperarm_l', aim_rotation(dirn('upperarm_l', 'lowerarm_l'), np.array([-0.5, -0.1, 1])), 1.0)],
        'elbow_flex_90': [('lowerarm_l', toward(dirn('lowerarm_l', 'hand_l'), fwd, 90), 1.0)],
        'elbow_flex_135': [('lowerarm_l', toward(dirn('lowerarm_l', 'hand_l'), fwd, 135), 1.0)],
        'forearm_pronate_90': [('hand_l', rot(dirn('lowerarm_l', 'hand_l'), math.radians(90)), 1.0)],
        'wrist_flex_60': [('hand_l', toward(dirn('hand_l', 'middle_01_l'), -fwd, 60), 1.0)],
        'wrist_extend_60': [('hand_l', toward(dirn('hand_l', 'middle_01_l'), fwd, 60), 1.0)],
        'hip_flex_90': [('thigh_l', aim_rotation(dirn('thigh_l', 'calf_l'), np.array([0.12, 0, 1])), 1.0)],
        'hip_abduct_45': [('thigh_l', toward(dirn('thigh_l', 'calf_l'), lat, 38), 1.0)],
        'hip_extend_20': [('thigh_l', toward(dirn('thigh_l', 'calf_l'), -fwd, 20), 1.0)],
        'sit_hip90_knee90': [('thigh_l', aim_rotation(dirn('thigh_l', 'calf_l'), np.array([0.12, 0, 1])), 1.0), ('calf_l', 'KNEE90', 1.0)],
        'knee_flex_90': [('calf_l', toward(dirn('calf_l', 'foot_l'), -fwd, 90), 1.0)],
        'knee_flex_135': [('calf_l', toward(dirn('calf_l', 'foot_l'), -fwd, 135), 1.0)],
        'ankle_dorsiflex_20': [('foot_l', toward(dirn('calf_l', 'foot_l'), fwd, -20) , 1.0)],
        'ankle_plantarflex_40': [('foot_l', toward(dirn('calf_l', 'foot_l'), fwd, 40), 1.0)],
        'spine_flex_forward_45': [('spine_01', rot(lat, math.radians(15)), 1.0), ('spine_02', rot(lat, math.radians(15)), 1.0), ('spine_03', rot(lat, math.radians(15)), 1.0)],
        'spine_twist_45': [('spine_01', rot(up, math.radians(15)), 1.0), ('spine_02', rot(up, math.radians(15)), 1.0), ('spine_03', rot(up, math.radians(15)), 1.0)],
        'spine_side_bend_30': [('spine_01', rot(fwd, math.radians(10)), 1.0), ('spine_02', rot(fwd, math.radians(10)), 1.0), ('spine_03', rot(fwd, math.radians(10)), 1.0)],
        'neck_flex_40': [('neck_01', rot(lat, math.radians(20)), 1.0), ('neck_02', rot(lat, math.radians(20)), 1.0)],
        'neck_turn_70': [('neck_01', rot(up, math.radians(35)), 1.0), ('neck_02', rot(up, math.radians(35)), 1.0)],
    }
    # ---- anatomically paced shoulder variants (added for helper pass 2; the 22 stress poses above are unchanged) ----
    # Same final arm direction as each stress pose; one rule shares the motion with the shoulder girdle:
    #   clavicle elevation  = arm elevation from arm-down / 6   (about 30 deg at full overhead: the clavicle's own range)
    #   clavicle protraction = 0.2 x horizontal adduction (arm direction forward of the coronal plane), deg, weighted by the
    #                          arm's horizontal component (a vertical arm has no horizontal adduction)
    # The shoulder joint takes the rest. Limitation: the skeleton has no scapula joint, so the scapula's own upward
    # rotation (~30 deg more at full elevation) cannot be represented; the shoulder joint still carries it.
    d0 = dirn('upperarm_l', 'lowerarm_l'); dc = P('upperarm_l') - P('clavicle_l'); dc = dc / np.linalg.norm(dc)
    def final_dir(ops):
        d = d0.copy()
        for j, Rm, _ in ops:
            if j in ('clavicle_l', 'upperarm_l'): d = Rm @ d
        return d
    for name in ('shoulder_abduct_to_horizontal', 'shoulder_abduct_overhead', 'shoulder_flex_forward', 'shoulder_adduct_across_chest'):
        tgt = final_dir(lib[name]); tgt = tgt / np.linalg.norm(tgt)
        elev = math.degrees(math.acos(np.clip(tgt @ np.array([0, -1.0, 0]), -1, 1)))
        hadd = max(0.0, math.degrees(math.atan2(tgt[2], tgt[0]))) * math.hypot(tgt[0], tgt[2])   # weighted by how horizontal the arm is
        Re = toward(dc, up, elev / 6); Rp = toward(Re @ dc, fwd, 0.2 * hadd) if hadd > 0 else np.eye(3)
        lib[name + '_paced'] = [('clavicle_l', Re, 1.0), ('clavicle_l', Rp, 1.0), ('upperarm_l', aim_rotation(Rp @ Re @ d0, tgt), 1.0)]
        PACED_RULE[name + '_paced'] = {'arm_elevation_deg': round(elev, 1), 'horizontal_adduction_deg': round(hadd, 1),
                                       'clavicle_elevation_deg': round(elev / 6, 1), 'clavicle_protraction_deg': round(0.2 * hadd, 1)}
    focus = {'shoulder_abduct_to_horizontal': 'upperarm_l', 'shoulder_abduct_overhead': 'upperarm_l', 'shoulder_flex_forward': 'upperarm_l',
             'shoulder_adduct_across_chest': 'upperarm_l', 'elbow_flex_90': 'lowerarm_l', 'elbow_flex_135': 'lowerarm_l',
             'forearm_pronate_90': 'lowerarm_twist_02_l', 'wrist_flex_60': 'hand_l', 'wrist_extend_60': 'hand_l', 'hip_flex_90': 'thigh_l',
             'hip_abduct_45': 'thigh_l', 'hip_extend_20': 'thigh_l', 'sit_hip90_knee90': 'thigh_l', 'knee_flex_90': 'calf_l', 'knee_flex_135': 'calf_l',
             'ankle_dorsiflex_20': 'foot_l', 'ankle_plantarflex_40': 'foot_l', 'spine_flex_forward_45': 'spine_02', 'spine_twist_45': 'spine_02',
             'spine_side_bend_30': 'spine_02', 'neck_flex_40': 'neck_01', 'neck_turn_70': 'neck_01'}
    focus.update({n: 'upperarm_l' for n in lib if n.endswith('_paced')})
    return lib, focus

def global_transforms(pos, par, kids, ops):
    """ops: list of (joint, R, _) applied in order, each in world space about the joint's CURRENT position."""
    G = {n: np.eye(4) for n in pos}
    for j, R, _ in ops:
        if isinstance(R, str):  # KNEE90 after hip flexion: bend 90 deg towards the back of the (moved) thigh
            cur = lambda n: (G[n] @ np.append(pos[n], 1))[:3]
            dthigh = cur('calf_l') - cur('thigh_l'); dcalf = cur('foot_l') - cur('calf_l')
            back = np.cross(np.cross(dthigh, dcalf), dcalf) if np.linalg.norm(np.cross(dthigh, dcalf)) > 1e-6 else -np.array([0, 1.0, 0])
            R = rot(np.cross(dcalf, -np.array([0, 1.0, 0])), math.radians(90))
        c = (G[j] @ np.append(pos[j], 1))[:3]
        T = np.eye(4); T[:3, :3] = R; T[:3, 3] = c - R @ c
        for n in descendants(kids, j):
            if j.startswith('hand') and R is not None and '_twist_' in n: pass
            G[n] = T @ G[n]
    return G

def twist_distribute(G, pos, ops, kids):
    """Pronation: lowerarm twist joints take 1/3 and 2/3 of the hand's twist (they are children of lowerarm)."""
    for j, R, _ in ops:
        if j.startswith('hand') and not isinstance(R, str):
            s = j[-1]; ax = pos[j] - pos[f'lowerarm_{s}']
            ang = math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))
            if np.linalg.norm(np.cross(np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]), ax)) < 1e-6 * np.linalg.norm(ax) + 1e-9 and ang > 1e-3:
                for k, f in ((f'lowerarm_twist_01_{s}', 1 / 3), (f'lowerarm_twist_02_{s}', 2 / 3)):
                    Rp = rot(ax * (1 if np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) @ ax > 0 else -1), ang * f)
                    c = pos[k]; T = np.eye(4); T[:3, :3] = Rp; T[:3, 3] = c - Rp @ c
                    G[k] = G[f'lowerarm_{s}'] @ T
    import helpers as H
    if H.ENABLED: G = H.augment(G, pos)
    return G

def quat(Rm):
    t = np.trace(Rm)
    if t > 0:
        s = math.sqrt(t + 1) * 2; return np.array([0.25 * s, (Rm[2, 1] - Rm[1, 2]) / s, (Rm[0, 2] - Rm[2, 0]) / s, (Rm[1, 0] - Rm[0, 1]) / s])
    i = np.argmax(np.diag(Rm)); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + Rm[i, i] - Rm[j, j] - Rm[k, k]) * 2; q = np.zeros(4); q[0] = (Rm[k, j] - Rm[j, k]) / s; q[1 + i] = 0.25 * s
    q[1 + j] = (Rm[j, i] + Rm[i, j]) / s; q[1 + k] = (Rm[k, i] + Rm[i, k]) / s; return q

def qmul(a, b):
    w1, x1, y1, z1 = a.T; w2, x2, y2, z2 = b.T
    return np.stack([w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2], -1)

def skin(V, bones, top, Wt, G, method):
    import correctives as CR
    if CR.ENABLED: V = CR.apply(V, G, method)
    M = np.array([G[b] for b in bones])
    if method == 'LBS':
        Mv = np.einsum('vk,vkij->vij', Wt, M[top]); return np.einsum('vij,vj->vi', Mv[:, :3, :3], V) + Mv[:, :3, 3]
    qr = np.array([quat(m[:3, :3]) for m in M]); tq = np.array([np.concatenate([[0], m[:3, 3]]) for m in M]); qd = 0.5 * qmul(tq, qr)
    r = qr[top]; dd = qd[top]
    sgn = np.sign(np.einsum('vkq,vq->vk', r, r[:, 0]))[..., None]; sgn[sgn == 0] = 1
    br = (Wt[..., None] * sgn * r).sum(1); bd = (Wt[..., None] * sgn * dd).sum(1)
    n = np.linalg.norm(br, axis=1, keepdims=True); br /= n; bd /= n
    w, x, y, z = br.T
    R = np.stack([np.stack([1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)], -1), np.stack([2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)], -1), np.stack([2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)], -1)], 1)
    conj = br * np.array([1, -1, -1, -1]); t = 2 * qmul(bd, conj)[:, 1:]
    return np.einsum('vij,vj->vi', R, V) + t

def metrics(V, Vp, Q, pos, G, focus, bones, top, Wt):
    c = pos[focus]; reg = (np.linalg.norm(V - c, axis=1) < 0.13) & ~INTERIOR
    tri = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]); tri = tri[reg[tri].all(1)]
    cp = (G[focus] @ np.append(c, 1))[:3]
    vol = lambda X, cc: np.einsum('ij,ij->i', X[tri[:, 0]] - cc, np.cross(X[tri[:, 1]] - cc, X[tri[:, 2]] - cc)).sum() / 6
    v0, v1 = vol(V, c), vol(Vp, cp)
    E = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    strain = np.linalg.norm(Vp[E[:, 0]] - Vp[E[:, 1]], axis=1) / np.maximum(np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1), 1e-9)
    n0 = np.cross(V[tri[:, 1]] - V[tri[:, 0]], V[tri[:, 2]] - V[tri[:, 0]]); n1 = np.cross(Vp[tri[:, 1]] - Vp[tri[:, 0]], Vp[tri[:, 2]] - Vp[tri[:, 0]])
    dom = top[tri[:, 0], 0]; Rdom = np.array([G[bones[b]][:3, :3] for b in dom])
    folded = int((np.einsum('ij,ij->i', np.einsum('ijk,ik->ij', Rdom, n0), n1) < 0).sum())
    return {'volume_ratio': round(float(v1 / v0), 3), 'strain_p5': round(float(np.percentile(strain, 5)), 3),
            'strain_p95': round(float(np.percentile(strain, 95)), 3), 'folded_faces': folded, 'region_faces': int(len(tri))}

def grade(m):
    bad = []
    if not THRESH['vol_min'] <= m['volume_ratio'] <= THRESH['vol_max']: bad.append('volume')
    if m['strain_p95'] > THRESH['strain_p95_max']: bad.append('stretch')
    if m['strain_p5'] < THRESH['strain_p5_min']: bad.append('compression')
    if m['folded_faces'] > THRESH['folded_max']: bad.append('folding')
    return 'OK' if not bad else 'WARN: ' + ','.join(bad)

if __name__ == '__main__':
    V, Q, pos, par, kids, bones, top, Wt = build()
    lib, focus = pose_library(pos)
    res, posed = {}, {}
    for name, ops in lib.items():
        G = twist_distribute(global_transforms(pos, par, kids, ops), pos, ops, kids)
        res[name] = {}
        for m in ('LBS', 'DQS'):
            Vp = skin(V, bones, top, Wt, G, m); posed[(name, m)] = Vp
            r = metrics(V, Vp, Q, pos, G, focus[name], bones, top, Wt); r['grade'] = grade(r); res[name][m] = r
        print('%-30s LBS vol %.2f s95 %.2f s5 %.2f fold %3d %-28s | DQS vol %.2f s95 %.2f s5 %.2f fold %3d %s' % (
            name, *[res[name]['LBS'][k] for k in ('volume_ratio', 'strain_p95', 'strain_p5', 'folded_faces', 'grade')],
            *[res[name]['DQS'][k] for k in ('volume_ratio', 'strain_p95', 'strain_p5', 'folded_faces', 'grade')]))
    print('head-cavity vertices (mouth, eye sockets, ear canals, nostrils; excluded from metrics; owned by the future face rig):', int(INTERIOR.sum()), 'centre', V[INTERIOR].mean(0).round(3) if INTERIOR.any() else None)
    json.dump({'test': 'skeleton fitting and deformation', 'head_cavity_vertices_excluded': int(INTERIOR.sum()), 'thresholds': THRESH, 'skinning': 'inverse-distance^4 to core+twist segments, restricted to bones visible through the body interior (voxel 5 mm, holes up to ~2 cm closed, head treated as solid (oral cavity); vertices with no visible bone keep plain distance weights), 8 smoothing iterations, 4 influences; helpers unused',
               'results': res}, open(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), 'test2_deformation.json'), 'w'), indent=1)
    np.savez_compressed(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), '_test2_posed.npz'), V=V, Q=Q, **{f'{n}__{m}': v for (n, m), v in posed.items()})
