"""Decode CR2W bitmap textures (.xbm: CBitmapTexture + rendRenderTextureBlobPC) to RGBA arrays.

Block-compressed data is handed to Pillow's BCn decoder by wrapping one mip level in a DDS (DX10)
header; BC1/BC4/BC5 are also decoded by an independent numpy decoder here for cross-checking.
"""
import io
import os
import struct
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402

# compression setting -> (DXGI format, bytes per 4x4 block, Pillow output kind)
FORMATS = {'TCM_QualityColor': (98, 16, 'BC7'), 'TCM_DXTNoAlpha': (71, 8, 'BC1'), 'TCM_DXTAlpha': (77, 16, 'BC3'),
           'TCM_QualityR': (80, 8, 'BC4'), 'TCM_Normalmap': (83, 16, 'BC5'), 'TCM_Normals': (83, 16, 'BC5'),
           'TCM_NormalsHigh': (83, 16, 'BC5'), 'TCM_QualityRG': (83, 16, 'BC5')}


def _dds(dxgi, w, h, data):
    # DDS_HEADER: size, flags, height, width, pitchOrLinearSize, depth, mipMapCount, reserved1[11],
    # DDS_PIXELFORMAT (32 bytes), caps, caps2, caps3, caps4, reserved2
    head = struct.pack('<IIIIIII', 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, len(data), 0, 1) + b'\0' * 44
    pf = struct.pack('<II4sIIIII', 32, 0x4, b'DX10', 0, 0, 0, 0, 0)
    caps = struct.pack('<IIIII', 0x1000, 0, 0, 0, 0)
    dx10 = struct.pack('<IIIII', dxgi, 3, 0, 1, 0)
    blob = b'DDS ' + head + pf + caps + dx10 + data
    assert len(blob) == 4 + 124 + 20 + len(data)
    return blob


