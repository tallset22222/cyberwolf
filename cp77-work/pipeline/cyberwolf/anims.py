"""Decode animation sets (.anims: animAnimSet -> animAnimation -> animAnimationBufferCompressed).

Key-block layout cross-checked against WolvenKit's animAnimationBufferCompressed (credited reference); this
implementation is independent. Per animation, at dataAddress (chunk, offset, size) in animationDataChunks:
  animKeys      numAnimKeys      x 10 B: u16 time, u16 bits, 3 x u16 quantised value (u/65535*2-1)
  animKeysRaw   numAnimKeysRaw   x 16 B: u16 time, u16 bits, 3 x f32
  constAnimKeys numConstAnimKeys x 16 B: u16 bits, u16 time, 3 x f32
  trackKeys     numTrackKeys     x  8 B: u16 time, u16 track, f32
  constTracks   numConstTrackKeys x 8 B: u16 track, u16 time, f32
bits: bit 15 = quaternion w sign, bits 13-14 = component (0 position, 1 rotation, 2 scale), bits 0-12 = bone index
(index into the animation set's rig). Rotation (x, y, z) -> (x, y, z) * sqrt(2 - d), w = +-(1 - d), d = x^2+y^2+z^2.
Keys are joint-local transforms; joints/channels without keys keep the rig's reference pose. Interpolation is linear
(nlerp for rotations).
"""
import os
import struct
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402


def _rot(x, y, z, wsign):
    d = x * x + y * y + z * z
    s = np.sqrt(np.maximum(2.0 - d, 0.0))
    w = 1.0 - d
    return np.array([x * s, y * s, z * s, -w if wsign else w])


class Animation:
    pass


class AnimSet:
    def __init__(self, path):
        self.path = path
        r = R(path)
        root = r.chunk(0)
        self.rig = (root.get('rig') or {}).get('ref')
        chunk_bufs = []
        for c in root.get('animationDataChunks', []):
            b = c.get('buffer', {}).get('buffer') if isinstance(c.get('buffer'), dict) else None
            chunk_bufs.append(open(f'{path}.buffer{b - 1}', 'rb').read() if b else None)
        self.animations = []
        self.problems = []
        for h in root.get('animations', []):
            entry = r.chunk(h['handle'])
            anim_h = entry.get('animation', {}).get('handle')
            if anim_h is None:
                continue
            a = r.chunk(anim_h)
            bh = a.get('animBuffer', {}).get('handle')
            cls = r.meta['chunks'][bh]['class'] if bh is not None else None
            if cls not in ('animAnimationBufferCompressed', 'animAnimationBufferSimd'):
                self.problems.append((a.get('name'), f'unsupported buffer class {cls}'))
                continue
            buf = r.chunk(bh)
            # dataAddress fields are read positionally: (chunk index, offset, size)
            da = list(buf.get('dataAddress', {}).values())
            chunk_i, off, size = (da + [0, 0, 0])[:3]
            data = chunk_bufs[chunk_i][off:off + size] if chunk_i < len(chunk_bufs) and chunk_bufs[chunk_i] else None
            if data is None:
                for k in ('inplaceCompressedBuffer', 'defferedBuffer', 'tempBuffer'):
                    v = buf.get(k)
                    if isinstance(v, dict) and 'buffer' in v:
                        data = open(f"{path}.buffer{v['buffer'] - 1}", 'rb').read(); size = len(data); break
            dec = self._decode if cls == 'animAnimationBufferCompressed' else self._decode_simd
            A = dec(a.get('name'), buf, data, size)
            A.buffer_class = cls
            self.animations.append(A)

    def _decode(self, name, b, data, size):
        A = Animation()
        A.name, A.duration = name, float(b.get('duration', 0.0))
        A.num_frames, A.num_joints, A.num_tracks = b.get('numFrames', 0), b.get('numJoints', 0), b.get('numTracks', 0)
        n = {k: b.get(k, 0) for k in ('numAnimKeys', 'numAnimKeysRaw', 'numConstAnimKeys', 'numTrackKeys', 'numConstTrackKeys')}
        A.counts = n
        A.expected_bytes = n['numAnimKeys'] * 10 + (n['numAnimKeysRaw'] + n['numConstAnimKeys']) * 16 + (n['numTrackKeys'] + n['numConstTrackKeys']) * 8
        A.declared_bytes = size
        A.keys = {}            # (joint, component) -> list of (time_s, value)
        A.tracks = {}          # track -> list of (time_s, value)
        A.rot_norm_dev = 0.0
        if data is None or len(data) < A.expected_bytes:
            A.ok = False
            return A
        o = 0

        def add(t, bits, vals):
            wsign, comp, bone = bits >> 15, (bits >> 13) & 3, bits & 0x1FFF
            if comp == 1:
                q = _rot(*vals, wsign)
                A.rot_norm_dev = max(A.rot_norm_dev, abs(float(np.linalg.norm(q)) - 1.0))
                v = q / np.linalg.norm(q)
            else:
                v = np.array(vals, dtype=np.float64)
            A.keys.setdefault((bone, comp), []).append((t / 65535.0 * A.duration, v))
        for _ in range(n['numAnimKeys']):
            t, bits, qx, qy, qz = struct.unpack_from('<HHHHH', data, o); o += 10
            add(t, bits, [q / 65535.0 * 2 - 1 for q in (qx, qy, qz)])
        for _ in range(n['numAnimKeysRaw']):
            t, bits, x, y, z = struct.unpack_from('<HHfff', data, o); o += 16
            add(t, bits, [x, y, z])
        for _ in range(n['numConstAnimKeys']):
            bits, t, x, y, z = struct.unpack_from('<HHfff', data, o); o += 16
            add(t, bits, [x, y, z])
        for _ in range(n['numTrackKeys']):
            t, tr, v = struct.unpack_from('<HHf', data, o); o += 8
            A.tracks.setdefault(tr, []).append((t / 65535.0 * A.duration, v))
        for _ in range(n['numConstTrackKeys']):
            tr, t, v = struct.unpack_from('<HHf', data, o); o += 8
            A.tracks.setdefault(tr, []).append((t / 65535.0 * A.duration, v))
        A.consumed = o
        for k in A.keys:
            A.keys[k].sort(key=lambda kv: kv[0])
        A.ok = True
        return A


