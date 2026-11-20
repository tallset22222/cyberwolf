"""Decode animRig resources: bone names, parents, reference pose, optional A-pose.

Format: docs/04_geometry_skeleton_materials.md section 3.
"""
import os
import struct
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402


def quat_to_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def trs_matrix(t, q, s=(1, 1, 1)):
    M = np.eye(4)
    M[:3, :3] = quat_to_mat(q) * np.asarray(s, dtype=np.float64)
    M[:3, 3] = t
    return M


class Rig:
    def __init__(self, path):
        self.path = path
        r = R(path)
        ci = [i for i, c in enumerate(r.meta['chunks']) if c['class'] == 'animRig'][0]
        c = r.meta['chunks'][ci]
        o, end = c['dataOffset'], c['dataOffset'] + c['dataSize']
        props, stop = r.props(o + 1, end)
        self.names = list(props['boneNames'])
        n = len(self.names)
        self.parents = list(struct.unpack_from(f'<{n}h', r.d, stop))
        p = stop + 2 * n
        self.ref_local = []
        for _ in range(n):
            t = struct.unpack_from('<4f', r.d, p)[:3]
            q = struct.unpack_from('<4f', r.d, p + 16)
            s = struct.unpack_from('<4f', r.d, p + 32)[:3]
            self.ref_local.append(trs_matrix(t, q, s))
            p += 48
        self.tail_consumed = (p == end)

        def tq(x):
            return trs_matrix((x['Translation']['X'], x['Translation']['Y'], x['Translation']['Z']),
                              (x['Rotation']['i'], x['Rotation']['j'], x['Rotation']['k'], x['Rotation']['r']))
        self.apose_local = [tq(x) for x in props['aPoseLS']] if props.get('aPoseLS') else None
        self.apose_model = [tq(x) for x in props['aPoseMS']] if props.get('aPoseMS') else None

    def model_space(self, pose='ref'):
        local = self.apose_local if (pose == 'apose' and self.apose_local) else self.ref_local
        out = [None] * len(self.names)
        for i, L in enumerate(local):
            out[i] = L if self.parents[i] < 0 else out[self.parents[i]] @ L
        return out

    def index(self, name):
        return self.names.index(name)
