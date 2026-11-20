"""Chest secondary motion (woman_base_breasts.animgraph, default dangle system) on top of the procedural layer.

Everything not stated in the data is a named, configurable assumption (ASSUMED) and is reported with each run.
Model (hypothesis, not decoded engine code): position-based particles in world space,
    a = pull*(target - x) - damping*(v - v_target) + gravity + extScale*compress(-a_root)
then ellipsoid and link projections; the joint keeps the procedural layer's rotation (RotationOnly restore,
decoded) and takes the particle's translation. Drag nodes are not simulated (blend weight omitted in data,
assumed 0; Drag semantics undecoded).
"""
import numpy as np
from .deform import tq

# Defaults: 'wk' = WolvenKit RTTI constructor default, checked against all 526 animgraphs (never stored
# explicitly with that value; see pipeline_out/research/defaults_check.json). Others are assumptions.
ASSUMED = {
    'substep': 0.01,              # wk: animDangleConstraint_SimulationDyng.substepTime (system 54 omits it)
    'iterations': 1,              # wk: solverIterations
    'gravity': 9.81,              # wk: animDyngParticlesContainer.gravityWS (system 54 omits it; 0.0 is stored explicitly 13x elsewhere)
    'mass_default': 1.0,          # wk: animDyngParticle.mass
    'pull_scale': 1.0,            # assumption: pullForceFactor used as stiffness [1/s^2] x scale (unit not decoded)
    'damping_scale': 1.0,         # assumption: damping as rate [1/s] (corpus values 2-5 common, so not a per-step fraction)
    'damping_relative': True,     # assumption: damp velocity relative to the target's velocity
    'ext': True,                  # data: externalForceWsLink is connected
    'ext_scale': 1.0,
    'ellipsoid': 'offset_needle',  # assumption (the only reading drift-free under gravity)
    'ellipsoid_projection': 'closest',
    'blend_weight': 0.0,          # wk: FloatConstant.value default 0 (1.0 stored explicitly 2238x, 0.0 never)
    'world_space': False,         # assumption: particle state in the character frame; entity motion enters only via
                                  # the fictitious-acceleration input (an input used by all 655 linked systems, incl. cars)
}


def load_system(g, sim_handle):
    sim = g.x[sim_handle]
    parts = sim['particlesContainer']['particles']
    names = [p['bone']['name'] for p in parts]
    links, ells, cones = [], [], []
    for _, m in g.data[sim_handle]:
        inner = [c for _, c in g.data[m]] if g.cls[m] == 'animDyngConstraintMulti' else [m]
        for c in inner:
            x = g.x[c]
            if g.cls[c] == 'animDyngConstraintLink':
                links.append((x['bone1']['name'], x['bone2']['name'], x.get('lengthLowerBoundRatioPercentage', 100) / 100,
                              x.get('lengthUpperBoundRatioPercentage', 100) / 100, x.get('linkType')))
            elif g.cls[c] == 'animDyngConstraintEllipsoid':
                ells.append({'bone': x['bone']['name'], 'offset': tq(x['ellipsoidTransformLS']), 'r': x['constraintRadius'],
                             's1': x.get('constraintScale1', 1.0), 's2': x.get('constraintScale2', 1.0)})
            elif g.cls[c] == 'animDyngConstraintCone':
                cones.append(x)
    return {'names': names, 'damping': np.array([p.get('damping', 1.0) for p in parts], float),
            'pull': np.array([p.get('pullForceFactor', 0.0) for p in parts], float),
            'mass': [p.get('mass') for p in parts],
            'free': np.array([bool(p.get('isFree', 1)) for p in parts]),
            'links': links, 'ellipsoids': ells, 'cones': cones,
            'stated': {k: sim.get(k) for k in ('substepTime', 'solverIterations', 'HACK_checkDangleTeleport', 'rotateParentToLookAtDangle')}}


def compress(v):
    """MathExpressionVector in the graph: (length(v)^(1/4)) * norm(v)."""
    n = np.linalg.norm(v)
    return v * (n ** 0.25 / n) if n > 1e-12 else v * 0


