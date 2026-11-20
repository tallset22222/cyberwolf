"""Helper-joint layer (standard v0.2 part 1, 'helper' layer): procedural drivers + skin-weight transfer.
Isolated by design: enabled only with CW_HELPERS=1. With it off, test 2/3 reproduce the v2 (no-helper) results exactly.
Core joints, sockets, seams, regions and poses are untouched.

Driver (one rule for every helper; nothing is tuned per pose):
  partial rotation: R_h = R_parent * slerp(I, R_parent^-1 R_child, FRACTION), pivoting about the core joint between
  parent and child. The helper's spec rest position is its frame/influence label only; the pivot is the core joint.
Weights (one rule for every helper):
  at a joint with parent-side bone set P and child-side set C, a vertex carrying a = sum w(P) and b = sum w(C)
  transfers h = STRENGTH * 2 * min(a, b) to the helper, taken half from each side in proportion to the weights there.
  A vertex fully on one side (min = 0) is unchanged. Then top-4 and renormalise, as in the base recipe."""
import os, math, numpy as np
MODE = os.environ.get('CW_HELPERS', '0')      # '0' off (v2 baseline), '1' pass 1 (half-angle bands), '2' pass 2 (anatomical landmarks)
ENABLED = MODE in ('1', '2')
FRACTION = float(os.environ.get('CW_HELPER_FRACTION', '0.5'))
STRENGTH = float(os.environ.get('CW_HELPER_STRENGTH', '1.0'))
FRONT_BACK_RAMP = 0.04          # m: hip/glute split blends over +-2 cm about the hip joint's z

def defs(side):
    s = side
    NT = {'upperarm': 2, 'lowerarm': 2, 'thigh': 2, 'calf': 1}     # twist joints per segment (skeleton v0.2)
    tw = lambda b: [b] + [f"{b[:-2]}_twist_0{k}_{s}" for k in range(1, NT[b[:-2]] + 1)]
    return [
        {'name': f'hlp_shoulder_{s}', 'parent': f'clavicle_{s}', 'child': f'upperarm_{s}',
         'P': [f'clavicle_{s}', 'spine_03', 'spine_02'], 'C': tw(f'upperarm_{s}')},
        {'name': f'hlp_elbow_{s}', 'parent': f'upperarm_{s}', 'child': f'lowerarm_{s}', 'P': tw(f'upperarm_{s}'), 'C': tw(f'lowerarm_{s}')},
        {'name': f'hlp_wrist_{s}', 'parent': f'lowerarm_{s}', 'child': f'hand_{s}', 'P': tw(f'lowerarm_{s}'), 'C': [f'hand_{s}']},
        {'name': f'hlp_hip_{s}', 'parent': 'pelvis', 'child': f'thigh_{s}', 'P': ['pelvis', 'spine_01'], 'C': tw(f'thigh_{s}'), 'part': 'front'},
        {'name': f'hlp_glute_{s}', 'parent': 'pelvis', 'child': f'thigh_{s}', 'P': ['pelvis', 'spine_01'], 'C': tw(f'thigh_{s}'), 'part': 'back'},
        {'name': f'hlp_knee_{s}', 'parent': f'thigh_{s}', 'child': f'calf_{s}', 'P': tw(f'thigh_{s}'), 'C': tw(f'calf_{s}')},
    ]
HELPERS = defs('l') + defs('r')

