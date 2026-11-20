"""Determinism proof for the export record (pipeline/cyberwolf/quantize.py export_record).
Each export runs in a FRESH process (different PYTHONHASHSEED, different wall-clock time) and rebuilds the v3 weights
from the MakeHuman master, so the whole chain is covered: weight build -> prune -> quantise -> .npz + .json.
Checks: (1) the .npz and .json files are byte-identical across processes; (2) the float weights inside equal the
in-memory build exactly; (3) per-vertex slot order doesn't matter: shuffling each vertex's influence slots gives the
same bone->byte assignment, the same dropped list and the same midline list."""
import os, sys, json, hashlib, subprocess, time, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'pipeline'))
OUT = os.path.join(HERE, 'reports', 'quantize_export', 'determinism')
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()

def child(K, tag, permute):
    os.environ['CW_INFLUENCES'] = str(K)
    import test2_deformation as T2; from cyberwolf.quantize import export_record
    V, Q, pos, par, kids, bones, top, Wt = T2.build('v3')
    W, J = np.asarray(Wt, np.float64), np.asarray(top)
    if permute:
        rng = np.random.default_rng(12345); P = np.argsort(rng.random(W.shape), 1)
        W, J = np.take_along_axis(W, P, 1), np.take_along_axis(J, P, 1)
    base = os.path.join(OUT, f'k{K}_{tag}'); export_record(base, W, J, bones)
    d = np.load(base + '.weights.npz'); assert np.array_equal(d['weights_float'], W) and np.array_equal(d['joints'], J)
    print(json.dumps({'weights_float_sha256': hashlib.sha256(W.tobytes()).hexdigest()}))

def canon(base, bones):
    d = np.load(base + '.weights.npz'); r = json.load(open(base + '.weights.json'))
    m = {}; B, J = d['bytes'], d['joints']
    for v in range(len(B)):
        m[v] = tuple(sorted((bones[j], int(b)) for j, b in zip(J[v], B[v]) if b > 0))
    return m, sorted((x['vertex'], x['bone']) for x in r['dropped_assignments']), sorted(r['midline_odd_unit_vertices'])

if __name__ == '__main__':
    if len(sys.argv) > 1: child(int(sys.argv[1]), sys.argv[2], int(sys.argv[3])); sys.exit()
    os.makedirs(OUT, exist_ok=True); import test2_deformation as T2; bones = T2.build('v3')[5]
    res = {}
    for K in (4, 8):
        runs = []
        for i, seed in enumerate(('0', '1', '987654')):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            o = subprocess.run([sys.executable, __file__, str(K), f'run{i}', '0'], env=env, capture_output=True, text=True, check=True)
            runs.append(json.loads(o.stdout.strip().splitlines()[-1])); time.sleep(2.5)    # different zip-time second
        subprocess.run([sys.executable, __file__, str(K), 'permuted', '1'], env=dict(os.environ, PYTHONHASHSEED='42'), check=True, capture_output=True)
        files = {f'run{i}': {e: sha(os.path.join(OUT, f'k{K}_run{i}.weights.{e}')) for e in ('npz', 'json')} for i in range(3)}
        c0, cp = canon(os.path.join(OUT, f'k{K}_run0'), bones), canon(os.path.join(OUT, f'k{K}_permuted'), bones)
        rec = json.load(open(os.path.join(OUT, f'k{K}_run0.weights.json')))
        res[K] = {'npz_identical_across_processes': len({f['npz'] for f in files.values()}) == 1,
                  'json_identical_across_processes': len({f['json'] for f in files.values()}) == 1,
                  'float_weights_identical_across_processes': len({r['weights_float_sha256'] for r in runs}) == 1,
                  'slot_order_invariant_assignment': c0[0] == cp[0], 'slot_order_invariant_dropped': c0[1] == cp[1],
                  'slot_order_invariant_midline': c0[2] == cp[2],
                  'npz_sha256': files['run0']['npz'][:16], 'json_sha256': files['run0']['json'][:16], 'bytes_sha256': rec['bytes_sha256'][:16],
                  'dropped_count': rec['dropped_count'], 'midline_odd_unit_vertices': len(rec['midline_odd_unit_vertices'])}
        print(K, res[K], flush=True)
    json.dump(res, open(os.path.join(OUT, 'determinism_proof.json'), 'w'), indent=1)
