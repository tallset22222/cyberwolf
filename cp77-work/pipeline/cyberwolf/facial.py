"""Facial setup (animFacialSetup, 'sermo' pose library) decoding.

Buffers (layouts cross-checked against WolvenKit's AnimFacialSetup*Reader, credited; independent code):
  bakedData:          u16 lipsyncOverrideMap[n], u8 jointRegions[numJointRegions], then per part (face, tongue, eyes):
                      envelopesPerTrackMapping(u16 track,u8 lod,u8 env) globalLimits(f32 max,mid,min,u16 track,u8 env,u8 cache)
                      influencedPoses(u16,u8,u8) influenceIndices(u16) upperLowerFace(u16,u8,u8) lipsyncPosesSides(u16,u8,u8)
                      globalCorrectiveEntries(u16 idx,u16 track<<4|x) inbetweenCorrectiveEntries(same)
                      correctiveInfluencedPoses(u16,u8,u8) correctiveInfluenceIndices(u16) allMainPoses(u16 track,u8 nInb,u8)
                      allMainPosesInbetweens(f32) inbetweenScopeMultipliers(f32) wrinkles(u16)
  mainPosesData:      per part: poses(i32 transformIdx, i32 scaleIdx, u16 n|isScale<<15, u16 x3) transforms(quat f32x4,
                      trans f32x3, u16 bone, u8 region, u8 pad) scales(f32x4)
"""
import os
import struct
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402

PARTS = ('face', 'tongue', 'eyes')


class Reader:
    def __init__(self, d):
        self.d, self.o = d, 0

    def take(self, fmt, n):
        out = []
        sz = struct.calcsize('<' + fmt)
        for _ in range(n):
            out.append(struct.unpack_from('<' + fmt, self.d, self.o)); self.o += sz
        return out


class FacialSetup:
    def __init__(self, path):
        r = R(path)
        c = r.chunk(0)
        self.rig = (c.get('rig') or {}).get('ref')
        self.info, self.poses_info = c['info'], c['posesInfo']
        buf = lambda k: open(f"{path}.buffer{c[k]['buffer'] - 1}", 'rb').read()
        self.corrective_names = {'face': list(c.get('faceCorrectiveNames') or []), 'tongue': list(c.get('tongueCorrectiveNames') or []), 'eyes': []}
        self._baked(buf('bakedData'))
        self._main(buf('mainPosesData'))
        self._corrective(buf('correctivePosesData'))

    def _baked(self, d):
        rd = Reader(d); info = self.info
        self.lipsync_map = [x[0] for x in rd.take('H', info.get('numLipsyncOverridesIndexMapping', 0))]
        self.joint_regions = [x[0] for x in rd.take('B', info.get('numJointRegions', 0))]
        self.baked = {}
        for part in PARTS:
            pi = info.get(part, {}) or {}
            g = lambda k: pi.get(k, 0)
            p = {'envelopes': rd.take('HBB', g('numEnvelopesPerTrackMapping')), 'limits': rd.take('fffHBB', g('numGlobalLimits')),
                 'influenced': rd.take('HBB', g('numInfluencedPoses')), 'influenceIdx': rd.take('H', g('numInfluenceIndices')),
                 'upperLower': rd.take('HBB', g('numUpperLowerFace')), 'sides': rd.take('HBB', g('numLipsyncPosesSides')),
                 'globalCorr': rd.take('HH', g('numGlobalCorrectiveEntries')), 'inbCorr': rd.take('HH', g('numInbetweenCorrectiveEntries')),
                 'corrInfluenced': rd.take('HBB', g('numCorrectiveInfluencedPoses')), 'corrInfluenceIdx': rd.take('H', g('numCorrectiveInfluenceIndices')),
                 'mainPoses': rd.take('HBB', g('numAllMainPoses')), 'inbetweens': [x[0] for x in rd.take('f', g('numAllMainPosesInbetweens'))],
                 'scopeMult': [x[0] for x in rd.take('f', g('numAllMainPosesInbetweenScopeMultipliers'))],
                 'wrinkles': rd.take('H', g('numWrinkles'))}
            self.baked[part] = p
        self.baked_consumed, self.baked_size = rd.o, len(d)

    def _main(self, d):
        rd = Reader(d)
        self.poses = {}
        for part in PARTS:
            pi = self.poses_info.get(part, {}) or {}
            heads = rd.take('iiHHHH', pi.get('numMainPoses', 0))
            tr = rd.take('fffffffHBB', pi.get('numMainTransforms', 0))
            sc = rd.take('ffff', pi.get('numMainScales', 0))
            self.poses[part] = {'heads': [{'transformIdx': h[0], 'scaleIdx': h[1], 'n': h[2] & 0x7FFF, 'isScale': bool(h[2] >> 15)} for h in heads],
                                'q': np.array([t[0:4] for t in tr]), 't': np.array([t[4:7] for t in tr]),
                                'bone': np.array([t[7] for t in tr], dtype=int), 'region': np.array([t[8] for t in tr], dtype=int),
                                'scales': np.array(sc)}
        self.main_consumed, self.main_size = rd.o, len(d)

    def _corrective(self, d):
        rd = Reader(d)
        self.corrective_poses = {}
        for part in PARTS:
            pi = self.poses_info.get(part, {}) or {}
            heads = rd.take('iiHHHH', pi.get('numCorrectivePoses', 0))
            tr = rd.take('fffffffHBB', pi.get('numCorrectiveTransforms', 0))
            sc = rd.take('ffff', pi.get('numCorrectiveScales', 0))
            self.corrective_poses[part] = {'heads': [{'transformIdx': h[0], 'scaleIdx': h[1], 'n': h[2] & 0x7FFF} for h in heads],
                                           'q': np.array([t[0:4] for t in tr]).reshape(-1, 4), 't': np.array([t[4:7] for t in tr]).reshape(-1, 3),
                                           'bone': np.array([t[7] for t in tr], dtype=int)}
        self.corrective_consumed, self.corrective_size = rd.o, len(d)

    def corrective_tracks(self, part='face'):
        """{corrective index: [(track, low nibble)]} from globalCorrectiveEntries (u16 index, u16 track<<4 | x)."""
        out = {}
        for idx, bits in self.baked[part]['globalCorr']:
            out.setdefault(idx, []).append((bits >> 4, bits & 0xF))
        return out

    def pose_slots(self, part='face'):
        """[(track, threshold, pose_index)] in storage order: each main pose has nInbetweens slots."""
        b = self.baked[part]; out = []; k = 0
        for track, ninb, _ in b['mainPoses']:
            for s in range(max(ninb, 1)):
                out.append((track, b['inbetweens'][k] if k < len(b['inbetweens']) else 1.0, k)); k += 1
        return out


