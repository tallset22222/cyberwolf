"""Step 5: chest secondary motion (default system, dangle node 54) on the reconstructed muscle layer.

Analysis only: writes pipeline_out/secondary/<name>.json, .md and plots. Nothing is written into GLBs.
"""
import argparse
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyberwolf.source import Source, WORK  # noqa: E402
from cyberwolf.animgraph import AnimGraph, dependency_cone  # noqa: E402
from cyberwolf.rig import Rig, trs_matrix  # noqa: E402
from cyberwolf import deform, secondary  # noqa: E402
from cyberwolf.anims import AnimSet, sample  # noqa: E402

D = 'base\\characters\\base_entities\\woman_base\\deformations_rigs\\'
BODY_RIG = 'base\\characters\\base_entities\\woman_base\\woman_base.rig'
CLIPS = 'base\\animations\\npc\\gameplay\\woman_average\\gang\\unarmed\\wa_gang_unarmed_reaction_ranged_supine_to_stand.anims'
FPS = 30.0
DANGLE_NODE = 54


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def rigid_profiles():
    """name -> (root 4x4 [F], motion_end_seconds). Character root in world, Z up."""
    out = {}
    t = np.arange(0, 3.0, 1 / FPS)
    out['stationary'] = (np.repeat(np.eye(4)[None], len(t), 0), 0.0)

    def trans(p):
        M = np.repeat(np.eye(4)[None], len(p), 0)
        M[:, :3, 3] = p
        return M
    # walk-speed start / stop along +Y (1.5 m/s reached in 0.4 s, held 1 s, stopped in 0.4 s), then 2 s still
    t = np.arange(0, 4.0, 1 / FPS)
    vel = 1.5 * (smoothstep(t / 0.4) - smoothstep((t - 1.4) / 0.4))
    y = np.cumsum(vel) / FPS
    out['start_stop'] = (trans(np.stack([0 * t, y, 0 * t], 1)), 1.8)
    # hard stop: 4 m/s to 0 in 0.15 s (sprint stop)
    vel = 4.0 * (1 - smoothstep((t - 0.5) / 0.15))
    out['hard_stop'] = (trans(np.stack([0 * t, np.cumsum(vel) / FPS, 0 * t], 1)), 0.65)
    # running bob: 3 cm vertical at 2.6 Hz, faded in/out smoothly (0-0.3 s, 1.7-2.0 s), then still
    env = smoothstep(t / 0.3) * (1 - smoothstep((t - 1.7) / 0.3))
    z = 0.03 * np.sin(2 * np.pi * 2.6 * t) * env
    out['run_bob'] = (trans(np.stack([0 * t, 0 * t, z], 1)), 2.0)
    # jump: 0.3 m ballistic hop, landing absorbed in 0.1 s
    tj = np.clip(t - 0.3, 0, None)
    vz0 = np.sqrt(2 * 9.81 * 0.3)
    z = np.where(t < 0.3, 0, np.maximum(vz0 * tj - 0.5 * 9.81 * tj ** 2, 0))
    out['jump_land'] = (trans(np.stack([0 * t, 0 * t, z], 1)), 0.3 + 2 * vz0 / 9.81 + 0.1)
    # turn: 90 degree yaw in 0.5 s
    yaw = np.radians(90) * smoothstep((t - 0.3) / 0.5)
    M = np.repeat(np.eye(4)[None], len(t), 0)
    M[:, 0, 0], M[:, 0, 1], M[:, 1, 0], M[:, 1, 1] = np.cos(yaw), -np.sin(yaw), np.sin(yaw), np.cos(yaw)
    out['turn_90'] = (M, 0.8)
    return out


def accel(pos, dt):
    return np.gradient(np.gradient(pos, dt, axis=0), dt, axis=0)


def chest_targets_rigid(gd, rd, cone, names, roots, cfg):
    pose = deform.evaluate(gd, rd, cone, None, cfg)
    local = np.stack([pose.ms[n] for n in names])
    return np.einsum('fij,njk->fnik', roots, local)


def chest_targets_clip(gd, rd, cone, names, body_rig, anim, cfg):
    t = np.arange(0, anim.duration, 1 / FPS)
    L = sample(anim, body_rig, t)
    ms = np.empty_like(L)
    for j, p in enumerate(body_rig.parents):
        ms[:, j] = L[:, j] if p < 0 else np.einsum('fij,fjk->fik', ms[:, p], L[:, j])
    tg = np.empty((len(t), len(names), 4, 4))
    for f in range(len(t)):
        body = {n: ms[f, j] for j, n in enumerate(body_rig.names)}
        pose = deform.evaluate(gd, rd, cone, body, cfg)
        tg[f] = np.stack([pose.ms[n] for n in names])
    root = ms[:, body_rig.index('Root'), :3, 3]
    hips = ms[:, body_rig.index('Hips'), :3, 3]
    return tg, root, hips, t


