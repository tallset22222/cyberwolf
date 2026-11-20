#!/usr/bin/env python3
"""Chest secondary-motion gates (no baseline: simulated motion depends on assumed engine defaults, so its
numbers are reported, not frozen). Gates for the current default (gravity 9.81, substep 0.01, 1 iteration,
character-frame particles, needle ellipsoid), its world-space variant, and gravity off:
  * zero acceleration for 9 s: displacement from the procedural target < 0.5 mm, not growing;
  * every rigid acceleration profile stays finite; links end within their 75-125 % bounds;
  * displacement stays within the ellipsoid range (<= 2 r + 1 mm).
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import simulate_secondary as S
from cyberwolf.source import Source
from cyberwolf.animgraph import AnimGraph, dependency_cone
from cyberwolf.rig import Rig
from cyberwolf import secondary


def run():
    src = Source(); gates = []
    sysd = S.setup(src)
    gd = AnimGraph(src.get(S.D + 'woman_base_deformations.animgraph')); rd = Rig(src.get(S.D + 'woman_base_deformations.rig'))
    cone, _ = dependency_cone(gd, gd.post_order(2), sysd['names'])
    profs = S.rigid_profiles(); dt = 1 / S.FPS
    rmax = max(e['r'] for e in sysd['ellipsoids'])
    for cn in ('default', 'default_world', 'gravity_off'):
        p = S.CONFIGS[cn]
        R0 = np.concatenate([profs['stationary'][0]] * 3)
        T = S.chest_targets_rigid(gd, rd, cone, sysd['names'], R0, {})
        I = np.repeat(np.eye(4)[None], len(T), 0)
        x, d = S.run_one(sysd, T, I, np.zeros((len(T), 3)), p, dt)
        dm = np.linalg.norm(x - T[:, :, :3, 3], axis=2).max(1) * 1000
        if dm.max() > 0.5 or dm[-1] > dm[30] + 1e-3:
            gates.append((cn, 'stationary drift', round(float(dm.max()), 4), round(float(dm[-1]), 4)))
        for pn, (R, _) in profs.items():
            T = S.chest_targets_rigid(gd, rd, cone, sysd['names'], R, {})
            x, d = S.run_one(sysd, T, R, S.accel(R[:, :3, 3], dt), p, dt)
            if not d['finite']:
                gates.append((cn, pn, 'non-finite'))
                continue
            if d['post_link_violation'] > 1e-6:
                gates.append((cn, pn, 'link violation', d['post_link_violation']))
            dm = np.linalg.norm(x - T[:, :, :3, 3], axis=2).max() * 1000
            if dm > 2 * rmax * 1000 + 1:
                gates.append((cn, pn, 'outside ellipsoid range', dm))
            print(f'{cn:10s} {pn:12s} max {dm:6.2f} mm  ellipsoid q after projection {d["post_ellipsoid_q"]:.3f}')
    return gates


if __name__ == '__main__':
    g = run(); print('gate failures:', g); sys.exit(1 if g else 0)
