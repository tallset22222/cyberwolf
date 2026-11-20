import struct, sys, os, json, collections
root = sys.argv[1]; outdir = sys.argv[2]
summary = []
for dp, dn, fn in os.walk(root):
    for f in sorted(fn):
        if not f.endswith('.archive'): continue
        p = os.path.join(dp, f)
        with open(p, 'rb') as fh:
            hdr = fh.read(40)
            magic, ver, ipos, isz, dpos, dsz, fsz = struct.unpack_from('<4sIQIQIQ', hdr, 0)
            if magic != b'RDAR':
                summary.append({'archive': os.path.relpath(p, root), 'error': 'bad magic'}); continue
            actual = os.path.getsize(p)
            if ipos + isz > actual:
                summary.append({'archive': os.path.relpath(p, root), 'error': f'truncated: header says {fsz} bytes, index at {ipos}, file is {actual}'}); continue
            fh.seek(ipos); idx = fh.read(isz)
            fto, fts, crc, nf, ns, nd = struct.unpack_from('<IIQIII', idx, 0)
            o = 28; files = []
            for i in range(nf):
                h, ts, ninl, s0, s1, r0, r1 = struct.unpack_from('<QqIIIII', idx, o); o += 56
                files.append((h, s0, s1, r1 - r0))
            segs = []
            for i in range(ns):
                segs.append(struct.unpack_from('<QII', idx, o)); o += 16
            zt = sum(s[1] for s in segs); rt = sum(s[2] for s in segs)
            multi = sum(1 for f_ in files if f_[2] - f_[1] > 1)
            rows = [{'hash': f'{h:016x}', 'segments': s1 - s0, 'deps': nd_,
                     'zsize': sum(segs[k][1] for k in range(s0, s1)),
                     'size': sum(segs[k][2] for k in range(s0, s1))} for h, s0, s1, nd_ in files]
            name = os.path.relpath(p, root).replace('/', '__')
            json.dump(rows, open(os.path.join(outdir, name + '.index.json'), 'w'))
            summary.append({'archive': os.path.relpath(p, root), 'version': ver, 'bytes': fsz,
                            'files': nf, 'segments': ns, 'deps': nd,
                            'files_with_buffers': multi,
                            'compressed_total': zt, 'raw_total': rt})
json.dump(summary, open(os.path.join(outdir, 'summary.json'), 'w'), indent=1)
for s in summary:
    if 'error' in s: print(s); continue
    print(f"{s['archive']:<62} files={s['files']:>7} withbuf={s['files_with_buffers']:>6} z={s['compressed_total']/2**30:6.2f}G raw={s['raw_total']/2**30:6.2f}G")