def metrics(x, tgt, motion_end, dt, tol_mm=0.5):
    d = np.linalg.norm(x - tgt[:, :, :3, 3], axis=2) * 1000  # [F, N] mm
    dm = d.max(1)
    i_end = int(np.ceil(motion_end / dt))
    rec = None
    if i_end < len(dm):
        after = dm[i_end:]
        settled = np.where(after >= tol_mm)[0]
        rec = 0.0 if len(settled) == 0 else (None if settled[-1] == len(after) - 1 else (settled[-1] + 1) * dt)
    return {'max_disp_mm': float(np.nanmax(dm)), 'rms_disp_mm': float(np.sqrt(np.nanmean(d ** 2))),
            'final_disp_mm': float(dm[-1]), 'first_frame_disp_mm': float(dm[0]),
            'recovery_s_to_%.1fmm' % tol_mm: rec, 'disp_series_mm': dm.round(3).tolist()}


CONFIGS = {
    # current defaults (WolvenKit/corpus-backed): gravity 9.81, substep 0.01, 1 iteration, character-frame particles
    'default': {},
    'default_world': {'world_space': True},
    'default_extoff': {'ext': False},
    'default_soft': {'pull_scale': 0.5, 'damping_scale': 0.5},
    'default_stiff': {'pull_scale': 2.0, 'damping_scale': 2.0},
    'default_dampabs': {'damping_relative': False},
    'default_unconstrained': {'ellipsoid': 'off', 'links_off': True},
    'default_sphere': {'ellipsoid': 'offset_sphere'},
    'default_ignore_offset': {'ellipsoid': 'ignore_offset'},
    'gravity_off': {'gravity': 0.0},
    # the previous step-5 run, reproduced for continuity (superseded assumptions)
    'prev_G0_needle': {'gravity': 0.0, 'world_space': True, 'substep': 1 / 60, 'iterations': 4},
    'prev_G1_needle': {'gravity': 9.81, 'world_space': True, 'substep': 1 / 60, 'iterations': 4},
}


def setup(src):
    gb = AnimGraph(src.get(D + 'woman_base_breasts.animgraph'))
    sysd = secondary.load_system(gb, gb.x[DANGLE_NODE]['dangleConstraint']['handle'])
    return sysd


def stage_targets(src, out_dir):
    gd = AnimGraph(src.get(D + 'woman_base_deformations.animgraph'))
    rd = Rig(src.get(D + 'woman_base_deformations.rig'))
    sysd = setup(src)
    names = sysd['names']
    cone, _ = dependency_cone(gd, gd.post_order(2), names)
    dt = 1 / FPS
    profiles = rigid_profiles()
    tg = {k: chest_targets_rigid(gd, rd, cone, names, R, {}) for k, (R, _) in profiles.items()}
    roots = {k: R for k, (R, _) in profiles.items()}
    racc = {k: accel(R[:, :3, 3], dt) for k, (R, _) in profiles.items()}
    ends = {k: e for k, (_, e) in profiles.items()}
    clips = {}
    s = AnimSet(src.get(CLIPS))
    body_rig = Rig(src.get(BODY_RIG))
    for an in s.animations:
        if an.name in ('supine_to_stand_0', 'supine_to_stand_90'):
            t_, root, hips, t = chest_targets_clip(gd, rd, cone, names, body_rig, an, {})
            hold = int(2 * FPS)  # hold the final standing frame 2 s to observe recovery
            t_ = np.concatenate([t_, np.repeat(t_[-1:], hold, 0)])
            root = np.concatenate([root, np.repeat(root[-1:], hold, 0)])
            tg[an.name] = t_
            roots[an.name] = np.repeat(np.eye(4)[None], len(t_), 0)  # clip Root bone never moves (root_travel 0)
            racc[an.name] = accel(root, dt)
            ends[an.name] = float(t[-1])
            clips[an.name] = {'frames': len(t), 'duration_s': float(an.duration), 'root_travel_m': float(np.linalg.norm(root[-1] - root[0])),
                              'hips_travel_m': float(np.linalg.norm(hips[-1] - hips[0])),
                              'root_acc_max': float(np.linalg.norm(racc[an.name], axis=1).max()),
                              'target_speed_max_mps': float(np.linalg.norm(np.gradient(t_[:, :, :3, 3], dt, axis=0), axis=2).max())}
    np.savez_compressed(os.path.join(out_dir, '_targets.npz'), **{'T_' + k: v for k, v in tg.items()}, **{'A_' + k: v for k, v in racc.items()}, **{'R_' + k: v for k, v in roots.items()})
    json.dump({'ends': ends, 'clips': clips, 'cone_nodes': len(cone)}, open(os.path.join(out_dir, '_targets.json'), 'w'), indent=1)
    print('targets cached:', list(tg), clips)


