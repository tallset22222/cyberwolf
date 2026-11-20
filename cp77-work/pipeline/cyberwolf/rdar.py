"""Read-only RDAR archive reader (format: docs/01_archive_format.md).

Opens archives for reading only. Decompression of KARK segments is delegated to a
pluggable backend, so locating and listing resources works without one.
"""
import os
import struct
import ctypes

HEADER = struct.Struct('<4sIQIQIQ')       # magic, version, indexPos, indexSize, debugPos, debugSize, fileSize
INDEX = struct.Struct('<IIQIII')           # fileTableOffset, fileTableSize, crc, nFiles, nSegments, nDeps
ENTRY = struct.Struct('<QqIIIII20s')       # 56 bytes
SEGMENT = struct.Struct('<QII')            # offset, zSize, size


def fnv1a64(path):
    """Path hash used by the archive index (lower-case, backslash separators)."""
    h = 0xcbf29ce484222325
    for b in path.lower().replace('/', '\\').encode('utf-8'):
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


class KrakenBackend:
    """ctypes binding to an external Kraken decompressor (e.g. the libkraken.so shipped with WolvenKit)."""

    def __init__(self, lib_path):
        self.lib = ctypes.CDLL(lib_path)
        self.lib.Kraken_Decompress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
        self.lib.Kraken_Decompress.restype = ctypes.c_int

    def decompress(self, blob, size):
        out = ctypes.create_string_buffer(size + 64)
        n = self.lib.Kraken_Decompress(blob, len(blob), out, size)
        if n != size:
            raise RuntimeError(f'Kraken returned {n}, expected {size}')
        return out.raw[:size]


class NoBackend:
    def decompress(self, blob, size):
        raise RuntimeError('compressed segment: no Kraken backend configured (pass --kraken <libkraken.so>)')


class Archive:
    def __init__(self, path, backend=None):
        self.path = path
        self.backend = backend or NoBackend()
        self.fh = open(path, 'rb')
        hdr = self.fh.read(HEADER.size)
        (magic, self.version, self.index_pos, self.index_size,
         _, _, self.declared_size) = HEADER.unpack(hdr)
        if magic != b'RDAR':
            raise ValueError(f'{path}: bad magic {magic!r}')
        self.actual_size = os.path.getsize(path)
        if self.index_pos + self.index_size > self.actual_size:
            raise ValueError(f'{path}: truncated (declares {self.declared_size}, is {self.actual_size})')
        self.fh.seek(self.index_pos)
        idx = self.fh.read(self.index_size)
        _, _, _, nf, ns, nd = INDEX.unpack_from(idx, 0)
        o = 28
        self.entries = {}          # hash -> first entry (s0, s1, d0, d1)
        self.duplicates = {}       # hash -> further entries with the same hash
        self.entry_count = nf
        for _ in range(nf):
            h, ts, ninl, s0, s1, d0, d1, sha = ENTRY.unpack_from(idx, o)
            o += ENTRY.size
            if h in self.entries:
                self.duplicates.setdefault(h, []).append((s0, s1, d0, d1))
            else:
                self.entries[h] = (s0, s1, d0, d1)
        self.segments = [SEGMENT.unpack_from(idx, o + SEGMENT.size * i) for i in range(ns)]
        o += SEGMENT.size * ns
        self.dependencies = list(struct.unpack_from(f'<{nd}Q', idx, o))

    def close(self):
        self.fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def find(self, depot_path):
        return self.entries.get(fnv1a64(depot_path))

    def read_segment(self, k):
        off, zsize, size = self.segments[k]
        self.fh.seek(off)
        blob = self.fh.read(zsize)
        if blob[:4] == b'KARK':
            size = struct.unpack_from('<I', blob, 4)[0]
            return self.backend.decompress(blob[8:], size)
        if zsize != size:
            return self.backend.decompress(blob, size)
        return blob

    def read(self, depot_path):
        """Return (cr2w_bytes, [buffer_bytes, ...]) for a resource, or None if absent."""
        e = self.find(depot_path)
        if e is None:
            return None
        s0, s1 = e[0], e[1]
        parts = [self.read_segment(k) for k in range(s0, s1)]
        return parts[0], parts[1:]


def locate(archives, depot_path, backend=None):
    """Search a list of archive paths; return (archive_path, cr2w, buffers) for the first hit."""
    for a in archives:
        with Archive(a, backend) as ar:
            got = ar.read(depot_path)
            if got is not None:
                return a, got[0], got[1]
    return None
