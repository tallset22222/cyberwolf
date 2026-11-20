"""Cyberwolf character standard v0.1: skeleton, attachment sockets, seam rings and body-hiding regions.

Single source of truth -> skeleton.json, hiding_regions.json, diagrams. Conventions:
  metres; Y up; character faces +Z; character's left = +X (glTF convention).
  Rest/bind pose: A-pose, upper arms 45 deg below horizontal, legs straight, reference stature 1.75 m (profile 'bio_reference').
  Joint frame: local +Y points from the joint to its primary child (along the bone); local X is the main flexion axis;
  twist is rotation about local Y.
"""
import json, math, numpy as np

H = 1.75
J = []  # (name, parent, layer, pos, note)
def add(name, parent, layer, pos, note=''):
    J.append({'name': name, 'parent': parent, 'layer': layer, 'rest_position_m': [round(float(v), 4) for v in pos], 'note': note})
def P(name):
    return np.array(next(j for j in J if j['name'] == name)['rest_position_m'])
def lerp(a, b, t):
    return P(a) * (1 - t) + P(b) * t

# ---- L0 core (animated; retargeting contract) ----
add('root', None, 'core', [0, 0, 0], 'ground projection of the character; carries root motion; never skinned')
add('pelvis', 'root', 'core', [0, 0.94, 0])
add('spine_01', 'pelvis', 'core', [0, 1.02, -0.005])
add('spine_02', 'spine_01', 'core', [0, 1.15, -0.01])
add('spine_03', 'spine_02', 'core', [0, 1.28, -0.01], 'ribcage / chest')
add('neck_01', 'spine_03', 'core', [0, 1.45, -0.02])
add('neck_02', 'neck_01', 'core', [0, 1.52, -0.01])
add('head', 'neck_02', 'core', [0, 1.585, 0.0], 'skull base pivot; the face rig binds here as a separate component')
add('jaw', 'head', 'core', [0, 1.60, 0.015])
for s, x in (('l', 1), ('r', -1)):
    add(f'eye_{s}', 'head', 'core', [0.032 * x, 1.645, 0.075])
a45 = math.radians(45)
for s, x in (('l', 1), ('r', -1)):
    add(f'clavicle_{s}', 'spine_03', 'core', [0.02 * x, 1.435, 0.03])
    sh = np.array([0.175 * x, 1.42, -0.01]); add(f'upperarm_{s}', f'clavicle_{s}', 'core', sh)
    d = np.array([math.sin(a45) * x, -math.cos(a45), 0.0])
    el = sh + 0.30 * d; add(f'lowerarm_{s}', f'upperarm_{s}', 'core', el)
    wr = el + 0.26 * d + np.array([0, 0, 0.01]); add(f'hand_{s}', f'lowerarm_{s}', 'core', wr)
    # fingers: palm faces down/in, fingers continue along d, spread along Z (front = +Z)
    for f, z, base, lens in (('index', 0.03, 0.095, (0.045, 0.027, 0.022)), ('middle', 0.01, 0.10, (0.05, 0.03, 0.023)),
                             ('ring', -0.01, 0.095, (0.046, 0.028, 0.022)), ('pinky', -0.028, 0.085, (0.037, 0.022, 0.019))):
        p = wr + np.array([0, 0, z])
        if f in ('ring', 'pinky'):
            m0 = wr + 0.035 * d + np.array([0, 0, z * 0.7]); add(f'{f}_00_{s}', f'hand_{s}', 'core', m0, 'metacarpal (palm cupping)')
            par = f'{f}_00_{s}'
        else:
            par = f'hand_{s}'
        p = wr + base * d + np.array([0, -0.005, z])
        for i, L in enumerate(lens, 1):
            add(f'{f}_{i:02d}_{s}', par, 'core', p); par = f'{f}_{i:02d}_{s}'; p = p + L * d
    tp = wr + 0.03 * d + np.array([0, -0.015, 0.035])
    tdir = (d + np.array([0, 0, 0.9])); tdir /= np.linalg.norm(tdir); par = f'hand_{s}'
    for i, L in enumerate((0.04, 0.035, 0.028), 1):
        add(f'thumb_{i:02d}_{s}', par, 'core', tp); par = f'thumb_{i:02d}_{s}'; tp = tp + L * tdir
