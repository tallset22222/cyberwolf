"""Dangle (secondary motion) systems from .animgraph: animDangleConstraint_SimulationDyng.

The data describes a runtime particle simulation, not baked motion: particles on rig bones, distance links and
half-cone swing limits. Values CR2W omits are engine defaults that are not in the data; every parameter used here is
recorded as 'stated' or 'assumed' so assumptions stay visible and can be swept.
Established from data: isFree defaults to TRUE (strand roots state isFree=0, nothing else does).
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402

ASSUMED = {'mass': 1.0, 'damping': 0.1, 'pullForceFactor': 0.0, 'gravity': 9.81, 'coneAngle': 45.0,
           'substep': 1 / 60, 'iterations': 4}


def load_systems(graph_path):
    r = R(graph_path)
    chunks = r.meta['chunks']
    systems = []
    for i, c in enumerate(chunks):
        if c['class'] != 'animDangleConstraint_SimulationDyng':
            continue
        sim = r.chunk(i)
        multi = r.chunk(sim['dyngConstraint']['handle'])
        links, cones, other = [], [], []
        for h in multi.get('innerConstraints', []):
            cc = chunks[h['handle']]['class']; x = r.chunk(h['handle'])
            if cc == 'animDyngConstraintLink':
                links.append((x['bone1']['name'], x['bone2']['name'], x.get('lengthLowerBoundRatioPercentage'), x.get('lengthUpperBoundRatioPercentage')))
            elif cc == 'animDyngConstraintCone':
                cones.append({'bone': x['constrainedBone']['name'], 'attach': x['coneAttachmentBone']['name'],
                              'angle': x.get('halfOfMaxApertureAngle'), 'type': x.get('constraintType')})
            else:
                other.append(cc)
        pc = sim.get('particlesContainer', {})
        parts = []
        for p in pc.get('particles', []):
            parts.append({'bone': p['bone']['name'], 'free': bool(p.get('isFree', 1)), 'mass': p.get('mass'),
                          'damping': p.get('damping'), 'pull': p.get('pullForceFactor'), 'radius': p.get('collisionCapsuleRadius', 0.0)})
        systems.append({'particles': parts, 'links': links, 'cones': cones, 'unsupported': other,
                        'gravity': pc.get('gravityWS'), 'substep': sim.get('substepTime'), 'iterations': sim.get('solverIterations'),
                        'collisionShapes': len(sim.get('collisionRoundedShapes') or [])})
    return systems


def simulate(system, rest_world, target_world, frame_dt, params=None, collide=None):
    """collide: optional (capsules, [F] list of {bone: 4x4 world}) for capsule collision; particle radius from
    collisionCapsuleRadius (stated) or 0 (assumed)."""
    """rest_world: {bone: (3,) bind position}; target_world: {bone: [F, 3]} animated (kinematic) positions.
    Free particles are simulated; pinned ones follow the target. Returns ({bone: [F, 3]}, provenance, diagnostics)."""
    P = dict(ASSUMED); P.update(params or {})
    prov = {}
    def val(stated, key):
        prov.setdefault(key, set()).add('stated' if stated is not None else 'assumed')
        return stated if stated is not None else P[key]
    g = val(system['gravity'], 'gravity'); sub = val(system['substep'], 'substep'); iters = int(val(system['iterations'], 'iterations'))
    names = [p['bone'] for p in system['particles']]
    free = np.array([p['free'] for p in system['particles']])
    mass = np.array([val(p['mass'], 'mass') for p in system['particles']])
    damp = np.array([val(p['damping'], 'damping') for p in system['particles']])
    pull = np.array([val(p['pull'], 'pullForceFactor') for p in system['particles']])
    ix = {n: i for i, n in enumerate(names)}
    links = [(ix[a], ix[b], np.linalg.norm(rest_world[a] - rest_world[b])) for a, b, lo, hi in system['links'] if a in ix and b in ix]
    cones = [(ix[c['attach']], ix[c['bone']], np.radians(val(c['angle'], 'coneAngle'))) for c in system['cones'] if c['bone'] in ix and c['attach'] in ix]
    F = len(next(iter(target_world.values())))
    T = np.stack([target_world[n] for n in names], 1)            # [F, N, 3]
    x = T[0].copy(); xp = x.copy(); out = np.empty_like(T)
    nsub = max(1, int(round(frame_dt / sub))); dt = frame_dt / nsub
    gvec = np.array([0, 0, -g])
    prad = np.array([p.get('radius') or 0.0 for p in system['particles']])
    collide_pen = [0.0]
    link_err = cone_viol = 0.0
    for f in range(F):
        for s in range(nsub):
            a = (f - 1 + (s + 1) / nsub) if f > 0 else 0.0
            tgt = T[max(f - 1, 0)] * (1 - (s + 1) / nsub) + T[f] * ((s + 1) / nsub) if f > 0 else T[0]
            v = (x - xp) * (1 - damp[:, None])
            acc = gvec[None, :] + pull[:, None] * (tgt - x) / mass[:, None] * 25.0
            xn = x + v + acc * dt * dt
            xn[~free] = tgt[~free]
            xp, x = x, xn
            for _ in range(iters):
                for e in system.get('ellipsoids', []):            # ellipsoid limit around the animated anchor (axis mapping assumed: local x,y,z <- r*s1, r*s2, r)
                    if collide and e['bone'] in ix:
                        k = ix[e['bone']]; Mb = collide[1][f][e['bone']]; Rm = Mb[:3, :3] / np.linalg.norm(Mb[:3, :3], axis=0)
                        rad = np.array([e['radius'] * (e['s1'] or 1), e['radius'] * (e['s2'] or 1), e['radius']])
                        dl = Rm.T @ (x[k] - tgt[k]); q = np.sqrt(np.sum((dl / rad) ** 2))
                        if q > 1: x[k] = tgt[k] + Rm @ (dl / q)
                if collide:
                    pen = apply_collisions(x, free, collide[0], collide[1][f], prad)
                    collide_pen[0] = max(collide_pen[0], pen) if s == nsub - 1 and _ == 0 else collide_pen[0]
                for i, j, L in links:
                    d = x[j] - x[i]; dist = np.linalg.norm(d) + 1e-12; corr = (dist - L) * d / dist
                    wi, wj = float(free[i]), float(free[j]); tot = wi + wj
                    if tot: x[i] += corr * wi / tot; x[j] -= corr * wj / tot
                for i, j, ang in cones:
                    rest_dir = tgt[j] - tgt[i]; rd = rest_dir / (np.linalg.norm(rest_dir) + 1e-12)
                    d = x[j] - x[i]; L = np.linalg.norm(d) + 1e-12; cur = d / L
                    c = np.clip(cur @ rd, -1, 1)
                    if np.arccos(c) > ang and free[j]:
                        axis = np.cross(rd, cur); axis /= (np.linalg.norm(axis) + 1e-12)
                        k = np.cross(axis, rd)
                        x[j] = x[i] + L * (np.cos(ang) * rd + np.sin(ang) * k)
        out[f] = x
        for i, j, L in links: link_err = max(link_err, abs(np.linalg.norm(x[j] - x[i]) - L))
        for i, j, ang in cones:
            rest_dir = T[f][j] - T[f][i]; d = x[j] - x[i]
            cone_viol = max(cone_viol, np.degrees(np.arccos(np.clip(d @ rest_dir / (np.linalg.norm(d) * np.linalg.norm(rest_dir) + 1e-12), -1, 1))) - np.degrees(ang))
    final_pen = 0.0
    if collide:
        for f in range(F):
            xx = out[f].copy(); final_pen = max(final_pen, apply_collisions(xx, free, collide[0], collide[1][f], prad))
    diag = {'maxLinkError_mm': round(link_err * 1000, 3), 'maxConeExcess_deg': round(max(cone_viol, 0.0), 2), 'substeps': nsub,
            'maxCapsulePenetration_mm': round(final_pen * 1000, 2) if collide else None}
    return {n: out[:, i] for i, n in enumerate(names)}, {k: sorted(v) for k, v in prov.items()}, diag


# ---- kinematic layer (verified) and collision/ellipsoid support ----
def _tq(x):
    from .rig import trs_matrix
    t, q = x['Translation'], x['Rotation']
    return trs_matrix((t.get('X', 0), t.get('Y', 0), t.get('Z', 0)), (q.get('i', 0), q.get('j', 0), q.get('k', 0), q.get('r', 1)))


def load_graph(graph_path):
    """Systems plus the graph's multiple-parent constraints, collision capsules and ellipsoid constraints."""
    r = R(graph_path)
    mpcs, ellipsoids = [], []
    for i, c in enumerate(r.meta['chunks']):
        x = r.chunk(i)
        if c['class'] == 'animAnimNode_MultipleParentConstraint':
            mpcs.append({'target': (x.get('visMask') or [{}])[0].get('name'),
                         'parents': [(p['parentTransform']['name'], p.get('parentStaticWeight', 1.0), _tq(p['offset']) if p.get('useOffset') else np.eye(4))
                                     for p in x.get('parentsTransforms', [])]})
        if c['class'] == 'animDyngConstraintEllipsoid':
            ellipsoids.append({'bone': x['bone']['name'], 'radius': x.get('constraintRadius'), 's1': x.get('constraintScale1'), 's2': x.get('constraintScale2')})
    systems = load_systems(graph_path)
    for (i, c), s in zip([(i, c) for i, c in enumerate(r.meta['chunks']) if c['class'] == 'animDangleConstraint_SimulationDyng'], systems):
        s['capsules'] = [{'bone': sh['bone']['name'], 'local': _tq(sh['transformLS']), 'radius': sh.get('roundedCornerRadius', 0.0),
                          'half': sh.get('zBoxExtent', 0.0)} for sh in (r.chunk(i).get('collisionRoundedShapes') or [])]
        names = {p['bone'] for p in s['particles']}
        s['ellipsoids'] = [e for e in ellipsoids if e['bone'] in names]
    return systems, mpcs


