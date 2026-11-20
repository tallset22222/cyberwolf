"""TEST 3: body-region separation and hiding (MakeHuman hm08 working copy, fitted skeleton from test 2).

Part A - separation. Cut lines are real closed edge loops only:
  * test-1 PASS seams; MOVE seams at their measured loops (shin_mid, neck_base);
  * option A for the limb roots: the first closed loop around the arm / leg (test 1);
  * extra region boundaries from the hiding map: forearm 15 %, shin 15 % (nearest loops), ribcage (torso ring nearest
    the spine_02 joint, approx. thoracolumbar level).
  Faces are flood-filled with those loops as walls. Torso and head sub-regions that the spec bounds by lines that are
  not loops (mid-axillary line, shoulder cap, hairline, jawline, ears) are split by geometric rules, and their
  boundaries are measured for jaggedness, to show where authored edge paths would be needed.
Part B - seam motion. For every replacement seam: skin within 30 mm proximal of the loop, measured in the frame of the
  bone the implant's cuff would be rigidly attached to, across all 22 test-2 poses, LBS and DQS:
  axial slide (consumes cuff overlap; the gap opens if it exceeds the overlap), outward bulge (pokes through a cuff
  that sits close to the skin), inward sink (opens a visible gap under a tight cuff).
"""
import json, os, sys, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test2_deformation as T2
from mhmesh import edge_loops
from test1_topology import winding

def seam_loops(V, Q, pos):
    loops, _ = edge_loops(Q)
    closed = [l for l in loops if l['closed']]
    def find(a, b, frac, rmax, tilt_max=22.0, first=False):
        A, B = pos[a], pos[b]; L = np.linalg.norm(B - A); d = (B - A) / L
        u = np.cross(d, [0, 0, 1.0]); u = u / np.linalg.norm(u) if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0]); w = np.cross(d, u)
        c = []
        for li, l in enumerate(closed):
            P = V[l['verts']]; s = (P - A) @ d
            rel = P - (A + np.outer(s, d))
            if np.linalg.norm(rel, axis=1).max() > rmax or s.min() < -0.35 * L or s.max() > 1.25 * L: continue
            if winding(np.stack([(P - A) @ u, (P - A) @ w], 1)) < 0.9: continue
            n = np.linalg.svd(P - P.mean(0))[2][-1]
            if np.degrees(np.arccos(min(1, abs(n @ d)))) > tilt_max: continue
            c.append((s.mean() / L, li))
        if not c: return None
        if first: return min(c)[1]
        return min(c, key=lambda x: abs(x[0] - frac))[1]
    S = {}
    for s in 'lr':
        S[f'shoulder_{s}'] = ('A', find(f'upperarm_{s}', f'lowerarm_{s}', 0, 0.10, first=True))
        S[f'upperarm_mid_{s}'] = ('', find(f'upperarm_{s}', f'lowerarm_{s}', 0.5, 0.075))
        S[f'elbow_{s}'] = ('', find(f'upperarm_{s}', f'lowerarm_{s}', 0.9, 0.065))
        S[f'forearm15_{s}'] = ('region', find(f'lowerarm_{s}', f'hand_{s}', 0.15, 0.065))
        S[f'forearm_mid_{s}'] = ('', find(f'lowerarm_{s}', f'hand_{s}', 0.5, 0.06))
        S[f'wrist_{s}'] = ('', find(f'lowerarm_{s}', f'hand_{s}', 0.92, 0.05))
        S[f'hip_{s}'] = ('A', find(f'thigh_{s}', f'calf_{s}', 0, 0.15, first=True))
        S[f'thigh_mid_{s}'] = ('', find(f'thigh_{s}', f'calf_{s}', 0.5, 0.12))
        S[f'knee_{s}'] = ('', find(f'thigh_{s}', f'calf_{s}', 0.92, 0.09))
        S[f'shin15_{s}'] = ('region', find(f'calf_{s}', f'foot_{s}', 0.15, 0.09))
        S[f'shin_mid_{s}'] = ('moved', find(f'calf_{s}', f'foot_{s}', 0.58, 0.075))
        S[f'ankle_{s}'] = ('', find(f'calf_{s}', f'foot_{s}', 0.92, 0.065))
    S['neck_mid'] = ('', find('neck_01', 'neck_02', 0.5, 0.09))
    S['neck_base'] = ('moved', find('neck_01', 'spine_03', 0.12, 0.09))
    S['waist'] = ('', find('spine_01', 'spine_02', 0.4, 0.24))
    S['ribcage'] = ('region', find('spine_01', 'spine_03', (pos['spine_02'][1] - pos['spine_01'][1]) / (pos['spine_03'][1] - pos['spine_01'][1]), 0.26))
    return closed, S

