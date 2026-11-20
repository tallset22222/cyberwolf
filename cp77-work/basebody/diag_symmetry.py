"""Diagnose the left/right asymmetry of the test-2 automatic weights. Re-implements build()'s weight pipeline with
instrumentation and switches; test2_deformation.py itself is not modified."""
import sys, os, numpy as np, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import voxel, test2_deformation as T2
from fit_skeleton import fitted

def mirror_index(V):
    key = {tuple(np.round(v * [-1, 1, 1], 6)): i for i, v in enumerate(V)}
    idx = np.array([key[tuple(np.round(v, 6))] for v in V]); return idx

def voxelize_sym(V, T, h, pad=2):
    """Same as voxel.voxelize, but the x extent is centred on the mirror plane: grid edges at k*h - n*h/2."""
    lo = V.min(0) - pad * h; hi = V.max(0) + pad * h
    half = max(-lo[0], hi[0]); nx = int(np.ceil(2 * half / h)); nx += nx % 2
    Vs = V.copy()
    inside, lo2, h2 = voxel.voxelize(np.vstack([V, [[-nx * h / 2 + pad * h, 0, 0], [nx * h / 2 - pad * h, 0, 0]]]), T, h, pad)
    return inside, lo2, h2

def weights(V, Q, pos, seg_bones, sym_grid=False, vote=7, fan=False):
    bones, A, B = seg_bones
    d = B - A; L2 = np.maximum((d * d).sum(1), 1e-12)
    t = np.clip(((V[:, None, :] - A[None]) * d[None]).sum(2) / L2, 0, 1)
    C = A[None] + t[..., None] * d[None]; D = np.linalg.norm(V[:, None, :] - C, axis=2)
    if fan:   # order-independent split: 4 triangles around each quad's centroid (mirror-consistent)
        Vx = np.vstack([V, V[Q].mean(1)]); c = len(V) + np.arange(len(Q))
        T = np.concatenate([np.stack([Q[:, k], Q[:, (k + 1) % 4], c], 1) for k in range(4)])
    else:
        Vx = V; T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    vn = np.zeros_like(Vx); fn = np.cross(Vx[T[:, 1]] - Vx[T[:, 0]], Vx[T[:, 2]] - Vx[T[:, 0]])
    for k in range(3): np.add.at(vn, T[:, k], fn)
    vn = vn[:len(V)]; vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    raw = voxel.voxelize(Vx, T, h=0.005, mirror_x=sym_grid)
    vox = voxel.close(raw, iters=2); hv = voxel.close(raw, iters=6)[0]
    ys = vox[1][1] + (np.arange(vox[0].shape[1]) + 0.5) * vox[2]
    filled = vox[0].copy(); rows = ys > pos['neck_01'][1] - 0.01; filled[:, rows, :] |= hv[:, rows, :]
    vox = (filled, vox[1], vox[2])
    start = V - 0.003 * vn; cand = np.argsort(D, 1, kind='stable')[:, :6]
    vis = np.zeros(D.shape, bool); ss = np.linspace(0.12, 1.0, 8); votes = np.zeros(D.shape, int)
    for kk in range(6):
        b = cand[:, kk]; tgt = C[np.arange(len(V)), b]
        pts = start[:, None, :] + ss[None, :, None] * (tgt - start)[:, None, :]
        v = voxel.is_inside(pts, vox).sum(1); votes[np.arange(len(V)), b] = v; vis[np.arange(len(V)), b] = v >= vote
    none = ~vis.any(1); vis[none] = True
    return dict(D=D, vis=vis, votes=votes, vox=vox, cand=cand, none=none)

