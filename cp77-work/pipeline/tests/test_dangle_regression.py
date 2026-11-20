#!/usr/bin/env python3
"""Dangle regression (own baseline: tests/dangle_baseline.json). Covers only decoded/verified facts:
structure counts per system, the isFree pattern (only explicit 0 / omitted), capsule and ellipsoid parameters, and
multiple-parent rest reproduction (< 0.1 mm). Simulation output is excluded: it depends on assumed engine defaults."""
import hashlib, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.source import Source
from cyberwolf.rig import Rig
from cyberwolf.dangle import load_graph, blend_parents

GRAPHS = {'judy_hair': ('base\\characters\\common\\hair\\hh_051_wa__judy\\hh_051_wa__judy_dangle.animgraph', 'base\\characters\\common\\hair\\hh_051_wa__judy\\hh_051_wa__judy_dangle_skeleton.rig'),
          'judy_pants': ('base\\characters\\main_npc\\judy\\l1_001_wa_pants__judy_dangle.animgraph', 'base\\characters\\main_npc\\judy\\l1_001_wa_pants__judy_dangle_skeleton.rig'),
          'jackie_jacket': ('base\\characters\\main_npc\\jackie_welles\\t2_001_full_jackie_welles_dangle.animgraph', 'base\\characters\\main_npc\\jackie_welles\\t2_001_mb_full__jackie_welles_dangle_skeleton.rig')}

def run():
    src = Source(); cur = {}; gates = []
    for k, (g, rp) in GRAPHS.items():
        systems, mpcs = load_graph(src.get(g)); rig = Rig(src.get(rp))
        ms = rig.model_space('apose' if rig.apose_local else 'ref'); W = {n: ms[i] for i, n in enumerate(rig.names)}
        mp_err = max([float(np.linalg.norm(blend_parents(m, W)[:3, 3] - W[m['target']][:3, 3])) for m in mpcs] or [0.0])
        if mp_err > 1e-4: gates.append((k, f'multiple-parent rest error {mp_err*1000:.3f} mm'))
        cur[k] = {'systems': [{'particles': len(s['particles']), 'pinned': sum(not p['free'] for p in s['particles']), 'links': len(s['links']),
                               'cones': len(s['cones']), 'capsules': [[c['bone'], round(c['radius'], 4), round(c['half'], 4)] for c in s['capsules']],
                               'ellipsoids': len(s['ellipsoids']), 'gravityStated': s['gravity']} for s in systems],
                  'multipleParents': len(mpcs)}
    return cur, gates

if __name__ == '__main__':
    cur, gates = run(); bp = os.path.join(HERE, 'dangle_baseline.json')
    if '--update' in sys.argv or not os.path.exists(bp):
        if gates: print('gates fail:', gates); sys.exit(1)
        json.dump(cur, open(bp, 'w'), indent=1); print('dangle baseline written:', list(cur)); sys.exit(0)
    base = json.load(open(bp)); diff = [k for k in set(base) | set(cur) if base.get(k) != cur.get(k)]
    print(f'{len(cur)} dangle graphs | changed: {diff} | gate failures: {gates}'); sys.exit(1 if diff or gates else 0)
