"""Write decoded meshes (and optional skins) as glTF 2.0 binary (.glb).

All vertex data, inverse bind matrices and joint transforms stay in source space
(right-handed, Z-up). A single root node rotates source space into glTF space
(+Y up, +Z forward, +X left): (x, y, z) -> (-x, z, y), a proper rotation.
Source triangles are clockwise-front, so index order is reversed to glTF's
counter-clockwise front faces.
"""
import json
import struct
import numpy as np

SRC_TO_GLTF = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float64)
ROOT_ROTATION = [0.0, 0.7071067811865476, 0.7071067811865476, 0.0]   # 180 deg about (0,1,1)/sqrt2

FLOAT, UBYTE, USHORT, UINT = 5126, 5121, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963
TYPES = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4', 16: 'MAT4'}


def mat_to_trs(M):
    t = M[:3, 3].copy()
    A = M[:3, :3]
    s = np.linalg.norm(A, axis=0)
    Rm = A / s
    if np.linalg.det(Rm) < 0:
        s[0] = -s[0]
        Rm[:, 0] = -Rm[:, 0]
    tr = np.trace(Rm)
    if tr > 0:
        S = np.sqrt(tr + 1.0) * 2
        q = [(Rm[2, 1] - Rm[1, 2]) / S, (Rm[0, 2] - Rm[2, 0]) / S, (Rm[1, 0] - Rm[0, 1]) / S, 0.25 * S]
    elif Rm[0, 0] > Rm[1, 1] and Rm[0, 0] > Rm[2, 2]:
        S = np.sqrt(1.0 + Rm[0, 0] - Rm[1, 1] - Rm[2, 2]) * 2
        q = [0.25 * S, (Rm[0, 1] + Rm[1, 0]) / S, (Rm[0, 2] + Rm[2, 0]) / S, (Rm[2, 1] - Rm[1, 2]) / S]
    elif Rm[1, 1] > Rm[2, 2]:
        S = np.sqrt(1.0 + Rm[1, 1] - Rm[0, 0] - Rm[2, 2]) * 2
        q = [(Rm[0, 1] + Rm[1, 0]) / S, 0.25 * S, (Rm[1, 2] + Rm[2, 1]) / S, (Rm[0, 2] - Rm[2, 0]) / S]
    else:
        S = np.sqrt(1.0 + Rm[2, 2] - Rm[0, 0] - Rm[1, 1]) * 2
        q = [(Rm[0, 2] + Rm[2, 0]) / S, (Rm[1, 2] + Rm[2, 1]) / S, 0.25 * S, (Rm[1, 0] - Rm[0, 1]) / S]
    q = np.array(q)
    q /= np.linalg.norm(q)
    return t, q, s


class GltfBuilder:
    def __init__(self):
        self.bin = bytearray()
        self.doc = {'asset': {'version': '2.0', 'generator': 'cyberwolf research pipeline'},
                    'scene': 0, 'scenes': [{'nodes': []}], 'nodes': [], 'meshes': [],
                    'buffers': [], 'bufferViews': [], 'accessors': []}

    def add_accessor(self, arr, ctype, target=None, minmax=False, normalized=False):
        arr = np.ascontiguousarray(arr)
        ncomp = 1 if arr.ndim == 1 else int(np.prod(arr.shape[1:]))
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': arr.nbytes}
        if target:
            view['target'] = target
        self.bin += arr.tobytes()
        self.doc['bufferViews'].append(view)
        acc = {'bufferView': len(self.doc['bufferViews']) - 1, 'componentType': ctype,
               'count': int(arr.shape[0]), 'type': TYPES[ncomp]}
        if normalized:
            acc['normalized'] = True
        if minmax:
            flat = arr.reshape(arr.shape[0], -1)
            acc['min'] = [float(x) for x in flat.min(axis=0)]
            acc['max'] = [float(x) for x in flat.max(axis=0)]
        self.doc['accessors'].append(acc)
        return len(self.doc['accessors']) - 1

    def add_node(self, node, parent=None):
        self.doc['nodes'].append(node)
        i = len(self.doc['nodes']) - 1
        if parent is None:
            self.doc['scenes'][0]['nodes'].append(i)
        else:
            self.doc['nodes'][parent].setdefault('children', []).append(i)
        return i

    def write(self, path):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(self.doc, separators=(',', ':')).encode('utf-8')
        js += b' ' * (-len(js) % 4)
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, 'wb') as f:
            f.write(struct.pack('<4sII', b'glTF', 2, total))
            f.write(struct.pack('<I4s', len(js), b'JSON') + js)
            f.write(struct.pack('<I4s', len(self.bin), b'BIN\0') + bytes(self.bin))
        return total


