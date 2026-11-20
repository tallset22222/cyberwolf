#!/usr/bin/env python3
"""Animation regression guard (separate baseline: tests/anim_baseline.json; the geometry suite is untouched).
Per clip: exact byte accounting, buffer format, and a fingerprint of decoded model-space joint positions
(0.1 mm grid) at five times. Plausibility gates: toes never below -2 cm; transition continuity where defined."""
import hashlib, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.source import Source
from cyberwolf.rig import Rig
from cyberwolf.anims import AnimSet, sample

SETS = ['base\\animations\\npc\\gameplay\\man_big\\corpo\\smg\\mb_corpo_smg_action_patrolling.anims',             # compressed, man_big (Jackie)
        'base\\animations\\npc\\gameplay\\man_average\\gang\\unarmed\\ma_gang_unarmed_reaction_ranged_supine_to_stand.anims',  # compressed, man_base (NPC)
        'base\\animations\\npc\\gameplay\\woman_average\\gang\\unarmed\\wa_gang_unarmed_reaction_ranged_supine_to_stand.anims']  # SIMD, woman_base (Judy)

def ms_of(rig, L):
    out = np.empty_like(L)
    for j, p in enumerate(rig.parents):
        out[:, j] = L[:, j] if p < 0 else np.einsum('fij,fjk->fik', out[:, p], L[:, j])
    return out

def run():
    src = Source(); cur = {}; gates = []
    for sp in SETS:
        s = AnimSet(src.get(sp)); rig = Rig(src.get(s.rig)); ix = {n: i for i, n in enumerate(rig.names)}
        for a in s.animations:
            t = np.linspace(0, a.duration, 5)
            P = ms_of(rig, sample(a, rig, t))[:, :, :3, 3]
            key = sp.split('\\')[-1] + ':' + a.name
            cur[key] = {'format': a.buffer_class, 'bytesOk': a.consumed == a.declared_bytes,
                        'poses': hashlib.sha256(np.round(P * 10000).astype(np.int64).tobytes()).hexdigest()[:16]}
            toes = min(P[:, ix[n], 2].min() for n in ('LeftToeBase', 'RightToeBase'))
            if toes < -0.02: gates.append((key, f'toes {toes:.3f} m below floor'))
            if not cur[key]['bytesOk']: gates.append((key, 'byte accounting mismatch'))
        for p in s.problems: gates.append((sp.split('\\')[-1] + ':' + str(p[0]), p[1]))
    return cur, gates

if __name__ == '__main__':
    cur, gates = run()
    bp = os.path.join(HERE, 'anim_baseline.json')
    if '--update' in sys.argv or not os.path.exists(bp):
        if gates: print('refusing to write a baseline while gates fail:', gates); sys.exit(1)
        json.dump(cur, open(bp, 'w'), indent=1); print('anim baseline written:', len(cur), 'clips'); sys.exit(0)
    base = json.load(open(bp))
    diff = [k for k in set(base) | set(cur) if base.get(k) != cur.get(k)]
    print(f'{len(cur)} clips | changed vs baseline: {len(diff)} {diff[:5]} | gate failures: {gates[:5]}')
    sys.exit(1 if diff or gates else 0)
