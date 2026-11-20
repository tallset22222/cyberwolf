"""Side-by-side renders of selected poses for several runs (strain colours: red > 1.3x stretch, blue < 0.75x).
Usage: render_compare.py out.png runA_dir:label runB_dir:label ... (each dir holds _test2_posed.npz)"""
import sys, os, numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'render_test2.py')).read()
ns = {'__file__': os.path.join(HERE, 'render_test2.py')}; exec(src[:src.index('FOCUS =')].replace("z = np.load(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), '_test2_posed.npz')); V, Q = z['V'], z['Q']", '').replace("R = json.load(open(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), 'test2_deformation.json')))['results']", ''), ns)
import json
runs = [a.split(':') for a in sys.argv[2:]]
Z = [np.load(os.path.join(HERE, d, '_test2_posed.npz')) for d, _ in runs]
ns['Q'] = Z[0]['Q']; V = Z[0]['V']
fit = {j['name']: np.array(j['rest_position_m']) for j in json.load(open(os.path.join(HERE, 'reports', 'skeleton_fitted.json')))['joints']}
POSES = [('shoulder_abduct_overhead', 'front', fit['upperarm_l'] + [0.0, 0.0, 0], 0.34), ('shoulder_adduct_across_chest', 'front', fit['upperarm_l'] + [-0.05, -0.05, 0], 0.34),
         ('elbow_flex_90', 'top', fit['lowerarm_l'], 0.24), ('elbow_flex_135', 'top', fit['lowerarm_l'], 0.24),
         ('hip_flex_90', 'side', fit['thigh_l'] + [0, -0.05, 0.05], 0.36), ('knee_flex_135', 'side', fit['calf_l'], 0.28)]
T = 240; lab = 18
sheet = Image.new('RGB', (len(runs) * 2 * T + 40, len(POSES) * (T + lab) + 20), (255, 255, 255)); dr = ImageDraw.Draw(sheet)
for c, (d, l) in enumerate(runs):
    for k, m in enumerate(('LBS', 'DQS')): dr.text((c * 2 * T + k * T + 6, 2), f'{l} {m}', fill=(0, 0, 0))
for r, (p, view, cen, span) in enumerate(POSES):
    for c in range(len(runs)):
        for k, m in enumerate(('LBS', 'DQS')):
            Vp = Z[c][f'{p}__{m}']; img = ns['draw'](Vp, view, cen, span, T, ns['face_strain'](V, Vp))
            sheet.paste(img, (c * 2 * T + k * T, 20 + r * (T + lab) + lab))
    dr.text((4, 20 + r * (T + lab) + 2), p, fill=(0, 0, 0))
sheet.save(sys.argv[1]); print(sheet.size)