def flood(Q, cut_edges):
    fe = collections.defaultdict(list)
    for fi, q in enumerate(Q):
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]; fe[(min(a, b), max(a, b))].append(fi)
    adj = [[] for _ in range(len(Q))]
    for e, fs in fe.items():
        if e in cut_edges: continue
        for i in fs:
            for j in fs:
                if i != j: adj[i].append(j)
    comp = -np.ones(len(Q), int); n = 0
    for s in range(len(Q)):
        if comp[s] >= 0: continue
        st = [s]; comp[s] = n
        while st:
            x = st.pop()
            for y in adj[x]:
                if comp[y] < 0: comp[y] = n; st.append(y)
        n += 1
    return comp, fe

def label_regions(V, Q, pos, closed, S, comp):
    C = V[Q].mean(1)
    lab = np.array([''] * len(Q), dtype=object)
    sizes = collections.Counter(comp)
    # name each component by where its centroid sits relative to the cuts
    def axial(p, a, b):
        A, B = pos[a], pos[b]; d = B - A; return ((p - A) @ d) / (d @ d)
    for c in sizes:
        m = comp == c; p = C[m].mean(0); side = 'l' if p[0] > 0 else 'r'
        if p[1] > pos['neck_01'][1] + 0.02 and abs(p[0]) < 0.12: name = 'HEAD'
        elif abs(p[0]) > 0.16 and p[1] > 0.9:  # arm chain
            t_up = axial(p, f'upperarm_{side}', f'lowerarm_{side}'); t_lo = axial(p, f'lowerarm_{side}', f'hand_{side}')
            if t_lo > 0.92: name = f'hand_{side}'
            elif t_lo > 0.15: name = f'forearm_{side}'
            elif t_up > 0.9: name = f'elbow_{side}'
            elif t_up > 0.5: name = f'upperarm_lower_{side}'
            else: name = f'upperarm_upper_{side}'
        elif p[1] < pos['thigh_l'][1] - 0.05 and abs(p[0]) > 0.02:  # leg chain
            t_th = axial(p, f'thigh_{side}', f'calf_{side}'); t_cf = axial(p, f'calf_{side}', f'foot_{side}')
            if t_cf > 0.92: name = f'foot_{side}'
            elif t_cf > 0.15: name = f'shin_{side}'
            elif t_th > 0.92: name = f'knee_{side}'
            elif t_th > 0.5: name = f'thigh_lower_{side}'
            else: name = f'thigh_upper_{side}'
        elif p[1] > pos['spine_03'][1] + 0.08 and abs(p[0]) < 0.1: name = 'neck_lower'
        else: name = 'TORSO'
        lab[m] = name
    # torso sub-regions: geometric rules (spec boundaries that are not loops)
    t = lab == 'TORSO'; Ct = C[t]
    waist_y = V[closed[S['waist'][1]]['verts']][:, 1].mean(); rib_y = V[closed[S['ribcage'][1]]['verts']][:, 1].mean()
    # bands come from the flood components (the waist and ribcage loops are cuts), not from a height threshold
    ct = comp[t]; cy = {c: C[comp == c][:, 1].mean() for c in set(ct)}
    above_rib = np.array([cy[c] > rib_y for c in ct]); above_waist = np.array([cy[c] > waist_y for c in ct])
    # front/back by angle around the torso axis at that height (mid-axillary = +-90 deg)
    front = Ct[:, 2] > pos['upperarm_l'][2]          # mid-axillary approximated by the coronal plane through the shoulders
    cap = (np.abs(Ct[:, 0]) > 0.135) & (Ct[:, 1] > pos['spine_03'][1] - 0.02)
    names = np.where(above_rib, np.where(front, 'chest', 'back_upper'), np.where(above_waist, np.where(front, 'abdomen', 'back_lower'), np.where(front, 'pelvis_front', 'pelvis_back')))
    names = np.where(cap, np.where(Ct[:, 0] > 0, 'shoulder_cap_l', 'shoulder_cap_r'), names)
    lab[np.where(t)[0]] = names
    # head sub-regions: rules (hairline/jawline/ears are not loops)
    h = lab == 'HEAD'; Ch = C[h]
    # jawline (sagittal profile): chin underside -> jaw angle, then the nape at the same height as the jaw angle.
    # Measured on this mesh: chin underside y=1.425 z=0.14; jaw angle approx. 5 cm above and 12 cm behind it.
    chin = np.array([pos['jaw'][1] - 0.111, 0.14]); gon = chin + np.array([0.05, -0.12])
    def below_jaw(P):
        t = np.clip((chin[1] - P[:, 2]) / (chin[1] - gon[1]), 0, 1)
        return P[:, 1] < chin[0] + t * (gon[0] - chin[0])
    jaw_y = chin[0]
    ear = (np.abs(Ch[:, 0]) > 0.062) & (Ch[:, 1] > pos['jaw'][1] - 0.04) & (Ch[:, 1] < pos['jaw'][1] + 0.05) & (Ch[:, 2] < pos['jaw'][2] + 0.01)
    neck_up = below_jaw(Ch)
    face = (Ch[:, 2] > pos['head'][2] + 0.04) & (Ch[:, 1] < pos['head'][1] + 0.11) & ~neck_up
    hn = np.where(ear, 'ears', np.where(neck_up & ~face, 'neck_upper', np.where(face, 'face', 'scalp')))
    lab[np.where(h)[0]] = hn
    return lab

