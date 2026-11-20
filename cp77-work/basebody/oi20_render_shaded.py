"""Shaded renders (same rasteriser as the Test 2 sheets) of the knee: offline prototype vs corrective-joint finalists,
side and front views at 90 and 135 degrees. Plain grey shading so that bumps show as shading breaks.
Writes reports/correctives/oi20_knee_shaded.png."""
import os, sys, numpy as np, importlib
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['CW_JOINT'] = 'knee'; os.environ['CW_OI20_JOINTFIT'] = '1'
src = open(os.path.join(HERE, 'render_test2.py')).read(); ns = {'__file__': os.path.join(HERE, 'render_test2.py')}
exec(src[:src.index('FOCUS =')].replace("z = np.load(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), '_test2_posed.npz')); V, Q = z['V'], z['Q']", '').replace("R = json.load(open(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), 'test2_deformation.json')))['results']", ''), ns)
cols = []   # (label, method, xform or None for the offline prototype, n)
for method, variants in (('LBS', [('prototype', None, 0), ('joints, rigid', 'rigid', 3), ('joints, with scale', 'scaled', 3)]),
                         ('DQS', [('prototype', None, 0), ('joints, rigid', 'rigid', 4)])):
    for lab, xf, n in variants: cols.append((f'{method} {lab}', method, xf, n))
T = 260; views = [(90, 'side'), (90, 'front'), (135, 'side'), (135, 'front')]
sheet = Image.new('RGB', (len(cols) * T, len(views) * (T + 16) + 22), (255, 255, 255)); dr = ImageDraw.Draw(sheet)
for c, (lab, method, xf, n) in enumerate(cols):
    os.environ['CW_OI20_XFORM'] = xf or 'rigid'
    O = importlib.reload(importlib.import_module('oi20_joints')); ns['Q'] = O.Q
    if xf: joints, _, _ = O.fit(method, n); O.fit_midkeys(joints, method); names, tp, Wt2, _ = O.build(joints, 8)
    dr.text((c * T + 6, 4), lab, fill=(0, 0, 0))
    for r, (th, view) in enumerate(views):
        G = O.G_at(th)
        if xf:
            Ge = O.G_ext(G, joints, O.CR.flex_angle(G, O.pos, 'knee', 'l'), O.CR.flex_angle(G, O.pos, 'knee', 'r'))
            O.CR._C['authoring'] = True; X = O.T2.skin(O.V, names, tp, Wt2, Ge, method); O.CR._C['authoring'] = False
        else: X = O.T2.skin(O.V, O.bones, O.top, O.Wt, G, method)
        cen = G['calf_l'][:3, 3]
        sheet.paste(ns['draw'](X, view, cen, 0.30, T), (c * T, 22 + r * (T + 16) + 16))
        if c == 0: dr.text((4, 22 + r * (T + 16) + 2), f'knee {th} deg, {view} view', fill=(0, 0, 0))
sheet.save(os.path.join(HERE, 'reports', 'correctives', 'oi20_knee_shaded.png')); print(sheet.size)
