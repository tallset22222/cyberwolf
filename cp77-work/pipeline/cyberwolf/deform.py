"""Procedural deformation graphs (.animgraph): reference-pose construction and per-node evaluation.

Every node handler documents its rule as a hypothesis. Unknown engine defaults live in DEFAULTS and are
reported, never hidden. Evaluation runs in model space (the graphs convert LS->MS at the start and MS->LS at
the end); a write to one transform does not move its children until MS->LS (hypothesis H_MS, recorded).
"""
import numpy as np
from .rig import Rig, trs_matrix
from .gltf import mat_to_trs
from .animgraph import AnimGraph

DEFAULTS = {  # value used when CR2W omits a field; status 'inferred' means chosen from data, see report
    'aim.forwardAxisLS': (1.0, 0.0, 0.0),
    'aim.upAxisLS': (0.0, 1.0, 0.0),
    'spline.defaultProgress': 0.5,
    'twist.positiveScale': 1.0,
    'twist.negativeScale': 1.0,
}


def tq(x):
    t, q = x['Translation'], x['Rotation']
    s = x.get('Scale', {})
    return trs_matrix((t.get('X', 0), t.get('Y', 0), t.get('Z', 0)), (q.get('i', 0), q.get('j', 0), q.get('k', 0), q.get('r', 1)),
                      (s.get('X', 1), s.get('Y', 1), s.get('Z', 1)))


class Pose:
    """Model-space pose over rig bones plus virtual transforms added by StackTransformsExtender."""

    def __init__(self, rig):
        self.parent, self.ref_local, self.ms, self.origin = {}, {}, {}, {}
        ms = rig.model_space('ref')
        for i, n in enumerate(rig.names):
            self.parent[n] = rig.names[rig.parents[i]] if rig.parents[i] >= 0 else None
            self.ref_local[n] = rig.ref_local[i]
            self.ms[n] = ms[i].copy()
            self.origin[n] = 'rig'
        self.ref_ms = {k: v.copy() for k, v in self.ms.items()}

    def extend(self, infos, tag):
        missing = []
        for t in infos:
            n, p = t['name'], t.get('parentName')
            L = tq(t['referenceTransformLs']) if 'referenceTransformLs' in t else np.eye(4)
            if p is not None and p not in self.ms:
                missing.append((n, p))
                P = np.eye(4)
            else:
                P = self.ms[p] if p else np.eye(4)
                Pr = self.ref_ms[p] if p else np.eye(4)
            self.parent[n], self.ref_local[n], self.origin[n] = p, L, tag
            self.ms[n] = P @ L
            self.ref_ms[n] = (Pr if p in self.ref_ms else np.eye(4)) @ L
        return missing


def build_reference(graph, rig):
    """Walk the live chain; return the pose with every virtual transform at its reference, plus problems."""
    pose = Pose(rig)
    problems = []
    for h in graph.post_order(2):
        if graph.cls[h] == 'animAnimNode_StackTransformsExtender':
            x = graph.x[h]
            if any(m != 'NoSnapping' for m in x.get('snapMethods', [])) or any(x.get('offsetToReferenceValues', [])):
                problems.append((h, 'extender uses snapping/offsets (not implemented)'))
            for n, p in pose.extend(x['transformInfos'], x['tag']):
                problems.append((h, f'virtual {n} parent {p} unknown'))
    return pose, problems


# ---------------------------------------------------------------------------------------------------------------
# Node handlers. Each takes (graph, h, pose, cfg) and writes pose.ms in place; returns the names written.
# 'cfg' holds hypothesis switches so rival readings can be compared against the same data.

def _v(x, default):
    if x is None:
        return np.asarray(default, float)
    return np.array([x.get('X', 0.0), x.get('Y', 0.0), x.get('Z', 0.0)], float)


def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _src_names(g, h, key='inputTransforms'):
    out = []
    for ref in g.x[h].get(key, []):
        c = ref['handle']
        w = g.x[c].get('weight', 1.0)
        inner = g.x[c]['channel']['handle'] if 'channel' in g.x[c] else c
        out.append((g.x[inner]['transformIndex']['name'], w))
    return out


def point(g, h, pose, cfg):
    x = g.x[h]
    srcs = _src_names(g, h)
    pw = x.get('preprocessedWeights') or [w for _, w in srcs]
    pw = np.asarray(pw, float)
    pw = pw / pw.sum()
    t = x['transformIndex']['name']
    p = sum(w * pose.ms[n][:3, 3] for (n, _), w in zip(srcs, pw))
    pose.ms[t] = pose.ms[t].copy()
    pose.ms[t][:3, 3] = p
    return [t]