def boundary_report(V, Q, lab, fe):
    """For each pair of adjacent regions: boundary length and jaggedness (boundary edge length / smoothed length)."""
    pairs = collections.defaultdict(list)
    for e, fs in fe.items():
        if len(fs) == 2 and lab[fs[0]] != lab[fs[1]]:
            pairs[tuple(sorted((lab[fs[0]], lab[fs[1]])))].append(e)
    out = {}
    for k, es in pairs.items():
        deg = collections.Counter(v for e in es for v in e)
        L = sum(np.linalg.norm(V[a] - V[b]) for a, b in es)
        branch = sum(1 for v, n in deg.items() if n > 2)
        # jaggedness: total length vs. length of the same vertex chain after 3 rounds of neighbour smoothing
        nb = collections.defaultdict(list)
        for a, b in es: nb[a].append(b); nb[b].append(a)
        P = {v: V[v].copy() for v in nb}
        for _ in range(3):
            P = {v: 0.5 * P[v] + 0.5 * np.mean([P[u] for u in nb[v]], 0) for v in nb}
        Ls = sum(np.linalg.norm(P[a] - P[b]) for a, b in es)
        out[f'{k[0]} | {k[1]}'] = {'edges': len(es), 'length_mm': round(L * 1000, 1), 'jaggedness': round(L / max(Ls, 1e-9), 2), 'branch_vertices': branch}
    return out

