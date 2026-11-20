#!/usr/bin/env python3
"""Render front and side preview images of an exported .glb (LOD0, skinned with the exported joints)."""
import sys, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyberwolf.validate import read_glb, accessor, node_globals


def axis_rot(axis, deg):
    a = np.radians(deg); c, s_ = np.cos(a), np.sin(a)
    R = {'x': [[1, 0, 0], [0, c, -s_], [0, s_, c]], 'y': [[c, 0, s_], [0, 1, 0], [-s_, 0, c]], 'z': [[c, -s_, 0], [s_, c, 0], [0, 0, 1]]}[axis]
    M = np.eye(4); M[:3, :3] = R; return M


def posed_globals(doc, pose):
    """Node globals with extra local rotations applied: pose = {node name: [(axis, degrees), ...]}."""
    from cyberwolf.rig import trs_matrix
    nodes = doc['nodes']; parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    G = [None] * len(nodes)
    def g(i):
        if G[i] is None:
            n = nodes[i]
            L = trs_matrix(n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1]), n.get('scale', [1, 1, 1]))
            for ax, deg in pose.get(n.get('name'), []):
                L = L @ axis_rot(ax, deg)
            G[i] = L if i not in parent else g(parent[i]) @ L
        return G[i]
    for i in range(len(nodes)): g(i)
    return G


def world_triangles(path, pose=None):
    doc, b = read_glb(path)
    G = posed_globals(doc, pose) if pose else node_globals(doc)
    SKM = []
    for sk in doc.get('skins', []):
        ibm = accessor(doc, b, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        SKM.append(np.array([G[j] @ ibm[k] for k, j in enumerate(sk['joints'])]))
    tris, cols = [], []
    import io
    from PIL import Image
    def image(ti):
        im = doc['images'][doc['textures'][ti]['source']]; v = doc['bufferViews'][im['bufferView']]
        return np.asarray(Image.open(io.BytesIO(b[v['byteOffset']:v['byteOffset'] + v['byteLength']])).convert('RGBA')).astype(float) / 255
    for ni, n in enumerate(doc['nodes']):
        if 'mesh' not in n or not doc['meshes'][n['mesh']]['name'].endswith('LOD0'):
            continue
        JM = SKM[n['skin']] if 'skin' in n else None
        for p in doc['meshes'][n['mesh']]['primitives']:
            A = p['attributes']
            P = accessor(doc, b, A['POSITION']).astype(np.float64)
            Ph = np.column_stack([P, np.ones(len(P))])
            if JM is not None and 'JOINTS_0' in A:
                J = np.concatenate([accessor(doc, b, A[k]).astype(int) for k in sorted(A) if k.startswith('JOINTS_')], 1)
                W = np.concatenate([accessor(doc, b, A[k]).astype(float) for k in sorted(A) if k.startswith('WEIGHTS_')], 1)
                X = sum(W[:, k:k + 1] * np.einsum('nij,nj->ni', JM[J[:, k]], Ph) for k in range(J.shape[1]))[:, :3]
            else:
                X = (G[ni] @ Ph.T).T[:, :3]
            I = accessor(doc, b, p['indices']).reshape(-1, 3)
            tris.append(X[I])
            col = np.full((len(I), 4), 0.8)
            mat = doc['materials'][p['material']] if 'material' in p else None
            bct = mat and mat['pbrMetallicRoughness'].get('baseColorTexture')
            if bct and 'TEXCOORD_0' in A:
                tex = image(bct['index']); uv = accessor(doc, b, A['TEXCOORD_0'])[I].mean(1)
                h, w = tex.shape[:2]
                px = np.clip((uv[:, 0] % 1) * w, 0, w - 1).astype(int); py = np.clip((uv[:, 1] % 1) * h, 0, h - 1).astype(int)
                col = tex[py, px] * np.array(mat['pbrMetallicRoughness'].get('baseColorFactor', [1, 1, 1, 1]))
            cols.append(col)
    return np.concatenate(tris), np.concatenate(cols)


def draw(ax, T, h, v, d, title, flip_h=False, sign=1.0, C=None):
    e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    n = np.cross(e1, e2)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    view = np.zeros(3); view[d] = sign
    facing = n @ view
    keep = facing > 0                                  # back-face cull: also checks winding
    T, shade = T[keep], 0.25 + 0.7 * facing[keep]
    C = None if C is None else C[keep]
    order = np.argsort(sign * T[:, :, d].mean(1))
    XY = T[order][:, :, [h, v]].copy()
    if flip_h:
        XY[:, :, 0] *= -1
    fc = plt.cm.gray(shade[order]) if C is None else np.column_stack([np.clip(C[order][:, :3] * (0.45 + 0.55 * shade[order, None]), 0, 1), C[order][:, 3]])
    poly = PolyCollection(XY, facecolors=fc, edgecolors='none')
    ax.add_collection(poly)
    ax.set_xlim(XY[:, :, 0].min(), XY[:, :, 0].max()); ax.set_ylim(XY[:, :, 1].min(), XY[:, :, 1].max())
    ax.set_aspect('equal'); ax.set_title(title, fontsize=9); ax.set_xticks([]); ax.set_yticks([])
    return int(keep.sum()), len(keep)


if __name__ == '__main__':
    args = sys.argv[1:]; pose = {}; tag = ''
    if '--pose' in args:
        k = args.index('--pose'); spec = args[k + 1]; del args[k:k + 2]
        for item in spec.split(','):
            nm, ax, deg = item.split(':'); pose.setdefault(nm, []).append((ax, float(deg)))
        tag = '.posed'
    for path in args:
        T, C = world_triangles(path, pose or None)
        C = C if (C != 0.8).any() else None
        fig, axs = plt.subplots(1, 2, figsize=(8, 5), dpi=110)
        # glTF space: +Y up, +Z forward, +X = model left. A viewer at +Z looking -Z has +X on their right.
        a = draw(axs[0], T, 0, 1, 2, 'front (viewer at +Z; model left on screen right)', C=C)
        b_ = draw(axs[1], T, 2, 1, 0, 'side (viewer at +X, sees model left)', C=C, flip_h=True)
        fig.suptitle(os.path.basename(path), fontsize=9)
        out = path[:-4] + tag + '.preview.png'
        fig.tight_layout(); fig.savefig(out); plt.close(fig)
        print(out, 'front-facing triangles', a, 'side', b_)
