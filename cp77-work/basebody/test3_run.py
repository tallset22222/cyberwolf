"""Test 3 part B driver: seam motion for the left-side and central seams across the 22 test-2 poses (poses are
left-side; right seams are mirror images). Cuff models:
  rigid/spec  - cuff rigid to the literal 'proximal joint' of attachment standard v0.1 sec. 2
  rigid/best  - cuff rigid to whichever single bone influencing the strip minimises the worst slide (best case for rigid)
  weight-transfer - cuff shell (2 mm) carrying the body's own skin weights at the seam (no slide by construction)."""
import sys, os, json, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test2_deformation as T2, test3_regions as T3
V, Q, pos, par, kids, bones, top, Wt = T2.build()
closed, S = T3.seam_loops(V, Q, pos)
SIDE = sys.argv[1] if len(sys.argv) > 1 else 'l'
lib, focus = T2.pose_library(pos)
M = np.diag([-1.0, 1, 1])
def mirror_ops(ops):
    out = []
    for j, Rm, w in ops:
        j2 = j[:-2] + '_r' if j.endswith('_l') else j
        out.append((j2, Rm if isinstance(Rm, str) else M @ Rm @ M, w))
    return out
def global_transforms(ops, side):
    """test-2 global_transforms with the KNEE90 special case generalised to either side (test-2 code untouched)."""
    G = {n: np.eye(4) for n in pos}
    for j, Rm, _ in ops:
        if isinstance(Rm, str):
            cur = lambda n: (G[n] @ np.append(pos[n], 1))[:3]
            dcalf = cur(f'foot_{side}') - cur(f'calf_{side}')
            Rm = T2.rot(np.cross(dcalf, -np.array([0, 1.0, 0])), np.radians(90)) if side == 'l' else M @ T2.rot(np.cross(M @ dcalf, -np.array([0, 1.0, 0])), np.radians(90)) @ M
        c = (G[j] @ np.append(pos[j], 1))[:3]
        T = np.eye(4); T[:3, :3] = Rm; T[:3, 3] = c - Rm @ c
        for n in T2.descendants(kids, j): G[n] = T @ G[n]
    return G
SET = os.environ.get('CW_POSESET', 'all')      # 'stress' = the original 22, 'paced' = the 4 paced shoulder poses
if SET == 'stress': lib = {k: v for k, v in lib.items() if not k.endswith('_paced')}
elif SET == 'paced': lib = {k: v for k, v in lib.items() if k.endswith('_paced')}
if SIDE == 'r': lib = {k: mirror_ops(v) for k, v in lib.items()}
Gs = {k: T2.twist_distribute(global_transforms(ops, SIDE), pos, ops, kids) for k, ops in lib.items()}
OVERLAP, MARGIN, SHELL = 0.015, 0.005, 0.002
N0 = T3.vertex_normals(V, Q)
SK = {}
for p, G in Gs.items():
    for m in ('LBS', 'DQS'):
        Vp = T2.skin(V, bones, top, Wt, G, m); Sp = T2.skin(V + SHELL * N0, bones, top, Wt, G, m)
        SK[(p, m)] = (Vp, ((Sp - Vp) * T3.vertex_normals(Vp, Q)).sum(1))
# seam -> (point on the kept-body side, literal proximal joint)
SEAMS = {'shoulder_l': ('spine_03', 'clavicle_l'), 'upperarm_mid_l': ('upperarm_l', 'upperarm_l'), 'elbow_l': ('upperarm_l', 'upperarm_l'),
         'forearm_mid_l': ('lowerarm_l', 'lowerarm_l'), 'wrist_l': ('lowerarm_l', 'lowerarm_l'), 'hip_l': ('pelvis', 'pelvis'),
         'thigh_mid_l': ('thigh_l', 'thigh_l'), 'knee_l': ('thigh_l', 'thigh_l'), 'shin_mid_l': ('calf_l', 'calf_l'), 'ankle_l': ('calf_l', 'calf_l'),
         'neck_mid': ('neck_01', 'neck_01'), 'neck_base': ('spine_03', 'spine_03'), 'waist': ('spine_02', 'spine_01')}
