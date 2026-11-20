"""Compare test-2 metrics: v2 baseline (no helpers) vs a helper pass, LBS and DQS. Usage: compare_helpers.py <pass_dir>"""
import json, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
a = json.load(open(os.path.join(HERE, 'reports', 'test2_deformation.json')))['results']
b = json.load(open(os.path.join(HERE, sys.argv[1], 'test2_deformation.json')))['results']
f = lambda r: '%.2f %.2f %.2f %3d' % (r['volume_ratio'], r['strain_p95'], r['strain_p5'], r['folded_faces'])
print('%-30s | %-21s %-21s | %-21s %-21s' % ('pose  (vol s95 s5 fold)', 'LBS base', 'LBS +helpers', 'DQS base', 'DQS +helpers'))
for p in a:
    print('%-30s | %-21s %-21s | %-21s %-21s' % (p, f(a[p]['LBS']), f(b[p]['LBS']), f(a[p]['DQS']), f(b[p]['DQS'])))