def prepare_skin_attributes(chunk):
    """Merge duplicate joint slots, normalise 8-bit weights to floats summing to 1.

    Returns (joints[N,K], weights[N,K], stats) with K = 4 or 8.
    """
    J = chunk.joints.copy()
    W = chunk.weights_raw.astype(np.float64)
    merged = 0
    K = J.shape[1]
    for a in range(K):
        for b in range(a + 1, K):
            dup = (J[:, a] == J[:, b]) & (W[:, b] > 0) & (W[:, a] > 0)
            if dup.any():
                merged += int(dup.sum())
                W[dup, a] += W[dup, b]
                W[dup, b] = 0
    J[W == 0] = 0
    tot = W.sum(axis=1)
    zero = tot == 0
    W[zero, 0] = 1.0
    tot[zero] = 1.0
    W = W / tot[:, None]
    stats = {'rawSumNot255': int((np.abs(chunk.weights_raw.sum(axis=1) - 255) > K // 2 + 1).sum()),
             'duplicateJointSlotsMerged': merged, 'zeroWeightVertices': int(zero.sum())}
    return J, W.astype(np.float32), stats


def build_skeleton(builder, mesh, rigs, root, pose='bind'):
    """Create joint nodes. Mesh joints are placed at their bind pose (inverse of the inverse bind matrix);
    rig-only ancestors use the rig's A-pose when stored, otherwise the reference pose.
    Returns (joint_node_indices in mesh bone order, skeleton_root_node, report)."""
    ibm_col = np.transpose(mesh.ibm_rowvec, (0, 2, 1))        # column-vector form
    world = {}
    parent_of = {}
    source = {}
    for rig in rigs:
        ms = rig.model_space('ref' if pose == 'ref' else ('apose' if rig.apose_local else 'ref'))
        for i, n in enumerate(rig.names):
            if n not in parent_of:
                source[n] = rig.path.replace('\\', '/').split('/')[-1]
                parent_of[n] = rig.names[rig.parents[i]] if rig.parents[i] >= 0 else None
                world[n] = ms[i]
    unresolved = [n for n in mesh.bone_names if n not in parent_of]
    for n in unresolved:
        parent_of[n] = None
    rig_world = dict(world)
    bind_world = {n: np.linalg.inv(ibm_col[k]) for k, n in enumerate(mesh.bone_names)}
    common = [n for n in mesh.bone_names if n in rig_world]
    per_rig = {}
    for n in common:
        per_rig.setdefault(source[n], []).append(float(np.linalg.norm(bind_world[n][:3, 3] - rig_world[n][:3, 3])))
    placement = {r: {'bones': len(v), 'max_mm': round(max(v) * 1000, 4), 'mean_mm': round(sum(v) / len(v) * 1000, 4)}
                 for r, v in per_rig.items()}
    if pose == 'bind':
        world.update(bind_world)
    else:   # 'rig': joints at the rig's own pose; mesh-only bones fall back to bind
        for n in mesh.bone_names:
            if n not in rig_world:
                world[n] = bind_world[n]
    needed = set()
    for n in mesh.bone_names:
        while n is not None and n not in needed:
            needed.add(n)
            n = parent_of[n]
    order = []
    seen = set()

    def visit(n):
        if n in seen:
            return
        p = parent_of[n]
        if p is not None:
            visit(p)
        seen.add(n)
        order.append(n)
    for n in sorted(needed, key=lambda x: (mesh.bone_names.index(x) if x in mesh.bone_names else 10**6, x)):
        visit(n)
    skel_root = builder.add_node({'name': 'skeleton', 'extras': {'pose': pose}}, parent=root)
    node_of = {}
    for n in order:
        p = parent_of[n]
        Pw = world[p] if p is not None else np.eye(4)
        local = np.linalg.inv(Pw) @ world[n]
        t, q, s = mat_to_trs(local)
        node = {'name': n, 'translation': [float(x) for x in t], 'rotation': [float(x) for x in q]}
        if np.abs(s - 1).max() > 1e-6:
            node['scale'] = [float(x) for x in s]
        node_of[n] = builder.add_node(node, parent=node_of[p] if p is not None else skel_root)
    report = {'pose': pose, 'meshBones': len(mesh.bone_names), 'jointNodes': len(order),
              'bindJointsVsRigPose': placement,
              'rigOnlyAncestorsAdded': len(order) - len(mesh.bone_names),
              'meshBonesWithoutRigParent': unresolved}
    return [node_of[n] for n in mesh.bone_names], skel_root, report


def add_materials(b, specs):
    """specs: list of material specs (see material.gltf_spec). Returns list of material indices."""
    doc = b.doc
    doc.setdefault('images', []); doc.setdefault('textures', []); doc.setdefault('materials', [])
    doc.setdefault('samplers', [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}])
    img_index = {}

    def tex(png):
        if png is None:
            return None
        if id(png) not in img_index:
            while len(b.bin) % 4:
                b.bin.append(0)
            doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(b.bin), 'byteLength': len(png)})
            b.bin += png
            doc['images'].append({'bufferView': len(doc['bufferViews']) - 1, 'mimeType': 'image/png'})
            doc['textures'].append({'source': len(doc['images']) - 1, 'sampler': 0})
            img_index[id(png)] = len(doc['textures']) - 1
        return {'index': img_index[id(png)]}
    out = []
    for s in specs:
        pbr = {'metallicFactor': s.get('metallicFactor', 0.0 if s.get('metallicRoughness') is None else 1.0),
               'roughnessFactor': s.get('roughnessFactor', 1.0)}
        if s.get('baseColorFactor'):
            pbr['baseColorFactor'] = s['baseColorFactor']
        for key, field in (('baseColor', 'baseColorTexture'), ('metallicRoughness', 'metallicRoughnessTexture')):
            t = tex(s.get(key))
            if t:
                pbr[field] = t
        m = {'name': s['name'], 'pbrMetallicRoughness': pbr, 'doubleSided': False,
             'extras': {'shader': s.get('shader'), 'chain': s.get('chain'), 'approximation': s.get('approximation'),
                        'sourceParams': s.get('params')}}
        t = tex(s.get('normal'))
        if t:
            m['normalTexture'] = t
        if s.get('alphaMode'):
            m['alphaMode'] = s['alphaMode']
            if s['alphaMode'] == 'MASK':
                m['alphaCutoff'] = s.get('alphaCutoff', 0.5)
        if s.get('emissiveFactor'):
            m['emissiveFactor'] = [min(1.0, x) for x in s['emissiveFactor']]
            t = tex(s.get('emissive'))
            if t:
                m['emissiveTexture'] = t
        doc['materials'].append(m)
        out.append(len(doc['materials']) - 1)
    return out