for s, x in (('l', 1), ('r', -1)):
    add(f'thigh_{s}', 'pelvis', 'core', [0.09 * x, 0.92, 0.0])
    add(f'calf_{s}', f'thigh_{s}', 'core', [0.10 * x, 0.50, 0.008])
    add(f'foot_{s}', f'calf_{s}', 'core', [0.105 * x, 0.085, -0.012])
    add(f'ball_{s}', f'foot_{s}', 'core', [0.11 * x, 0.022, 0.125], 'toe joint; toes are one segment')

# ---- L1 twist (driven from core, never keyed; carry skin weights) ----
for s in 'lr':
    for seg, a, b, ts in (('upperarm', f'upperarm_{s}', f'lowerarm_{s}', (0.33, 0.66)), ('lowerarm', f'lowerarm_{s}', f'hand_{s}', (0.33, 0.66)),
                          ('thigh', f'thigh_{s}', f'calf_{s}', (0.33, 0.66)), ('calf', f'calf_{s}', f'foot_{s}', (0.5,))):
        for i, t in enumerate(ts, 1):
            add(f'{seg}_twist_{i:02d}_{s}', a, 'twist', lerp(a, b, t), f'{int(t*100)}% along {seg}; driven by twist of {b} relative to {a}')

# ---- L2 deformation helpers (driven procedurally, never keyed; carry skin weights) ----
for s, x in (('l', 1), ('r', -1)):
    add(f'hlp_shoulder_{s}', f'clavicle_{s}', 'helper', P(f'upperarm_{s}') + [0.01 * x, 0.03, 0.0], 'deltoid volume')
    add(f'hlp_elbow_{s}', f'upperarm_{s}', 'helper', P(f'lowerarm_{s}') + [0, 0, -0.035], 'olecranon / crease preservation')
    add(f'hlp_wrist_{s}', f'lowerarm_{s}', 'helper', P(f'hand_{s}') + [0, 0.01, 0], 'wrist volume')
    add(f'hlp_hip_{s}', 'pelvis', 'helper', P(f'thigh_{s}') + [0.02 * x, 0, 0.05], 'front hip crease')
    add(f'hlp_glute_{s}', 'pelvis', 'helper', P(f'thigh_{s}') + [0, -0.03, -0.09], 'gluteal fold')
    add(f'hlp_knee_{s}', f'thigh_{s}', 'helper', P(f'calf_{s}') + [0, 0, 0.05], 'patella')
    add(f'hlp_breast_{s}', 'spine_03', 'helper', [0.09 * x, 1.30, 0.10], 'chest volume; secondary-motion target (sim layer)')
add('hlp_neck_front', 'neck_01', 'helper', [0, 1.47, 0.05], 'throat / swallow volume')
add('hlp_belly', 'spine_01', 'helper', [0, 1.05, 0.10], 'abdominal volume; secondary-motion target')

# ---- L3 attachment sockets (never skinned; rigid attachment frames) ----
S = [('sock_head_top', 'head', [0, 1.75, -0.01], 'helmets, headgear'),
     ('sock_face', 'head', [0, 1.635, 0.10], 'masks, face plates, visors'),
     ('sock_eye_l', 'eye_l', [0.032, 1.645, 0.088], 'optic replacement (left)'), ('sock_eye_r', 'eye_r', [-0.032, 1.645, 0.088], 'optic replacement (right)'),
     ('sock_neck_port', 'neck_01', [0, 1.49, -0.06], 'spinal / neural port; helmet cable terminus'),
     ('sock_spine_upper', 'spine_03', [0, 1.33, -0.11], 'back-mounted cyberware (upper)'),
     ('sock_spine_lower', 'spine_01', [0, 1.07, -0.10], 'back-mounted cyberware (lower)'),
     ('sock_chest_core', 'spine_03', [0, 1.30, 0.02], 'internal implants (logical location; life support, processors)'),
     ('sock_waist', 'pelvis', [0, 1.00, 0.0], 'belt hardware, waist implants'),
     ('sock_hip_l', 'pelvis', [0.10, 0.93, 0.0], 'hip joint (full-leg replacement anchor)'), ('sock_hip_r', 'pelvis', [-0.10, 0.93, 0.0], ''),
     ]