if __name__ == '__main__':
    V, Q, pos, par, kids, bones, top, Wt = T2.build()
    mi = mirror_index(V)
    sw = lambda n: (n[:-2] + ('_r' if n.endswith('_l') else '_l')) if n.endswith(('_l', '_r')) else n
    perm = np.array([bones.index(sw(b)) for b in bones])
    # rebuild bone segments exactly as build() does (re-derive from its returned bones via a second build call path)
    import inspect
    src = inspect.getsource(T2.build); 
    # segments: reuse build's code by executing up to 'bones = list(seg)'
    ns = {}; ns = {**T2.__dict__, 'fitted': fitted}; exec(src.split('    bones = list(seg)')[0].replace('def build():', 'if True:'), ns)
    seg = ns['seg']; A = np.array([seg[b][0] for b in bones]); B = np.array([seg[b][1] for b in bones])
    # 1. is the skeleton segment set itself symmetric?
    segerr = max(np.abs(A[perm] * [-1, 1, 1] - A).max(), np.abs(B[perm] * [-1, 1, 1] - B).max())
    print('bone segments mirror error mm: %.4f' % (segerr * 1000))
    M = np.array([-1.0, 1, 1]); As, Bs = A.copy(), B.copy()
    for i, j in enumerate(perm):
        if j != i: As[i] = (A[i] + A[j] * M) / 2; Bs[i] = (B[i] + B[j] * M) / 2
        elif np.allclose(A[i] * M, A[i], atol=1e-3): As[i] = A[i] * [0, 1, 1]; Bs[i] = B[i] * [0, 1, 1]
        else: As[i] = (A[i] + B[i] * M) / 2; Bs[i] = As[i] * M          # self-mirror reversed segment (pelvis)
    print('max joint correction from symmetrising: %.4f mm' % (max(np.abs(As - A).max(), np.abs(Bs - B).max()) * 1000))
    res = {}
    for name, sym, segs in (('original grid', False, (bones, A, B)), ('symmetric grid', True, (bones, A, B)), ('symmetric grid + symmetric joints', True, (bones, As, Bs)), ('+ centroid-fan split', 'fan', (bones, As, Bs))):
        r = weights(V, Q, pos, segs, sym_grid=bool(sym), fan=(sym == 'fan'))
        inside = r['vox'][0]; lo, h = r['vox'][1], r['vox'][2]
        xs = lo[0] + (np.arange(inside.shape[0]) + 0.5) * h
        voxsym = np.array_equal(inside, inside[::-1]) and np.allclose(xs, -xs[::-1])
        Dm = r['D'][mi][:, perm]; visd = (r['vis'] != r['vis'][mi][:, perm])
        vdiff = np.abs(r['votes'] - r['votes'][mi][:, perm])
        print(f"[{name}] voxel x-centres symmetric: {np.allclose(xs, -xs[::-1])}; solid mirror-identical: {np.array_equal(inside, inside[::-1])}; "
              f"distance asym max {np.abs(r['D'] - Dm).max()*1000:.4f} mm; visibility decisions differing from mirror: {int(visd.any(1).sum())} vertices; "
              f"vote differences >0: {int((vdiff>0).any(1).sum())} vertices; fallback-to-distance vertices: {int(r['none'].sum())} (mirror-mismatched {int((r['none'] != r['none'][mi]).sum())})")
        res[name] = r
    # 2. candidate-set ties: does argsort pick a different (mirrored) candidate set?
    r = res['+ centroid-fan split']; cd = (np.sort(perm[r['cand'][mi]], 1) != np.sort(r['cand'], 1)).any(1)
    print('vertices whose 6-candidate bone set is not the mirror of their partner\'s:', int(cd.sum()))

    mid = np.abs(V[:, 0]) < 1e-6
    print('  of which on the midline (self-mirror vertices):', int((cd & mid).sum()), '; off-midline:', int((cd & ~mid).sum()))
    visd = (r['vis'] != r['vis'][mi][:, perm]).any(1)
    print('remaining visibility mismatches: midline', int((visd & mid).sum()), 'off-midline', int((visd & ~mid).sum()))
    if (visd & ~mid).any():
        P = V[visd & ~mid]; print('   where:', np.round(P[:5], 3).tolist())
