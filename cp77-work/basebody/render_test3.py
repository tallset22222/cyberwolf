import sys, os, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
def front_cut(V, a, b, d, ds):
    return -1e9 if FRONT is None else FRONT[(a, b)]
FRONT = None
def draw(ax, V, Q, lab, view, names, cmap, xlim=None, ylim=None, title='', boundary=None):
    # view: (horizontal axis index, sign, depth axis index, sign)
    h, hs, d, ds = view
    P = V[Q]; X = np.stack([hs * P[..., h], P[..., 1]], -1); depth = ds * P[..., d].mean(1)
    e1 = X[:, 1] - X[:, 0]; e2 = X[:, 2] - X[:, 0]; facing = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    o = np.argsort(depth)
    cols = np.array([cmap[names.index(l)] for l in lab])
    shade = np.full((len(Q), 1), 1.0)
    pc = PolyCollection(X[o], facecolors=cols[o] * shade[o], edgecolors=(0, 0, 0, 0.08), linewidths=0.1)
    ax.add_collection(pc); ax.set_aspect('equal')
    if boundary is not None:   # region boundaries drawn as lines (front-most half only, approximate)
        for (a, b), loop in boundary:
            pa = np.array([hs * V[a, h], V[a, 1]]); pb = np.array([hs * V[b, h], V[b, 1]])
            if ds * (V[a, d] + V[b, d]) / 2 >= front_cut(V, a, b, d, ds):
                ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color='k' if loop else '#d00', lw=0.9 if loop else 1.1, solid_capstyle='round')
    ax.set_xlim(*(xlim or (X[..., 0].min(), X[..., 0].max()))); ax.set_ylim(*(ylim or (X[..., 1].min(), X[..., 1].max())))
    ax.set_title(title, fontsize=9); ax.axis('off')
def render(V, Q, lab, path):
    names = sorted(set(lab)); rng = np.random.default_rng(3)
    cmap = [plt.cm.tab20(i % 20)[:3] if i < 20 else tuple(rng.uniform(0.2, 0.95, 3)) for i in range(len(names))]
    cmap = [np.array(c) for c in cmap]
    fig, axs = plt.subplots(1, 6, figsize=(24, 9), gridspec_kw={'width_ratios': [3, 3, 1.6, 1.4, 1.4, 1.4]})
    draw(axs[0], V, Q, lab, (0, -1, 2, 1), names, cmap, title='front')
    draw(axs[1], V, Q, lab, (0, 1, 2, -1), names, cmap, title='back')
    draw(axs[2], V, Q, lab, (2, 1, 0, 1), names, cmap, title='left side')
    hl = (-0.13, 0.13); hy = (1.36, 1.70)
    draw(axs[3], V, Q, lab, (0, -1, 2, 1), names, cmap, hl, hy, 'head front')
    draw(axs[4], V, Q, lab, (2, 1, 0, 1), names, cmap, (-0.14, 0.2), hy, 'head left')
    draw(axs[5], V, Q, lab, (0, 1, 2, -1), names, cmap, hl, hy, 'head back')
    handles = [plt.Rectangle((0, 0), 1, 1, color=cmap[i]) for i in range(len(names))]
    fig.legend(handles, names, loc='lower center', ncol=11, fontsize=8)
    plt.tight_layout(rect=(0, 0.07, 1, 1)); plt.savefig(path, dpi=110); plt.close()

def visible_edges(V, Q, edges, view_dir, eps=0.004):
    """Edges whose midpoint is not occluded along view_dir (simple z-buffer on a 2 mm raster of face centroids)."""
    import collections
    h = {0: 0, 2: 2}
    return edges

