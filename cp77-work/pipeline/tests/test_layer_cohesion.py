#!/usr/bin/env python3
"""Cross-rig binding check: components bound through different rigs must move together where they touch.
For each vertex of an outer layer within 1.5 cm of an inner layer (in bind pose), compare their displacements
under a pose. A wrong joint mapping or bind pose shows up as large relative differences even for small poses."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.validate import read_glb, accessor, node_globals
from render_preview import posed_globals

def skinned(doc, b, G, node):
    sk = doc['skins'][node['skin']]
    ibm = accessor(doc, b, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
    JM = np.array([G[j] @ ibm[k] for k, j in enumerate(sk['joints'])]); out = []
    for prim in doc['meshes'][node['mesh']]['primitives']:
        A = prim['attributes']; P = accessor(doc, b, A['POSITION']).astype(np.float64); Ph = np.column_stack([P, np.ones(len(P))])
        J = np.concatenate([accessor(doc, b, A[k]).astype(int) for k in sorted(A) if k.startswith('JOINTS_')], 1)
        W = np.concatenate([accessor(doc, b, A[k]).astype(float) for k in sorted(A) if k.startswith('WEIGHTS_')], 1)
        out.append(sum(W[:, k:k + 1] * np.einsum('nij,nj->ni', JM[J[:, k]], Ph) for k in range(J.shape[1]))[:, :3])
    return np.concatenate(out)

def nearest(a, b, chunk=4000):
    idx = np.empty(len(a), int); d = np.empty(len(a))
    for s in range(0, len(a), chunk):
        D = ((a[s:s + chunk, None, :] - b[None, ::3, :]) ** 2).sum(-1)
        k = D.argmin(1); idx[s:s + chunk] = k * 3; d[s:s + chunk] = np.sqrt(D[np.arange(len(k)), k])
    return idx, d

path = os.path.join(HERE, '..', '..', 'pipeline_out', 'characters', 'jackie_welles.geometry.glb')
doc, b = read_glb(path); G0 = node_globals(doc)
by = {n['name'].replace(' LOD0', ''): n for n in doc['nodes'] if 'skin' in n}
pairs = [('t2_001_full__jackie_welles6078', 't1_001_full__jackie_welles1604', 'jacket (dangle rig) over tank top (body rig)'),
         ('t2_001_full__jackie_welles6078', 't0_001_mb_body__jackie_welles4264', 'jacket (dangle rig) over body skin (body rig)'),
         ('head', 't0_001_mb_body__jackie_welles4264', 'head (face rig) at neck seam with body (body rig)'),
         ('i1_001_full__jackie_welles', 't0_001_mb_body__jackie_welles4264', 'accessory i1 (deformation rig) over body (body rig)')]
poses = {'arms 10 deg': {'RightArm': [('z', -10)], 'LeftForeArm': [('z', 10)]},
         'spine+head 10 deg': {'Spine2': [('y', 10)], 'Head': [('z', 10)]}}
ok_all = True
for pname, pose in poses.items():
    G1 = posed_globals(doc, pose)
    print('pose:', pname)
    for outer, inner, label in pairs:
        if outer not in by or inner not in by: continue
        o0, o1 = skinned(doc, b, G0, by[outer]), skinned(doc, b, G1, by[outer])
        i0, i1 = skinned(doc, b, G0, by[inner]), skinned(doc, b, G1, by[inner])
        k, d = nearest(o0, i0); close = d < 0.015
        if close.sum() < 20: print(f'   {label}: too few contacts ({close.sum()})'); continue
        do, di = (o1 - o0)[close], (i1 - i0)[k[close]]
        moving = np.linalg.norm(di, axis=1) > 0.002
        diff = np.linalg.norm(do - di, axis=1)[moving]; mag = np.linalg.norm(di, axis=1)[moving]
        rel = float(np.median(diff / mag)) if len(mag) else 0.0
        ok = rel < 0.25; ok_all &= ok
        print(f'   {label:52s} contacts {int(close.sum()):6d}  moving {int(moving.sum()):6d}  median |d_outer - d_inner| / |d_inner| = {rel:.3f}  {"OK" if ok else "CHECK"}')
sys.exit(0 if ok_all else 1)