def _slerp_id(q, w):
    """Scale a rotation by weight w (slerp from identity)."""
    q = np.asarray(q, dtype=np.float64)
    q = q if q[3] >= 0 else -q
    ang = 2 * np.arccos(np.clip(q[3], -1, 1))
    if ang < 1e-9:
        return np.array([0, 0, 0, 1.0])
    axis = q[:3] / np.sin(ang / 2)
    a = ang * w
    return np.concatenate([axis * np.sin(a / 2), [np.cos(a / 2)]])


def _qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz])


def slot_weights(fs, weights, part):
    """Layer 1 (main poses): per pose-slot activation from track weights; in-betweens interpolated linearly."""
    b = fs.baked[part]; sw_all = []; k = 0
    for track, ninb, _ in b['mainPoses']:
        n = max(ninb, 1); th = b['inbetweens'][k:k + n]; w = float(weights.get(track, 0.0)); sw = np.zeros(n)
        if w > 0:
            prev = 0.0
            for s in range(n):
                lo, hi = prev, th[s]
                if w <= hi or s == n - 1:
                    f = min(1.0, (w - lo) / max(hi - lo, 1e-9)) if w >= lo else 0.0
                    sw[s] = f
                    if s > 0: sw[s - 1] = 1 - f
                    break
                prev = hi
        sw_all.extend(sw); k += n
    return np.array(sw_all)


def corrective_weights(fs, weights, sw, part, rule='product'):
    """Layer 2 (correctives): activation of each corrective from its components. Components are decoded and verified
    against the corrective names (255/255 face, 4/4 tongue); the combination RULE is inferred (default: product)."""
    b = fs.baked[part]; comp = {}
    for idx, bits in b['globalCorr']:
        comp.setdefault(idx, []).append(min(max(float(weights.get(bits >> 4, 0.0)), 0.0), 1.0))
    for idx, bits in b['inbCorr']:
        comp.setdefault(idx, []).append(float(sw[bits >> 4]) if (bits >> 4) < len(sw) else 0.0)
    n = len(fs.corrective_poses[part]['heads'])
    cw = np.zeros(n)
    for idx, vals in comp.items():
        if idx < n:
            cw[idx] = np.prod(vals) if rule == 'product' else min(vals)
    return cw