def _rot(M):
    A = M[:3, :3]
    return A / np.linalg.norm(A, axis=0)


def _aim_matrix(fwd_ls, up_ls, fwd_w, up_w):
    """Rotation R with R@fwd_ls || fwd_w and R@up_ls in the plane of (fwd_w, up_w)."""
    f1, u1 = _norm(fwd_ls), _norm(up_ls - np.dot(up_ls, _norm(fwd_ls)) * _norm(fwd_ls))
    f2 = _norm(fwd_w)
    u2 = up_w - np.dot(up_w, f2) * f2
    if np.linalg.norm(u2) < 1e-9:  # degenerate up: keep any perpendicular (reported via rest residuals)
        u2 = np.cross(f2, [1.0, 0, 0]) if abs(f2[0]) < 0.9 else np.cross(f2, [0, 1.0, 0])
    u2 = _norm(u2)
    B1 = np.stack([f1, u1, np.cross(f1, u1)], 1)
    B2 = np.stack([f2, u2, np.cross(f2, u2)], 1)
    return B2 @ B1.T


def aim(g, h, pose, cfg, mode):
    x = g.x[h]
    t = x['transformIndex']['name']
    fwd = _v(x.get('forwardAxisLS'), cfg.get('aim.forwardAxisLS', DEFAULTS['aim.forwardAxisLS']))
    up = _v(x.get('upAxisLS'), cfg.get('aim.upAxisLS', DEFAULTS['aim.upAxisLS']))
    if 'targetTransform' in x:
        tgt = x['targetTransform']['name']
        tp = pose.ms[tgt][:3, 3]
    else:  # AimConstraint (weighted source channels)
        srcs = _src_names(g, h, 'targetTransforms')
        tp = np.mean([pose.ms[n][:3, 3] for n, _ in srcs], 0)
    me = pose.ms[t][:3, 3]
    upn = x['upTransform']['name'] if 'name' in x.get('upTransform', {}) else None
    if mode == 'object':
        upw = pose.ms[upn][:3, 3] - (tp if cfg.get('aim.upFrom') == 'target' else me)
    else:  # object-rotation up: the up object's own axis
        axis = np.asarray(cfg['aimrot.worldUpAxis'], float) if 'aimrot.worldUpAxis' in cfg else up
        upw = _rot(pose.ms[upn]) @ axis
    R = _aim_matrix(fwd, up, tp - me, upw)
    M = pose.ms[t].copy()
    s = np.linalg.norm(M[:3, :3], axis=0)
    M[:3, :3] = R * s
    pose.ms[t] = M
    return [t]


def set_bone(g, h, pose, cfg):
    out = []
    for e in g.x[h]['entries']:
        t, s = e['transformToChange']['name'], e['sourceBone']['name']
        sp = e.get('offsetSpaceBone', {}).get('name', s)
        O = tq(e['offset']) if 'offset' in e else np.eye(4)
        method = e.get('setMethod', cfg.get('setbone.defaultMethod', 'Full'))
        if cfg.get('setbone.rule', 'space') == 'source':
            M = pose.ms[s] @ O
        else:  # offset expressed in offsetSpaceBone's frame, applied to the source
            Sp = pose.ms[sp].copy()
            Sp[:3, :3] = _rot(Sp)
            M = Sp @ O @ np.linalg.inv(Sp) @ pose.ms[s]
        cur = pose.ms[t].copy()
        if method == 'RotationOnly':
            cur[:3, :3] = M[:3, :3]
        elif method == 'TranslationOnly':
            cur[:3, 3] = M[:3, 3]
        else:
            cur = M
        pose.ms[t] = cur
        out.append(t)
    return out


def spline(g, h, pose, cfg):
    x = g.x[h]
    P0, P1, P2 = (pose.ms[x[k]['name']][:3, 3] for k in ('startTransform', 'middleTransform', 'endTransform'))
    u = x.get('defaultProgress', cfg.get('spline.defaultProgress', DEFAULTS['spline.defaultProgress']))
    if cfg.get('spline.rule', 'bezier') == 'bezier':
        p = (1 - u) ** 2 * P0 + 2 * u * (1 - u) * P1 + u * u * P2
    else:  # interpolating quadratic through the middle point at u = 0.5
        C = 2 * P1 - 0.5 * (P0 + P2)
        p = (1 - u) ** 2 * P0 + 2 * u * (1 - u) * C + u * u * P2
    t = x['constrainedTransform']['name']
    pose.ms[t] = pose.ms[t].copy()
    pose.ms[t][:3, 3] = p
    return [t]