def _simd_decode(self, name, b, data, size):
    """animAnimationBufferSimd: dense per-frame data in blocks of 4 joints (x[4], y[4], z[4] per block).
    Layout cross-checked against WolvenKit's AnimSIMD.cs (credited); independent implementation."""
    A = Animation()
    A.name, A.duration = name, float(b.get('duration', 0.0))
    F, NJ, NX = b.get('numFrames', 0), b.get('numJoints', 0), b.get('numExtraJoints', 0)
    NT = b.get('numTracks', 0)
    A.num_frames, A.num_joints, A.num_tracks = F, NJ, NT
    qb = b.get('quantizationBits', 0)
    NTe, NTc = b.get('numTranslationsToEvalAlignedToSimd', 0), b.get('numTranslationsToCopy', 0)
    Ja = (NJ - NX + 3) & ~3
    A.counts = {'frames': F, 'joints': NJ, 'extraJoints': NX, 'quantBits': qb, 'evalT': NTe, 'copyT': NTc, 'tracks': NT}
    A.keys, A.tracks, A.rot_norm_dev = {}, {}, 0.0
    A.declared_bytes = size
    if data is None or F < 1:
        A.ok, A.expected_bytes = False, None
        return A
    times = np.linspace(0, A.duration, F) if F > 1 else np.zeros(1)
    o = 0
    rot = np.zeros((F, Ja, 4))
    if qb:
        total = (F * Ja * 3 + 3) & ~3
        nbytes = ((total * qb + 7) // 8 + 15) & ~15
        bits = np.unpackbits(np.frombuffer(data[:nbytes] + b'\0' * 4, dtype=np.uint8), bitorder='little')
        idx = np.arange(total)[:, None] * qb + np.arange(qb)[None, :]
        vals = (bits[idx] * (1 << np.arange(qb))).sum(1).astype(np.float64)
        f = vals / ((1 << qb) - 1) * 2 - 1
        f = f[:F * Ja * 3].reshape(F, Ja // 4, 3, 4)           # [frame, block, xyz, lane]
        x, y, z = f[:, :, 0, :].reshape(F, Ja), f[:, :, 1, :].reshape(F, Ja), f[:, :, 2, :].reshape(F, Ja)
        d = x * x + y * y + z * z
        sc = np.sqrt(np.maximum(2 - d, 0))
        rot = np.stack([x * sc, y * sc, z * sc, 1 - d], -1)
        o = nbytes
    else:
        raw = np.frombuffer(data, dtype='<f4', count=F * Ja * 4, offset=0).reshape(F, Ja // 4, 4, 4).astype(np.float64)
        rot = np.transpose(raw, (0, 1, 3, 2)).reshape(F, Ja, 4)  # lanes -> joints, components xyzw
        o = F * Ja * 16
    n = np.linalg.norm(rot, axis=-1, keepdims=True)
    A.rot_norm_dev = float(np.abs(n - 1).max()) if qb == 0 else 0.0
    rot = rot / np.maximum(n, 1e-12)
    evalp = np.frombuffer(data, dtype='<f4', count=F * NTe * 3, offset=o).reshape(F, max(NTe, 1) // 4 if NTe else 0, 3, 4).astype(np.float64) if NTe else None
    o += F * NTe * 3 * 4
    if b.get('isScaleConstant', 0):
        sconst = np.frombuffer(data, dtype='<f4', count=4, offset=o).astype(np.float64); o += 16
        scales = None
    else:
        scales = np.frombuffer(data, dtype='<f4', count=F * Ja * 3, offset=o).reshape(F, Ja // 4, 3, 4).astype(np.float64); o += F * Ja * 12
    if NT > 0:
        if b.get('isTrackConstant', 0):
            v = struct.unpack_from('<f', data, o)[0]; o += 4
            for t_ in range(NT):
                A.tracks[t_] = [(0.0, v)]
        else:
            nt4 = (NT + 3) & ~3
            tv = np.frombuffer(data, dtype='<f4', count=F * nt4, offset=o).reshape(F, nt4); o += F * nt4 * 4
            for t_ in range(NT):
                A.tracks[t_] = list(zip(times, tv[:, t_].astype(float)))
    copyp = np.frombuffer(data, dtype='<f4', count=NTc * 3, offset=o).reshape(NTc, 3).astype(np.float64); o += NTc * 12
    copyi = np.frombuffer(data, dtype='<i2', count=NTc, offset=o).astype(int); o += NTc * 2
    evali = np.frombuffer(data, dtype='<i2', count=NTe, offset=o).astype(int); o += NTe * 2
    A.consumed = o
    A.expected_bytes = o
    real = NJ - NX
    for j in range(min(real, Ja)):
        A.keys[(j, 1)] = list(zip(times, rot[:, j]))
        if scales is not None:
            sj = scales[:, j // 4, :, j % 4]
            A.keys[(j, 2)] = list(zip(times, sj))
        else:
            A.keys[(j, 2)] = [(0.0, sconst[:3].copy())]
    for e, j in enumerate(evali):
        if 0 <= j < real:
            A.keys[(j, 0)] = list(zip(times, evalp[:, e // 4, :, e % 4]))
    for e, j in enumerate(copyi):
        if 0 <= j < real:
            A.keys[(j, 0)] = [(0.0, copyp[e])]
    A.translation_coverage = len({j for (j, c) in A.keys if c == 0}) / max(real, 1)
    A.ok = True
    return A


AnimSet._decode_simd = _simd_decode


def sample(anim, rig, times):
    """Joint-local 4x4 matrices [len(times), joints] for a rig (reference pose where no keys)."""
    from .rig import quat_to_mat
    nj = len(rig.names)
    out = np.repeat(np.array(rig.ref_local)[None], len(times), axis=0)
    # decompose reference into T, R, S
    ref_t = np.array([L[:3, 3] for L in rig.ref_local])
    ref_s = np.array([np.linalg.norm(L[:3, :3], axis=0) for L in rig.ref_local])
    ref_r = [L[:3, :3] / s for L, s in zip(rig.ref_local, ref_s)]

    def interp(keys, t, rot):
        ts = np.array([k[0] for k in keys])
        vs = np.array([k[1] for k in keys])
        if len(ts) == 1:
            return np.repeat(vs[:1], len(t), 0)
        i = np.clip(np.searchsorted(ts, t) - 1, 0, len(ts) - 2)
        f = np.clip((t - ts[i]) / np.maximum(ts[i + 1] - ts[i], 1e-9), 0, 1)[:, None]
        a, b = vs[i], vs[i + 1]
        if rot:
            b = np.where((np.sum(a * b, 1) < 0)[:, None], -b, b)
            v = a * (1 - f) + b * f
            return v / np.linalg.norm(v, axis=1, keepdims=True)
        return a * (1 - f) + b * f
    t = np.asarray(times, dtype=np.float64)
    for j in range(nj):
        T = interp(anim.keys[(j, 0)], t, False) if (j, 0) in anim.keys else np.repeat(ref_t[j][None], len(t), 0)
        S = interp(anim.keys[(j, 2)], t, False) if (j, 2) in anim.keys else np.repeat(ref_s[j][None], len(t), 0)
        if (j, 1) in anim.keys:
            Q = interp(anim.keys[(j, 1)], t, True)
            Rm = np.array([quat_to_mat(q) for q in Q])
        else:
            Rm = np.repeat(ref_r[j][None], len(t), 0)
        out[:, j, :3, :3] = Rm * S[:, None, :]
        out[:, j, :3, 3] = T
    return out


def add_to_glb(glb_in, glb_out, rig, anims, fps=30.0):
    """Append glTF animations driving joint nodes by name. A rig joint is animated only if its node's parent in the
    file is the same joint as in the rig (else reported), so differing hierarchies are never silently re-parented."""
    import json as _json
    from .validate import read_glb
    from .gltf import GltfBuilder, FLOAT, mat_to_trs
    doc, bin_ = read_glb(glb_in)
    b = GltfBuilder()
    b.doc, b.bin = doc, bytearray(bin_)
    for v in doc['bufferViews']:
        v.pop('target', None) if False else None
    by_name, parent_name = {}, {}
    for i, n in enumerate(doc['nodes']):
        by_name.setdefault(n.get('name'), i)
        for c in n.get('children', []):
            parent_name[c] = n.get('name')
    report = {'rig': rig.path, 'animations': []}
    mapped, skipped = [], {'missing': [], 'parentMismatch': []}
    for j, nm in enumerate(rig.names):
        if nm not in by_name:
            skipped['missing'].append(nm); continue
        p = rig.names[rig.parents[j]] if rig.parents[j] >= 0 else None
        if p is not None and parent_name.get(by_name[nm]) != p:
            skipped['parentMismatch'].append(nm); continue
        mapped.append(j)
    doc.setdefault('animations', [])
    for a in anims:
        n = max(2, int(round(a.duration * fps)) + 1)
        t = np.linspace(0, a.duration, n)
        L = sample(a, rig, t)
        tacc = b.add_accessor(t.astype(np.float32), FLOAT, minmax=True)
        samplers, channels = [], []
        for j in mapped:
            T, Q, S = [], [], []
            for f in range(n):
                tt, qq, ss = mat_to_trs(L[f, j]); T.append(tt); Q.append(qq); S.append(ss)
            Q = np.array(Q)
            for f in range(1, n):                 # keep quaternion hemisphere continuous
                if np.dot(Q[f], Q[f - 1]) < 0: Q[f] = -Q[f]
            node = by_name[rig.names[j]]
            for path, arr in (('translation', np.array(T)), ('rotation', Q)):
                samplers.append({'input': tacc, 'output': b.add_accessor(arr.astype(np.float32), FLOAT), 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': node, 'path': path}})
        doc['animations'].append({'name': a.name, 'samplers': samplers, 'channels': channels})
        report['animations'].append({'name': a.name, 'duration': a.duration, 'frames': n})
    report['jointsAnimated'] = len(mapped)
    report['skipped'] = {k: v for k, v in skipped.items()}
    b.write(glb_out)
    return report