LIPSYNC_SUFFIX_OUTPUT = 'LipsyncPoseOutput'
LIPSYNC_SUFFIX_OVERRIDE = 'AnimOverrideWeight'


def lipsync_weights(weights, track_names, rule='pose_output', overrides='ignore'):
    """Layer 0 (lipsync): combine a clip's tracks into main-pose weights before evaluation.
    Established (22 voice lines, loudness vs lip opening r = 0.81 pooled, 0 ms offset): '<pose>LipsyncPoseOutput'
    tracks drive their poses. NOT established: the role of '<pose>AnimOverrideWeight' tracks (values -1.2..0; default
    'ignore'; 'suppress' scales expression weights by (1 + override)) and of the lipsync envelopes."""
    if rule == 'none':
        return dict(weights)
    out = dict(weights)
    idx = {n: i for i, n in enumerate(track_names)}
    for i, n in enumerate(track_names):
        if n.endswith(LIPSYNC_SUFFIX_OUTPUT) and i in weights:
            tgt = idx.get(n[:-len(LIPSYNC_SUFFIX_OUTPUT)])
            if tgt is not None:
                out[tgt] = weights[i]
    if overrides == 'suppress':
        for i, n in enumerate(track_names):
            if n.endswith(LIPSYNC_SUFFIX_OVERRIDE) and i in weights:
                tgt = idx.get(n[:-len(LIPSYNC_SUFFIX_OVERRIDE)])
                if tgt is not None and (tgt + 0) in weights and track_names[tgt] + LIPSYNC_SUFFIX_OUTPUT not in idx:
                    out[tgt] = weights[tgt] * max(0.0, 1.0 + weights[i])
    return out


def envelope_check(fs, weights):
    """Layer 3 (envelopes/limits): exactly neutral while all envelope tracks (0-12) are 0, which holds for the idle
    clips examined. Their behaviour when non-zero is not yet established; report rather than guess."""
    active = {t: v for t, v in weights.items() if t < 13 and abs(v) > 1e-6}
    return {'neutral': not active, 'activeEnvelopes': active}


def evaluate(fs, weights, parts=PARTS, layers=('main', 'correctives'), rule='product'):
    """Facial evaluation from track weights {track: value} -> {joint index: (dq, dt)} local deltas.
    Layers are kept separate: main poses, correctives (inferred product rule), envelopes/limits (see envelope_check)."""
    out = {}
    def apply(P, k, w):
        h = P['heads'][k]
        for i in range(h['transformIdx'], h['transformIdx'] + h['n']):
            j = int(P['bone'][i])
            dq, dt = out.get(j, (np.array([0, 0, 0, 1.0]), np.zeros(3)))
            out[j] = (_qmul(dq, _slerp_id(P['q'][i], w)), dt + P['t'][i] * w)
    for part in parts:
        sw = slot_weights(fs, weights, part)
        if 'main' in layers:
            for k, w in enumerate(sw):
                if w > 0: apply(fs.poses[part], k, w)
        if 'correctives' in layers and fs.corrective_poses[part]['heads']:
            for k, w in enumerate(corrective_weights(fs, weights, sw, part, rule)):
                if w > 1e-6: apply(fs.corrective_poses[part], k, w)
    return out


def _evaluate_main_only_legacy(fs, weights, parts=PARTS):
    out = {}
    for part in parts:
        P, b = fs.poses[part], fs.baked[part]
        k = 0
        for track, ninb, _ in b['mainPoses']:
            n = max(ninb, 1)
            th = b['inbetweens'][k:k + n]
            w = float(weights.get(track, 0.0))
            sw = np.zeros(n)
            if w > 0:
                prev = 0.0
                for s in range(n):
                    lo, hi = prev, th[s]
                    if w <= hi or s == n - 1:
                        f = min(1.0, (w - lo) / max(hi - lo, 1e-9)) if w >= lo else 0.0
                        sw[s] = f
                        if s > 0: sw[s - 1] = 1 - f
                        break
                    prev = hi
            for s in range(n):
                if sw[s] <= 0: continue
                h = P['heads'][k + s]
                for i in range(h['transformIdx'], h['transformIdx'] + h['n']):
                    j = int(P['bone'][i])
                    dq, dt = out.get(j, (np.array([0, 0, 0, 1.0]), np.zeros(3)))
                    out[j] = (_qmul(dq, _slerp_id(P['q'][i], sw[s])), dt + P['t'][i] * sw[s])
            k += n
    return out


