"""Validation render for metrics2: intersection quads red, pinch-edge quads yellow, crease-line quads green,
fold-over quads magenta. Usage: render_events.py <run_dir> <out.png> pose:view ..."""
import sys, os, numpy as np, json
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test2_deformation as T2, metrics2 as M2
V, Q, pos, *_ = T2.build(); lib, focus = T2.pose_library(pos)
M = M2.Metric2(V, Q, T2.INTERIOR); z = np.load(os.path.join(HERE, sys.argv[1], '_test2_posed.npz'))
def proj(X, v):
    if v == 'front': return X[:, 0], X[:, 1], X[:, 2]
    if v == 'side': return X[:, 2], X[:, 1], -X[:, 0]
    if v == 'back': return -X[:, 0], X[:, 1], -X[:, 2]
    return X[:, 0], -X[:, 2], X[:, 1]
items = [a.split(':') for a in sys.argv[3:]]; S = 300
sheet = Image.new('RGB', (2 * S, len(items) * (S + 16)), 'white'); dr0 = ImageDraw.Draw(sheet)
for r, (p, v) in enumerate(items):
    for k, m in enumerate(('LBS', 'DQS')):
        X = z[f'{p}__{m}']; c = pos[focus[p]]
        M.measure(X, c); ev = M.events(X, c); rest = M.rest[1]
        inter = ev['inter'] & ~rest['inter']; sharp = ev['ereg'] & (ev['dih'] - M.dih0 > M2.PINCH); fold = ev['ereg'] & (ev['dih'] > M2.FOLDOVER)
        zone = inter | ev['contact']; zr = zone.copy(); zr[M.E[zone[M.E[:, 0]] | zone[M.E[:, 1]]].ravel()] = True; inz = zr[M.E].any(1)
        col = np.full((len(Q), 3), 205.0)
        col[inter[Q].any(1)] = (225, 70, 60)
        for mask, cc in ((sharp & inz, (60, 170, 80)), (sharp & ~inz, (235, 200, 40)), (fold, (210, 60, 200))):
            col[M.EF[mask].ravel()] = cc
        x, y, d = proj(X, v); cx, cy, _ = proj(c[None], v); sc = S / 0.36
        Xs, Ys = (x - cx[0]) * sc + S / 2, S / 2 - (y - cy[0]) * sc
        img = Image.new('RGB', (S, S), (246, 246, 246)); dr = ImageDraw.Draw(img)
        P3 = np.stack([x, y, d], 1); n = np.cross(P3[Q[:, 1]] - P3[Q[:, 0]], P3[Q[:, 2]] - P3[Q[:, 0]]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        L = np.array([0.3, 0.5, 0.8]); L /= np.linalg.norm(L); sh = 0.45 + 0.55 * np.clip(n @ L, 0, 1)
        idx = np.where((n[:, 2] > 0) & (np.abs(Xs[Q]).max(1) < 2 * S))[0]; idx = idx[np.argsort(d[Q[idx]].mean(1))]
        for i in idx: dr.polygon([(Xs[j], Ys[j]) for j in Q[i]], fill=tuple(int(cc * sh[i]) for cc in col[i]), outline=(90, 90, 90))
        sheet.paste(img, (k * S, r * (S + 16) + 16)); dr0.text((k * S + 4, r * (S + 16) + 2), f'{p} {m}', fill='black')
sheet.save(sys.argv[2]); print(sheet.size)