def add_weights(V, pos, bones, top, Wt, Q=None):
    """Return (bones', top', Wt') with helper influences added (pass 1 transfer rule, or pass 2 landmark patches)."""
    if MODE == '2': return p2_add_weights(V, Q, pos, bones, top, Wt)
    B = len(bones); names = list(bones) + [h['name'] for h in HELPERS]
    W = np.zeros((len(V), len(names))); np.add.at(W, (np.repeat(np.arange(len(V)), top.shape[1]), top.ravel()), Wt.ravel())
    idx = {n: i for i, n in enumerate(names)}
    W0 = W.copy(); take = np.zeros_like(W)       # all helpers read the same snapshot W0: order-independent, so L/R symmetric
    for h in HELPERS:
        missing = [b for b in h['P'] + h['C'] if b not in idx]; assert not missing, (h['name'], missing)
        Pi = [idx[b] for b in h['P']]; Ci = [idx[b] for b in h['C']]
        a = W0[:, Pi].sum(1); b = W0[:, Ci].sum(1)
        hw = STRENGTH * 2 * np.minimum(a, b)
        if 'part' in h:   # hip (front) / glute (back) share one joint: split the transferred weight by z
            f = np.clip((V[:, 2] - pos[h['child']][2]) / FRONT_BACK_RAMP + 0.5, 0, 1)
            hw = hw * (f if h['part'] == 'front' else 1 - f)
        with np.errstate(invalid='ignore', divide='ignore'):
            fa = np.where(a > 0, (hw / 2) / a, 0); fb = np.where(b > 0, (hw / 2) / b, 0)
        take[:, Pi] += W0[:, Pi] * fa[:, None]; take[:, Ci] += W0[:, Ci] * fb[:, None]
        W[:, idx[h['name']]] += hw
    # a bone shared by both sides' helpers (spine, pelvis) can be asked for more than it has: scale the helpers'
    # requests on such vertices down uniformly (symmetric), so no weight goes negative and the total stays 1
    over = np.where(take > W0 + 1e-15, W0 / np.maximum(take, 1e-30), 1.0).min(1)
    W[:, :B] = W0[:, :B] - take[:, :B] * over[:, None]; W[:, B:] *= over[:, None]
    W = np.maximum(W, 0)
    sw = lambda n: (n[:-2] + ('_r' if n.endswith('_l') else '_l')) if n.endswith(('_l', '_r')) else n
    perm = np.array([idx[sw(n)] for n in names]); mid = np.abs(V[:, 0]) < 1e-9
    W[mid] = (W[mid] + W[mid][:, perm]) / 2
    top2 = np.argsort(-W, 1, kind='stable')[:, :4]; Wt2 = np.take_along_axis(W, top2, 1)
    for v in np.where(mid)[0]:   # same rule as the base weights: never keep one bone of an exactly tied mirror pair
        kept = set(top2[v])
        for k in range(4):
            bb = top2[v, k]
            if perm[bb] != bb and perm[bb] not in kept and np.isclose(W[v, perm[bb]], W[v, bb], rtol=1e-9, atol=0): Wt2[v, k] = 0.0
    Wt2 /= Wt2.sum(1, keepdims=True)
    return names, top2, Wt2

def _slerp_identity(Rm, f):
    ang = math.acos(np.clip((np.trace(Rm) - 1) / 2, -1, 1))
    if ang < 1e-9: return np.eye(3)
    ax = np.array([Rm[2, 1] - Rm[1, 2], Rm[0, 2] - Rm[2, 0], Rm[1, 0] - Rm[0, 1]])
    if np.linalg.norm(ax) < 1e-9:   # 180 deg: axis from the symmetric part
        w, v = np.linalg.eigh((Rm + np.eye(3)) / 2); ax = v[:, -1]
    ax /= np.linalg.norm(ax); a = ang * f; K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K

def augment(G, pos):
    """Add helper global transforms to G (rest-relative 4x4 skinning matrices, as the rest of the pipeline uses)."""
    if MODE == '2': return p2_augment(G, pos)
    for h in HELPERS:
        Gp, Gc = G[h['parent']], G[h['child']]
        Rrel = Gp[:3, :3].T @ Gc[:3, :3]
        R = Gp[:3, :3] @ _slerp_identity(Rrel, FRACTION)
        pivot0 = pos[h['child']]; pivot = (Gc @ np.append(pivot0, 1))[:3]
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = pivot - R @ pivot0
        G[h['name']] = M
    return G


