"""Multilayered materials: decode .mlmask tile atlases, read .mlsetup layer stacks and .mltemplate presets,
and bake an approximate PBR result in the mesh's UV0 space.

Mask format (docs/04, docs/05 section 2; layout cross-checked against WolvenKit's MlmaskTools.cs, which is
credited as the reference): a BC4 atlas of 14x14 tiles stored with a 1-pixel border (16x16 cells); a full-res
tile grid then a low-res grid of (declOffset, layerBits) pairs; one 32-bit declaration per present layer:
bits 0-9 atlas tile x, 10-19 tile y, 20-23 / 24-27 x / y scale shift. Implementation here is independent.

Layer blending is an approximation (the shader is not in the data): layers are composited in order with
mask * opacity as coverage; colour = linear(template colour) * colorScale (treated as linear), output sRGB; roughness/metalness = template value
remapped by levelsOut = [hi, lo]; normals are lerped and renormalised. Microblends are not applied.
"""
import io
import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402
from .texture import Texture, _dds  # noqa: E402


def _bc4_image(data, w, h):
    img = Image.open(io.BytesIO(_dds(80, w, h, data)))
    img.load()
    return np.asarray(img.convert('L'))


class MultilayerMask:
    def __init__(self, path):
        r = R(path)
        blob = [r.chunk(i) for i, c in enumerate(r.meta['chunks']) if c['class'].startswith('rendRenderMultilayerMaskBlob')][0]
        h = blob['header']
        self.layers = h['numLayers']
        self.w, self.h, self.ts = h['maskWidth'], h['maskHeight'], h['maskTileSize']
        self.wl, self.hl = h.get('maskWidthLow', 0), h.get('maskHeightLow', 0)
        self.aw, self.ah = h['atlasWidth'], h['atlasHeight']
        atlas = open(f"{path}.buffer{blob['atlasData']['buffer'] - 1}", 'rb').read()
        tiles = open(f"{path}.buffer{blob['tilesData']['buffer'] - 1}", 'rb').read()
        self.atlas = _bc4_image(atlas, self.aw, self.ah)
        self.tiles = np.frombuffer(tiles, dtype='<u4').astype(np.int64)

    def _lookup(self, X, Y, layer, offset, scale, width_tiles):
        ts, T = self.ts, self.tiles
        ti = width_tiles * (Y // ts // scale) + (X // ts // scale) + offset
        valid = 2 * ti + 1 < len(T)
        ti = np.where(valid, ti, 0)
        off, bits = T[2 * ti], T[2 * ti + 1]
        has = valid & ((bits >> layer) & 1).astype(bool)
        below = bits & ((1 << layer) - 1)
        extra = np.zeros_like(below)
        b = below.copy()
        while b.any():
            extra += b & 1
            b >>= 1
        k = off + extra
        has &= k < len(T)
        d = T[np.where(has, k, 0)]
        dx, dy = d & 0x3FF, (d >> 10) & 0x3FF
        sx, sy = (d >> 20) & 0xF, (d >> 24) & 0xF
        lx = np.minimum((X >> sx) % ts, ts - 1)
        ly = np.minimum((Y >> sy) % ts, ts - 1)
        ux = lx + 1 + dx * (ts + 2)
        uy = ly + 1 + dy * (ts + 2)
        ok = has & (ux < self.aw) & (uy < self.ah)
        vals = self.atlas[np.where(ok, uy, 0), np.where(ok, ux, 0)]
        return ok, vals

    def decode(self, layer):
        """Full-resolution mask (uint8, maskHeight x maskWidth) for one layer."""
        Y, X = np.mgrid[0:self.h, 0:self.w]
        wt = -(-self.w // self.ts)
        ht = -(-self.h // self.ts)
        out = np.zeros((self.h, self.w), dtype=np.uint8)
        ok, v = self._lookup(X, Y, layer, 0, 1, wt)
        out[ok] = v[ok]
        if self.wl and self.hl and self.wl < self.w:
            scale = self.w // self.wl
            ok2, v2 = self._lookup(X, Y, layer, wt * ht, scale, -(-(self.w // scale) // self.ts))
            fill = ~ok & ok2
            out[fill] = v2[fill]
        return out, float(ok.mean())


def _presets(tmpl_chunk, key):
    return {e['n']: e.get('v') for e in tmpl_chunk.get('overrides', {}).get(key, [])}


class LayerTemplate:
    def __init__(self, path):
        c = R(path).chunk(0)
        self.textures = {k: c[k]['ref'] for k in ('colorTexture', 'normalTexture', 'roughnessTexture', 'metalnessTexture') if k in c}
        self.tiling = c.get('tilingMultiplier', 1.0)
        self.presets = {k: _presets(c, k) for k in ('colorScale', 'roughLevelsOut', 'metalLevelsOut', 'normalStrength')}


def read_setup(path):
    c = R(path).chunk(0)
    out = []
    for l in c.get('layers', []):
        out.append({'template': l.get('material', {}).get('ref'), 'colorScale': l.get('colorScale'),
                    'matTile': l.get('matTile', 1.0), 'opacity': l.get('opacity', 1.0),
                    'roughLevelsOut': l.get('roughLevelsOut'), 'metalLevelsOut': l.get('metalLevelsOut'),
                    'normalStrength': l.get('normalStrength'), 'microblend': l.get('microblend', {}).get('ref')})
    return out


def _sample(img, U, V, tiling):
    h, w = img.shape[:2]
    px = ((U * tiling) % 1.0 * w).astype(np.int64) % w
    py = ((V * tiling) % 1.0 * h).astype(np.int64) % h
    return img[py, px]


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


_bake_cache = {}
BAKE_VERSION = 1      # bump when the blending model changes (invalidates the disk cache)


def bake(setup_path, mask_path, src, size=1024):
    key = (setup_path, mask_path, size)
    if key not in _bake_cache:
        import hashlib, pickle
        h = hashlib.sha256(repr((os.path.relpath(setup_path, src.cache), mask_path and os.path.relpath(mask_path, src.cache),
                                 size, BAKE_VERSION)).encode()).hexdigest()[:20]
        f = os.path.join(src.cache, '_bakes', h + '.pkl')
        if os.path.exists(f):
            _bake_cache[key] = pickle.load(open(f, 'rb'))
        else:
            _bake_cache[key] = _bake(setup_path, mask_path, src, size)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            pickle.dump(_bake_cache[key], open(f, 'wb'))
    return _bake_cache[key]


def _bake(setup_path, mask_path, src, size):
    """Return (baseColor RGBA, normal RGBA, metallicRoughness RGBA, report) baked in UV0 space."""
    layers = read_setup(setup_path)
    mask = MultilayerMask(mask_path) if mask_path else None
    V, U = (np.mgrid[0:size, 0:size] + 0.5) / size
    col = np.full((size, size, 3), 0.214)          # linear mid grey
    nrm = np.zeros((size, size, 3)); nrm[..., 2] = 1
    rough = np.full((size, size), 0.5)
    metal = np.zeros((size, size))
    tex_cache = {}

    def tex(depot):
        if depot not in tex_cache:
            loc = src.get(depot) if depot else None
            try:
                tex_cache[depot] = Texture(loc).decode(0).astype(np.float64) / 255 if loc else None
            except Exception:
                tex_cache[depot] = None
        return tex_cache[depot]
    rep = {'setup': setup_path, 'mask': mask_path, 'layers': [], 'maskLayers': mask.layers if mask else None}
    for i, L in enumerate(layers):
        tp = src.get(L['template']) if L['template'] else None
        if tp is None:
            rep['layers'].append({'layer': i, 'skipped': 'template missing'}); continue
        T = LayerTemplate(tp)
        if mask and i < mask.layers:
            m, fullres = mask.decode(i)
            m = m.astype(np.float64) / 255
            if i == 0 and not m.any():
                m = np.ones_like(m)          # base layer: coverage implied
            mi = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR)) / 255
        else:
            mi, fullres = (np.ones((size, size)) if i == 0 else np.zeros((size, size))), None
        a = (mi * float(L['opacity']))[..., None]
        tiling = float(L['matTile']) * float(T.tiling)
        cs = T.presets['colorScale'].get(L['colorScale'], [1, 1, 1])
        ct, nt, rt, mt = (tex(T.textures.get(k)) for k in ('colorTexture', 'normalTexture', 'roughnessTexture', 'metalnessTexture'))
        lc = (srgb_to_linear(_sample(ct, U, V, tiling)[..., :3]) if ct is not None else 0.214) * np.asarray(cs[:3])   # colorScale treated as linear
        col = col * (1 - a) + lc * a
        if nt is not None:
            n = _sample(nt, U, V, tiling)[..., :3] * 2 - 1
            nrm = nrm * (1 - a) + n * a
        hi, lo = (T.presets['roughLevelsOut'].get(L['roughLevelsOut']) or [1, 0])[:2]
        r = _sample(rt, U, V, tiling)[..., 0] if rt is not None else 0.5
        rough = rough * (1 - a[..., 0]) + (lo + r * (hi - lo)) * a[..., 0]
        hi, lo = (T.presets['metalLevelsOut'].get(L['metalLevelsOut']) or [1, 0])[:2]
        mm = _sample(mt, U, V, tiling)[..., 0] if mt is not None else 0.0
        metal = metal * (1 - a[..., 0]) + (lo + mm * (hi - lo)) * a[..., 0]
        rep['layers'].append({'layer': i, 'template': L['template'].split('\\')[-1], 'tiling': round(tiling, 2),
                              'opacity': L['opacity'], 'colorScale': [round(x, 3) for x in cs[:3]],
                              'maskCoverage': round(float(mi.mean()), 3), 'fullResTileFraction': fullres})
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-9)
    to8 = lambda x: np.clip(np.round(x * 255), 0, 255).astype(np.uint8)
    one = np.full((size, size), 255, np.uint8)
    base = np.dstack([to8(linear_to_srgb(col)), one])
    normal = np.dstack([to8((nrm + 1) / 2), one])
    mr = np.dstack([np.zeros_like(one), to8(np.clip(rough, 0, 1)), to8(np.clip(metal, 0, 1)), one])
    return base, normal, mr, rep