for s, x in (('l', 1), ('r', -1)):
    S += [(f'sock_shoulder_{s}', f'clavicle_{s}', P(f'upperarm_{s}') + [0.025 * x, 0.045, 0], 'shoulder pods / plates (do not twist with the arm)'),
          (f'sock_elbow_{s}', f'lowerarm_{s}', P(f'lowerarm_{s}'), 'elbow hardware'),
          (f'sock_wrist_{s}', f'lowerarm_{s}', P(f'hand_{s}'), 'wrist hardware, forearm-mounted tools'),
          (f'sock_hand_grip_{s}', f'hand_{s}', P(f'hand_{s}') + np.array([0.055 * x, -0.055, 0.0]) + [0, -0.02, 0], 'held items / weapons'),
          (f'sock_palm_{s}', f'hand_{s}', P(f'hand_{s}') + np.array([0.04 * x, -0.04, 0.0]) + [0, -0.02, 0], 'palm implants'),
          (f'sock_thigh_mid_{s}', f'thigh_{s}', lerp(f'thigh_{s}', f'calf_{s}', 0.5), 'mid-thigh hardware'),
          (f'sock_knee_{s}', f'calf_{s}', P(f'calf_{s}') + [0, 0, 0.05], 'knee hardware'),
          (f'sock_ankle_{s}', f'foot_{s}', P(f'foot_{s}'), 'ankle hardware'),
          (f'sock_sole_{s}', f'foot_{s}', [P(f'foot_{s}')[0], 0.0, 0.03], 'ground contact (feet replacements, footstep effects)')]
for n, par, pos, note in S:
    add(n, par, 'socket', pos, note)

# ---- seam rings: where replacements may start. Fraction measured along the segment (0 = proximal joint) ----
SEAMS = []
def seam(code, a, b, t, note):
    SEAMS.append({'code': code, 'from_joint': a, 'to_joint': b, 'fraction': t, 'note': note})
seam('neck_base', 'neck_01', 'spine_03', 0.35, 'head + neck replacement starts here (collar)')
seam('neck_mid', 'neck_01', 'neck_02', 0.5, 'head replacement (keeps the neck)')
seam('waist', 'spine_01', 'spine_02', 0.4, 'lower-body chassis boundary (abdomen / pelvis)')
for s in 'lr':
    seam(f'shoulder_{s}', f'upperarm_{s}', f'lowerarm_{s}', 0.0, 'full-arm replacement (includes the deltoid cap)')
    seam(f'upperarm_mid_{s}', f'upperarm_{s}', f'lowerarm_{s}', 0.5, '')
    seam(f'elbow_{s}', f'upperarm_{s}', f'lowerarm_{s}', 0.9, 'forearm replacement (cuff covers the elbow)')
    seam(f'forearm_mid_{s}', f'lowerarm_{s}', f'hand_{s}', 0.5, '')
    seam(f'wrist_{s}', f'lowerarm_{s}', f'hand_{s}', 0.92, 'hand replacement')
    seam(f'hip_{s}', f'thigh_{s}', f'calf_{s}', 0.0, 'full-leg replacement (from the hip crease)')
    seam(f'thigh_mid_{s}', f'thigh_{s}', f'calf_{s}', 0.5, 'mid-thigh replacement (the military-leg default)')
    seam(f'knee_{s}', f'thigh_{s}', f'calf_{s}', 0.92, 'lower-leg replacement (cuff covers the knee)')
    seam(f'shin_mid_{s}', f'calf_{s}', f'foot_{s}', 0.5, '')
    seam(f'ankle_{s}', f'calf_{s}', f'foot_{s}', 0.92, 'foot replacement')
for sm in SEAMS:
    sm['rest_position_m'] = [round(float(v), 4) for v in lerp(sm['from_joint'], sm['to_joint'], sm['fraction'])]

# ---- body-hiding regions: one bit each, boundaries are seam rings or named torso cuts ----
R = []
def reg(name, bounds, note=''):
    R.append({'bit': len(R), 'name': name, 'bounded_by': bounds, 'note': note})
