"""Decode CR2W mesh resources (rendRenderMeshBlob) into numpy arrays.

Format: docs/04_geometry_skeleton_materials.md section 2 and docs/05 section 1.
Coordinates are returned in source space: right-handed, Z-up, metres, clockwise front faces.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402  (existing research decoder)

ELEM_SIZE = {'PT_Short4N': 8, 'PT_Float16_2': 4, 'PT_Dec4': 4, 'PT_Color': 4, 'PT_UByte4': 4, 'PT_UByte4N': 4,
             'PT_Float16_4': 8, 'PT_Float3': 12, 'PT_Float4': 16, 'PT_Float2': 8, 'PT_Short2N': 4,
             'PT_UShort4': 8, 'PT_UShort4N': 8, 'PT_Float1': 4}


def _v(d, keys):
    return np.array([d.get(k, 0.0) for k in keys], dtype=np.float64)


def _dec4(u):
    u = u.astype(np.uint32)
    xyz = np.stack([(u >> s) & 0x3FF for s in (0, 10, 20)], axis=1).astype(np.float64) / 1023.0 * 2.0 - 1.0
    w = (u >> 30).astype(np.int64)
    return xyz, w


class MeshChunk:
    pass


class Mesh:
    def __init__(self, path):
        self.path = path
        self.r = R(path)
        chunks = self.r.meta['chunks']
        self.cmesh = self.r.chunk(0)
        bi = [i for i, c in enumerate(chunks) if c['class'] == 'rendRenderMeshBlob'][0]
        blob = self.r.chunk(bi)
        h = blob['header']
        self.header = h
        bidx = blob['renderBuffer']['buffer'] - 1
        self.buffer_path = f"{path}.buffer{bidx}"
        if os.path.exists(self.buffer_path):          # buffers extracted beside the file
            self.B = open(self.buffer_path, 'rb').read()
        else:                                         # buffers embedded in the CR2W file (WolvenKit project files)
            from kark import unkark
            b = self.r.meta['buffers'][bidx]
            self.B = unkark(self.r.d[b['offset']:b['offset'] + b['diskSize']], b['memSize'])
            self.buffer_path = f"{path}#embedded{bidx}"
        self.qs = _v(h['quantizationScale'], 'XYZ')
        self.qo = _v(h['quantizationOffset'], 'XYZ')
        self.lod_distances = h.get('renderLODs', [])
        self.bone_names = list(self.cmesh.get('boneNames') or [])
        mats = self.cmesh.get('boneRigMatrices') or []
        # Stored row-vector form, rows X,Y,Z,W (W = translation): p' = p @ M
        self.ibm_rowvec = np.array([[[m[r][c] for c in 'XYZW'] for r in 'XYZW'] for m in mats], dtype=np.float64)
        self.chunks = [self._decode_chunk(i, c) for i, c in enumerate(h['renderChunkInfos'])]

    def _decode_chunk(self, ci, c):
        B = self.B
        h = self.header
        cv = c['chunkVertices']
        lay = cv['vertexLayout']
        offs = cv['byteOffsets']
        strides = lay['slotStrides']
        nv = c['numVertices']
        ni = c['numIndices']
        # CR2W omits properties at their default value. For vertex elements the enum defaults (value 0) are
        # type = PT_Float1 (4 bytes) and usage = PS_SysPosition; first seen on Judy's head (PS_LightBlockerIntensity).
        els = [dict(e, type=e.get('type', 'PT_Float1'), usage=e.get('usage', 'PS_SysPosition')) for e in lay['elements']]
        in_stream = {}
        pos_in_stream = {}
        for e in els:
            s = e.get('streamIndex', 0)
            in_stream[id(e)] = pos_in_stream.get(s, 0)
            pos_in_stream[s] = pos_in_stream.get(s, 0) + ELEM_SIZE.get(e['type'], 0)

        def column(e):
            s = e.get('streamIndex', 0)
            if s >= len(offs) or not strides[s]:
                return None          # runtime-supplied stream (e.g. stream 7): no bytes in the buffer
            st = strides[s]
            raw = np.frombuffer(B, dtype=np.uint8, count=nv * st, offset=offs[s]).reshape(nv, st)
            o = in_stream[id(e)]
            return np.ascontiguousarray(raw[:, o:o + ELEM_SIZE[e['type']]])

        m = MeshChunk()
        m.index, m.lod_mask, m.num_vertices = ci, c['lodMask'], nv
        m.layout = [f"{e.get('usage')}{e.get('usageIndex', 0) or ''}:{e['type']}@s{e.get('streamIndex', 0)}" for e in els]
        m.normal = m.tangent = m.tangent_w = m.uv0 = m.uv1 = m.color = None
        joints, weights = [], []
        for e in els:
            u, t, ui = e.get('usage'), e['type'], e.get('usageIndex', 0)
            if t not in ELEM_SIZE:
                continue             # PT_Invalid / unknown: layout terminator, no bytes
            col = column(e)
            if col is None:
                continue
            if u == 'PS_Position' and t == 'PT_Short4N':
                q = col.view('<i2').reshape(nv, 4)[:, :3].astype(np.float64)
                m.position = q / 32767.0 * self.qs + self.qo
            elif u == 'PS_Normal' and t == 'PT_Dec4':
                m.normal, _ = _dec4(col.view('<u4').reshape(nv))
            elif u == 'PS_Tangent' and t == 'PT_Dec4':
                xyz, w = _dec4(col.view('<u4').reshape(nv))
                m.tangent, m.tangent_w = xyz, np.where(w == 3, -1.0, 1.0)
            elif u == 'PS_TexCoord' and t == 'PT_Float16_2':
                uv = col.view('<f2').reshape(nv, 2).astype(np.float32)
                if ui == 0:
                    m.uv0 = uv
                elif ui == 1:
                    m.uv1 = uv
            elif u == 'PS_Color' and t == 'PT_Color':
                m.color = col.reshape(nv, 4)
            elif u == 'PS_SkinIndices' and t == 'PT_UByte4':
                joints.append(col.reshape(nv, 4))
            elif u == 'PS_SkinWeights' and t == 'PT_UByte4N':
                weights.append(col.reshape(nv, 4))
        m.joints = np.concatenate(joints, axis=1).astype(np.int64) if joints else None
        m.weights_raw = np.concatenate(weights, axis=1).astype(np.int64) if weights else None
        te = c['chunkIndices'].get('teOffset', 0)
        m.indices = np.frombuffer(B, dtype='<u2', count=ni, offset=h['indexBufferOffset'] + te).astype(np.int64)
        return m

    def lod_chunks(self, lod):
        return [c for c in self.chunks if c.lod_mask >> lod & 1]

    @property
    def lods(self):
        return sorted({b for c in self.chunks for b in range(8) if c.lod_mask >> b & 1})
