#!/usr/bin/env python3
"""Self-test for cyberwolf.rdar without the game install.

Packs extracted sample resources (CR2W + buffers, stored uncompressed) into a synthetic
RDAR archive laid out per docs/01_archive_format.md, then reads every resource back
through rdar.Archive and checks byte equality. Also runs the full mesh pipeline on a
resource read from the synthetic archive. Writes only inside pipeline_cache/.
"""
import glob, hashlib, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf import rdar
from cyberwolf.mesh import Mesh

WORK = os.path.normpath(os.path.join(HERE, '..', '..'))
RAW = os.path.join(WORK, 'extract', 'raw')
CACHE = os.path.join(WORK, 'pipeline_cache')


def build(path, resources):
    body = bytearray(b'\0' * 40)
    entries, segs = [], []
    for depot, parts in resources:
        s0 = len(segs)
        for p in parts:
            segs.append((len(body), len(p), len(p)))
            body += p
        entries.append((rdar.fnv1a64(depot), 0, 0, s0, len(segs), 0, 0, hashlib.sha1(parts[0]).digest()))
    entries.sort()
    idx = bytearray(struct.pack('<IIQIII', 8, 0, 0, len(entries), len(segs), 0))
    for e in entries:
        idx += rdar.ENTRY.pack(*e)
    for s in segs:
        idx += rdar.SEGMENT.pack(*s)
    ipos = len(body)
    body += idx
    struct.pack_into('<4sIQIQIQ', body, 0, b'RDAR', 12, ipos, len(idx), 0, 0, len(body))
    open(path, 'wb').write(body)


def main():
    res = []
    for f in sorted(glob.glob(os.path.join(RAW, '**', '*'), recursive=True)):
        if os.path.isdir(f) or '.buffer' in os.path.basename(f):
            continue
        depot = os.path.relpath(f, RAW).replace('/', '\\')
        parts = [open(f, 'rb').read()]
        k = 0
        while os.path.exists(f'{f}.buffer{k}'):
            parts.append(open(f'{f}.buffer{k}', 'rb').read()); k += 1
        res.append((depot, parts))
    os.makedirs(CACHE, exist_ok=True)
    arc = os.path.join(CACHE, 'selftest.archive')
    build(arc, res)
    ok = 0
    with rdar.Archive(arc) as a:
        assert a.version == 12 and a.declared_size == a.actual_size
        for depot, parts in res:
            got = a.read(depot.upper())             # lookup is case-insensitive via the hash
            ok += got is not None and [got[0]] + got[1] == parts
        assert a.read('base\\does\\not\\exist.mesh') is None
    print(f'roundtrip: {ok}/{len(res)} resources byte-identical ({os.path.getsize(arc)} byte archive)')
    # decode a mesh straight from the synthetic archive
    depot = 'base\\environment\\architecture\\common\\shop\\shop_vending_machine_b_w300_h400_aa.mesh'
    _, cr2w, bufs = rdar.locate([arc], depot)
    dst = os.path.join(CACHE, 'from_archive', depot.replace('\\', '/'))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(cr2w)
    for i, b in enumerate(bufs):
        open(f'{dst}.buffer{i}', 'wb').write(b)
    m = Mesh(dst)
    print('decoded from archive:', [(l, sum(c.num_vertices for c in m.lod_chunks(l))) for l in m.lods])
    return ok == len(res)


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
