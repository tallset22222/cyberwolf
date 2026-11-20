"""Gate: skin weights must mirror left/right (standard v0.2 part 1). Exit code 1 if any vertex differs by more than TOL."""
import sys, os, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test2_deformation as T2
TOL = 0.02
def asym(which):
    V, Q, pos, par, kids, bones, top, Wt = T2.build(which)
    key = {tuple(np.round(v * [-1, 1, 1], 6)): i for i, v in enumerate(V)}; mi = np.array([key[tuple(np.round(v, 6))] for v in V])
    perm = np.array([bones.index(T2._side_swap(b)) for b in bones])
    W = np.zeros((len(V), len(bones))); np.add.at(W, (np.repeat(np.arange(len(V)), top.shape[1]), top.ravel()), Wt.ravel())
    e = np.abs(W - W[mi][:, perm]).sum(1) / 2
    jerr = max(np.linalg.norm(pos[n] * T2.MIRROR - pos[T2._side_swap(n)]) for n in pos)
    return e, jerr, (W > 1e-9).sum(1).max()
if __name__ == '__main__':
    out = {}
    for w in sys.argv[1:] or ['v2']:
        e, jerr, maxinf = asym(w)
        out[w] = {'max_vertex_asymmetry': float(e.max()), 'vertices_over_tol': int((e > TOL).sum()), 'vertices_over_1e-6': int((e > 1e-6).sum()),
                  'joint_mirror_error_mm': round(jerr * 1000, 6), 'max_influences': int(maxinf), 'pass': bool(e.max() <= TOL)}
        print(w, out[w])
    json.dump({'tolerance': TOL, 'results': out}, open(os.path.join(HERE, os.environ.get('CW_OUT', 'reports'), 'weight_symmetry.json'), 'w'), indent=1)
    sys.exit(0 if all(r['pass'] for r in out.values()) else 1)
