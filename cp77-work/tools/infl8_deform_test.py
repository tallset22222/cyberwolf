"""Offline deformation test of the WolvenKit-imported 8-influence test mesh (stage 2 of the import gate).
Bends the left knee of the imported tube and compares three skins at each angle:
  A  imported   : the imported .mesh as an engine reads it (joints + UByte4N bytes / 255, no renormalisation)
  B  intended   : the same vertices with the float weights authored in the .glb (the reference)
  C  imported-4 : the imported bytes cut to the 4 largest and renormalised (what a 4-influence path would give)
Pose: bind pose from the mesh's own inverse bind matrices; the LeftLeg subtree of man_base_deformations.rig rotates
about the knee (flexion, foot moves backwards). Checks: A vs B error (exact vertices vs sentinel band), rest-pose
return, spikes (edge stretch), triangles flipped relative to B, vertices collapsed toward the origin.
Writes tests_assets/infl8_import/deform_test.json and deform_test.png."""
import sys, os, json, struct, numpy as np
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
from cyberwolf.mesh import Mesh
from cyberwolf.rig import Rig
D = os.path.join(ROOT, 'tests_assets', 'infl8_import')
M = Mesh(os.path.join(D, 'imported', 'l1_003_ma_pants__jeans.mesh')); names = M.bone_names
c = [ch for ch in M.chunks if ch.lod_mask & 1][0]
X = c.position.astype(np.float64); J = c.joints.astype(int); Wb = c.weights_raw.astype(np.float64)
TRI = np.asarray(c.indices).reshape(-1, 3) if hasattr(c, 'indices') else None
rig = Rig(os.path.join(ROOT, 'pipeline_cache/base/characters/base_entities/man_base/deformations_rigs/man_base_deformations.rig'))
ibm = np.transpose(M.ibm_rowvec, (0, 2, 1)); bindw = np.array([np.linalg.inv(m) for m in ibm])
# descendants of LeftLeg (inclusive), via the rig hierarchy
def desc(root):
    out = {root}; ch = True
    while ch:
        ch = False
        for i, p in enumerate(rig.parents):
            if p >= 0 and rig.names[p] in out and rig.names[i] not in out: out.add(rig.names[i]); ch = True
    return out
moving = desc('LeftLeg'); knee = bindw[names.index('LeftLeg')][:3, 3]
foot = bindw[names.index('LeftFoot')][:3, 3]

# ---- intended float weights from the glb ----
def read_glb(p):
    b = open(p, 'rb').read(); jl = struct.unpack_from('<I', b, 12)[0]; js = json.loads(b[20:20 + jl]); bin_ = b[20 + jl + 8:]
    def acc(i):
        a = js['accessors'][i]; v = js['bufferViews'][a['bufferView']]
        ct = {5126: np.float32, 5121: np.uint8, 5123: np.uint16, 5125: np.uint32}[a['componentType']]
        n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0); stride = v.get('byteStride', 0) or n * np.dtype(ct).itemsize
        raw = np.frombuffer(bin_, np.uint8, count=stride * (a['count'] - 1) + n * np.dtype(ct).itemsize, offset=off)
        return np.lib.stride_tricks.as_strided(raw.view(ct) if stride == n * np.dtype(ct).itemsize else np.frombuffer(bin_, ct, offset=off, count=a['count'] * stride // np.dtype(ct).itemsize), (a['count'], n)).copy() if stride == n * np.dtype(ct).itemsize else np.array([np.frombuffer(bin_, ct, count=n, offset=off + k * stride) for k in range(a['count'])])
    prim = js['meshes'][0]['primitives'][0]; at = prim['attributes']
    pos = acc(at['POSITION']).astype(np.float64) @ np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0.0]])   # glTF -> RED (x,-z,y)
    jn = [js['nodes'][k]['name'] for k in js['skins'][0]['joints']]
    jj = np.hstack([acc(at['JOINTS_0']), acc(at['JOINTS_1'])]).astype(int); ww = np.hstack([acc(at['WEIGHTS_0']), acc(at['WEIGHTS_1'])]).astype(np.float64)
    return pos, np.vectorize(lambda k: names.index(jn[k]))(jj), ww, acc(prim['indices']).astype(int).reshape(-1, 3)
Pg, Jg, Wg, Tg = read_glb(os.path.join(D, 'l1_003_ma_pants__jeans.glb'))
# map imported vertices to glb vertices by position
class cKDTree:                      # brute force: 360 vertices
    def __init__(self, P): self.P = np.asarray(P)
    def query(self, Q):
        d = np.linalg.norm(np.asarray(Q)[:, None] - self.P[None], axis=2); i = d.argmin(1); return d[np.arange(len(i)), i], i
dd, gi = cKDTree(Pg).query(X); assert dd.max() < 5e-4, dd.max()
Jb, Wf = Jg[gi], Wg[gi]
# triangles in imported indexing
ii = cKDTree(X).query(Pg)[1]; T = ii[Tg]
E = json.load(open(os.path.join(D, 'expected.json')))
sent_pos = np.array([p for p, e in zip(E['positions_red'], E['expected']) if e['kind'] == 'sentinel_equal_8'])
is_sent = np.zeros(len(X), bool); is_sent[cKDTree(X).query(sent_pos)[1]] = True

