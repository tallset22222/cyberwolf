"""Independent re-read and validation of exported .glb files.

Reads the file back without using the exporter's in-memory state and checks:
- container and JSON structure, buffer/accessor bounds, index ranges
- vertex/triangle counts and bounds against the research report (docs/mesh_geometry.json)
- skinned meshes: CPU skinning with the exported joints reproduces the source positions
- orientation: glTF space has +Y up, +Z forward, +X left (checked on named bones)
"""
import json
import struct
import numpy as np

from .rig import trs_matrix

CT = {5126: ('<f4', 4), 5121: ('<u1', 1), 5123: ('<u2', 2), 5125: ('<u4', 4)}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    d = open(path, 'rb').read()
    magic, ver, total = struct.unpack_from('<4sII', d, 0)
    assert magic == b'glTF' and ver == 2 and total == len(d), 'bad GLB header'
    jl, jt = struct.unpack_from('<I4s', d, 12)
    assert jt == b'JSON'
    doc = json.loads(d[20:20 + jl])
    bl, bt = struct.unpack_from('<I4s', d, 20 + jl)
    assert bt == b'BIN\0'
    bin_ = d[28 + jl:28 + jl + bl]
    return doc, bin_


def accessor(doc, bin_, i):
    a = doc['accessors'][i]
    v = doc['bufferViews'][a['bufferView']]
    dt, sz = CT[a['componentType']]
    n = NC[a['type']]
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    assert off + a['count'] * n * sz <= v['byteOffset'] + v['byteLength'] <= len(bin_), f'accessor {i} out of bounds'
    arr = np.frombuffer(bin_, dtype=dt, count=a['count'] * n, offset=off)
    return arr.reshape(a['count'], n) if n > 1 else arr


def node_globals(doc):
    nodes = doc['nodes']
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            parent[c] = i
    G = [None] * len(nodes)

    def g(i):
        if G[i] is None:
            n = nodes[i]
            L = trs_matrix(n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1]), n.get('scale', [1, 1, 1]))
            G[i] = L if i not in parent else g(parent[i]) @ L
        return G[i]
    for i in range(len(nodes)):
        g(i)
    return G


