"""OI-19 import test asset: a simple tube around the left knee, skinned with up to 8 influences, written as a glTF
that WolvenKit's importer accepts (conventions read from WolvenKit.Modkit/RED4/Tools/MeshImportTools.cs):
  * positions/normals/tangents are read raw from accessors, glTF (x,y,z) -> RED (x,-z,y); node transforms ignored
  * JOINTS_0/1 + WEIGHTS_0/1 read; joint indices remapped to the template mesh's bones BY NAME
  * weight bytes = Convert.ToByte(w*255) per weight, no renormalisation (sum can drift from 255)
  * submeshes named submesh_NN_LOD_1 (LOD_1 = highest detail); every joint node needs a parent node
Template: the vanilla jeans mesh l1_003_ma_pants__jeans.mesh (8 influences at LOD0). Isolated test only.
Outputs: tests_assets/infl8_import/{l1_003_ma_pants__jeans.glb, expected.json}"""
import sys, os, json, struct, numpy as np
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
from cyberwolf.mesh import Mesh
from cyberwolf.gltf import GltfBuilder, FLOAT, UBYTE, USHORT, ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER
TEMPLATE = os.path.join(ROOT, 'pipeline_cache/base/characters/garment/citizen_casual/legs/l1_003_pants__jeans/l1_003_ma_pants__jeans.mesh')
OUT = os.path.join(ROOT, 'tests_assets', 'infl8_import')
M = Mesh(TEMPLATE); names = M.bone_names
ibm = np.transpose(M.ibm_rowvec, (0, 2, 1))                  # column-vector inverse bind, RED space
bw = {n: np.linalg.inv(ibm[i]) for i, n in enumerate(names)}
P = lambda n: bw[n][:3, 3]
C = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0.0]])            # RED -> glTF: (x, y, z) -> (x, z, -y); inverse of WolvenKit's import map
C4 = np.eye(4); C4[:3, :3] = C
# ---- geometry (RED space): tube from mid-thigh to mid-calf around the left knee ----
a = 0.5 * (P('LeftUpLeg') + P('LeftLeg')); b = 0.5 * (P('LeftLeg') + P('LeftFoot'))
knee = P('LeftLeg'); RING, SEG, RAD = 13, 24, 0.075
def frame(d):
    d = d / np.linalg.norm(d); u = np.cross(d, [0, 0, 1.0]); u = u if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0]); u /= np.linalg.norm(u)
    return d, u, np.cross(d, u)
pos, nrm, tan, uv, tsel = [], [], [], [], []
for r in range(RING):
    t = r / (RING - 1)
    c = (1 - t) * a + t * b if True else None
    # bend the axis through the knee: piecewise linear a -> knee -> b
    c = a + (knee - a) * (2 * t) if t <= 0.5 else knee + (b - knee) * (2 * t - 1)
    d = (knee - a) if t < 0.5 else (b - knee); d, u, w = frame(d)
    for s in range(SEG):
        th = 2 * np.pi * s / SEG; n = np.cos(th) * u + np.sin(th) * w
        pos.append(c + RAD * n); nrm.append(n); tan.append(np.cross(d, n)); uv.append((s / SEG, t)); tsel.append(t)
pos, nrm, tan, uv, tsel = map(np.array, (pos, nrm, tan, uv, tsel))
idx = []
for r in range(RING - 1):
    for s in range(SEG):
        i0 = r * SEG + s; i1 = r * SEG + (s + 1) % SEG; j0 = i0 + SEG; j1 = i1 + SEG
        idx += [i0, j0, i1, i1, j0, j1]
# sentinel band: a separate short tube below the knee, 2 rings, with 8 EQUAL weights (0.125: not a multiple of 1/255)
sent0 = len(pos); sc = knee + (b - knee) * 0.9; d, u, w = frame(b - knee)
for k, off in enumerate((-0.01, 0.01)):
    for s in range(SEG):
        th = 2 * np.pi * s / SEG; n = np.cos(th) * u + np.sin(th) * w
        pos = np.vstack([pos, sc + d * off + (RAD + 0.01) * n]); nrm = np.vstack([nrm, n]); tan = np.vstack([tan, np.cross(d, n)])
        uv = np.vstack([uv, [s / SEG, 0.95 + 0.05 * k]]); tsel = np.append(tsel, 0.95)
for s in range(SEG):
    i0 = sent0 + s; i1 = sent0 + (s + 1) % SEG; idx += [i0, i0 + SEG, i1, i1, i0 + SEG, i1 + SEG]