# ======================= pass 2: anatomical landmark helpers (CW_HELPERS=2) =======================
# Each helper owns a skin patch centred on its anatomical landmark (spec rest position on the fitted body, projected to
# the skin along the landmark's anatomical direction: front for hip crease and patella, back for olecranon and glute,
# up for the deltoid). Weight: (1 + cos(pi d / R)) / 2 inside radius R (rest distance), taken from the
# existing influences in proportion. Base motion: rotation about the core joint by an anatomical FRACTION of the joint's
# rotation (which bone the tissue belongs to). Muscle helpers add a volume-conserving thickness change
# t = T0 * (sqrt(L0 / L) - 1) along the landmark's outward normal, L = origin-insertion distance of the muscle
# (origin on the parent bone, insertion on the child bone). Every driver is exactly zero at rest (L = L0, angle 0).
# Constants are anatomical (sizes, thickness, which bone the tissue rides on); none was fitted to the test poses.
P2 = {   # name: parent, child (joint), fraction, patch radius R m, muscle (origin, insertion, thickness m) or None
    'hlp_shoulder': dict(surface_dir=[0.0, 1.0, 0.0], parent='clavicle', child='upperarm', fraction=0.5, target=None, R=0.08, offset=lambda J, x: J['upperarm'] + [0.01 * x, 0.03, 0.0],
                         muscle=dict(origin=lambda J, x: J['upperarm'] + [0.0, 0.03, 0.0], origin_bone='clavicle',
                                     insertion=lambda J, x: J['upperarm'] + 0.45 * (J['lowerarm'] - J['upperarm']), insertion_bone='upperarm', T0=0.020),
                         note='deltoid: spans girdle and humerus (0.5); thickness 20 mm'),
    'hlp_elbow':    dict(surface_dir=[0.0, 0.0, -1.0], parent='upperarm', child='lowerarm', fraction=1.0, target=1.0, R=0.045, offset=lambda J, x: J['lowerarm'] + [0.0, 0.0, -0.035], muscle=None,
                         note='olecranon: bony point of the ulna, moves with the forearm (1.0)'),
    'hlp_knee':     dict(surface_dir=[0.0, 0.0, 1.0], parent='thigh', child='calf', fraction=0.5, target=0.5, R=0.05, offset=lambda J, x: J['calf'] + [0.0, 0.0, 0.05], muscle=None,
                         note='patella: tracks the femoral groove at about half the knee angle (0.5)'),
    'hlp_hip':      dict(surface_dir=[0.0, 0.0, 1.0], parent='pelvis', child='thigh', fraction=0.5, target=0.0, R=0.06, offset=lambda J, x: J['thigh'] + [0.02 * x, 0.0, 0.05], muscle=None,
                         note='front hip crease: between pelvis and thigh (0.5)'),
    'hlp_glute':    dict(surface_dir=[0.0, 0.0, -1.0], parent='pelvis', child='thigh', fraction=0.25, target=None, R=0.08, offset=lambda J, x: J['thigh'] + [0.0, -0.03, -0.09],
                         muscle=dict(origin=lambda J, x: J['pelvis'] + [0.05 * x, 0.06, -0.10], origin_bone='pelvis',
                                     insertion=lambda J, x: J['thigh'] + 0.12 * (J['calf'] - J['thigh']) + [0.0, 0.0, -0.02], insertion_bone='thigh', T0=0.030),
                         note='gluteus maximus: bulk mostly on the pelvis (0.25); thickness 30 mm'),
}
_P2_CACHE = {}

def _side_name(n, s): return n if n == 'pelvis' else f'{n}_{s}'

def p2_setup(V, pos):
    """Landmarks (snapped to skin), normals and muscle rest lengths for both sides."""
    if _P2_CACHE.get('nV') == len(V): return _P2_CACHE['H']
    scale = 1.0   # spec offsets are in metres for the 1.75 m reference; hm08 is 1.667 m: offsets are small (<= 9 cm), used as-is
    H = []
    for s, x in (('l', 1.0), ('r', -1.0)):
        J = {k: pos[_side_name(k, s)] for k in ('clavicle', 'upperarm', 'lowerarm', 'thigh', 'calf')}; J['pelvis'] = pos['pelvis']
        for base, d in P2.items():
            target = np.asarray(d['offset'](J, x), float); u = np.array(d['surface_dir'], float)
            # snap along the anatomical direction: the skin vertex closest to the ray target + t*u (t > 0)
            rel = V - target; t = rel @ u; perp = np.linalg.norm(rel - np.outer(t, u), axis=1)
            vi = int(np.argmin(np.where(t > 0, perp + 0.05 * t, np.inf)))
            h = dict(name=f'{base}_{s}', parent=_side_name(d['parent'], s), child=_side_name(d['child'], s), fraction=d['fraction'], R=d['R'], target=d['target'],
                     landmark=V[vi].copy(), landmark_vertex=vi, snap_mm=float(np.linalg.norm(V[vi] - target) * 1000))
            if d['muscle']:
                m = d['muscle']; O = np.asarray(m['origin'](J, x), float); I = np.asarray(m['insertion'](J, x), float)
                h['muscle'] = dict(O=O, I=I, ob=_side_name(m['origin_bone'], s), ib=_side_name(m['insertion_bone'], s), L0=float(np.linalg.norm(I - O)), T0=m['T0'])
            H.append(h)
    _P2_CACHE.update(nV=len(V), H=H)
    return H