def load_targets(out_dir):
    z = np.load(os.path.join(out_dir, '_targets.npz'))
    meta = json.load(open(os.path.join(out_dir, '_targets.json')))
    tg = {k[2:]: z[k] for k in z.files if k.startswith('T_')}
    racc = {k[2:]: z[k] for k in z.files if k.startswith('A_')}
    roots = {k[2:]: z[k] for k in z.files if k.startswith('R_')}
    return tg, racc, meta, roots


def run_one(sysd, T, Rt, acc, p, dt):
    """Simulate in the world or the character frame; returns world positions and diagnostics."""
    P = dict(secondary.ASSUMED); P.update({k: v for k, v in p.items() if k != 'links_off'})
    sd = dict(sysd, links=[] if p.get('links_off') else sysd['links'])
    if P['world_space']:
        return secondary.simulate(sd, T, dt, acc, P)
    inv = np.linalg.inv(Rt)
    Tl = np.einsum('fij,fnjk->fnik', inv, T)
    Rm = Rt[:, :3, :3]
    acc_l = np.einsum('fji,fj->fi', Rm, acc)
    P['gravity_frames'] = np.einsum('fji,j->fi', Rm, np.array([0, 0, -1.0]))
    x, d = secondary.simulate(sd, Tl, dt, acc_l, P)
    xw = np.einsum('fij,fnj->fni', Rm, x) + Rt[:, None, :3, 3]
    return xw, d


def stage_run(src, out_dir, cfg_names):
    sysd = setup(src)
    tg, racc, meta, roots = load_targets(out_dir)
    dt = 1 / FPS
    os.makedirs(os.path.join(out_dir, '_runs'), exist_ok=True)
    for cn in cfg_names:
        p = CONFIGS[cn]
        res, series = {}, {}
        for pn, T in tg.items():
            x, dg = run_one(sysd, T, roots[pn], racc[pn], p, dt)
            m = metrics(x, T, meta['ends'][pn], dt)
            series['X_' + pn] = x
            res[pn] = {**{k: v for k, v in m.items() if k != 'disp_series_mm'}, 'disp_series_mm': m['disp_series_mm'],
                       **{k: dg[k] for k in ('finite', 'pre_link_violation', 'post_link_violation', 'pre_ellipsoid_q',
                                             'post_ellipsoid_q', 'ellipsoid_contact_frac', 'substeps', 'iterations')}}
            r = res[pn]
            print('%-18s %-20s max %7.2f rms %6.2f final %6.3f mm rec %s  link %.3f->%.3f  q %.2f->%.3f %s' % (
                cn, pn, r['max_disp_mm'], r['rms_disp_mm'], r['final_disp_mm'], r['recovery_s_to_0.5mm'],
                r['pre_link_violation'], r['post_link_violation'], r['pre_ellipsoid_q'], r['post_ellipsoid_q'], '' if r['finite'] else 'NaN!'))
        json.dump({'config': p, 'params': dg['params'], 'results': res}, open(os.path.join(out_dir, '_runs', cn + '.json'), 'w'), default=str)
        np.savez_compressed(os.path.join(out_dir, '_runs', cn + '.npz'), **series)


def stage_drift(src, out_dir):
    sysd = setup(src)
    tg, racc, meta, roots = load_targets(out_dir)
    dt = 1 / FPS
    rows = []
    for grav, ell, proj, ws in itertools.product((0.0, 9.81), ('offset_needle', 'offset_sphere', 'ignore_offset', 'off'), ('closest', 'radial'), (False, True)):
        if ell == 'off' and proj == 'radial':
            continue
        p = {'gravity': grav, 'ellipsoid': ell, 'ellipsoid_projection': proj, 'world_space': ws}
        T = np.concatenate([tg['stationary']] * 3)  # 9 s still
        x, dg = run_one(sysd, T, np.repeat(np.eye(4)[None], len(T), 0), np.zeros((len(T), 3)), p, dt)
        m = metrics(x, T, 0.0, dt)
        rows.append({'params': p, 'max_disp_mm': m['max_disp_mm'], 'final_disp_mm': m['final_disp_mm'],
                     'disp_at_1s_mm': m['disp_series_mm'][30], 'disp_at_9s_mm': m['disp_series_mm'][-1],
                     'post_ellipsoid_q': dg['post_ellipsoid_q'], 'contact_frac': dg['ellipsoid_contact_frac'], 'finite': dg['finite']})
        print(p, 'max %.3f  1s %.3f  9s %.3f mm' % (m['max_disp_mm'], rows[-1]['disp_at_1s_mm'], rows[-1]['disp_at_9s_mm']))
    json.dump(rows, open(os.path.join(out_dir, '_runs', '_drift.json'), 'w'), indent=1)