def skin(Jx, Wx, S):
    out = np.zeros_like(X)
    for k in range(Jx.shape[1]):
        Sm = S[Jx[:, k]]; out += Wx[:, k:k + 1] * (np.einsum('nij,nj->ni', Sm[:, :3, :3], X) + Sm[:, :3, 3])
    return out
def pose(theta):
    a = np.radians(theta); axis = np.array([1.0, 0, 0])
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]]); R = np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K
    Rt = np.eye(4); Rt[:3, :3] = R; Rt[:3, 3] = knee - R @ knee
    return np.array([(Rt if n in moving else np.eye(4)) @ bindw[i] @ ibm[i] for i, n in enumerate(names)]), Rt
# sign: flexion moves the foot backwards (-Y in RED's character frame)
_, Rt = pose(30); sgn = 1 if (Rt[:3, :3] @ (foot - knee))[1] < (foot - knee)[1] else -1
top = np.argsort(-Wb, 1, kind='stable')[:, :4]; W4 = np.take_along_axis(Wb, top, 1); W4 /= W4.sum(1, keepdims=True); J4 = np.take_along_axis(J, top, 1)
def edges(T): e = np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]); return np.unique(np.sort(e, 1), axis=0)
EG = edges(T); L0 = np.linalg.norm(X[EG[:, 0]] - X[EG[:, 1]], axis=1)
def normals(P): return np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
res = {'imported_vertices': int(len(X)), 'sentinel_vertices': int(is_sent.sum()), 'angles': {}}
shots = {}
for th in (0, 30, 60, 90, 120, 135):
    S, _ = pose(sgn * th)
    A = skin(J, Wb / 255.0, S); B = skin(Jb, Wf, S); C = skin(J4, W4, S)
    eA = np.linalg.norm(A - B, axis=1) * 1000; eC = np.linalg.norm(C - B, axis=1) * 1000
    st = np.linalg.norm(A[EG[:, 0]] - A[EG[:, 1]], axis=1) / L0; stB = np.linalg.norm(B[EG[:, 0]] - B[EG[:, 1]], axis=1) / L0
    nA, nB = normals(A), normals(B)
    res['angles'][th] = {
        'A_vs_intended_exact_max_mm': round(float(eA[~is_sent].max()), 3), 'A_vs_intended_exact_mean_mm': round(float(eA[~is_sent].mean()), 3),
        'A_vs_intended_sentinel_max_mm': round(float(eA[is_sent].max()), 3),
        'A_edge_stretch_min_max': [round(float(st.min()), 3), round(float(st.max()), 3)],
        'intended_edge_stretch_min_max': [round(float(stB.min()), 3), round(float(stB.max()), 3)], 'A_minus_intended_stretch_max_abs': round(float(np.abs(st - stB)[~(is_sent[EG[:, 0]] | is_sent[EG[:, 1]])].max()), 5),
        'A_triangles_flipped_vs_intended': int(((nA * nB).sum(1) < 0).sum()),
        'A_min_distance_from_origin_m': round(float(np.linalg.norm(A, axis=1).min()), 3),
        'A_finite': bool(np.isfinite(A).all()),
        'four_influence_vs_intended_max_mm': round(float(eC.max()), 3), 'four_influence_vs_intended_mean_mm': round(float(eC.mean()), 3)}
    if th == 0: res['rest_return_exact_max_mm'] = round(float(np.linalg.norm(A - X, axis=1)[~is_sent].max() * 1000), 4); res['rest_sentinel_offset_mm'] = round(float(np.linalg.norm(A - X, axis=1)[is_sent].max() * 1000), 3)
    if th in (0, 90, 135): shots[th] = (A, eA, C, eC)
    r = res['angles'][th]; print(th, r, flush=True)
json.dump(res, open(os.path.join(D, 'deform_test.json'), 'w'), indent=1)
# ---- picture: side view (Y forward, Z up), colour = distance from the intended result ----
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig, ax = plt.subplots(2, 3, figsize=(13, 8.5), facecolor='white')
for col, th in enumerate((0, 90, 135)):
    A, eA, C, eC = shots[th]
    for row, (P, e, lab) in enumerate(((A, eA, 'imported 8 influences'), (C, eC, 'cut to 4 influences'))):
        a = ax[row, col]; sc = a.scatter(P[:, 1], P[:, 2], c=e, s=9, cmap='viridis', vmin=0, vmax=max(2.0, float(shots[135][3].max())))
        a.triplot(P[:, 1], P[:, 2], T, lw=0.15, color='0.6'); a.set_aspect('equal'); a.set_title(f'knee {th}°, {lab}\nmax {e.max():.2f} mm from intended', fontsize=10)
        a.set_xticks([]); a.set_yticks([])
fig.colorbar(sc, ax=ax, shrink=0.6, label='distance from the intended (float-weight) result, mm')
fig.suptitle('WolvenKit-imported 8-influence test mesh: offline knee bend (side view)', fontsize=12)
fig.savefig(os.path.join(D, 'deform_test.png'), dpi=110)