def ear_faces(V, Q, cand_faces):
    """Auricle by a protrusion test (no closed quad loop exists at the ear root on hm08): a vertex is auricle if a ray
    cast medially (towards x=0) meets the head surface again within 25 mm. Skull skin meets the far side of the head
    instead (>100 mm). Faces with all four vertices flagged; then the faces enclosed by them are added back."""
    T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    TV = V[T]; e1 = TV[:, 1] - TV[:, 0]; e2 = TV[:, 2] - TV[:, 0]
    vids = np.unique(Q[cand_faces]); flag = np.zeros(len(V), bool)
    near = (np.abs(TV[:, :, 0]).min(1) > 0.03) & (TV[:, :, 1].min(1) > 1.43)
    TVn, e1n, e2n = TV[near], e1[near], e2[near]
    for v in vids:
        o = V[v]; d = np.array([-np.sign(o[0]), 0, 0.0])
        p = np.cross(d, e2n); det = (e1n * p).sum(1); ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1 / np.where(ok, det, 1), 0); s = o - TVn[:, 0]
        u = (s * p).sum(1) * inv; q = np.cross(s, e1n); w = (q * d).sum(1) * inv; t = (q * e2n).sum(1) * inv
        hit = ok & (u >= 0) & (w >= 0) & (u + w <= 1) & (t > 1e-4) & (t < 0.025)
        flag[v] = hit.any()
    return np.array([f for f in cand_faces if flag[Q[f]].all()])

# ---------------- Part B: seam motion ----------------
def vertex_normals(V, Q):
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    N = np.zeros_like(V); np.add.at(N, Q.ravel(), np.repeat(n, 4, 0))
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)

def seam_strip(V, Q, loop_verts, proximal_point, width=0.030):
    """Body skin under the cuff: vertices connected to the loop, on the proximal side, within `width` of the loop plane."""
    P = V[loop_verts]; c = P.mean(0); n = np.linalg.svd(P - c)[2][-1]
    if (proximal_point - c) @ n < 0: n = -n                      # n points proximally
    r = np.linalg.norm(P - c, axis=1).max()
    adj = collections.defaultdict(set)
    for q in Q:
        for k in range(4): adj[q[k]].add(q[(k + 1) % 4]); adj[q[(k + 1) % 4]].add(q[k])
    ok = lambda v: -0.002 <= (V[v] - c) @ n <= width and np.linalg.norm((V[v] - c) - ((V[v] - c) @ n) * n) < 1.6 * r
    seen = set(loop_verts); st = list(loop_verts)
    while st:
        x = st.pop()
        for y in adj[x]:
            if y not in seen and ok(y): seen.add(y); st.append(y)
    return np.array(sorted(seen)), c, n

def seam_motion(V, Vp, G, strip, c, n, cuff_bone, N0, Np, shell=0.002):
    """(b) rigid cuff (spec v0.1: cuff weighted to the proximal joint): skin motion in the cuff bone's frame.
       slide = displacement along the seam normal (+ = proximal); radial = along the rest outward radial direction.
       (a) weight-transfer cuff: a shell offset `shell` along the rest normal, skinned with the skin's own weights;
       clearance = posed (shell - skin) . posed normal; < 0 means the skin pokes through."""
    Ginv = np.linalg.inv(G[cuff_bone])
    loc = (Ginv[:3, :3] @ Vp[strip].T).T + Ginv[:3, 3]
    d = loc - V[strip]
    rad = V[strip] - c; rad -= np.outer(rad @ n, n); rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
    slide = d @ n; radial = (d * rad).sum(1)
    return {'slide_max_mm': float(np.abs(slide).max() * 1000), 'outward_max_mm': float(max(radial.max(), 0) * 1000),
            'inward_max_mm': float(max(-radial.min(), 0) * 1000)}

def shell_clearance(V, Q, strip, method, bones, top, Wt, G, shell=0.002):
    N0 = vertex_normals(V, Q); S = V + shell * N0
    Vp = T2.skin(V, bones, top, Wt, G, method); Sp = T2.skin(S, bones, top, Wt, G, method); Np = vertex_normals(Vp, Q)
    cl = ((Sp - Vp)[strip] * Np[strip]).sum(1)
    return float(cl.min() * 1000), Vp
