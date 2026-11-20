"""Apply metrics2 to a run directory's _test2_posed.npz. Usage: metrics2_run.py <dir> [pose_substring]"""
import sys, os, json, time, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.pop('CW_HELPERS', None)
import test2_deformation as T2, metrics2 as M2
d = sys.argv[1]; filt = sys.argv[2] if len(sys.argv) > 2 else ''
V, Q, pos, *_ = T2.build()
lib, focus = T2.pose_library(pos)
z = np.load(os.path.join(HERE, d, '_test2_posed.npz')); assert np.allclose(z['V'], V)
M = M2.Metric2(V, Q, T2.INTERIOR)
out = {}
t0 = time.time()
for p in lib:
    if filt not in p or f'{p}__LBS' not in z: continue
    c = pos[focus[p]]
    out[p] = {m: M.measure(z[f'{p}__{m}'], c) for m in ('LBS', 'DQS')}
json.dump({'metric': 'metrics2 (categorised)', 'params': {k: getattr(M2, k) for k in ('REGION', 'LOCAL', 'CONTACT', 'DEPTH', 'FOLDOVER', 'PINCH')}, 'results': out},
          open(os.path.join(HERE, d, 'metrics2.json'), 'w'), indent=1)
print(f'{len(out)} poses in {time.time() - t0:.0f}s')
