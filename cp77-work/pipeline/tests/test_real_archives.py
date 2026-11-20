#!/usr/bin/env python3
"""Re-extract every resource in docs/provenance.json through cyberwolf.rdar, directly from the
game archives (read-only), and compare: index entry, segment offsets/sizes, SHA-256 of stored
bytes, and SHA-256 of each decompressed output against the original extraction."""
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf import rdar

def main(game_pc, kraken):
    work = os.path.normpath(os.path.join(HERE, '..', '..'))
    prov = json.load(open(os.path.join(work, 'docs', 'provenance.json')))
    kb = rdar.KrakenBackend(kraken)
    opened = {}
    res = {'records': len(prov), 'found': 0, 'segmentsMatch': 0, 'storedShaMatch': 0, 'outputsChecked': 0, 'outputShaMatch': 0, 'failures': []}
    for r in prov:
        rel = r['archive'].split('archive/pc/', 1)[1]
        if rel not in opened:
            opened[rel] = rdar.Archive(os.path.join(game_pc, rel), kb)
        ar = opened[rel]
        e = ar.find(r['path'])
        if e is None:
            res['failures'].append(('not found', r['path'])); continue
        res['found'] += 1
        s0, s1 = e[0], e[1]
        segs = r['segmentsExtracted']
        ok_seg = (s1 - s0) == r['segmentsTotal'] and all(tuple(ar.segments[s0 + i]) == (s['offset'], s['zsize'], s['size']) for i, s in enumerate(segs))
        res['segmentsMatch'] += ok_seg
        stored_ok = True
        for i, s in enumerate(segs):
            ar.fh.seek(s['offset'])
            stored_ok &= hashlib.sha256(ar.fh.read(s['zsize'])).hexdigest() == s['sha256_stored']
        res['storedShaMatch'] += stored_ok
        for i, out in enumerate(r['outputs']):
            res['outputsChecked'] += 1
            data = ar.read_segment(s0 + i)
            if hashlib.sha256(data).hexdigest() == out['sha256']:
                res['outputShaMatch'] += 1
            else:
                res['failures'].append(('output sha', out['file']))
        if not (ok_seg and stored_ok):
            res['failures'].append(('segments/stored', r['path']))
    for a in opened.values():
        a.close()
    return res

if __name__ == '__main__':
    r = main(sys.argv[1], sys.argv[2])
    print(json.dumps({k: v for k, v in r.items() if k != 'failures'}), 'failures:', r['failures'][:10])
    sys.exit(0 if not r['failures'] else 1)