def euler_xyz(R):
    return np.array([np.arctan2(-R[1, 2], R[2, 2]), np.arcsin(np.clip(R[0, 2], -1, 1)), np.arctan2(-R[0, 1], R[0, 0])])


def from_euler_xyz(e):
    a, b, c = e
    Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    Ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    Rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


CH = {'PosX': ('t', 0), 'PosY': ('t', 1), 'PosZ': ('t', 2), 'ScaleX': ('s', 0), 'ScaleY': ('s', 1), 'ScaleZ': ('s', 2),
      'RotX': ('r', 0), 'RotY': ('r', 1), 'RotZ': ('r', 2)}


def bounce(g, h, pose, cfg, measure=None):
    """Static part only: channel = channelMultiplier * (offset + m(v)); v = change of start-end distance from
    the reference (assumed); the temporal smoothStep/delay response is NOT applied here."""
    x = g.x[h]
    s, e = x['startTransform']['name'], x['endTransform']['name']
    d = np.linalg.norm(pose.ms[s][:3, 3] - pose.ms[e][:3, 3])
    d0 = np.linalg.norm(pose.ref_ms[s][:3, 3] - pose.ref_ms[e][:3, 3])
    v = d - d0 if measure is None else measure
    m = v * (x.get('multiplier', 1.0) if v >= 0 else x.get('negativeMultiplier', x.get('multiplier', 1.0)))
    out = []
    for o in x.get('transformOutputs', []):
        t = o['targetTransform']['name']
        p = o.get('parentTransform', {}).get('name') or pose.parent[t]
        L = np.linalg.inv(pose.ms[p]) @ pose.ms[t]
        for c in o.get('channelEntries', [{}]):
            kind, i = CH[c.get('transformChannel', 'PosX')]
            val = c.get('multiplier', 1.0) * (x.get('offset', 0.0) + m)
            if kind == 't':
                L[i, 3] = val
            elif kind == 's':
                L[:3, i] = L[:3, i] / np.linalg.norm(L[:3, i]) * val
            else:
                sc = np.linalg.norm(L[:3, :3], axis=0)
                eul = euler_xyz(L[:3, :3] / sc)
                eul[i] = np.radians(val)  # assumed: degrees, R = Rx Ry Rz
                L[:3, :3] = from_euler_xyz(eul) * sc
        pose.ms[t] = pose.ms[p] @ L
        out.append(t)
    return out


def twist(g, h, pose, cfg):
    """At the reference pose the measured twist is zero by construction (relative to reference), so this is a
    no-op at rest; implemented for motion as twist about the B transform's X axis (assumed)."""
    x = g.x[h]
    A, B = x['transformA']['name'], x['transformB']['name']
    rel = np.linalg.inv(_rot(pose.ms[A])) @ _rot(pose.ms[B])
    rel0 = np.linalg.inv(_rot(pose.ref_ms[A])) @ _rot(pose.ref_ms[B])
    D = rel0.T @ rel
    ang = np.arctan2(D[2, 1] - D[1, 2], D[0, 0] + D[1, 1] + D[2, 2] - D[0, 0] + 1e-30) if False else np.arctan2(D[2, 1], D[1, 1])
    out = []
    for o in x.get('outputs', []):
        t = o['twistedTransform']['name']
        k = o.get('positiveScale', 1.0) if ang >= 0 else o.get('negativeScale', 1.0)
        a = k * ang
        Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
        M = pose.ms[t].copy()
        s = np.linalg.norm(M[:3, :3], axis=0)
        M[:3, :3] = (_rot(pose.ref_ms[t]) @ Rx) * s
        pose.ms[t] = M
        out.append(t)
    return out


def _quat(M):
    return np.asarray(mat_to_trs(np.vstack([np.hstack([_rot(M), [[0], [0], [0]]]), [0, 0, 0, 1]]))[1], float)


def _slerp(q1, q2, t):
    if np.dot(q1, q2) < 0:
        q2 = -q2
    d = np.clip(np.dot(q1, q2), -1, 1)
    if d > 0.9995:
        q = q1 + t * (q2 - q1)
        return q / np.linalg.norm(q)
    a = np.arccos(d)
    return (np.sin((1 - t) * a) * q1 + np.sin(t * a) * q2) / np.sin(a)