def p2_add_weights(V, Q, pos, bones, top, Wt):
    H = p2_setup(V, pos)
    # landmark outward normals
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]]); vn = np.zeros_like(V)
    for k in range(4): np.add.at(vn, Q[:, k], n)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-15
    for h in H: h['normal'] = vn[h['landmark_vertex']].copy()
    names = list(bones) + [h['name'] for h in H]; B = len(bones)
    W = np.zeros((len(V), len(names))); np.add.at(W, (np.repeat(np.arange(len(V)), top.shape[1]), top.ravel()), Wt.ravel())
    # pass 2b: base fraction = the local blend at the landmark (patch-weighted child-side share), so the patch moves like
    # the skin around it; the anatomical correction is applied on top in p2_augment
    NT = {'upperarm': 2, 'lowerarm': 2, 'thigh': 2, 'calf': 1}
    def side_set(b):
        base = b[:-2] if b.endswith(('_l', '_r')) else b
        out = [b] + ([f"{base}_twist_0{k}_{b[-1]}" for k in range(1, NT[base] + 1)] if base in NT else [])
        return [bones.index(x) for x in out if x in bones]
    PARENT_EXTRA = {'clavicle': ['spine_03', 'spine_02'], 'pelvis': ['spine_01']}
    for h in H:
        pb = h['parent'][:-2] if h['parent'].endswith(('_l', '_r')) else h['parent']
        Pi = side_set(h['parent']) + [bones.index(x) for x in PARENT_EXTRA.get(pb, [])]; Ci = side_set(h['child'])
        d = np.linalg.norm(V - h['landmark'], axis=1); wpatch = np.where(d < h['R'], 0.5 * (1 + np.cos(np.pi * d / h['R'])), 0.0)
        a = W[:, Pi].sum(1); b = W[:, Ci].sum(1); m = (a + b) > 1e-9
        h['fraction'] = float((wpatch[m] * (b[m] / (a[m] + b[m]))).sum() / max(wpatch[m].sum(), 1e-12))
    hw = np.zeros((len(V), len(H)))
    for i, h in enumerate(H):
        d = np.linalg.norm(V - h['landmark'], axis=1)
        hw[:, i] = np.where(d < h['R'], 0.5 * (1 + np.cos(np.pi * d / h['R'])), 0.0)
    tot = hw.sum(1); sc = np.where(tot > 1, 1 / np.maximum(tot, 1e-15), 1.0); hw *= sc[:, None]; tot = hw.sum(1)
    W[:, :B] *= (1 - tot)[:, None]; W[:, B:] = hw
    idx = {nm: i for i, nm in enumerate(names)}
    sw = lambda nm: (nm[:-2] + ('_r' if nm.endswith('_l') else '_l')) if nm.endswith(('_l', '_r')) else nm
    perm = np.array([idx[sw(nm)] for nm in names]); mid = np.abs(V[:, 0]) < 1e-9
    W[mid] = (W[mid] + W[mid][:, perm]) / 2
    top2 = np.argsort(-W, 1, kind='stable')[:, :4]; Wt2 = np.take_along_axis(W, top2, 1)
    for v in np.where(mid)[0]:
        kept = set(top2[v])
        for k in range(4):
            bb = top2[v, k]
            if perm[bb] != bb and perm[bb] not in kept and np.isclose(W[v, perm[bb]], W[v, bb], rtol=1e-9, atol=0): Wt2[v, k] = 0.0
    Wt2 /= Wt2.sum(1, keepdims=True)
    return names, top2, Wt2

def p2_augment(G, pos):
    H = _P2_CACHE['H']
    for h in H:
        Gp, Gc = G[h['parent']], G[h['child']]
        R = Gp[:3, :3] @ _slerp_identity(Gp[:3, :3].T @ Gc[:3, :3], h['fraction'])
        pivot0 = pos[h['child']]; pivot = (Gc @ np.append(pivot0, 1))[:3]
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = pivot - R @ pivot0
        if h.get('target') is not None:   # bony/anchored landmark: put it where its anatomical fraction puts it
            Rt = Gp[:3, :3] @ _slerp_identity(Gp[:3, :3].T @ Gc[:3, :3], h['target'])
            Lt = pivot + Rt @ (h['landmark'] - pivot0); Lb = M[:3, :3] @ h['landmark'] + M[:3, 3]
            M[:3, 3] += Lt - Lb
        if 'muscle' in h:
            m = h['muscle']; O = (G[m['ob']] @ np.append(m['O'], 1))[:3]; I = (G[m['ib']] @ np.append(m['I'], 1))[:3]
            L = float(np.linalg.norm(I - O)); t = m['T0'] * (np.sqrt(m['L0'] / L) - 1.0)
            M[:3, 3] += t * (R @ h['normal'])
            h['last_thickness_change_mm'] = t * 1000
        G[h['name']] = M
    return G
