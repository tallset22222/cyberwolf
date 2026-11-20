import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
S = json.load(open('skeleton.json')); R = json.load(open('hiding_regions.json'))['regions']
J = {j['name']: j for j in S['joints']}
pos = {n: np.array(j['rest_position_m']) for n, j in J.items()}
COL = {'core': '#1d3557', 'twist': '#2a9d8f', 'helper': '#8d99ae', 'socket': '#e76f51'}

def skeleton_view(ax, axis, title, flip=1):
    for n, j in J.items():
        if j['parent'] and j['layer'] in ('core',):
            a, b = pos[j['parent']], pos[n]
            ax.plot([a[axis] * flip, b[axis] * flip], [a[1], b[1]], '-', color='#1d3557', lw=1.6, zorder=1)
    for n, j in J.items():
        p = pos[n]
        if j['layer'] == 'socket':
            ax.plot(p[axis] * flip, p[1], 'D', color=COL['socket'], ms=4.5, zorder=4)
            a = pos[j['parent']]; ax.plot([a[axis] * flip, p[axis] * flip], [a[1], p[1]], ':', color=COL['socket'], lw=0.8, zorder=2)
        else:
            ax.plot(p[axis] * flip, p[1], 'o', color=COL[j['layer']], ms={'core': 4, 'twist': 3.2, 'helper': 3}[j['layer']], zorder=3)
    for sm in S['seam_rings']:
        a, b = pos[sm['from_joint']], pos[sm['to_joint']]; c = np.array(sm['rest_position_m'])
        d = np.array([(b - a)[axis] * flip, (b - a)[1]]); d = d / (np.linalg.norm(d) + 1e-9); nrm = np.array([-d[1], d[0]])
        r = 0.075 if 'thigh' in sm['code'] or 'hip' in sm['code'] or sm['code'] == 'waist' else (0.05 if 'neck' in sm['code'] or 'shoulder' in sm['code'] or 'upperarm' in sm['code'] or 'knee' in sm['code'] else 0.04)
        if axis == 2 and sm['code'].endswith('_r'): continue
        p0 = np.array([c[axis] * flip, c[1]]) - nrm * r; p1 = np.array([c[axis] * flip, c[1]]) + nrm * r
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], '-', color='#d62828', lw=2.0, alpha=0.75, zorder=2)
        if axis == 0 and (sm['code'].endswith('_l') or not sm['code'][-2:] in ('_l', '_r')):
            ax.text(p1[0] + 0.01, p1[1], sm['code'][:-2] if sm['code'][-2:] in ('_l','_r') else sm['code'], fontsize=6.5, color='#d62828', va='center')
    ax.set_aspect('equal'); ax.set_title(title, fontsize=10); ax.set_ylim(-0.03, 1.8); ax.grid(alpha=0.15)
    ax.tick_params(labelsize=7)

fig, axs = plt.subplots(1, 2, figsize=(13, 9), gridspec_kw={'width_ratios': [1.6, 1]})
skeleton_view(axs[0], 0, 'Front (viewer sees the character facing them; +X = character left, drawn on the right)')
skeleton_view(axs[1], 2, 'Side (left profile; +Z forward drawn to the right)')
axs[0].set_xlim(-0.75, 0.95)
for lab, c in COL.items(): axs[1].plot([], [], 'D' if lab == 'socket' else 'o', color=c, label={'core': 'core (animated)', 'twist': 'twist (driven)', 'helper': 'helper (procedural)', 'socket': 'socket (attachment)'}[lab])
axs[1].plot([], [], '-', color='#d62828', lw=2, label='seam ring (replacement start)')
axs[1].legend(fontsize=8, loc='upper right')
c = S['counts']
fig.suptitle(f"Cyberwolf skeleton v{S['version']}: {c['core']} core, {c['twist']} twist, {c['helper']} helper joints, {c['socket']} sockets; {len(S['seam_rings'])} seam rings; v0.1 A-pose 1.75 m reference positions (rest pose open, OI-07); seams at v0.2 hm08 fractions", fontsize=11)
fig.tight_layout(); fig.savefig('skeleton_overview.png', dpi=130)

# ---- body-hiding map: stylised capsules per region, front and back ----
def cap(ax, a, b, r, color, label=None):
    a, b = np.array(a), np.array(b); d = b - a; L = np.linalg.norm(d) + 1e-9; d /= L; n = np.array([-d[1], d[0]])
    th = np.linspace(0, np.pi, 12)
    pts = [a + n * r * np.cos(t) - d * r * np.sin(t) for t in th] + [b - n * r * np.cos(t) + d * r * np.sin(t) for t in th]
    ax.add_patch(Polygon(pts, closed=True, fc=color, ec='white', lw=1.2))
    if label is not None:
        m = (a + b) / 2; ax.text(m[0], m[1], label, fontsize=6.5, ha='center', va='center', color='black')