def _ellipsoid_frame(e, M, mode):
    """Centre, axes (columns) and semi-axes of an ellipsoid constraint for a bone frame M (world)."""
    R = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)
    off = e['offset'][:3, 3]
    r = e['r']
    if mode == 'ignore_offset':
        return M[:3, 3], R, np.array([r * e['s1'], r * e['s2'], r])
    c = M[:3, 3] + R @ off
    if mode == 'offset_sphere':
        return c, R, np.array([r, r, r])
    a = R @ (off / np.linalg.norm(off))          # long axis along the offset; scales on the two perpendicular axes
    b = np.cross(a, R[:, 2]); b /= np.linalg.norm(b)
    return c, np.stack([a, b, np.cross(a, b)], 1), np.array([r, r * e['s1'], r * e['s2']])


def closest_on_ellipsoid(y, a, iters=60):
    """Closest point on the axis-aligned ellipsoid sum((x/a)^2)=1 to an outside point y (bisection on the
    Lagrange parameter; exact up to tolerance)."""
    a2 = a * a
    lo, hi = 0.0, float(np.linalg.norm(y) * a.max())
    for _ in range(iters):
        t = 0.5 * (lo + hi)
        f = np.sum(a2 * y * y / (t + a2) ** 2) - 1
        lo, hi = (t, hi) if f > 0 else (lo, t)
    t = 0.5 * (lo + hi)
    return a2 * y / (t + a2)


def _frames(sysd, mode):
    """Per-ellipsoid constants: particle index, centre offset, axes (both bone-local), semi-axes."""
    ix = {n: i for i, n in enumerate(sysd['names'])}
    rows = []
    for e in sysd['ellipsoids']:
        if e['bone'] not in ix:
            continue
        off = e['offset'][:3, 3]
        r = e['r']
        if mode == 'ignore_offset':
            A = np.eye(3); ax = np.array([r * e['s1'], r * e['s2'], r]); c = np.zeros(3)
        elif mode == 'offset_sphere':
            A = np.eye(3); ax = np.array([r, r, r]); c = off
        else:  # offset_needle: long axis r along the offset, r*s1 and r*s2 across it
            a = off / np.linalg.norm(off)
            b = np.cross(a, [0, 0, 1.0]); b /= np.linalg.norm(b)
            A = np.stack([a, b, np.cross(a, b)], 1); ax = np.array([r, r * e['s1'], r * e['s2']]); c = off
        rows.append((ix[e['bone']], c, A, ax))
    if not rows:
        return None
    return (np.array([r[0] for r in rows]), np.stack([r[1] for r in rows]), np.stack([r[2] for r in rows]),
            np.stack([r[3] for r in rows]))


def _project_ellipsoids(p, rot, tgt, E, closest=True, iters=40):
    """Vectorised keep-inside projection (in place). rot: [N,3,3] bone rotations, tgt: [N,3] bone positions."""
    idx, c, A, ax = E
    R = rot[idx]
    C = tgt[idx] + np.einsum('nij,nj->ni', R, c)
    W = np.einsum('nij,njk->nik', R, A)
    y = np.einsum('nji,nj->ni', W, p[idx] - C)
    q = np.sqrt(np.sum((y / ax) ** 2, 1))
    out = q > 1
    if out.any():
        yo, ao = y[out], ax[out]
        if closest:
            a2 = ao * ao
            lo = np.zeros(len(yo)); hi = np.linalg.norm(yo, axis=1) * ao.max(1)
            for _ in range(iters):
                t = 0.5 * (lo + hi)
                f = np.sum(a2 * yo * yo / (t[:, None] + a2) ** 2, 1) - 1
                lo = np.where(f > 0, t, lo); hi = np.where(f > 0, hi, t)
            t = 0.5 * (lo + hi)
            yn = a2 * yo / (t[:, None] + a2)
        else:
            yn = yo / q[out][:, None]
        p[idx[out]] = C[out] + np.einsum('nij,nj->ni', W[out], yn)
    return q


