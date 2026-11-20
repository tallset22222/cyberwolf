"""Do the elbow and knee corrective vertex sets (DQS primary candidates, both sides) overlap?"""
import os, sys, importlib, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sets = {}
for jn, n, jf, mk in (('elbow', 3, '0', '50,70'), ('knee', 4, '1', '')):
    os.environ.update(CW_JOINT=jn, CW_OI20_JOINTFIT=jf, CW_OI20_MIDKEYS=mk, CW_OI20_XFORM='rigid', CW_OI20_MODE='share')
    O = importlib.reload(importlib.import_module('oi20_joints')); joints, _, _ = O.fit('DQS', n)
    s = set()
    for J in joints: s |= set(J['verts'][J['share'] > 1e-12].tolist()); s |= set(O.mi[J['verts'][J['share'] > 1e-12]].tolist())
    sets[jn] = s
print({k: len(v) for k, v in sets.items()}, 'overlap', len(sets['elbow'] & sets['knee']), 'union', len(sets['elbow'] | sets['knee']))
