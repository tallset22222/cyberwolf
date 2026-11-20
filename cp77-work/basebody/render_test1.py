import json, os, sys, numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test1_topology import run
V, Q, closed, out, M = run()
COL = {'PASS': (40, 160, 70), 'MOVE': (235, 140, 20), 'FAIL': (210, 40, 40)}
def view(V, mode):
    if mode == 'front': return V[:, 0], V[:, 1], V[:, 2]
    if mode == 'back': return -V[:, 0], V[:, 1], -V[:, 2]
    return V[:, 2], V[:, 1], -V[:, 0]  # left side: +Z to the right
def render(mode, fn, res=1100, W=900):
    x, y, z = view(V, mode); s = res / 1.85; ox, oy = W / 2, res * 0.06 + (V[:, 1].max()) * s
    X, Y = x * s + ox, oy - y * s
    img = Image.new('RGB', (W, res), (244, 244, 244)); dr = ImageDraw.Draw(img)
    T = Q; tz = z[T].mean(1)
    P3 = np.stack([x, y, z], 1); n = np.cross(P3[T[:, 1]] - P3[T[:, 0]], P3[T[:, 2]] - P3[T[:, 0]]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    vis = n[:, 2] > 0
    L = np.array([0.3, 0.5, 0.8]); L /= np.linalg.norm(L); sh = np.clip(0.35 + 0.65 * np.clip(n @ L, 0, 1), 0, 1)
    for i in np.where(vis)[0][np.argsort(tz[vis])]:
        g = int(120 + 110 * sh[i]); dr.polygon([(X[j], Y[j]) for j in T[i]], fill=(g, g, g), outline=(g - 25, g - 25, g - 25))
    for r in out:
        if r['best'] is None: continue
        st = r['status'].split(':')[0]; lp = closed[r['best']['loop']]
        for e in lp['edges']:
            a, b = e
            if (z[a] + z[b]) / 2 < np.percentile(z[lp['verts']], 35): continue  # draw the near half more strongly
            dr.line([(X[a], Y[a]), (X[b], Y[b])], fill=COL[st], width=4)
        for e in lp['edges']:
            a, b = e; dr.line([(X[a], Y[a]), (X[b], Y[b])], fill=COL[st], width=1)
        if mode == 'front' and not r['seam'].endswith('_r'):
            c = np.mean(V[lp['verts']], 0); cx, cy = c[0] * s + ox, oy - c[1] * s
            dr.text((cx + 40 if c[0] >= 0 else cx - 150, cy - 6), f"{r['seam'].replace('_l','')}: {st}", fill=COL[st])
    img.save(fn)
for m in ('front', 'side', 'back'): render(m, f'reports/test1_{m}.png')
ims = [Image.open(f'reports/test1_{m}.png') for m in ('front', 'side', 'back')]
S = Image.new('RGB', (2700, 1100), (244, 244, 244)); [S.paste(im, (900 * i, 0)) for i, im in enumerate(ims)]; S.save('reports/test1_seams.png')
print('ok')
