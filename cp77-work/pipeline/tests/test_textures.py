#!/usr/bin/env python3
"""Decode every texture referenced in the research (docs/textures_*.json) straight from the archives.
Checks: mip placement vs block arithmetic; Pillow decode vs independent numpy decoder (BC1/BC4/BC5);
mip 1 vs 2x2-averaged mip 0 (catches wrong offsets/pitches/formats, incl. BC7). Writes PNGs of mip 0."""
import json, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from cyberwolf.source import Source, WORK
from cyberwolf.texture import Texture, ref_bc1, ref_bc4

def main():
    paths = []
    for f in ('textures_characters.json', 'textures_templates.json'):
        paths += list(json.load(open(os.path.join(WORK, 'docs', f))))
    src = Source()
    out = os.path.join(WORK, 'pipeline_out', 'textures'); os.makedirs(out, exist_ok=True)
    rows, fails = [], []
    for p in paths:
        loc = src.get(p)
        if loc is None:
            fails.append(('missing', p)); continue
        t = Texture(loc)
        sc = t.structure_check()
        if not sc['supported']:
            rows.append({'path': p, **sc}); continue
        img = t.decode(0)
        row = {'path': p, 'format': sc['format'], 'size': [t.width, t.height], 'mips': t.mip_count,
               'mipsConsistent': sc['mipsConsistent'], 'fitsBuffer': sc['fitsBuffer']}
        data, w, h = t.mip_bytes(0)
        if sc['format'] == 'BC1':
            row['refDecoderMaxDiff'] = int(np.abs(ref_bc1(data, w, h) - img[..., :3].astype(float)).max().round())
        elif sc['format'] == 'BC4':
            row['refDecoderMaxDiff'] = int(np.abs(ref_bc4(data, w, h) - img[..., 0].astype(float)).max().round())
        elif sc['format'] == 'BC5':
            rx = ref_bc4(data, w, h, 16, 0); ry = ref_bc4(data, w, h, 16, 8)
            row['refDecoderMaxDiff'] = int(max(np.abs(rx - img[..., 0]).max(), np.abs(ry - img[..., 1]).max()).round())
        if t.mip_count > 1 and t.width >= 16:
            m1 = t.decode(1).astype(np.float64)
            d0 = img.astype(np.float64)[:t.height // 2 * 2, :t.width // 2 * 2]
            down = d0.reshape(t.height // 2, 2, t.width // 2, 2, 4).mean((1, 3))
            row['mip1VsDownsampledMip0_meanAbs'] = round(float(np.abs(m1[..., :3] - down[..., :3]).mean()), 2)
        name = p.split('\\')[-1].rsplit('.', 1)[0] + '.png'
        Image.fromarray(img).save(os.path.join(out, name))
        rows.append(row)
    json.dump(rows, open(os.path.join(out, 'texture_report.json'), 'w'), indent=1)
    from collections import Counter
    dec = [r for r in rows if 'format' in r]
    print('decoded', len(dec), 'of', len(paths), dict(Counter(r['format'] for r in dec)), 'unsupported', [(r['path'].split('\\')[-1], r.get('compression'), r.get('rawFormat')) for r in rows if 'format' not in r], 'missing', fails)
    print('mip placement consistent:', sum(r['mipsConsistent'] and r['fitsBuffer'] for r in dec), '/', len(dec))
    rd = [r['refDecoderMaxDiff'] for r in dec if 'refDecoderMaxDiff' in r]
    print('independent decoder vs Pillow (BC1/4/5):', len(rd), 'textures, max abs diff', max(rd) if rd else None)
    mm = [r['mip1VsDownsampledMip0_meanAbs'] for r in dec if 'mip1VsDownsampledMip0_meanAbs' in r]
    print('mip1 vs downsampled mip0 mean abs diff (0-255): median', float(np.median(mm)), 'max', max(mm))
    for r in sorted(dec, key=lambda r: -r.get('mip1VsDownsampledMip0_meanAbs', 0))[:4]:
        print('  ', r['format'], r['size'], r.get('mip1VsDownsampledMip0_meanAbs'), r['path'].split('\\')[-1])

if __name__ == '__main__':
    main()
