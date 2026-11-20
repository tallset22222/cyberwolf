"""Fit the Cyberwolf skeleton (names/hierarchy from specs/character_standard/skeleton.json, unchanged) to the
MakeHuman body using MakeHuman's anatomical joint markers. Produces profile 'bio_makehuman_default'.
Working-copy transform: mesh shifted so the ground marker is at y = 0 (standard convention). Core + twist joints only;
helpers and sockets are fitted later (they are not used by test 2)."""
import json, os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from mhmesh import load
SPEC = os.path.join(HERE, '..', 'specs', 'character_standard', 'skeleton.json')

def fitted():
    V, Q, J, _ = load()
    g = J['ground'].copy(); g[0] = g[2] = 0
    V = V - g; J = {k: v - g for k, v in J.items()}
    spec = json.load(open(SPEC))
    P = {'root': np.zeros(3), 'pelvis': J['pelvis'], 'spine_01': J['spine-3'], 'spine_02': J['spine-2'], 'spine_03': J['spine-1'],
         'neck_01': J['neck'], 'neck_02': (J['neck'] + J['head']) / 2, 'head': J['head'],
         # MakeHuman's 'jaw' marker is the CHIN TIP (verified: on the chin surface). Our jaw joint is the hinge
         # (temporomandibular joint), just in front of the ear: 2 cm above and 3 cm in front of the skull-base joint.
         'jaw': J['head'] + np.array([0, 0.02, 0.03])}
    for s in 'lr':
        P.update({f'eye_{s}': J[f'{s}-eye'], f'clavicle_{s}': J[f'{s}-clavicle'], f'upperarm_{s}': J[f'{s}-shoulder'],
                  f'lowerarm_{s}': J[f'{s}-elbow'], f'hand_{s}': J[f'{s}-hand'], f'thigh_{s}': J[f'{s}-upper-leg'],
                  f'calf_{s}': J[f'{s}-knee'], f'foot_{s}': J[f'{s}-ankle'], f'ball_{s}': J[f'{s}-foot-1']})
        for i in (1, 2, 3):
            P[f'thumb_{i:02d}_{s}'] = J[f'{s}-finger-1-{i}']
        # MakeHuman finger markers: k-1 = knuckle (MCP), k-2 = PIP, k-3 = DIP, k-4 = fingertip (verified: k-4 lies
        # within 1 mm of the tip surface). Ring/pinky metacarpal joints have no marker: placed 40% wrist -> knuckle.
        for f, k in (('index', 2), ('middle', 3), ('ring', 4), ('pinky', 5)):
            for i in (1, 2, 3):
                P[f'{f}_{i:02d}_{s}'] = J[f'{s}-finger-{k}-{i}']
        for f, k in (('ring', 4), ('pinky', 5)):
            P[f'{f}_00_{s}'] = J[f'{s}-hand'] * 0.6 + J[f'{s}-finger-{k}-1'] * 0.4
    # MakeHuman's foot markers (foot-1 = toe joint, foot-2 = toe tip) sit on the sole (y ~ 1 cm). The toe joint and
    # tip are lifted to the vertical middle of the foot at that point (mean of the top and bottom surface there).
    def mid_height(p):
        sel = (np.abs(V[:, 0] - p[0]) < 0.03) & (np.abs(V[:, 2] - p[2]) < 0.006) & (V[:, 1] < 0.12)
        return p if sel.sum() < 4 else np.array([p[0], (V[sel, 1].min() + V[sel, 1].max()) / 2, p[2]])
    for s in 'lr':
        P[f'ball_{s}'] = mid_height(P[f'ball_{s}'])
    joints = []
    for j in spec['joints']:
        n = j['name']
        if j['layer'] == 'core':
            p = P[n]
        elif j['layer'] == 'twist':
            seg, _, idx, side = n.rsplit('_', 3)[0], None, None, n[-1]
            base = n.split('_twist_')[0]; k = int(n.split('_twist_')[1][:2])
            child = {'upperarm': 'lowerarm', 'lowerarm': 'hand', 'thigh': 'calf', 'calf': 'foot'}[base]
            t = {('upperarm', 1): .33, ('upperarm', 2): .66, ('lowerarm', 1): .33, ('lowerarm', 2): .66, ('thigh', 1): .33, ('thigh', 2): .66, ('calf', 1): .5}[(base, k)]
            p = P[f'{base}_{side}'] * (1 - t) + P[f'{child}_{side}'] * t
        else:
            continue
        joints.append({**j, 'rest_position_m': [round(float(v), 5) for v in p]})
    tips = {}  # segment end points for leaf bones (used for skin weights only)
    for s in 'lr':
        tips[f'thumb_03_{s}'] = J[f'{s}-finger-1-4']
        for f, k in (('index', 2), ('middle', 3), ('ring', 4), ('pinky', 5)):
            tips[f'{f}_03_{s}'] = J[f'{s}-finger-{k}-4']
        tips[f'ball_{s}'] = mid_height(J[f'{s}-foot-2'] - np.array([0, 0, 0.012]))
    # head skinning segment aims through the middle of the skull (between crown and eyes), not up the back of it,
    # so the face is nearer the head bone than the neck (skinning only; the joint itself is unchanged)
    tips['head'] = (J['head-2'] + (J['l-eye'] + J['r-eye']) / 2) / 2
    tips['jaw'] = J['jaw'] - np.array([0, 0, 0.012])   # chin tip, 12 mm inside the surface
    return V, Q, joints, tips

def winding_number(V, Q, pts):
    T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    out = []
    for p in pts:
        a, b, c = V[T[:, 0]] - p, V[T[:, 1]] - p, V[T[:, 2]] - p
        la, lb, lc = [np.linalg.norm(x, axis=1) for x in (a, b, c)]
        num = np.einsum('ij,ij->i', a, np.cross(b, c))
        den = la * lb * lc + np.einsum('ij,ij->i', a, b) * lc + np.einsum('ij,ij->i', b, c) * la + np.einsum('ij,ij->i', c, a) * lb
        out.append(np.sum(np.arctan2(num, den)) / (2 * np.pi))
    return np.array(out)

if __name__ == '__main__':
    V, Q, joints, tips = fitted()
    wn = winding_number(V, Q, [np.array(j['rest_position_m']) for j in joints])
    inside = {j['name']: round(float(w), 2) for j, w in zip(joints, wn)}
    outside = {k: v for k, v in inside.items() if v < 0.5 and k != 'root'}
    json.dump({'profile': 'bio_makehuman_default', 'source': 'MakeHuman hm08 working copy, ground at y=0',
               'standard_version': '0.1-draft', 'stature_m': round(float(V[:, 1].max()), 4), 'joints': joints,
               'leaf_tips': {k: [round(float(x), 5) for x in v] for k, v in tips.items()},
               'inside_mesh_winding_number': inside}, open(os.path.join(HERE, 'reports', 'skeleton_fitted.json'), 'w'), indent=1)
    print('joints fitted', len(joints), 'stature', round(float(V[:, 1].max()), 3), '| joints outside the body (winding < 0.5):', outside)