def simulate(sysd, targets, frame_dt, root_acc=None, params=None):
    """targets: [F, N, 4, 4] world transforms of the particle bones from the procedural layer.
    root_acc: [F, 3] world acceleration of the character (external-force input).
    Returns positions [F, N, 3] and diagnostics (constraint violations before/after projection)."""
    P = dict(ASSUMED)
    P.update(params or {})
    F, N = targets.shape[:2]
    sub = sysd['stated'].get('substepTime') or P['substep']
    iters = int(sysd['stated'].get('solverIterations') or P['iterations'])
    nsub = max(1, int(round(frame_dt / sub)))
    dt = frame_dt / nsub
    k = (sysd['pull'] * P['pull_scale'])[:, None]
    c = (sysd['damping'] * P['damping_scale'])[:, None]
    mass = np.array([m if m is not None else P['mass_default'] for m in sysd.get('mass', [None] * len(sysd['names']))])[:, None]
    ix = {n: i for i, n in enumerate(sysd['names'])}
    T = targets[:, :, :3, 3]
    ROT = targets[:, :, :3, :3] / np.linalg.norm(targets[:, :, :3, :3], axis=2, keepdims=True)
    Tv = np.gradient(T, frame_dt, axis=0) if F > 1 else np.zeros_like(T)
    g_frames = P.get('gravity_frames')  # [F,3] gravity in the simulation frame (character frame)
    g = np.array([0, 0, -P['gravity']])
    x = T[0].copy()
    v = Tv[0].copy()
    out = np.empty_like(T)
    diag = {'pre_link_violation': 0.0, 'post_link_violation': 0.0, 'pre_ellipsoid_q': 0.0, 'post_ellipsoid_q': 0.0,
            'ellipsoid_contact_frac': 0.0, 'finite': True, 'substeps': nsub, 'dt': dt, 'iterations': iters}
    contacts = total = 0
    links = [(ix[a], ix[b], lo, hi) for a, b, lo, hi, _ in sysd['links'] if a in ix and b in ix]
    E = _frames(sysd, P['ellipsoid']) if P['ellipsoid'] != 'off' else None
    closest = P['ellipsoid_projection'] == 'closest'
    for f in range(F):
        fa = max(f - 1, 0)
        ext = compress(-root_acc[f]) * P['ext_scale'] if (P['ext'] and root_acc is not None) else 0.0
        for s in range(nsub):
            u = (s + 1) / nsub if f > 0 else 1.0
            tgt = T[fa] * (1 - u) + T[f] * u
            tv = Tv[fa] * (1 - u) + Tv[f] * u
            vrel = v - tv if P['damping_relative'] else v
            gg = g_frames[f] * P['gravity'] if g_frames is not None else g
            a = (k * (tgt - x) - c * vrel) / mass + gg + ext
            v = v + a * dt
            p = x + v * dt
            for it in range(iters):
                if E is not None:
                    q = _project_ellipsoids(p, ROT[f], tgt, E, closest)
                    if it == 0:
                        diag['pre_ellipsoid_q'] = max(diag['pre_ellipsoid_q'], float(q.max()))
                        total += len(q)
                        contacts += int((q > 1 + 1e-6).sum())
                for i, j, lo, hi in links:
                    L = np.linalg.norm(tgt[j] - tgt[i])
                    dvec = p[j] - p[i]
                    dist = np.linalg.norm(dvec) + 1e-12
                    if it == 0:
                        diag['pre_link_violation'] = max(diag['pre_link_violation'], max(lo - dist / L, dist / L - hi, 0))
                    goal = min(max(dist, lo * L), hi * L)
                    corr = (dist - goal) * dvec / dist / 2
                    p[i] += corr
                    p[j] -= corr
            v = (p - x) / dt
            x = p
        if not np.all(np.isfinite(x)):
            diag['finite'] = False
            out[f:] = np.nan
            break
        out[f] = x
        for i, j, lo, hi in links:
            r = np.linalg.norm(x[j] - x[i]) / np.linalg.norm(T[f, j] - T[f, i])
            diag['post_link_violation'] = max(diag['post_link_violation'], max(lo - r, r - hi, 0))
        if E is not None:
            diag['post_ellipsoid_q'] = max(diag['post_ellipsoid_q'], float(_project_ellipsoids(x.copy(), ROT[f], T[f], E, closest).max()))
    diag['ellipsoid_contact_frac'] = contacts / total if total else 0.0
    diag['params'] = {kk: P[kk] for kk in ASSUMED if kk != 'gravity_frames'}
    diag['stated'] = sysd['stated']
    return out, diag
