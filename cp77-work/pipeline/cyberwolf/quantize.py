"""Deterministic skin-weight quantisation for export (OI-19).

WolvenKit's importer turns each glTF weight into a byte separately (Convert.ToByte(w * 255), no renormalisation), so
float weights can arrive summing to 254 or 256. Cyberwolf therefore quantises BEFORE export and writes floats that are
exactly k/255, which WolvenKit's rounding reproduces byte for byte.

Guarantees, for every vertex:
  1. every weight is a valid byte 0..255, and the bytes sum to exactly 255;
  2. bone assignments are unchanged: a nonzero weight never becomes 0 (minimum 1), a zero weight stays 0;
  3. it is deterministic, and ties are broken WITHOUT reference to side: the tie key is the bone name with its
     _l/_r suffix removed, so a vertex and its mirror partner always quantise to mirror-identical bytes;
  4. the only unavoidable asymmetry is a midline vertex whose weights are an exact mirror pair with no other bone to
     absorb the odd unit (255 is odd). Then a centre bone, if present, takes it; otherwise the left bone does, and the
     vertex is reported.
Method: largest remainder. Floor every share of 255; distribute the remaining units by descending remainder, then
centre bones first, then side-stripped name; keep the minimum of 1 for every nonzero weight."""
import numpy as np

def _strip(n):
    return n[:-2] if n.endswith(('_l', '_r')) else n

def quantize(weights, joints, bone_names):
    """weights [N,K] float (any scale), joints [N,K] int (indices into bone_names). Returns (bytes [N,K] uint8, report)."""
    W = np.asarray(weights, np.float64); J = np.asarray(joints); N, K = W.shape
    out = np.zeros((N, K), np.int64); last_resort = []
    for v in range(N):
        w = W[v]; nz = w > 0
        if not nz.any(): continue
        x = np.where(nz, w / w[nz].sum() * 255.0, 0.0)
        f = np.where(nz, np.maximum(np.floor(x), 1), 0).astype(np.int64)
        rem = 255 - int(f.sum())
        names = [bone_names[j] for j in J[v]]
        frac = x - np.floor(x)
        def key(k, sign):
            n = names[k]; centre = 0 if not n.endswith(('_l', '_r')) else 1
            # sign=+1: give units (largest remainder first); sign=-1: take units back (smallest remainder first)
            return (-sign * frac[k], centre, _strip(n), 0 if n.endswith('_l') else 1)
        if rem > 0:
            order = sorted([k for k in range(K) if nz[k]], key=lambda k: key(k, +1))
            for i in range(rem): f[order[i % len(order)]] += 1
        elif rem < 0:   # minimum-1 rule overshot: take units back from the largest bytes, smallest remainder first
            for _ in range(-rem):
                cand = [k for k in range(K) if f[k] > 1]
                k = sorted(cand, key=lambda k: (-f[k],) + key(k, -1))[0]; f[k] -= 1
        # flag the unavoidable midline case: an exact mirror tie decided only by the side term
        sel = [k for k in range(K) if nz[k]]
        for a in sel:
            for b in sel:
                if a < b and _strip(names[a]) == _strip(names[b]) and names[a] != names[b] and abs(x[a] - x[b]) < 1e-9 and f[a] != f[b]:
                    last_resort.append(v)
        out[v] = f
    assert (out.sum(1)[W.max(1) > 0] == 255).all() and (out >= 0).all() and (out <= 255).all()
    assert ((out > 0) == (W > 0)).all(), 'a bone assignment changed'
    return out.astype(np.uint8), {'vertices': N, 'midline_last_resort_vertices': sorted(set(last_resort))}

def export_floats(bytes_):
    """Floats that WolvenKit's per-weight Convert.ToByte(w*255) maps back to exactly these bytes."""
    return (np.asarray(bytes_, np.float64) / 255.0).astype(np.float32)

SUB_BYTE = 0.5 / 255.0

def prepare_for_export(weights, joints, bone_names, prune_sub_byte=True):
    """Export path. Optionally remove weights below half a byte first (they can't be represented: WolvenKit's rounding
    would silently turn them into 0) and renormalise, then quantise with the guarantees above. Returns
    (bytes, export_floats, report). With prune_sub_byte=False every nonzero weight is kept at >= 1/255, at the cost of
    larger errors elsewhere on that vertex (measured on v3: up to 2.9/255 at 4 influences, 5.9/255 at 8; 1.5/255 with
    pruning)."""
    W = np.asarray(weights, np.float64).copy(); pruned = 0
    if prune_sub_byte:
        tiny = (W > 0) & (W < SUB_BYTE); pruned = int(tiny.sum()); W[tiny] = 0
        W /= np.maximum(W.sum(1, keepdims=True), 1e-30)
    B, rep = quantize(W, joints, bone_names)
    rep.update(pruned_sub_byte_weights=pruned, max_abs_error=float(np.abs(B / 255.0 - np.asarray(weights)).max()))
    return B, export_floats(B), rep

def _savez_deterministic(path, **arrays):
    """np.savez_compressed stamps the current time into each zip entry, so identical data written at different times
    gives different files. Write the same .npz layout (readable by np.load) with a fixed timestamp and fixed entry
    order, so the file itself is byte-identical across exports."""
    import zipfile, io
    with zipfile.ZipFile(path, 'w') as z:
        for name in sorted(arrays):
            buf = io.BytesIO(); np.lib.format.write_array(buf, np.ascontiguousarray(arrays[name]), allow_pickle=False)
            zi = zipfile.ZipInfo(name + '.npy', date_time=(1980, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16; z.writestr(zi, buf.getvalue(), compresslevel=6)

def export_record(path_base, weights, joints, bone_names, prune_sub_byte=True, mesh_sha256=None):
    """Export with a full record: the quantised output is NEVER the only stored representation.
    Writes <path_base>.weights.npz  - original float weights + joints (as given), the bytes, and the export floats
           <path_base>.weights.json - every dropped assignment (vertex, bone, original weight), the midline odd-unit
                                     allocations, settings, and SHA-256 of the byte array (determinism check).
    Midline rule (documented): when a vertex's weights are an exact left/right mirror pair with no centre bone, 255 is
    odd, so one side must take the extra unit: a centre bone takes it if present, otherwise the LEFT bone. Every such
    vertex is listed. The method has no randomness and no dependence on bone index order, so repeated exports of the
    same input are byte-identical."""
    import json, hashlib
    W = np.asarray(weights, np.float64); J = np.asarray(joints)
    B, F, rep = prepare_for_export(W, J, bone_names, prune_sub_byte)
    dropped = [{'vertex': int(v), 'bone': bone_names[int(J[v, k])], 'weight': float(W[v, k])}
               for v, k in zip(*np.where((W > 0) & (B == 0)))]
    _savez_deterministic(path_base + '.weights.npz', weights_float=W, joints=J, bytes=B, export_floats=F)
    rec = {'settings': {'prune_sub_byte': prune_sub_byte, 'sub_byte_threshold': SUB_BYTE, 'sum': 255,
                        'tie_rule': 'largest remainder; ties: centre bones first, then side-stripped bone name, then left before right'},
           'mesh_sha256': mesh_sha256, 'vertices': int(len(W)), 'bytes_sha256': hashlib.sha256(np.ascontiguousarray(B).tobytes()).hexdigest(),
           'dropped_assignments': dropped, 'dropped_count': len(dropped),
           'midline_odd_unit_vertices': rep['midline_last_resort_vertices'], 'max_abs_error': rep['max_abs_error']}
    json.dump(rec, open(path_base + '.weights.json', 'w'), indent=1, sort_keys=True)
    return B, F, rec
