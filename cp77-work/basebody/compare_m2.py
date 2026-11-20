import json, sys
runs = [a.split(':') for a in sys.argv[1:]]
M = {l: json.load(open(d + '/metrics2.json'))['results'] for d, l in runs}; T = {l: json.load(open(d + '/test2_deformation.json'))['results'] for d, l in runs}
f = lambda t, r: '%.2f %3d/%2.0f %4.0f %.2f' % (t['volume_ratio'], r['intersection_vertices'], r['intersection_max_depth_mm'], r['pinch_length_mm'], t['strain_p95'])
L = [l for _, l in runs]
print('%-36s %-3s | ' % ('pose', 'm') + ' | '.join('%-23s' % (l + ': vol int/dep pinch s95') for l in L))
for p in M[L[0]]:
    if p.startswith(('wrist', 'ankle', 'spine', 'hip_extend', 'hip_abduct', 'forearm', 'neck', 'sit')): continue
    for m in ('LBS', 'DQS'): print('%-36s %-3s | ' % (p, m) + ' | '.join('%-23s' % f(T[l][p][m], M[l][p][m]) for l in L))