def render_regions(V, Q, lab, fe, loop_edges, path):
    names = sorted(set(lab))
    base = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#8a63d2', '#b05c3b']
    import colorsys
    cmap = []
    for i in range(len(names)):
        c = matplotlib.colors.to_rgb(base[i % 8]); hh, l, s_ = colorsys.rgb_to_hls(*c)
        l = [0.62, 0.45, 0.75, 0.35][(i // 8) % 4]; cmap.append(np.array(colorsys.hls_to_rgb(hh, l, s_ * 0.85)))
    bnd = []
    for e, fs in fe.items():
        if len(fs) == 2 and lab[fs[0]] != lab[fs[1]]: bnd.append((e, e in loop_edges))
    fig, axs = plt.subplots(1, 5, figsize=(26, 10), gridspec_kw={'width_ratios': [3, 3, 1.6, 1.5, 1.5]})
    # depth-tested boundary drawing: keep edges whose depth is within 6 mm of the max depth at that 2D cell
    for ax, view, title, xl, yl in [(axs[0], (0, -1, 2, 1), 'front', None, None), (axs[1], (0, 1, 2, -1), 'back', None, None),
                                     (axs[2], (2, 1, 0, 1), 'left side', None, None), (axs[3], (0, -1, 2, 1), 'head front', (-0.13, 0.13), (1.36, 1.70)),
                                     (axs[4], (2, 1, 0, 1), 'head left', (-0.14, 0.2), (1.36, 1.70))]:
        h, hs, d, ds = view
        cell = 0.006; P = V[Q].mean(1); key = lambda x, y: (int(np.floor(x / cell)), int(np.floor(y / cell)))
        zbuf = {}
        for p in P:
            k = key(hs * p[h], p[1]); zbuf[k] = max(zbuf.get(k, -9), ds * p[d])
        vis = []
        for (a, b), loop in bnd:
            m = (V[a] + V[b]) / 2; k = key(hs * m[h], m[1])
            if ds * m[d] >= zbuf.get(k, -9) - 0.012: vis.append(((a, b), loop))
        draw(ax, V, Q, lab, view, names, cmap, xl, yl, title, boundary=vis)
    handles = [plt.Rectangle((0, 0), 1, 1, color=cmap[i]) for i in range(len(names))]
    handles += [plt.Line2D([0], [0], color='k', lw=1.5), plt.Line2D([0], [0], color='#d00', lw=1.5)]
    fig.legend(handles, names + ['boundary on a real edge loop', 'boundary from a geometric rule (not a loop)'], loc='lower center', ncol=12, fontsize=8.5, frameon=False)
    plt.tight_layout(rect=(0, 0.07, 1, 1)); plt.savefig(path, dpi=100); plt.close()

def render_motion(partB, path):
    seams = list(partB.keys())
    fig, axs = plt.subplots(1, 2, figsize=(14, 6.5), sharey=True)
    y = np.arange(len(seams))[::-1]
    C = {'LBS': '#2a78d6', 'DQS': '#eb6834'}
    for m, off in (('LBS', 0.12), ('DQS', -0.12)):
        need = [partB[s][m]['rigid_best']['overlap_needed_mm'] for s in seams]
        clr = [partB[s][m]['weight_transfer']['min_clearance_mm_of_2mm_shell'] for s in seams]
        axs[0].scatter(np.minimum(need, 80), y + off, s=46, color=C[m], label=m, zorder=3, edgecolor='white', linewidth=1.5)
        for yy, v in zip(y + off, need):
            if v > 80: axs[0].annotate(f'{v:.0f}', (80, yy), xytext=(4, -3), textcoords='offset points', fontsize=8, color='#555')
        axs[1].scatter(clr, y + off, s=46, color=C[m], label=m, zorder=3, edgecolor='white', linewidth=1.5)
    axs[0].axvline(15, color='#333', lw=1, ls='--'); axs[0].text(15.5, len(seams) - 0.4, '15 mm (v0.1)', fontsize=8.5, color='#333')
    axs[0].set_xlim(0, 88); axs[0].set_xlabel('overlap needed, mm  (seam slide + 5 mm margin; cuff rigid to the best single bone)')
    axs[1].axvline(0, color='#333', lw=1, ls='--'); axs[1].axvline(2, color='#bbb', lw=0.8)
    axs[1].text(0.05, len(seams) - 0.4, 'skin pokes through  <  0', fontsize=8.5, color='#333')
    axs[1].set_xlabel('worst clearance of a 2 mm cuff shell carrying the body weights, mm'); axs[1].set_xlim(-2.2, 2.2)
    axs[0].set_yticks(y); axs[0].set_yticklabels([f"{s}{'  (option A)' if partB[s]['kind']=='A' else ''}" for s in seams], fontsize=9)
    for ax in axs:
        ax.grid(axis='x', color='#eee'); ax.spines[['top', 'right']].set_visible(False); ax.tick_params(colors='#555')
    axs[0].set_title('Rigid cuff: is 15 mm overlap enough?', fontsize=11, loc='left'); axs[1].set_title('Weight-transfer cuff: does skin poke through?', fontsize=11, loc='left')
    axs[1].legend(frameon=False, loc='lower left')
    plt.tight_layout(); plt.savefig(path, dpi=110); plt.close()
