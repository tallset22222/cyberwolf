"""Render the knee corrective-joint finalists against the offline prototype: error heat maps on the knee region
(lateral and back views) at 90 and 135 degrees. Writes reports/correctives/oi20_knee_compare.png."""
import os, sys, numpy as np
os.environ['CW_JOINT'] = 'knee'; os.environ['CW_OI20_JOINTFIT'] = '1'
import importlib, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
rows = [('LBS', 3, 'rigid', 'LBS, 6 joints/leg, rigid'), ('LBS', 3, 'scaled', 'LBS, 6 joints/leg, with scale'), ('DQS', 4, 'rigid', 'DQS, 8 joints/leg, rigid')]
fig, ax = plt.subplots(len(rows), 4, figsize=(15, 4.3 * len(rows)), facecolor='white')
for ri, (method, n, xf, label) in enumerate(rows):
    os.environ['CW_OI20_XFORM'] = xf
    O = importlib.import_module('oi20_joints'); O = importlib.reload(O)
    joints, D, patch = O.fit(method, n); O.fit_midkeys(joints, method); names, tp, Wt2, over = O.build(joints, 8)
    V, pos, T2, CR = O.V, O.pos, O.T2, O.CR
    near = (np.linalg.norm(V - pos['calf_l'], axis=1) < 0.16) & (V[:, 0] > 0)
    for ci, th in enumerate((90, 135)):
        G = O.G_at(th); Ge = O.G_ext(G, joints, CR.flex_angle(G, pos, 'knee', 'l'), CR.flex_angle(G, pos, 'knee', 'r'))
        X_off = T2.skin(V, O.bones, O.top, O.Wt, G, method); CR._C['authoring'] = True
        X_j = T2.skin(V, names, tp, Wt2, Ge, method); CR._C['authoring'] = False
        e = np.linalg.norm(X_j - X_off, axis=1) * 1000
        c0 = pos['calf_l'] if False else (G['calf_l'][:3, 3])
        for vi, (a_, b_, vname) in enumerate(((1, 2, 'lateral (y-z)'), (0, 2, 'back (x-z)'))):
            a = ax[ri, 2 * ci + vi]; P = X_j[near] - c0
            order = np.argsort(P[:, 0] if vi == 0 else -P[:, 1])            # draw near side last
            sc = a.scatter(P[order, a_], P[order, b_], c=e[near][order], s=4, cmap='magma', vmin=0, vmax=4)
            a.set_aspect('equal'); a.set_xticks([]); a.set_yticks([])
            a.set_title(f'{label}\nknee {th}°, {vname}: max {e[near].max():.2f} mm', fontsize=9)
fig.colorbar(sc, ax=ax, shrink=0.5, label='distance from the offline prototype, mm (clipped at 4)')
fig.suptitle('OI-20 knee: corrective joints vs the offline prototype (left leg)', fontsize=12)
fig.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports', 'correctives', 'oi20_knee_compare.png'), dpi=95)
print('ok')