reg('scalp', ['hairline', 'ears'], 'hidden by helmets, hair caps')
reg('face', ['hairline', 'jawline'], 'hidden only by full masks; optional per item')
reg('ears', ['scalp'], 'both ears')
reg('neck_upper', ['jawline', 'seam neck_mid'])
reg('neck_lower', ['seam neck_mid', 'seam neck_base'])
reg('chest', ['seam neck_base', 'ribcage line', 'mid-axillary lines', 'seams shoulder_l/r'], 'front torso above the ribcage line')
reg('abdomen', ['ribcage line', 'seam waist', 'mid-axillary lines'])
reg('back_upper', ['seam neck_base', 'back mid line', 'mid-axillary lines'])
reg('back_lower', ['back mid line', 'seam waist'])
reg('pelvis_front', ['seam waist', 'seams hip_l/r'], 'includes the groin')
reg('pelvis_back', ['seam waist', 'gluteal folds'], 'glutes')
for s in 'lr':
    reg(f'shoulder_cap_{s}', [f'seam shoulder_{s}', 'chest', 'back_upper'], 'deltoid cap')
    reg(f'upperarm_upper_{s}', [f'seam shoulder_{s}', f'seam upperarm_mid_{s}'])
    reg(f'upperarm_lower_{s}', [f'seam upperarm_mid_{s}', f'seam elbow_{s}'])
    reg(f'elbow_{s}', [f'seam elbow_{s}', 'forearm 15%'])
    reg(f'forearm_{s}', ['forearm 15%', f'seam wrist_{s}'], 'split at forearm_mid allowed later (reserved bit)')
    reg(f'hand_{s}', [f'seam wrist_{s}'], 'hand and fingers')
    reg(f'thigh_upper_{s}', [f'seam hip_{s}', f'seam thigh_mid_{s}'])
    reg(f'thigh_lower_{s}', [f'seam thigh_mid_{s}', f'seam knee_{s}'])
    reg(f'knee_{s}', [f'seam knee_{s}', 'shin 15%'])
    reg(f'shin_{s}', ['shin 15%', f'seam ankle_{s}'], 'split at shin_mid allowed later (reserved bit)')
    reg(f'foot_{s}', [f'seam ankle_{s}'], 'foot and toes')
assert len(R) <= 64

# ---- checks ----
names = [j['name'] for j in J]
assert len(names) == len(set(names)), 'duplicate joint'
for j in J:
    assert j['parent'] is None or j['parent'] in names, j
    assert j['layer'] != 'socket' or not any(k['parent'] == j['name'] for k in J), 'sockets must be leaves'
for j in J:
    if j['name'].endswith('_l'):
        m = j['name'][:-2] + '_r'; pl, pr = np.array(j['rest_position_m']), np.array(next(k for k in J if k['name'] == m)['rest_position_m'])
        assert np.allclose(pl * [-1, 1, 1], pr, atol=1e-4), (j['name'], pl, pr)
order_ok = all(J[i]['parent'] is None or names.index(J[i]['parent']) < i for i in range(len(J)))
counts = {L: sum(j['layer'] == L for j in J) for L in ('core', 'twist', 'helper', 'socket')}
skel = {'standard': 'cyberwolf_character', 'version': '0.1-draft', 'profile': 'bio_reference', 'stature_m': H,
        'conventions': {'units': 'metres', 'up': '+Y', 'forward': '+Z', 'character_left': '+X', 'rest_pose': 'A-pose, upper arms 45 deg below horizontal',
                        'joint_frame': 'local +Y towards primary child; local X = main flexion axis; twist about local Y',
                        'naming': 'snake_case; side suffix _l/_r; prefixes: hlp_ helper, sock_ socket, ext_ chassis extension (reserved), face rig separate'},
        'layers': {'core': 'animated; the retargeting contract; may carry skin weights',
                   'twist': 'driven from core, never keyed; carries skin weights',
                   'helper': 'procedural deformation (anatomy layer), never keyed; carries skin weights',
                   'socket': 'rigid attachment frames; never carries skin weights; always a leaf',
                   'ext': 'reserved: chassis-specific joints (pistons, plates), parented under core joints; ignored by retargeting'},
        'counts': counts, 'parents_before_children': order_ok, 'joints': J, 'seam_rings': SEAMS}
json.dump(skel, open('skeleton.json', 'w'), indent=1)
json.dump({'standard': 'cyberwolf_character', 'version': '0.1-draft', 'mask_width_bits': 64, 'regions': R}, open('hiding_regions.json', 'w'), indent=1)
print(counts, 'total', len(J), 'seams', len(SEAMS), 'regions', len(R), 'order ok', order_ok)