def pt(n, t=None, m=None):
    p = pos[n] if t is None else pos[n] * (1 - t) + pos[m] * t
    return [p[0], p[1]]
bits = {r['name']: r['bit'] for r in R}
cmap = plt.get_cmap('tab20')
def col(name): return cmap(bits[name] % 20)
def lab(name): return f"{bits[name]}\n{name[:-2] if name[-2:] in ('_l', '_r') else name}"
def draw(ax, back=False):
    f = -1 if back else 1
    X = lambda p: [p[0] * f, p[1]]
    # legs
    for s in 'lr':
        segs = [(f'thigh_upper_{s}', pt(f'thigh_{s}'), pt(f'thigh_{s}', .5, f'calf_{s}'), 0.075), (f'thigh_lower_{s}', pt(f'thigh_{s}', .5, f'calf_{s}'), pt(f'thigh_{s}', .92, f'calf_{s}'), 0.06),
                (f'knee_{s}', pt(f'thigh_{s}', .92, f'calf_{s}'), pt(f'calf_{s}', .15, f'foot_{s}'), 0.055), (f'shin_{s}', pt(f'calf_{s}', .15, f'foot_{s}'), pt(f'calf_{s}', .92, f'foot_{s}'), 0.045),
                (f'foot_{s}', pt(f'foot_{s}'), [pt(f'foot_{s}')[0], 0.03], 0.045),
                (f'upperarm_upper_{s}', pt(f'upperarm_{s}', .08, f'lowerarm_{s}'), pt(f'upperarm_{s}', .5, f'lowerarm_{s}'), 0.045), (f'upperarm_lower_{s}', pt(f'upperarm_{s}', .5, f'lowerarm_{s}'), pt(f'upperarm_{s}', .9, f'lowerarm_{s}'), 0.04),
                (f'elbow_{s}', pt(f'upperarm_{s}', .9, f'lowerarm_{s}'), pt(f'lowerarm_{s}', .15, f'hand_{s}'), 0.037), (f'forearm_{s}', pt(f'lowerarm_{s}', .15, f'hand_{s}'), pt(f'lowerarm_{s}', .92, f'hand_{s}'), 0.035),
                (f'hand_{s}', pt(f'lowerarm_{s}', .92, f'hand_{s}'), pt(f'middle_02_{s}'), 0.03)]
        for name, a, b, r in segs: cap(ax, X(a), X(b), r, col(name), lab(name))
        cap(ax, X(pt(f'upperarm_{s}')), X([pt(f'upperarm_{s}')[0] * 0.92, pt(f'upperarm_{s}')[1] + 0.02]), 0.055, col(f'shoulder_cap_{s}'), lab(f'shoulder_cap_{s}'))
    # torso blocks
    if not back:
        for name, a, b, r in (('pelvis_front', [0, 0.97], [0, 0.88], 0.14), ('abdomen', [0, 1.20], [0, 1.0], 0.13), ('chest', [0, 1.40], [0, 1.24], 0.15)):
            cap(ax, a, b, r, col(name), lab(name))
    else:
        for name, a, b, r in (('pelvis_back', [0, 0.97], [0, 0.86], 0.145), ('back_lower', [0, 1.20], [0, 1.0], 0.13), ('back_upper', [0, 1.42], [0, 1.24], 0.15)):
            cap(ax, a, b, r, col(name), lab(name))
    cap(ax, [0, 1.44], [0, 1.49], 0.05, col('neck_lower'), lab('neck_lower')); cap(ax, [0, 1.515], [0, 1.555], 0.045, col('neck_upper'), lab('neck_upper'))
    cap(ax, [0, 1.62], [0, 1.69], 0.085, col('scalp'), lab('scalp'))
    if not back: cap(ax, [0, 1.575], [0, 1.66], 0.06, col('face'), lab('face'))
    for x in (0.08, -0.08): cap(ax, [x, 1.63], [x, 1.66], 0.015, col('ears'), None)
    ax.set_xlim(-0.75, 0.75); ax.set_ylim(-0.02, 1.8); ax.set_aspect('equal'); ax.axis('off')
fig, axs = plt.subplots(1, 2, figsize=(14, 9))
draw(axs[0]); axs[0].set_title('Front (character left on the right)', fontsize=10)
draw(axs[1], back=True); axs[1].set_title('Back (character left on the left)', fontsize=10)
fig.suptitle(f'Cyberwolf body-hiding map v{S["version"]}: {len(R)} regions (bit number shown); boundaries: seam rings and drawn lines (see part 3)', fontsize=11)
fig.tight_layout(); fig.savefig('hiding_map.png', dpi=130)
print('ok')
