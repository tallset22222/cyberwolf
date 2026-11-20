#!/usr/bin/env python3
"""Pose the assembled character with explicit joint rotations and measure triangle edge stretch per component
(posed edge length / bind edge length). Broken or mismatched skin bindings show up as extreme stretch."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.validate import read_glb, accessor, node_globals
from render_preview import posed_globals

POSE = {'LeftForeArm': [('z', 70)], 'RightArm': [('z', -50)], 'Head': [('z', 25)], 'jaw_root_JNT': [('x', 15)],
        'LeftUpLeg': [('z', 30)], 'Spine2': [('y', 15)]}

def skin_positions(doc, b, G, node, prim):
    sk = doc['skins'][node['skin']]
    ibm = accessor(doc, b, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
    JM = np.array([G[j] @ ibm[k] for k, j in enumerate(sk['joints'])])
    A = prim['attributes']; P = accessor(doc, b, A['POSITION']).astype(np.float64); Ph = np.column_stack([P, np.ones(len(P))])
    J = np.concatenate([accessor(doc, b, A[k]).astype(int) for k in sorted(A) if k.startswith('JOINTS_')], 1)
    W = np.concatenate([accessor(doc, b, A[k]).astype(float) for k in sorted(A) if k.startswith('WEIGHTS_')], 1)
    return sum(W[:, k:k + 1] * np.einsum('nij,nj->ni', JM[J[:, k]], Ph) for k in range(J.shape[1]))[:, :3]

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'pipeline_out', 'characters', 'jackie_welles.geometry.glb')
doc, b = read_glb(path)
G0, G1 = node_globals(doc), posed_globals(doc, POSE)
rows = {}
for node in doc['nodes']:
    if 'mesh' not in node or 'skin' not in node: continue
    st = []
    for prim in doc['meshes'][node['mesh']]['primitives']:
        I = accessor(doc, b, prim['indices']).reshape(-1, 3)
        p0, p1 = skin_positions(doc, b, G0, node, prim), skin_positions(doc, b, G1, node, prim)
        for a, c in ((0, 1), (1, 2), (2, 0)):
            l0 = np.linalg.norm(p0[I[:, a]] - p0[I[:, c]], axis=1); l1 = np.linalg.norm(p1[I[:, a]] - p1[I[:, c]], axis=1)
            ok = l0 > 1e-5; st.append(l1[ok] / l0[ok])
    s = np.concatenate(st)
    rows[node['name'].replace(' LOD0', '')] = {'edges': int(len(s)), 'p50': round(float(np.median(s)), 3), 'p99_9': round(float(np.percentile(s, 99.9)), 3), 'max': round(float(s.max()), 2)}
for k, v in sorted(rows.items(), key=lambda kv: -kv[1]['max']):
    print(f"{k[:44]:44s} edges {v['edges']:7d}  median {v['p50']}  99.9% {v['p99_9']}  max {v['max']}")
worst = max(v['p99_9'] for v in rows.values())
print('worst 99.9th-percentile stretch across components:', worst)
sys.exit(0 if worst < 2.0 else 1)