def track_values(anim, t):
    """Linear interpolation of an animation's float tracks at times t -> {track: array}."""
    out = {}
    for tr, ks in anim.tracks.items():
        ks = sorted(ks)
        ts = np.array([k[0] for k in ks]); vs = np.array([k[1] for k in ks])
        out[tr] = np.full(len(t), vs[0]) if len(ks) == 1 else np.interp(t, ts, vs)
    return out


def add_facial_animation(glb_in, glb_out, fs, anim, anim_rig, fps=30.0, max_seconds=None, track_names=None, lipsync='pose_output'):
    """Write one facial clip as a glTF animation: per frame, pose deltas from the clip's tracks are applied on top of
    each face joint's node transform; joints with their own keys in the clip (head/neck) take the clip's rotation."""
    from .validate import read_glb
    from .gltf import GltfBuilder, FLOAT, mat_to_trs
    from .rig import quat_to_mat, trs_matrix
    from .anims import sample
    doc, bin_ = read_glb(glb_in)
    b = GltfBuilder(); b.doc, b.bin = doc, bytearray(bin_)
    by_name = {}
    for i, n in enumerate(doc['nodes']):
        by_name.setdefault(n.get('name'), i)
    dur = anim.duration if not max_seconds else min(anim.duration, max_seconds)
    n = max(2, int(round(dur * fps)) + 1)
    t = np.linspace(0, dur, n)
    tv = track_values(anim, t)
    keyed = sorted({j for (j, c) in anim.keys if len(anim.keys[(j, c)]) > 1 and c == 1})
    L_anim = sample(anim, anim_rig, t) if keyed else None
    per_joint = {}
    for f in range(n):
        w = {tr: float(v[f]) for tr, v in tv.items()}
        if track_names is not None:
            w = lipsync_weights(w, track_names, rule=lipsync)
        d = evaluate(fs, w)
        for j in set(d) | set(keyed):
            nm = anim_rig.names[j]
            if nm not in by_name: continue
            node = doc['nodes'][by_name[nm]]
            L = trs_matrix(node.get('translation', [0, 0, 0]), node.get('rotation', [0, 0, 0, 1]), node.get('scale', [1, 1, 1]))
            if j in keyed:
                L[:3, :3] = L_anim[f, j][:3, :3]                    # clip rotation; keep this character's offsets
            if j in d:
                L[:3, :3] = L[:3, :3] @ quat_to_mat(d[j][0]); L[:3, 3] = L[:3, 3] + d[j][1]
            per_joint.setdefault(j, [None] * n)[f] = L
    tacc = b.add_accessor(t.astype(np.float32), FLOAT, minmax=True)
    samplers, channels = [], []
    for j, Ls in per_joint.items():
        node_i = by_name[anim_rig.names[j]]; base = doc['nodes'][node_i]
        Ls = [L if L is not None else trs_matrix(base.get('translation', [0, 0, 0]), base.get('rotation', [0, 0, 0, 1])) for L in Ls]
        T, Q = [], []
        for L in Ls:
            tt, qq, _ = mat_to_trs(L); T.append(tt); Q.append(qq)
        Q = np.array(Q)
        for f in range(1, n):
            if np.dot(Q[f], Q[f - 1]) < 0: Q[f] = -Q[f]
        for path, arr in (('translation', np.array(T)), ('rotation', Q)):
            samplers.append({'input': tacc, 'output': b.add_accessor(arr.astype(np.float32), FLOAT), 'interpolation': 'LINEAR'})
            channels.append({'sampler': len(samplers) - 1, 'target': {'node': node_i, 'path': path}})
    doc.setdefault('animations', []).append({'name': 'facial: ' + anim.name, 'samplers': samplers, 'channels': channels})
    b.write(glb_out)
    rng = {tr: (float(v.min()), float(v.max())) for tr, v in tv.items() if v.max() - v.min() > 1e-4}
    return {'frames': n, 'duration': dur, 'jointsAnimated': len(per_joint), 'tracksVarying': len(rng),
            'trackRange': (min(r[0] for r in rng.values()), max(r[1] for r in rng.values())) if rng else None}