def orient(g, h, pose, cfg):
    """Rotation = sequential slerp of the inputs; preprocessedWeights[k] is the slerp factor towards input k+1
    (inferred: 2-input nodes store one value, e.g. weights 1,1 -> 0.5)."""
    from .rig import quat_to_mat
    x = g.x[h]
    srcs = _src_names(g, h)
    pw = x.get('preprocessedWeights', [])
    rel = cfg.get('orient.relative')  # H-offset: blend each input's change from its reference, keep target's rest
    t = x['transformIndex']['name']

    def qi(n):
        if not rel:
            return _quat(pose.ms[n])
        return _quat(pose.ms[n] @ np.linalg.inv(pose.ref_ms[n]) @ pose.ref_ms[t])
    q = qi(srcs[0][0])
    for k, (n, _) in enumerate(srcs[1:]):
        f = pw[k] if k < len(pw) else 0.5
        if cfg.get('orient.reverse'):
            f = 1 - f
        q = _slerp(q, qi(n), f)
    M = pose.ms[t].copy()
    sc = np.linalg.norm(M[:3, :3], axis=0)
    M[:3, :3] = quat_to_mat(q) * sc
    pose.ms[t] = M
    return [t]


def translation_limit(g, h, pose, cfg):
    x = g.x[h]
    t = x['constrainedTransform']['name']
    p = x.get('parentTransform', {}).get('name') or pose.parent[t]
    L = np.linalg.inv(pose.ms[p]) @ pose.ms[t]
    for i, ax in enumerate('XYZ'):
        lim = x.get(f'limitOn{ax}Axis')
        if not lim:
            continue
        if lim.get('useMin'):
            L[i, 3] = max(L[i, 3], lim.get('min', 0.0))
        if lim.get('useMax'):
            L[i, 3] = min(L[i, 3], lim.get('max', 0.0))
    pose.ms[t] = pose.ms[p] @ L
    return [t]


HANDLERS = {
    'animAnimNode_OrientConstraint': orient,
    'animAnimNode_TranslationLimit': translation_limit,
    'animAnimNode_PointConstraint': point,
    'animAnimNode_AimConstraint_ObjectUp': lambda g, h, p, c: aim(g, h, p, c, 'object'),
    'animAnimNode_AimConstraint_ObjectRotationUp': lambda g, h, p, c: aim(g, h, p, c, 'rotation'),
    'animAnimNode_SetBoneTransform': set_bone,
    'animAnimNode_SimpleSpline': spline,
    'animAnimNode_SimpleBounce': bounce,
    'animAnimNode_TwistConstraint': twist,
}


def rot_err_deg(A, B):
    R = _rot(A).T @ _rot(B)
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def rest_check(graph, rig, nodes, cfg=None, isolated=False):
    """Evaluate `nodes` (in order) from the reference pose; compare each write with the reference transform.
    isolated=True resets every transform to its reference before each node, so each node is judged on exact
    reference inputs (no error propagation)."""
    cfg = cfg or {}
    pose, problems = build_reference(graph, rig)
    rows = []
    for h in nodes:
        if isolated:
            pose.ms = {k: v.copy() for k, v in pose.ref_ms.items()}
        fn = HANDLERS.get(graph.cls[h])
        if fn is None:
            rows.append({'node': h, 'class': graph.short(h), 'status': 'no handler'})
            continue
        for t in fn(graph, h, pose, cfg):
            if t.startswith('<'):
                rows.append({'node': h, 'class': graph.short(h), 'status': t})
                continue
            rows.append({'node': h, 'class': graph.short(h), 'target': t, 'origin': pose.origin.get(t),
                         'pos_mm': float(np.linalg.norm(pose.ms[t][:3, 3] - pose.ref_ms[t][:3, 3]) * 1000),
                         'rot_deg': rot_err_deg(pose.ms[t], pose.ref_ms[t])})
    return rows, pose, problems


def evaluate(graph, rig, nodes, body_ms=None, cfg=None):
    """Run `nodes` (a sub-sequence of the live chain, in order) on an animated input pose.

    body_ms: {bone: 4x4 model-space} from the driving component (bones not given keep their reference local
    transform under their parent). Extenders run at their place in the chain, so helper GRPs follow the
    animated parents. Returns the Pose (pose.ms = evaluated, pose.ref_ms = reference)."""
    cfg = cfg or {}
    pose = Pose(rig)
    if body_ms:
        for n in pose.ms:  # rig order is parent-first
            if n in body_ms:
                pose.ms[n] = body_ms[n].copy()
            elif pose.parent[n] is not None:
                pose.ms[n] = pose.ms[pose.parent[n]] @ pose.ref_local[n]
    want = set(nodes)
    for h in graph.post_order(2):
        c = graph.cls[h]
        if c == 'animAnimNode_StackTransformsExtender':
            pose.extend(graph.x[h]['transformInfos'], graph.x[h]['tag'])
        elif h in want and c in HANDLERS:
            HANDLERS[c](graph, h, pose, cfg)
    return pose