nv = len(pos)
# ---- weights: exact bytes (sum 255) for the tube; 8 x 0.125 for the sentinel ----
BONES = ['LeftUpLeg', 'LeftLeg', 'l_thigh_1_JNT', 'l_knee_mscl_JNT', 'l_calf_0_JNT', 'l_leg_back_A_mscl_JNT', 'l_lowLeg_back_A_mscl_JNT', 'l_thigh_0_JNT']
assert all(x in names for x in BONES), [x for x in BONES if x not in names]
SECOND = np.array([0.30, 0.22, 0.18, 0.12, 0.10, 0.08])       # secondary-bone shares (of 25 %), descending
def ring_count(t): return 4 if t < 0.15 else (5 if t < 0.3 else (6 if t < 0.45 else 8))
def exact_bytes(wf):
    """Largest-remainder rounding to bytes summing exactly 255, no zero for a nonzero weight."""
    x = wf / wf.sum() * 255; f = np.floor(x).astype(int); f = np.maximum(f, 1); rem = 255 - f.sum()
    order = np.argsort(-(x - np.floor(x)))
    i = 0
    while rem != 0:
        k = order[i % len(order)]
        if rem > 0: f[k] += 1; rem -= 1
        elif f[k] > 1: f[k] -= 1; rem += 1
        i += 1
    return f
J = np.zeros((nv, 8), int); WB = np.zeros((nv, 8), int); WF = np.zeros((nv, 8), np.float32); expect = []
for v in range(nv):
    if v >= sent0:
        J[v] = [names.index(x) for x in BONES]; WF[v] = 0.125; WB[v] = -1; expect.append({'bones': BONES, 'gltf_weight': 0.125, 'kind': 'sentinel_equal_8'}); continue
    t = tsel[v]; k = ring_count(t); s = (v % SEG)
    main = np.array([1 - t, t]) * 0.75
    sec = np.roll(SECOND, s % 6)[: k - 2]                       # which secondary bone is largest rotates around the ring
    wf = np.concatenate([main, 0.25 * sec / sec.sum()]) if k > 2 else main
    bb = exact_bytes(np.maximum(wf, 1e-6))
    J[v, :k] = [names.index(x) for x in BONES[:k]]; WB[v, :k] = bb; WF[v, :k] = bb / 255.0
    expect.append({'bones': BONES[:k], 'bytes': [int(x) for x in bb], 'kind': f'exact_{k}'})
# ---- write glTF ----
B = GltfBuilder(); doc = B.doc
arm = B.add_node({'name': 'Armature'})
joint_nodes = []
for i, n in enumerate(names):
    Wg = C4 @ bw[n] @ np.linalg.inv(C4)
    from cyberwolf.gltf import mat_to_trs
    t_, q_, s_ = mat_to_trs(Wg)
    joint_nodes.append(B.add_node({'name': n, 'translation': [float(x) for x in t_], 'rotation': [float(x) for x in q_]}, parent=arm))
ibm_g = np.array([np.linalg.inv(C4 @ bw[n] @ np.linalg.inv(C4)) for n in names])
acc_ibm = B.add_accessor(ibm_g.transpose(0, 2, 1).reshape(len(names), 16).astype(np.float32), FLOAT)   # column-major
doc['skins'] = [{'name': 'Armature', 'joints': joint_nodes, 'inverseBindMatrices': acc_ibm, 'skeleton': arm}]
g = lambda X: (X @ C.T).astype(np.float32)
attrs = {'POSITION': B.add_accessor(g(pos), FLOAT, ARRAY_BUFFER, minmax=True), 'NORMAL': B.add_accessor(g(nrm), FLOAT, ARRAY_BUFFER),
         'TANGENT': B.add_accessor(np.column_stack([g(tan), np.ones(nv)]).astype(np.float32), FLOAT, ARRAY_BUFFER),
         'TEXCOORD_0': B.add_accessor(uv.astype(np.float32), FLOAT, ARRAY_BUFFER)}
for k in range(2):
    attrs[f'JOINTS_{k}'] = B.add_accessor(J[:, 4 * k:4 * k + 4].astype(np.uint8), UBYTE, ARRAY_BUFFER)
    attrs[f'WEIGHTS_{k}'] = B.add_accessor(WF[:, 4 * k:4 * k + 4], FLOAT, ARRAY_BUFFER)
ind = B.add_accessor(np.array(idx, np.uint16), USHORT, ELEMENT_ARRAY_BUFFER)
doc['meshes'] = [{'name': 'submesh_00_LOD_1', 'primitives': [{'attributes': attrs, 'indices': ind, 'mode': 4}]}]
B.add_node({'name': 'submesh_00_LOD_1', 'mesh': 0, 'skin': 0}, parent=arm)
path = os.path.join(OUT, 'l1_003_ma_pants__jeans.glb'); B.write(path)
# predicted WolvenKit bytes for the sentinel (Convert.ToByte rounds half to even): 0.125*255 = 31.875 -> 32
json.dump({'template': os.path.relpath(TEMPLATE, ROOT), 'vertices': nv, 'tube_vertices': sent0, 'sentinel_vertices': nv - sent0,
           'positions_red': [[round(float(x), 6) for x in p] for p in pos], 'expected': expect,
           'sentinel_prediction': {'bytes_each': 32, 'sum': 256, 'reason': 'Convert.ToByte(0.125*255=31.875) rounds to 32; no renormalisation'}},
          open(os.path.join(OUT, 'expected.json'), 'w'))
cnt = {}
for e in expect: cnt[e['kind']] = cnt.get(e['kind'], 0) + 1
print(path, os.path.getsize(path), 'bytes |', nv, 'vertices', len(idx) // 3, 'triangles |', cnt)
