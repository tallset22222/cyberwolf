#!/usr/bin/env python3
"""Facial regression guard (own baseline: tests/facial_baseline.json). Checks exact byte accounting of the facial
setup buffers for Jackie and Judy, track-list identity with the facial clips' authoring rig, and fingerprints of
evaluated pose deltas (jaw open at 0.5 / 1.0, left blink) and of a facial clip's sampled track values."""
import hashlib, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.source import Source
from cyberwolf.facial import FacialSetup, evaluate, track_values
from cyberwolf.anims import AnimSet
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools")); from cr2w_props import R

SETUPS = {'jackie': 'base\\characters\\main_npc\\jackie_welles\\h0_001_mb_c__jackie_welles\\h0_001_mb_c__jackie_welles_rigsetup.facialsetup',
          'judy': 'base\\characters\\main_npc\\judy\\h0_001_wa_c__judy\\h0_001_wa_c__judy_rigsetup.facialsetup'}
CLIPS = 'base\\animations\\facial\\male_average\\interactive_scene\\generic_average_male_facial_idle.anims'

def tracks_of(src, rig):
    r = R(src.get(rig)); return [r.chunk(i) for i, x in enumerate(r.meta['chunks']) if x['class'] == 'animRig'][0]['trackNames']

def h(a): return hashlib.sha256(np.round(np.asarray(a, dtype=np.float64) * 1e5).astype(np.int64).tobytes()).hexdigest()[:16]

def run():
    src = Source(); cur = {}; gates = []
    clips = AnimSet(src.get(CLIPS)); clip_tracks = tracks_of(src, clips.rig)
    for who, sp in SETUPS.items():
        fs = FacialSetup(src.get(sp)); tn = tracks_of(src, fs.rig)
        if (fs.baked_consumed, fs.main_consumed) != (fs.baked_size, fs.main_size): gates.append((who, 'facial buffer byte mismatch'))
        if tn != clip_tracks: gates.append((who, 'face rig track list differs from clip rig'))
        cur[f'{who}:buffers'] = {'baked': fs.baked_size, 'main': fs.main_size, 'corrective': fs.corrective_size}
        for label, w in {'jaw_open_1': {tn.index('jaw_mid_open'): 1.0}, 'jaw_open_05': {tn.index('jaw_mid_open'): 0.5}, 'blink_l': {tn.index('eye_l_blink'): 1.0}}.items():
            d = evaluate(fs, w); keys = sorted(d)
            cur[f'{who}:{label}'] = {'joints': len(keys), 'deltas': h([np.concatenate([d[k][0], d[k][1]]) for k in keys])}
    from cyberwolf.facial import lipsync_weights
    ls = AnimSet(src.get('base\\localization\\en-us\\lipsync\\base\\quest\\main_quests\\prologue\\q000\\scenes\\q000_kid_03_back_to_bar\\jackie.anims'))
    fsj = FacialSetup(src.get(SETUPS['jackie'])); tnj = tracks_of(src, fsj.rig)
    la = [x for x in ls.animations if x.name == 'f_19751E65C82EF000'][0]; ltv = track_values(la, np.linspace(0, la.duration, 9))
    lw = [lipsync_weights({k: float(v[f]) for k, v in ltv.items()}, tnj) for f in range(9)]
    jaw = tnj.index('jaw_mid_open')
    cur['lipsync:f_19751E65C82EF000'] = {'jawOpenWeights': [round(w.get(jaw, 0.0), 4) for w in lw],
                                         'deltas': h([np.concatenate([d[k][0], d[k][1]]) for d in [evaluate(fsj, lw[4])] for k in sorted(d)])}
    a = [x for x in clips.animations if x.name == 'idle__joy__male'][0]
    tv = track_values(a, np.linspace(0, a.duration, 9))
    cur['clip:idle__joy__male'] = {'tracks': len(tv), 'values': h([tv[k] for k in sorted(tv)])}
    if max(v.max() for v in tv.values()) > 1.0001 or min(v.min() for v in tv.values()) < -0.0001: gates.append(('clip', 'track weight outside [0, 1]'))
    return cur, gates

if __name__ == '__main__':
    cur, gates = run(); bp = os.path.join(HERE, 'facial_baseline.json')
    if '--update' in sys.argv or not os.path.exists(bp):
        if gates: print('refusing to write baseline, gates fail:', gates); sys.exit(1)
        json.dump(cur, open(bp, 'w'), indent=1); print('facial baseline written:', list(cur)); sys.exit(0)
    base = json.load(open(bp)); diff = [k for k in set(base) | set(cur) if base.get(k) != cur.get(k)]
    print(f'{len(cur)} facial checks | changed: {diff} | gate failures: {gates}'); sys.exit(1 if diff or gates else 0)
