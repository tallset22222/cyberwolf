"""TEST 1 (independent of our skeleton fit): do the base mesh's edge loops support the standard's seam rings?

Seam positions come from MakeHuman's own anatomical joint markers mapped to our joints (no skeleton fitting).
For each seam: find closed edge loops that encircle the segment axis near the seam; report the best one.
Thresholds are configurable (THRESH). Writes reports/test1_topology.json/.md and renders.
"""
import json, os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mhmesh import load, edge_loops
HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, '..', 'specs', 'character_standard', 'skeleton.json')
# Pass rule uses loop TILT (angle between the loop plane and the segment's cross-section), not spread: spread grows
# with limb thickness (a 16 deg tilt on a thigh spreads ~41 mm), so a spread limit penalised thick limbs unfairly.
# The first run used spread <= 25 mm; that rule is kept as 'spread_mm' in the report for comparison.
THRESH = {'pass_offset_mm': 15.0, 'max_tilt_deg': 22.0, 'move_offset_mm': 60.0}

def mh_joint_map(J):
    m = {'neck_01': J['neck'], 'neck_02': (J['neck'] + J['head']) / 2, 'head': J['head'],
         'spine_01': J['spine-3'], 'spine_02': J['spine-2'], 'spine_03': J['spine-1'], 'pelvis': J['pelvis']}
    for s in 'lr':
        m.update({f'upperarm_{s}': J[f'{s}-shoulder'], f'lowerarm_{s}': J[f'{s}-elbow'], f'hand_{s}': J[f'{s}-hand'],
                  f'thigh_{s}': J[f'{s}-upper-leg'], f'calf_{s}': J[f'{s}-knee'], f'foot_{s}': J[f'{s}-ankle']})
    return m

RMAX = [('neck', 0.09), ('waist', 0.24), ('shoulder', 0.10), ('upperarm', 0.075), ('elbow', 0.065), ('forearm', 0.06),
        ('wrist', 0.05), ('hip', 0.15), ('thigh', 0.12), ('knee', 0.09), ('shin', 0.075), ('ankle', 0.065)]

def rmax(code):
    return next(r for k, r in RMAX if code.startswith(k))

def winding(P2):
    a = np.arctan2(P2[:, 1], P2[:, 0]); d = np.diff(np.append(a, a[0]))
    d = (d + np.pi) % (2 * np.pi) - np.pi
    return abs(d.sum()) / (2 * np.pi)

def run():
    V, Q, J, _ = load(); loops, _ = edge_loops(Q)
    closed = [l for l in loops if l['closed']]
    M = mh_joint_map(J)
    seams = json.load(open(SPEC))['seam_rings']
    out = []
    for sm in seams:
        a, b = M[sm['from_joint']], M[sm['to_joint']]; L = np.linalg.norm(b - a); d = (b - a) / L
        c = a + sm['fraction'] * (b - a); sc = sm['fraction'] * L
        u = np.cross(d, [0, 0, 1.0]); u = u / np.linalg.norm(u) if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0]); w = np.cross(d, u)
        root = sm['fraction'] == 0.0
        cands = []
        for li, l in enumerate(closed):
            P = V[l['verts']]; rel = P - c
            s = (P - a) @ d
            radial = np.linalg.norm(rel - np.outer(rel @ d, d), axis=1)
            if radial.max() > rmax(sm['code']) or s.min() < -0.35 * L or s.max() > 1.25 * L:
                continue
            if winding(np.stack([rel @ u, rel @ w], 1)) < 0.9:
                continue
            ctr = P.mean(0); n = np.linalg.svd(P - ctr)[2][-1]
            tilt = np.degrees(np.arccos(min(1.0, abs(n @ d))))
            cands.append({'loop': li, 'offset_mm': float((s.mean() - sc) * 1000), 'spread_mm': float((s.max() - s.min()) * 1000),
                          'tilt_deg': float(tilt), 'verts': len(l['verts']), 'fraction': float(s.mean() / L)})
        cands.sort(key=lambda x: abs(x['offset_mm']))
        best = cands[0] if cands else None
        good = [x for x in cands if x['tilt_deg'] <= THRESH['max_tilt_deg']]
        if not good:
            status = 'FAIL: no encircling loop with acceptable tilt'
        elif abs(good[0]['offset_mm']) <= THRESH['pass_offset_mm']:
            status, best = 'PASS', good[0]
        elif abs(good[0]['offset_mm']) <= THRESH['move_offset_mm']:
            status, best = 'MOVE', good[0]
        else:
            status, best = f"FAIL: nearest usable loop {good[0]['offset_mm']:+.0f} mm away", good[0]
        out.append({'seam': sm['code'], 'segment': f"{sm['from_joint']}->{sm['to_joint']}", 'segment_length_mm': round(L * 1000, 1),
                    'spec_fraction': sm['fraction'], 'status': status, 'best': best,
                    'nearby_loops': [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in x.items() if k != 'loop'} for x in cands[:5]],
                    'loop_spacing_mm': (round(float(np.median(np.diff(sorted(x['offset_mm'] for x in cands)))), 1) if len(cands) > 2 else None)})
    return V, Q, closed, out, M

if __name__ == '__main__':
    V, Q, closed, out, M = run()
    json.dump({'test': 'topology/seam compatibility', 'thresholds': THRESH, 'mesh': 'concepts/base_mesh_work/base_working.obj (body group)',
               'results': out}, open(os.path.join(HERE, 'reports', 'test1_topology.json'), 'w'), indent=1)
    for r in out:
        b = r['best']
        print('%-15s %-10s %s' % (r['seam'], r['status'][:42], '' if not b else 'off %+6.1f mm spread %5.1f tilt %4.1f verts %d frac %.2f (spec %.2f) spacing %s' % (
            b['offset_mm'], b['spread_mm'], b['tilt_deg'], b['verts'], b['fraction'], r['spec_fraction'], r['loop_spacing_mm'])))