class Texture:
    def __init__(self, path):
        self.path = path
        r = R(path)
        t = r.chunk(0)
        bi = [i for i, c in enumerate(r.meta['chunks']) if c['class'] == 'rendRenderTextureBlobPC'][0]
        blob = r.chunk(bi)
        h = blob['header']
        setup = t.get('setup', {})
        self.compression = setup.get('compression', 'TCM_None')
        self.raw_format = setup.get('rawFormat')
        self.gamma = bool(setup.get('isGamma'))
        self.logical = (t.get('width'), t.get('height'))
        self.width, self.height = h['sizeInfo']['width'], h['sizeInfo']['height']
        ti = h['textureInfo']
        self.mip_count, self.slices, self.data_size = ti.get('mipCount', 1), ti.get('sliceCount', 1), ti['textureDataSize']
        self.mips = []
        bpb = FORMATS.get(self.compression, (0, 16, ''))[1]
        off = 0
        for k, m in enumerate(h.get('mipMapInfo') or [{}] * self.mip_count):
            w, hh = max(1, self.width >> k), max(1, self.height >> k)
            tight = max(1, (w + 3) // 4) * max(1, (hh + 3) // 4) * bpb       # fallback when fields are absent
            pl = m.get('placement', {}) if isinstance(m, dict) else {}
            o = pl.get('offset', off if k else 0)
            size = pl.get('size', tight)
            self.mips.append((o, size, (m.get('layout') or {}).get('rowPitch', 0) if isinstance(m, dict) else 0))
            off = o + size
        self.data = open(f"{path}.buffer{blob['textureData']['buffer'] - 1}", 'rb').read()

    def structure_check(self):
        """Mip placements must agree with the format's block arithmetic and fit the buffer."""
        if self.compression not in FORMATS:
            return {'supported': False, 'compression': self.compression, 'rawFormat': self.raw_format}
        _, bpb, kind = FORMATS[self.compression]
        ok, expect_off, pitch_checked = True, 0, 0
        for k, (off, size, pitch) in enumerate(self.mips):
            w, h = max(1, self.width >> k), max(1, self.height >> k)
            bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
            ok &= size >= bh * bw * bpb and off >= expect_off
            if 0 < pitch <= size:            # stored pitch is only trusted when plausible (see note in mip_bytes)
                pitch_checked += 1
                ok &= pitch >= bw * bpb
            expect_off = off + size
        return {'supported': True, 'format': kind, 'mipsConsistent': bool(ok), 'storedPitchesChecked': pitch_checked,
                'bufferBytes': len(self.data), 'declaredBytes': self.data_size,
                'fitsBuffer': expect_off <= len(self.data) == self.data_size}

    def mip_bytes(self, k):
        off, size, pitch = self.mips[k]
        w, h = max(1, self.width >> k), max(1, self.height >> k)
        _, bpb, _ = FORMATS[self.compression]
        bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
        # Some textures decode with an implausible stored rowPitch (a property-decoding issue in the generic
        # CR2W reader for this struct), so the pitch is derived from the format; padded rows are honoured
        # only when the stored pitch is plausible and the mip's size accounts for it.
        tight = bw * bpb
        if not (tight < pitch <= size and size >= bh * pitch):
            pitch = tight
        rows = [self.data[off + r * pitch: off + r * pitch + tight] for r in range(bh)]
        return b''.join(rows), w, h

    def decode(self, k=0):
        """RGBA uint8 array of mip k (BC5 normal maps: RG = XY, B = reconstructed Z, A = 255)."""
        dxgi, _, kind = FORMATS[self.compression]
        data, w, h = self.mip_bytes(k)
        img = Image.open(io.BytesIO(_dds(dxgi, max(4, w), max(4, h), data)))
        img.load()
        a = np.asarray(img.convert('RGBA') if img.mode != 'RGBA' else img).copy()[:h, :w]
        if kind == 'BC4':
            a[..., 1] = a[..., 2] = a[..., 0]
        if kind == 'BC5':
            x = a[..., 0].astype(np.float64) / 255 * 2 - 1
            y = a[..., 1].astype(np.float64) / 255 * 2 - 1
            z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
            a[..., 2] = np.round((z + 1) / 2 * 255).astype(np.uint8)
            a[..., 3] = 255
        return a


# ---- independent reference decoders (numpy) for BC1 / BC4 / BC5, used only for validation ----

def _bc4_block_values(e0, e1):
    e0 = e0.astype(np.float64)
    e1 = e1.astype(np.float64)
    pal = np.zeros(e0.shape + (8,))
    pal[..., 0], pal[..., 1] = e0, e1
    big = e0 > e1
    for i in range(1, 7):
        pal[..., i + 1] = np.where(big, ((7 - i) * e0 + i * e1) / 7, 0)
    for i in range(1, 5):
        pal[..., i + 1] = np.where(big, pal[..., i + 1], ((5 - i) * e0 + i * e1) / 5)
    pal[..., 6] = np.where(big, pal[..., 6], 0)
    pal[..., 7] = np.where(big, pal[..., 7], 255)
    return pal


def ref_bc4(data, w, h, stride=8, offset=0):
    bw, bh = (w + 3) // 4, (h + 3) // 4
    b = np.frombuffer(data, dtype=np.uint8).reshape(bh * bw, stride)[:, offset:offset + 8]
    pal = _bc4_block_values(b[:, 0], b[:, 1])
    bits = np.zeros(len(b), dtype=np.uint64)
    for i in range(6):
        bits |= b[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
    idx = np.stack([(bits >> np.uint64(3 * j)) & np.uint64(7) for j in range(16)], 1).astype(np.int64)
    vals = np.take_along_axis(pal, idx, 1)
    out = vals.reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(bh * 4, bw * 4)[:h, :w]
    return out


def ref_bc1(data, w, h):
    bw, bh = (w + 3) // 4, (h + 3) // 4
    b = np.frombuffer(data, dtype=np.uint8).reshape(bh * bw, 8)
    c0 = b[:, 0].astype(np.int64) | (b[:, 1].astype(np.int64) << 8)
    c1 = b[:, 2].astype(np.int64) | (b[:, 3].astype(np.int64) << 8)

    def rgb(c):
        return np.stack([((c >> 11) & 31) * 255 / 31, ((c >> 5) & 63) * 255 / 63, (c & 31) * 255 / 31], 1)
    p0, p1 = rgb(c0), rgb(c1)
    four = (c0 > c1)[:, None]
    p2 = np.where(four, (2 * p0 + p1) / 3, (p0 + p1) / 2)
    p3 = np.where(four, (p0 + 2 * p1) / 3, 0)
    pal = np.stack([p0, p1, p2, p3], 1)
    bits = b[:, 4].astype(np.int64) | (b[:, 5].astype(np.int64) << 8) | (b[:, 6].astype(np.int64) << 16) | (b[:, 7].astype(np.int64) << 24)
    idx = np.stack([(bits >> (2 * j)) & 3 for j in range(16)], 1)
    vals = pal[np.arange(len(b))[:, None], idx]
    return vals.reshape(bh, bw, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 3)[:h, :w]
