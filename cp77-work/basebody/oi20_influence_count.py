"""Influence count per vertex once corrective joints are added (base v3 weights + the joints' shares, both sides),
for any OI-20 fit. Usage: CW_JOINT=elbow CW_METHOD=LBS CW_NJ=3 [CW_OI20_JOINTFIT=1] [CW_OI20_XFORM=scaled] python3 oi20_influence_count.py"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import oi20_joints as O
method, n = os.environ.get('CW_METHOD', 'LBS'), int(os.environ.get('CW_NJ', '3'))
joints, _, _ = O.fit(method, n); O.fit_midkeys(joints, method)
Wx = np.zeros((len(O.V), len(O.bones) + 2 * len(joints))); Wx[:, :len(O.bones)] = O.Wd
for j_i, J in enumerate(joints):
    for vv, gb, sh in zip(J['verts'], J['give'], J['share']):
        Wx[vv, gb] -= sh; Wx[vv, len(O.bones) + 2 * j_i] += sh
        gr = O.bones.index(O.bones[gb][:-2] + '_r'); vr = O.mi[vv]; Wx[vr, gr] -= sh; Wx[vr, len(O.bones) + 2 * j_i + 1] += sh
nz = (Wx > 1e-12).sum(1); base = (O.Wd > 1e-12).sum(1)
r = {'joint': O.JNAME, 'method': method, 'joints_per_limb': len(joints), 'base_max_influences': int(base.max()),
     'histogram': {int(k): int((nz == k).sum()) for k in range(1, nz.max() + 1)}, 'max_influences': int(nz.max()),
     'vertices_over_4': int((nz > 4).sum()), 'vertices_gaining': int((nz > base).sum()),
     'extra_bytes_second_set_affected_only': int((nz > 4).sum()) * 8,
     'shares_equal_whole_slot': int(sum(int((np.abs(J['share'] - O.Wd[J['verts'], J['give']]) < 1e-9).sum()) for J in joints)) * 2}
print(json.dumps(r))
