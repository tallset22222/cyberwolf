#!/usr/bin/env python3
"""Deformation-graph regression (own baseline: tests/deformation_baseline.json).

Freezes STRUCTURE (live chains, nodesToInit agreement, the seven dangle systems and which are reachable,
dependency cone of the breast rig) and the MEASURED rest-pose residuals of the procedural layer under the
default hypotheses. The residuals are a measurement, not a pass claim: if a decode change moves them, the
change must be reviewed, never silently re-baselined.

Gates (must hold regardless of baseline): nodesToInit == live set (both graphs); breast and deformation rig
references agree < 0.01 mm; the deformation graph is a single linear chain.
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.source import Source
from cyberwolf.animgraph import AnimGraph, dependency_cone
from cyberwolf.rig import Rig
from cyberwolf import deform

D = 'base\\characters\\base_entities\\woman_base\\deformations_rigs\\'


def summary(g):
    live = g.post_order(2)
    init = {r['handle'] for r in g.x[0].get('nodesToInit', [])}
    return live, init


def run():
    src = Source(); gates = []
    gb = AnimGraph(src.get(D + 'woman_base_breasts.animgraph')); gd = AnimGraph(src.get(D + 'woman_base_deformations.animgraph'))
    rd = Rig(src.get(D + 'woman_base_deformations.rig')); rb = Rig(src.get(D + 'woman_base_breasts.rig'))
    cur = {}
    for k, g in (('breasts', gb), ('deformations', gd)):
        live, init = summary(g)
        extra = sorted(g.short(h) for h in init - set(live))
        if not set(live) <= init or any(c not in ('Root', 'MathExpressionVector', 'VectorInput') for c in extra):
            gates.append((k, 'nodesToInit != live set', extra))
        cur[k] = {'chunks': len(g.cls), 'live': len(live), 'nodesToInit_extra': extra}
    if not all(len(gd.links[h]) <= 1 for h in gd.post_order(2)):
        gates.append(('deformations', 'not a linear chain'))
    live_b = set(gb.post_order(2))
    cur['dangles'] = [{'node': h, 'live': h in live_b,
                       'particles': len(gb.x[gb.x[h]['dangleConstraint']['handle']]['particlesContainer']['particles'])}
                      for h, c in enumerate(gb.cls) if c == 'animAnimNode_Dangle']
    md, mb = rd.model_space('ref'), rb.model_space('ref')
    rc = max(float(np.linalg.norm(mb[i][:3, 3] - md[rd.index(n)][:3, 3])) for i, n in enumerate(rb.names))
    if rc > 1e-5:
        gates.append(('rigs', f'breast vs deformation rig reference differ {rc*1000:.4f} mm'))
    order = gd.post_order(2)
    cone, _ = dependency_cone(gd, order, rb.names)
    cur['breast_cone'] = {'nodes': len(cone)}
    rows, pose, _ = deform.rest_check(gd, rd, order, {})
    written = set(t for h in order for t in gd.targets(h))
    per = {n: [round(float(np.linalg.norm(pose.ms[n][:3, 3] - pose.ref_ms[n][:3, 3]) * 1000), 2),
               round(deform.rot_err_deg(pose.ms[n], pose.ref_ms[n]), 2)] for n in rd.names if n in written}
    cur['rest_default_cfg'] = {'bones': len(per), 'exact': sum(p < 0.1 and r < 0.1 for p, r in per.values()),
                               'breast_rig_bones': {n: per[n] for n in rb.names if n in per}}
    return cur, gates


if __name__ == '__main__':
    cur, gates = run(); bp = os.path.join(HERE, 'deformation_baseline.json')
    if '--update' in sys.argv or not os.path.exists(bp):
        if gates: print('gates fail:', gates); sys.exit(1)
        json.dump(cur, open(bp, 'w'), indent=1); print('deformation baseline written'); sys.exit(0)
    base = json.load(open(bp)); diff = [k for k in set(base) | set(cur) if base.get(k) != cur.get(k)]
    print(f'deformation graphs | changed: {diff} | gate failures: {gates}'); sys.exit(1 if diff or gates else 0)
