#!/usr/bin/env python3
"""Plausibility checks for decoded animations (beyond byte accounting, which only proves the layout):
feet near the ground and head at standing height; bone lengths preserved; no frame-to-frame flips;
continuity between a transition clip and the clip it leads into."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.source import Source
from cyberwolf.rig import Rig
from cyberwolf.anims import AnimSet, sample

def model_space(rig, local):           # local: [F, J, 4, 4]
    out = np.empty_like(local)
    for j, p in enumerate(rig.parents):
        out[:, j] = local[:, j] if p < 0 else np.einsum('fij,fjk->fik', out[:, p], local[:, j])
    return out

def check_set(src, path):
    s = AnimSet(src.get(path)); rig = Rig(src.get(s.rig)); idx = {n: i for i, n in enumerate(rig.names)}
    ref_len = {j: np.linalg.norm(L[:3, 3]) for j, L in enumerate(rig.ref_local)}
    res = {}
    for a in s.animations:
        t = np.linspace(0, a.duration, max(a.num_frames, 2))
        ms = model_space(rig, sample(a, rig, t))
        P = ms[:, :, :3, 3]
        foot = min(P[:, idx[f], 2].min() for f in ('LeftFoot', 'RightFoot') if f in idx)
        toe = min(P[:, idx[f], 2].min() for f in ('LeftToeBase', 'RightToeBase') if f in idx)
        head = P[:, idx['Head'], 2] if 'Head' in idx else None
        tj = {j for (j, c) in a.keys if c == 0}
        bl = [abs(np.linalg.norm(v) - ref_len[j]) for (j, c), ks in a.keys.items() if c == 0 and rig.names[j] not in ('Root', 'Trajectory', 'Hips', 'reference_joint') and ref_len[j] > 0.02 for _, v in ks]
        rot_step = max(float(np.degrees(np.arccos(np.clip((np.einsum('fii->f', np.einsum('fij,fkj->fik', ms[1:, j, :3, :3], ms[:-1, j, :3, :3])) - 1) / 2, -1, 1))).max()) for j in range(len(rig.names)))
        res[a.name] = {'frames': len(t), 'footMinZ_m': round(float(foot), 3), 'toeMinZ_m': round(float(toe), 3),
                       'headZ_m': [round(float(head.min()), 3), round(float(head.max()), 3)] if head is not None else None,
                       'jointsWithTranslationKeys': len(tj), 'boneLengthMaxDev_mm': round(max(bl) * 1000, 2) if bl else None,
                       'maxJointRotationPerFrame_deg': round(rot_step, 2),
                       'endPose': P[-1], 'startPose': P[0]}
    return s, res

src = Source()
s, res = check_set(src, 'base\\animations\\npc\\gameplay\\man_big\\corpo\\smg\\mb_corpo_smg_action_patrolling.anims')
for n, r in res.items():
    print(f"{n[:50]:50s} foot {r['footMinZ_m']:+.3f} toe {r['toeMinZ_m']:+.3f} head {r['headZ_m']} boneLenDev {r['boneLengthMaxDev_mm']} mm  maxRot/frame {r['maxJointRotationPerFrame_deg']} deg")
a, b = 'idle_stand__to__ws_corpo_long_gun_pose__turn0__01', 'ws_corpo_long_gun_pose'
if a in res and b in res:
    d = np.linalg.norm(res[a]['endPose'] - res[b]['startPose'], axis=1)
    print(f'continuity {a} end -> {b} start: joint positions differ median {np.median(d)*1000:.1f} mm, max {d.max()*1000:.1f} mm')