def stage_report(src, out_dir, name):
    sysd = setup(src)
    tg, racc, meta, roots = load_targets(out_dir)
    runs, sims = {}, {}
    for cn in CONFIGS:
        fp = os.path.join(out_dir, '_runs', cn + '.json')
        if not os.path.exists(fp):
            continue
        r = json.load(open(fp))
        z = np.load(os.path.join(out_dir, '_runs', cn + '.npz'))
        runs[cn] = {'config': r['config'], 'results': {pn: {k: v for k, v in d.items() if k != 'disp_series_mm'} for pn, d in r['results'].items()}}
        for pn, d in r['results'].items():
            sims[(cn, pn)] = (z['X_' + pn], d['disp_series_mm'])
    report = {'system': {'dangle_node': DANGLE_NODE, 'particles': sysd['names'], 'damping': sysd['damping'].tolist(),
                         'pull': sysd['pull'].tolist(), 'links': len(sysd['links']), 'ellipsoids': len(sysd['ellipsoids']),
                         'cones': len(sysd['cones']), 'stated': sysd['stated']},
              'assumed_defaults': secondary.ASSUMED, 'muscle_layer': 'literal (deform.py defaults)', 'fps': FPS,
              'profiles': meta, 'zero_acceleration': json.load(open(os.path.join(out_dir, '_runs', '_drift.json'))),
              'runs': runs}
    json.dump(report, open(os.path.join(out_dir, f'{name}.json'), 'w'), indent=1, default=str)
    plot(sims, tg, meta['ends'], sysd['names'], 1 / FPS, out_dir, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['targets', 'drift', 'run', 'report'])
    ap.add_argument('--configs', nargs='*', default=list(CONFIGS))
    ap.add_argument('--name', default='judy_chest')
    a = ap.parse_args()
    src = Source()
    out_dir = os.path.join(WORK, 'pipeline_out', 'secondary')
    os.makedirs(os.path.join(out_dir, '_runs'), exist_ok=True)
    if a.stage == 'targets':
        stage_targets(src, out_dir)
    elif a.stage == 'drift':
        stage_drift(src, out_dir)
    elif a.stage == 'run':
        stage_run(src, out_dir, a.configs)
    else:
        stage_report(src, out_dir, a.name)


def plot(sims, tg, ends, names, dt, out_dir, name):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    profs = list(tg)
    fig, axs = plt.subplots(len(profs), 2, figsize=(13, 2.3 * len(profs)), squeeze=False)
    i_l = names.index('l_chest_front_C_bot_out_JNT')
    for r, pn in enumerate(profs):
        ax = axs[r][0]
        for cn, col in (('default', '#d1495b'), ('default_world', '#1f6fb4'), ('default_unconstrained', '#999999')):
            ser = sims[(cn, pn)][1]
            ax.plot(np.arange(len(ser)) * dt, ser, color=col, lw=1.3, label=cn)
        ax.axvline(ends[pn], color='k', lw=0.6, ls=':')
        ax.set_title(f'{pn}: max particle offset from procedural target', fontsize=9)
        ax.set_ylabel('mm', fontsize=8)
        ax.tick_params(labelsize=7)
        if r == 0:
            ax.legend(fontsize=7)
        ax = axs[r][1]
        T = tg[pn][:, i_l, :3, 3]
        for cn, col in (('default', '#d1495b'), ('default_world', '#1f6fb4')):
            x = sims[(cn, pn)][0][:, i_l]
            ax.plot(np.arange(len(x)) * dt, (x[:, 2] - T[:, 2]) * 1000, color=col, lw=1.3, label=cn + ' (vertical)')
            ax.plot(np.arange(len(x)) * dt, (x[:, 1] - T[:, 1]) * 1000, color=col, lw=0.9, ls='--', label=cn + ' (Y)')
        ax.axhline(0, color='k', lw=0.5)
        ax.set_title(f'{pn}: l_chest_front_C_bot_out simulated minus unsimulated', fontsize=9)
        ax.tick_params(labelsize=7)
        if r == 0:
            ax.legend(fontsize=7, ncol=2)
    axs[-1][0].set_xlabel('s', fontsize=8)
    axs[-1][1].set_xlabel('s', fontsize=8)
    fig.tight_layout()
    fp = os.path.join(out_dir, f'{name}_profiles.png')
    fig.savefig(fp, dpi=110)
    print('wrote', fp)


if __name__ == '__main__':
    main()