def add_mesh_nodes(b, mesh, root, lods, name, skin_idx, mat_index, chunk_materials, rep, skinned):
    """Append one glTF mesh + node per LOD for a decoded Mesh (shared by single-mesh and character export)."""
    jtype = UBYTE if len(mesh.bone_names) < 256 else USHORT
    for lod in lods:
        prims = []
        for c in mesh.lod_chunks(lod):
            attrs = {'POSITION': b.add_accessor(c.position.astype(np.float32), FLOAT, ARRAY_BUFFER, minmax=True)}
            if c.normal is not None:
                n = c.normal / np.maximum(np.linalg.norm(c.normal, axis=1, keepdims=True), 1e-12)
                attrs['NORMAL'] = b.add_accessor(n.astype(np.float32), FLOAT, ARRAY_BUFFER)
            if c.tangent is not None:
                t = c.tangent / np.maximum(np.linalg.norm(c.tangent, axis=1, keepdims=True), 1e-12)
                # w is negated: source bitangent cross(N,T)*w points to +v on 98-100% of triangles, while the normal
                # maps' green axis points to -v (curl test, tests/test_normal_convention.py). glTF applies green along
                # cross(N,T)*w, so flipping w makes every normal map read correctly without altering the textures.
                attrs['TANGENT'] = b.add_accessor(np.column_stack([t, -c.tangent_w]).astype(np.float32), FLOAT, ARRAY_BUFFER)
            if c.uv0 is not None:
                attrs['TEXCOORD_0'] = b.add_accessor(c.uv0, FLOAT, ARRAY_BUFFER)
            if c.uv1 is not None and np.any(c.uv1):
                attrs['TEXCOORD_1'] = b.add_accessor(c.uv1, FLOAT, ARRAY_BUFFER)
            if skinned:
                J, W, st = prepare_skin_attributes(c)
                st['chunk'] = c.index
                rep['skinStats'].append(st)
                dt = np.uint8 if jtype == UBYTE else np.uint16
                for k in range(J.shape[1] // 4):
                    attrs[f'JOINTS_{k}'] = b.add_accessor(J[:, 4 * k:4 * k + 4].astype(dt), jtype, ARRAY_BUFFER)
                    attrs[f'WEIGHTS_{k}'] = b.add_accessor(W[:, 4 * k:4 * k + 4], FLOAT, ARRAY_BUFFER)
            tri = c.indices.reshape(-1, 3)[:, [0, 2, 1]].reshape(-1)        # clockwise -> counter-clockwise
            itype = USHORT if c.num_vertices <= 65535 else UINT
            ind = b.add_accessor(tri.astype(np.uint16 if itype == USHORT else np.uint32), itype, ELEMENT_ARRAY_BUFFER)
            prim = {'attributes': attrs, 'indices': ind, 'mode': 4, 'extras': {'sourceChunk': c.index}}
            if chunk_materials and c.index < len(chunk_materials) and chunk_materials[c.index] in mat_index:
                prim['material'] = mat_index[chunk_materials[c.index]]
                prim['extras']['materialSlot'] = chunk_materials[c.index]
            prims.append(prim)
        if not prims:
            continue
        b.doc['meshes'].append({'name': f'{name} LOD{lod}', 'primitives': prims})
        node = {'name': f'{name} LOD{lod}', 'mesh': len(b.doc['meshes']) - 1}
        if skin_idx is not None:
            node['skin'] = skin_idx
        b.add_node(node, parent=root)
        rep['lods'][f'LOD{lod}'] = {'primitives': len(prims),
                                    'vertices': int(sum(mesh.chunks[p['extras']['sourceChunk']].num_vertices for p in prims)),
                                    'triangles': int(sum(len(mesh.chunks[p['extras']['sourceChunk']].indices) // 3 for p in prims))}

def export_mesh(mesh, out_path, rigs=(), lods=(0,), name=None, pose='bind', materials=None, chunk_materials=None):
    """materials: {slot name: spec}; chunk_materials: slot name per render chunk (from one appearance)."""
    b = GltfBuilder()
    root = b.add_node({'name': 'cyberwolf_root (Z-up to Y-up)', 'rotation': ROOT_ROTATION})
    name = name or mesh.path.replace('\\', '/').split('/')[-1]
    skinned = bool(mesh.bone_names) and all(c.joints is not None for c in mesh.chunks)
    skin_idx = None
    rep = {'source': mesh.path, 'skinned': skinned, 'lods': {}, 'skinStats': []}
    if skinned:
        joints, skel_root, srep = build_skeleton(b, mesh, list(rigs), root, pose)
        ibm = mesh.ibm_rowvec.astype(np.float32).reshape(len(mesh.bone_names), 16)   # row-major rowvec == column-major colvec
        acc = b.add_accessor(ibm, FLOAT)
        b.doc['skins'] = [{'name': f'{name} skin', 'joints': joints, 'inverseBindMatrices': acc, 'skeleton': skel_root}]
        skin_idx = 0
        rep['skeleton'] = srep
    mat_index = {}
    if materials:
        names = list(materials)
        for n, i in zip(names, add_materials(b, [materials[n] for n in names])):
            mat_index[n] = i
    add_mesh_nodes(b, mesh, root, lods, name, skin_idx, mat_index, chunk_materials, rep, skinned)
    rep['bytes'] = b.write(out_path)
    rep['output'] = out_path
    return rep
