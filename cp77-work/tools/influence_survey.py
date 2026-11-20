"""OI-19 evidence: how many skin influences shipped Cyberpunk 2077 meshes declare and actually use.
Read-only over meshes already extracted into the workspace (never touches game files)."""
import sys, os, json, glob, collections, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pipeline'))
from cyberwolf.mesh import Mesh
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
rows = []
for p in sorted(set(glob.glob(os.path.join(root, 'pipeline_cache', '**', '*.mesh'), recursive=True) + glob.glob(os.path.join(root, 'extract', '**', '*.mesh'), recursive=True))):
    try: M = Mesh(p)
    except Exception as e: rows.append({'mesh': os.path.relpath(p, root), 'error': str(e)[:80]}); continue
    for c in M.chunks:
        if c.joints is None: continue
        w = c.weights_raw; nz = (w > 0).sum(1)
        rows.append({'mesh': os.path.relpath(p, root).replace('pipeline_cache/', '').replace('extract/raw/', ''), 'chunk': c.index, 'lod_mask': c.lod_mask,
                     'declared': int(c.joints.shape[1]), 'vertices': int(c.num_vertices), 'max_used': int(nz.max()),
                     'pct_over_4': round(float((nz > 4).mean() * 100), 1), 'hist': dict(sorted(collections.Counter(nz.tolist()).items()))})
json.dump(rows, open(os.path.join(root, 'basebody', 'reports', 'oi19_influence_survey.json'), 'w'), indent=1)
by = collections.defaultdict(list)
for r in rows:
    if 'error' in r: continue
    by[r['mesh']].append(r)
for m, rs in by.items():
    d = sorted({r['declared'] for r in rs}); mu = max(r['max_used'] for r in rs); nv = sum(r['vertices'] for r in rs)
    o4 = sum(r['pct_over_4'] * r['vertices'] for r in rs) / max(nv, 1)
    print(f'{m[-70:]:70s} declared {d} max used {mu}  verts {nv:6d}  >4 used {o4:5.1f}%')
print('errors:', sum('error' in r for r in rows))
