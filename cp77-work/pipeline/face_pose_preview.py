#!/usr/bin/env python3
"""Render a character's head under facial pose weights, evaluated from its facial setup, using the GLB's own skins."""
import io, os, sys, json
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyberwolf.validate import read_glb, accessor
from cyberwolf.rig import trs_matrix, quat_to_mat, Rig
from cyberwolf.facial import FacialSetup, evaluate
from cyberwolf.source import Source
from render_preview import draw

def head_tris(doc, b, deltas_by_name, keep):
    nodes = doc['nodes']; parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    G = [None] * len(nodes)
    def g(i):
        if G[i] is None:
            n = nodes[i]; L = trs_matrix(n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1]), n.get('scale', [1, 1, 1]))
            d = deltas_by_name.get(n.get('name'))
            if d is not None:
                D = np.eye(4); D[:3, :3] = quat_to_mat(d[0])
                L = L.copy(); L[:3, :3] = L[:3, :3] @ D[:3, :3]; L[:3, 3] = L[:3, 3] + d[1]
            G[i] = L if i not in parent else g(parent[i]) @ L
        return G[i]
    tris = []
    for n in nodes:
        if 'mesh' not in n or 'skin' not in n or not any(k in n['name'] for k in keep): continue
        sk = doc['skins'][n['skin']]
        ibm = accessor(doc, b, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        JM = np.array([g(j) @ ibm[k] for k, j in enumerate(sk['joints'])])
        for p in doc['meshes'][n['mesh']]['primitives']:
            A = p['attributes']; P = accessor(doc, b, A['POSITION']).astype(np.float64); Ph = np.column_stack([P, np.ones(len(P))])
            J = np.concatenate([accessor(doc, b, A[k]).astype(int) for k in sorted(A) if k.startswith('JOINTS_')], 1)
            W = np.concatenate([accessor(doc, b, A[k]).astype(float) for k in sorted(A) if k.startswith('WEIGHTS_')], 1)
            X = sum(W[:, k:k + 1] * np.einsum('nij,nj->ni', JM[J[:, k]], Ph) for k in range(J.shape[1]))[:, :3]
            tris.append(X[accessor(doc, b, p['indices']).reshape(-1, 3)])
    return np.concatenate(tris)

if __name__ == '__main__':
    glb, setup, out = sys.argv[1], sys.argv[2], sys.argv[3]; keep = sys.argv[4].split(','); poses = json.loads(sys.argv[5])
    src = Source(); fs = FacialSetup(src.get(setup)); rig = Rig(src.get(fs.rig))
    from cr2w_props import R
    r = R(src.get(fs.rig)); tn = [r.chunk(i) for i, x in enumerate(r.meta['chunks']) if x['class'] == 'animRig'][0]['trackNames']
    doc, b = read_glb(glb)
    panels = [('neutral', {})] + [(k, {tn.index(t): w for t, w in v.items()}) for k, v in poses.items()]
    fig, axs = plt.subplots(2, len(panels), figsize=(3.0 * len(panels), 6.2), dpi=90)
    lim = None; stats = {}
    for c, (label, wts) in enumerate(panels):
        d = evaluate(fs, wts)
        T = head_tris(doc, b, {rig.names[j]: v for j, v in d.items()}, keep)
        if lim is None:
            P = T.reshape(-1, 3); lim = (P.min(0) - 0.01, P.max(0) + 0.01); T0 = T
        stats[label] = {'jointsMoved': len(d), 'maxVertexShift_mm': round(float(np.linalg.norm(T - T0, axis=2).max()) * 1000, 2)}
        draw(axs[0, c], T, 0, 1, 2, f'{label}  (front)'); axs[0, c].set_xlim(lim[0][0], lim[1][0]); axs[0, c].set_ylim(lim[0][1], lim[1][1])
        draw(axs[1, c], T, 2, 1, 0, 'side', flip_h=True); axs[1, c].set_xlim(-lim[1][2], -lim[0][2]); axs[1, c].set_ylim(lim[0][1], lim[1][1])
    fig.tight_layout(); fig.savefig(out); print(out, json.dumps(stats))
