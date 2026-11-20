import json, os, sys, numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
z = np.load(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), '_test2_posed.npz')); V, Q = z['V'], z['Q']
R = json.load(open(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), 'test2_deformation.json')))['results']
VIEW = {'shoulder': 'front', 'elbow': 'top', 'forearm': 'front', 'wrist': 'side', 'hip_flex': 'side', 'sit': 'side', 'hip_abduct': 'front',
        'hip_extend': 'side', 'knee': 'side', 'ankle': 'side', 'spine_flex': 'side', 'spine_twist': 'top', 'spine_side': 'front', 'neck_flex': 'side', 'neck_turn': 'top'}
def proj(X, v):
    if v == 'front': return X[:, 0], X[:, 1], X[:, 2]
    if v == 'side': return X[:, 2], X[:, 1], -X[:, 0]          # left side view
    return X[:, 0], -X[:, 2], X[:, 1]                           # top view
def draw(X, v, center, span, size=300, strain=None):
    x, y, d = proj(X, v); cx, cy, _ = proj(center[None], v); s = size / span
    Xs, Ys = (x - cx[0]) * s + size / 2, size / 2 - (y - cy[0]) * s
    img = Image.new('RGB', (size, size), (246, 246, 246)); dr = ImageDraw.Draw(img)
    P3 = np.stack([x, y, d], 1); n = np.cross(P3[Q[:, 1]] - P3[Q[:, 0]], P3[Q[:, 2]] - P3[Q[:, 0]]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    vis = n[:, 2] > 0; inside = (np.abs(Xs[Q]).max(1) < size * 1.5) & (np.abs(Ys[Q]).max(1) < size * 1.5)
    idx = np.where(vis & inside)[0]; idx = idx[np.argsort(d[Q[idx]].mean(1))]
    L = np.array([0.3, 0.5, 0.8]); L /= np.linalg.norm(L); sh = 0.35 + 0.65 * np.clip(n @ L, 0, 1)
    for i in idx:
        g = sh[i]
        col = (int(205 * g), int(205 * g), int(210 * g))
        if strain is not None:
            st = strain[i]
            if st < 0.75: col = (int(90 * g + 40), int(120 * g + 40), int(230 * g))
            elif st > 1.3: col = (int(230 * g), int(90 * g + 30), int(70 * g + 30))
        dr.polygon([(Xs[j], Ys[j]) for j in Q[i]], fill=col, outline=tuple(max(0, c - 30) for c in col))
    return img
def face_strain(V, Vp):
    e = lambda X, a, b: np.linalg.norm(X[Q[:, a]] - X[Q[:, b]], axis=1)
    r = np.stack([e(Vp, a, b) / np.maximum(e(V, a, b), 1e-9) for a, b in ((0, 1), (1, 2), (2, 3), (3, 0))], 1)
    return np.where(np.abs(r.min(1) - 1) > np.abs(r.max(1) - 1), r.min(1), r.max(1))
FOCUS = {'shoulder': 'upperarm', 'elbow': 'lowerarm', 'forearm': 'lowerarm', 'wrist': 'hand', 'hip': 'thigh', 'sit': 'thigh', 'knee': 'calf', 'ankle': 'foot', 'spine': 'spine', 'neck': 'neck'}
fit = {j['name']: np.array(j['rest_position_m']) for j in json.load(open(os.path.join(HERE, 'reports', 'skeleton_fitted.json')))['joints']}
cen = {'upperarm': fit['upperarm_l'] + [0.03, -0.03, 0], 'lowerarm': fit['lowerarm_l'], 'hand': fit['hand_l'], 'thigh': fit['thigh_l'] + [0, -0.05, 0],
       'calf': fit['calf_l'], 'foot': fit['foot_l'] + [0, 0, 0.04], 'spine': fit['spine_02'], 'neck': fit['neck_01'] + [0, 0.04, 0]}
names = list(R)
cols = 4; tile = 300; lab = 34
sheet = Image.new('RGB', (cols * 2 * tile + (cols - 1) * 10, ((len(names) + cols - 1) // cols) * (tile + lab)), (255, 255, 255)); dr = ImageDraw.Draw(sheet)
for i, n in enumerate(names):
    key = next(k for k in VIEW if n.startswith(k)); v = VIEW[key]
    f = next(k for k in FOCUS if n.startswith(k)); c = cen[FOCUS[f]]
    span = 0.32 if FOCUS[f] in ('upperarm', 'thigh', 'spine') else 0.26
    if n.startswith('sit') or n.startswith('spine_flex'): span = 0.75; c = c + np.array([0, -0.2, 0.15]) if n.startswith('sit') else c
    x0 = (i % cols) * (2 * tile + 10); y0 = (i // cols) * (tile + lab)
    for k, m in enumerate(('LBS', 'DQS')):
        Vp = z[f'{n}__{m}']; img = draw(Vp, v, c, span, tile, face_strain(V, Vp)); sheet.paste(img, (x0 + k * tile, y0 + lab))
        r = R[n][m]; g = r['grade']
        dr.text((x0 + k * tile + 4, y0 + 2), f"{m} vol {r['volume_ratio']:.2f} fold {r['folded_faces']}", fill=(0, 120, 0) if g == 'OK' else (190, 60, 0))
    dr.text((x0 + 4, y0 + 17), n, fill=(0, 0, 0))
sheet.save(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), 'test2_poses.png')); print(sheet.size)