def blend_parents(mpc, world):
    """Verified at rest (offsets reproduce Offset_GRP within 0.06 mm). Under motion: weighted position and
    normalised weighted rotation (standard parent-constraint blend; assumption)."""
    from .gltf import mat_to_trs
    from .rig import trs_matrix
    ws = np.array([w for _, w, _ in mpc['parents']]); ws = ws / ws.sum()
    T = np.zeros(3); Q = np.zeros(4); q0 = None
    for (pn, _, O), w in zip(mpc['parents'], ws):
        t, q, _ = mat_to_trs(world[pn] @ O)
        if q0 is None: q0 = q
        if np.dot(q, q0) < 0: q = -q
        T += w * t; Q += w * q
    return trs_matrix(T, Q / np.linalg.norm(Q))


def kinematic_targets(dangle_rig, body_rig, body_local, mpcs):
    """Per-frame world transforms of every dangle-rig bone: body bones from the body animation, Offset_GRP roots from
    the multiple-parent blend, everything else rigidly at its rest offset. body_local: [F, Jbody, 4, 4]."""
    F = body_local.shape[0]
    bix = {n: i for i, n in enumerate(body_rig.names)}
    mp = {m['target']: m for m in mpcs}
    out = np.empty((F, len(dangle_rig.names), 4, 4))
    rest_local = dangle_rig.apose_local or dangle_rig.ref_local
    for f in range(F):
        W = {}
        for j, n in enumerate(dangle_rig.names):
            p = dangle_rig.parents[j]
            L = body_local[f, bix[n]] if n in bix else rest_local[j]
            if n in mp and all(pp in W for pp, _, _ in mp[n]['parents']):
                M = blend_parents(mp[n], W)
            else:
                M = L if p < 0 else W[dangle_rig.names[p]] @ L
            W[n] = M; out[f, j] = M
    return out


def apply_collisions(x, free, capsules, world_frame, particle_radius):
    """Push free particles out of capsules (segment along local z, half-length `half`, radius `radius`)."""
    pen = 0.0
    for c in capsules:
        M = world_frame[c['bone']] @ c['local']
        a = M[:3, 3] - M[:3, 2] / np.linalg.norm(M[:3, 2]) * c['half']; b = M[:3, 3] + M[:3, 2] / np.linalg.norm(M[:3, 2]) * c['half']
        ab = b - a; t = np.clip(((x - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        closest = a + t[:, None] * ab; d = x - closest; dist = np.linalg.norm(d, axis=1) + 1e-12
        rmin = c['radius'] + np.broadcast_to(np.asarray(particle_radius, dtype=float), dist.shape)
        inside = (dist < rmin) & free
        pen = max(pen, float((rmin - dist)[inside].max()) if inside.any() else 0.0)
        x[inside] = closest[inside] + d[inside] / dist[inside, None] * rmin[inside, None]
    return pen