SEAMS['neck_base'] = ('spine_03', 'spine_03')
if SIDE == 'r': SEAMS = {(k[:-2] + '_r' if k.endswith('_l') else k): tuple(x[:-2] + '_r' if x.endswith('_l') else x for x in v) for k, v in SEAMS.items()}
def rigid(strip, c, n, bone, m, loop_set, band, edge):
    """slide: the seam loop itself (the body's open edge must stay under the cuff); outward: anywhere in the 0-15 mm
    overlap band (pokes through a close cuff); inward: at the cuff's proximal edge, 12-18 mm (visible gap at the edge)."""
    worst = {'slide': (0, ''), 'out': (0, ''), 'in': (0, '')}
    for p, G in Gs.items():
        Ginv = np.linalg.inv(G[bone]); Vp = SK[(p, m)][0]
        d = (Ginv[:3, :3] @ Vp[strip].T).T + Ginv[:3, 3] - V[strip]
        rad = V[strip] - c; rad -= np.outer(rad @ n, n); rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
        slide = np.abs(d @ n); radial = (d * rad).sum(1)
        vals = {'slide': slide[loop_set].max() * 1000, 'out': max(radial[band].max(), 0) * 1000, 'in': (max(-radial[edge].min(), 0) * 1000 if edge.any() else 0)}
        for k in worst:
            if vals[k] > worst[k][0]: worst[k] = (float(vals[k]), p)
    need = worst['slide'][0] + MARGIN * 1000
    return {'bone': bone, 'max_slide_mm': round(worst['slide'][0], 1), 'slide_pose': worst['slide'][1], 'overlap_needed_mm': round(need, 1),
            '15mm_sufficient': bool(need <= OVERLAP * 1000), 'max_outward_mm': round(worst['out'][0], 1), 'outward_pose': worst['out'][1],
            'max_inward_mm': round(worst['in'][0], 1), 'inward_pose': worst['in'][1]}
out = {}
for seam, (side_pt, prox) in SEAMS.items():
    kind, li = S[seam]; lv = closed[li]['verts']
    strip, c, n = T3.seam_strip(V, Q, lv, pos[side_pt])
    acc = collections.Counter()
    for v in strip:
        for k in range(top.shape[1]): acc[bones[top[v, k]]] += Wt[v, k]
    ax = (V[strip] - c) @ n
    loop_set = np.isin(strip, lv); band = ax <= OVERLAP + 1e-4; edge = (ax >= 0.012) & (ax <= 0.018)
    cands = [b for b, w in acc.items() if w / sum(acc.values()) > 0.05 and not b.startswith('hlp_')]   # rigid cuffs attach to core/twist only
    res = {'kind': kind or 'pass', 'loop_vertices': len(lv), 'strip_vertices': int(len(strip)), 'loop_y_mm': round(float(V[lv][:, 1].mean() * 1000)),
           'strip_influences': {b: round(w / sum(acc.values()), 2) for b, w in acc.most_common(5)}}
    for m in ('LBS', 'DQS'):
        spec = rigid(strip, c, n, prox, m, loop_set, band, edge)
        best = min((rigid(strip, c, n, b, m, loop_set, band, edge) for b in cands), key=lambda r: r['max_slide_mm'])
        cl = min((float(SK[(p, m)][1][strip[band]].min() * 1000), p) for p in Gs)
        res[m] = {'rigid_spec': spec, 'rigid_best': best,
                  'weight_transfer': {'min_clearance_mm_of_2mm_shell': round(cl[0], 2), 'pose': cl[1], 'pokes_through': bool(cl[0] < 0)}}
    out[seam] = res
    f = lambda m: (res[m]['rigid_spec']['max_slide_mm'], res[m]['rigid_best']['bone'], res[m]['rigid_best']['max_slide_mm'], res[m]['rigid_best']['max_outward_mm'], res[m]['weight_transfer']['min_clearance_mm_of_2mm_shell'])
    print('%-15s %-6s spec/best/out/clear LBS %s  DQS %s' % (seam, res['kind'], f('LBS'), f('DQS')), flush=True)
json.dump(out, open(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), f'_test3_partB_{SIDE}' + ('' if SET == 'all' else '_' + SET) + '.json'), 'w'), indent=1)