def validate(path, reference=None):
    doc, bin_ = read_glb(path)
    rep = {'file': path, 'checks': {}, 'lods': {}}
    ok = rep['checks']
    G = node_globals(doc)
    root = [i for i, n in enumerate(doc['nodes']) if n['name'].startswith('cyberwolf_root')][0]
    Rroot = G[root]
    skin = doc.get('skins', [None])[0]
    skin_mats = {}
    for si, sk in enumerate(doc.get('skins', [])):
        ibm = accessor(doc, bin_, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        skin_mats[si] = np.array([G[j] @ ibm[k] for k, j in enumerate(sk['joints'])])
    mesh_skin = {n['mesh']: n.get('skin') for n in doc['nodes'] if 'mesh' in n}
    per_mesh_err = {}
    max_skin_err = 0.0
    disp = []
    idx_ok = True
    norm_dev = 0.0
    wsum_dev = 0.0
    mins, maxs = [], []
    for mi, m in enumerate(doc['meshes']):
        lodname = m['name'].rsplit(' ', 1)[-1]
        joint_mats = skin_mats.get(mesh_skin.get(mi))
        nv = nt = 0
        for p in m['primitives']:
            A = p['attributes']
            P = accessor(doc, bin_, A['POSITION']).astype(np.float64)
            I = accessor(doc, bin_, p['indices'])
            idx_ok &= bool(I.max() < len(P)) and len(I) % 3 == 0
            nv += len(P)
            nt += len(I) // 3
            if lodname == 'LOD0':
                mins.append(P.min(axis=0))
                maxs.append(P.max(axis=0))
            if 'NORMAL' in A:
                N = accessor(doc, bin_, A['NORMAL'])
                norm_dev = max(norm_dev, float(np.abs(np.linalg.norm(N, axis=1) - 1).max()))
            if joint_mats is not None and 'JOINTS_0' in A:
                Js = [accessor(doc, bin_, A[k]).astype(np.int64) for k in sorted(A) if k.startswith('JOINTS_')]
                Ws = [accessor(doc, bin_, A[k]).astype(np.float64) for k in sorted(A) if k.startswith('WEIGHTS_')]
                J = np.concatenate(Js, axis=1)
                W = np.concatenate(Ws, axis=1)
                wsum_dev = max(wsum_dev, float(np.abs(W.sum(axis=1) - 1).max()))
                Ph = np.column_stack([P, np.ones(len(P))])
                skinned = np.zeros((len(P), 4))
                for k in range(J.shape[1]):
                    M = joint_mats[J[:, k]]
                    skinned += W[:, k:k + 1] * np.einsum('nij,nj->ni', M, Ph)
                expected = (Rroot @ Ph.T).T
                e = np.linalg.norm(skinned[:, :3] - expected[:, :3], axis=1)
                max_skin_err = max(max_skin_err, float(e.max()))
                per_mesh_err[m['name']] = max(per_mesh_err.get(m['name'], 0.0), float(e.max()))
                disp.append(e)
        if lodname in rep['lods']:
            lodname = m['name']                  # multi-mesh files: keep each mesh separately
        rep['lods'][lodname] = {'primitives': len(m['primitives']), 'vertices': nv, 'triangles': nt}
    ok['indicesInRange'] = idx_ok
    ok['normalUnitLengthMaxDeviation'] = round(norm_dev, 7)
    if skin:
        ok['skinWeightSumMaxDeviation'] = round(wsum_dev, 7)
        if len(doc['skins']) > 1:
            rep['bindPoseSkinningMaxError_mm_perMesh'] = {k: round(v * 1000, 4) for k, v in per_mesh_err.items()}
        if doc['nodes'][skin['skeleton']].get('extras', {}).get('pose', 'bind') == 'bind':
            ok['bindPoseSkinningMaxError_mm'] = round(max_skin_err * 1000, 4)
        else:
            allD = np.concatenate(disp)
            ok['posedDisplacementFromBind_mm'] = {'max': round(float(allD.max()) * 1000, 1),
                                                  'mean': round(float(allD.mean()) * 1000, 1)}
    if mins:
        lo, hi = np.min(mins, axis=0), np.max(maxs, axis=0)
        rep['lod0BoundsSource_m'] = {'min': [round(float(x), 4) for x in lo], 'max': [round(float(x), 4) for x in hi]}
    if reference:
        diffs = {}
        for k, v in reference.get('lods', {}).items():
            got = rep['lods'].get(k)
            diffs[k] = 'match' if got and got['vertices'] == v['vertices'] and got['triangles'] == v['triangles'] \
                else {'report': v, 'export': got}
        ok['countsMatchResearchReport'] = diffs
        if mins and reference.get('chunks'):
            rlo = np.min([c['bboxMin'] for c in reference['chunks'] if c['lodMask'] & 1], axis=0)
            rhi = np.max([c['bboxMax'] for c in reference['chunks'] if c['lodMask'] & 1], axis=0)
            ok['lod0BoundsMaxDiffVsReport_mm'] = round(float(max(np.abs(lo - rlo).max(), np.abs(hi - rhi).max())) * 1000, 3)
    if skin:
        names = {doc['nodes'][j]['name']: G[j][:3, 3] for sk in doc['skins'] for j in sk['joints']}
        orient = {}
        if 'LeftArm' in names and 'RightArm' in names:
            orient['leftSideIsPlusX'] = bool(names['LeftArm'][0] > names['RightArm'][0])
        hi = next((n for n in ('Head', 'Neck', 'Spine3', 'LeftArm') if n in names), None)
        if hi and 'Hips' in names:
            orient['upIsPlusY'] = bool(names[hi][1] > names['Hips'][1])
        if 'LeftToeBase' in names and 'LeftFoot' in names:
            orient['forwardIsPlusZ'] = bool(names['LeftToeBase'][2] > names['LeftFoot'][2])
        if orient:
            ok['orientation'] = orient
    return rep
