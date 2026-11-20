#!/usr/bin/env python3
"""Render an animation stored in a .glb (evaluated from the file's own channels and skins) as a GIF."""
import io, os, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyberwolf.validate import read_glb, accessor
from cyberwolf.rig import trs_matrix
from render_preview import draw

def frames(path, anim_index, step):
    doc, b = read_glb(path); nodes = doc['nodes']; parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    A = doc['animations'][anim_index]; tin = accessor(doc, b, A['samplers'][0]['input'])
    over = {}
    for ch in A['channels']:
        over.setdefault(ch['target']['node'], {})[ch['target']['path']] = accessor(doc, b, A['samplers'][ch['sampler']]['output'])
    prims = []
    for ni, n in enumerate(nodes):
        if 'mesh' in n and doc['meshes'][n['mesh']]['name'].endswith('LOD0') and 'skin' in n:
            sk = doc['skins'][n['skin']]
            ibm = accessor(doc, b, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
            for p in doc['meshes'][n['mesh']]['primitives']:
                At = p['attributes']; P = accessor(doc, b, At['POSITION']).astype(np.float64)
                J = np.concatenate([accessor(doc, b, At[k]).astype(int) for k in sorted(At) if k.startswith('JOINTS_')], 1)
                W = np.concatenate([accessor(doc, b, At[k]).astype(float) for k in sorted(At) if k.startswith('WEIGHTS_')], 1)
                prims.append((sk['joints'], ibm, np.column_stack([P, np.ones(len(P))]), J, W, accessor(doc, b, p['indices']).reshape(-1, 3)))
    for f in range(0, len(tin), step):
        G = [None] * len(nodes)
        def g(i):
            if G[i] is None:
                n = nodes[i]; o = over.get(i, {})
                L = trs_matrix(o['translation'][f] if 'translation' in o else n.get('translation', [0, 0, 0]),
                               o['rotation'][f] if 'rotation' in o else n.get('rotation', [0, 0, 0, 1]), n.get('scale', [1, 1, 1]))
                G[i] = L if i not in parent else g(parent[i]) @ L
            return G[i]
        tris = []
        for joints, ibm, Ph, J, W, I in prims:
            JM = np.array([g(j) @ ibm[k] for k, j in enumerate(joints)])
            X = sum(W[:, k:k + 1] * np.einsum('nij,nj->ni', JM[J[:, k]], Ph) for k in range(J.shape[1]))[:, :3]
            tris.append(X[I])
        yield float(tin[f]), np.concatenate(tris), A['name']

path, ai = sys.argv[1], int(sys.argv[2]); step = int(sys.argv[3]) if len(sys.argv) > 3 else 6
imgs = []
lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
for t, T, name in frames(path, ai, step):                # pass 1: bounds over the whole clip
    P = T.reshape(-1, 3); lo = np.minimum(lo, P.min(0)); hi = np.maximum(hi, P.max(0))
lim = (lo - 0.1, hi + 0.1)
for t, T, name in frames(path, ai, step):
    fig, axs = plt.subplots(1, 2, figsize=(6.4, 4.6), dpi=80)
    draw(axs[0], T, 0, 1, 2, f'front  t={t:.2f}s'); draw(axs[1], T, 2, 1, 0, 'side', flip_h=True)
    axs[0].set_xlim(lim[0][0], lim[1][0]); axs[0].set_ylim(lim[0][1], lim[1][1]); axs[1].set_xlim(-lim[1][2], -lim[0][2]); axs[1].set_ylim(lim[0][1], lim[1][1])
    fig.suptitle(name, fontsize=8); fig.tight_layout(); buf = io.BytesIO(); fig.savefig(buf, format='png'); plt.close(fig)
    imgs.append(Image.open(buf).convert('P', palette=Image.ADAPTIVE))
out = path[:-4] + f'.anim{ai}.gif'
imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=int(1000 * step / 30), loop=0)
print(out, len(imgs), 'frames')
