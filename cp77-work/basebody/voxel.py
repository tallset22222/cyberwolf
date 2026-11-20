"""Solid voxelisation of a closed-ish triangle mesh by vertical ray parity (per (x,z) column).
Used for skin-weight visibility: a bone may influence a vertex only if the straight path from the vertex
(moved slightly inward) to the nearest point on the bone stays inside the body."""
import numpy as np

def voxelize(V, T, h=0.008, pad=2, mirror_x=False):
    """mirror_x=True: the grid is placed symmetrically about x = 0 (cell edges at x = k*h, an even number of columns), so a
    mirror-symmetric mesh gives a mirror-identical solid. Default (False) is the original test-2 grid, kept reproducible."""
    lo = V.min(0) - pad * h; hi = V.max(0) + pad * h
    n = np.ceil((hi - lo) / h).astype(int) + 1
    if mirror_x:
        half = int(np.ceil(max(-lo[0], hi[0]) / h)); lo = lo.copy(); lo[0] = -half * h; n = n.copy(); n[0] = 2 * half
    inside = np.zeros(n, bool)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    xs = lo[0] + (np.arange(n[0]) + 0.5) * h; zs = lo[2] + (np.arange(n[2]) + 0.5) * h
    hits = [[[] for _ in range(n[2])] for _ in range(n[0])]
    xmin = np.minimum(np.minimum(a[:, 0], b[:, 0]), c[:, 0]); xmax = np.maximum(np.maximum(a[:, 0], b[:, 0]), c[:, 0])
    zmin = np.minimum(np.minimum(a[:, 2], b[:, 2]), c[:, 2]); zmax = np.maximum(np.maximum(a[:, 2], b[:, 2]), c[:, 2])
    i0 = np.ceil((xmin - lo[0]) / h - 0.5).astype(int); i1 = np.floor((xmax - lo[0]) / h - 0.5).astype(int)
    k0 = np.ceil((zmin - lo[2]) / h - 0.5).astype(int); k1 = np.floor((zmax - lo[2]) / h - 0.5).astype(int)
    for t in np.where((i1 >= i0) & (k1 >= k0))[0]:
        ii, kk = np.meshgrid(np.arange(i0[t], i1[t] + 1), np.arange(k0[t], k1[t] + 1), indexing='ij')
        px, pz = xs[ii].ravel(), zs[kk].ravel()
        # barycentric in the xz plane
        x0, z0 = a[t, 0], a[t, 2]; x1, z1 = b[t, 0], b[t, 2]; x2, z2 = c[t, 0], c[t, 2]
        det = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2)
        if abs(det) < 1e-14: continue
        l0 = ((z1 - z2) * (px - x2) + (x2 - x1) * (pz - z2)) / det; l1 = ((z2 - z0) * (px - x2) + (x0 - x2) * (pz - z2)) / det; l2 = 1 - l0 - l1
        ok = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        y = l0 * a[t, 1] + l1 * b[t, 1] + l2 * c[t, 1]
        for i, k, yy in zip(ii.ravel()[ok], kk.ravel()[ok], y[ok]): hits[i][k].append(yy)
    ys = lo[1] + (np.arange(n[1]) + 0.5) * h
    for i in range(n[0]):
        for k in range(n[2]):
            hs = sorted(hits[i][k])
            for j in range(0, len(hs) - 1, 2):
                inside[i, (ys > hs[j]) & (ys < hs[j + 1]), k] = True
    return inside, lo, h

def is_inside(points, vox):
    inside, lo, h = vox
    idx = np.floor((points - lo) / h).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(inside.shape)), axis=-1)
    out = np.zeros(points.shape[:-1], bool)
    out[ok] = inside[tuple(idx[ok].T)]
    return out


def _shift_or(a):
    out = a.copy()
    for ax in range(3):
        for s in (1, -1):
            out |= np.roll(a, s, axis=ax)
    return out


def close(vox, iters=2):
    """Morphological closing (6-neighbour dilate then erode, `iters` voxels): fills cavities and gaps narrower than
    about 2*iters voxels (mouth, eye sockets, gaps between toes) so visibility isn't blocked by them."""
    inside, lo, h = vox
    a = inside.copy()
    for _ in range(iters): a = _shift_or(a)
    for _ in range(iters): a = ~_shift_or(~a)
    return a, lo, h
