#!/usr/bin/env python3
"""Render selected frames of an animation stored in a .glb (head meshes only), evaluated from the file's channels."""
import os, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyberwolf.validate import read_glb, accessor
from cyberwolf.rig import trs_matrix
from render_preview import draw

path, ai, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]; keep = sys.argv[4].split(','); n_panels = int(sys.argv[5]) if len(sys.argv) > 5 else 5
doc, b = read_glb(path); nodes = doc['nodes']; parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
A = doc['animations'][ai]; tin = accessor(doc, b, A['samplers'][0]['input'])
over = {}
for ch in A['channels']:
    over.setdefault(ch['target']['node'], {})[ch['target']['path']] = accessor(doc, b, A['samplers'][ch['sampler']]['output'])
picks = np.linspace(0, len(tin) - 1, n_panels).astype(int)
fig, axs = plt.subplots(1, n_panels, figsize=(2.8 * n_panels, 3.4), dpi=100); lim = None
for c, f in enumerate(picks):
    G = [None] * len(nodes)
    def g(i):
        if G[i] is None:
            n = nodes[i]; o = over.get(i, {})
            L = trs_matrix(o['translation'][f] if 'translation' in o else n.get('translation', [0, 0, 0]),
                           o['rotation'][f] if 'rotation' in o else n.get('rotation', [0, 0, 0, 1]), n.get('scale', [1, 1, 1]))
            G[i] = L if i not in parent else g(parent[i]) @ L
        return G[i]
    tris = []
    for n in nodes:
        if 'mesh' not in n or 'skin' not in n or not any(k in n['name'] for k in keep): continue
        sk = doc['skins'][n['skin']]
        ibm = accessor(doc, b, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        JM = np.array([g(j) @ ibm[k] for k, j in enumerate(sk['joints'])])
        for p in doc['meshes'][n['mesh']]['primitives']:
            At = p['attributes']; P = accessor(doc, b, At['POSITION']).astype(np.float64); Ph = np.column_stack([P, np.ones(len(P))])
            J = np.concatenate([accessor(doc, b, At[k]).astype(int) for k in sorted(At) if k.startswith('JOINTS_')], 1)
            W = np.concatenate([accessor(doc, b, At[k]).astype(float) for k in sorted(At) if k.startswith('WEIGHTS_')], 1)
            X = sum(W[:, k:k + 1] * np.einsum('nij,nj->ni', JM[J[:, k]], Ph) for k in range(J.shape[1]))[:, :3]
            tris.append(X[accessor(doc, b, p['indices']).reshape(-1, 3)])
    T = np.concatenate(tris)
    if lim is None:
        P = T.reshape(-1, 3); lim = (P.min(0) - 0.02, P.max(0) + 0.02)
    draw(axs[c], T, 0, 1, 2, f't = {float(tin[f]):.1f} s'); axs[c].set_xlim(lim[0][0], lim[1][0]); axs[c].set_ylim(lim[0][1], lim[1][1])
fig.suptitle(A['name'], fontsize=9); fig.tight_layout(); fig.savefig(out); print(out)
