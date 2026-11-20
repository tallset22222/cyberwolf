"""Reader for the engine's compact 'package' buffers (e.g. appearanceAppearanceDefinition.compiledData,
entity compiledData). Layout cross-checked against WolvenKit's RedPackageReader (credited reference);
this implementation is independent and decodes simple field types only (others are returned raw).

header: u8 version, u8 unk, u16 numSections, u32 numComponents, [u32 refDesc, u32 refData if 7 sections],
        u32 nameDesc, u32 nameData, u32 chunkDesc, u32 chunkData, i16 cruidIndex, u16 numCruids, u64[numCruids]
then, relative to the end of that header: import descs (u32: offset 23 bits | size 8 bits | sync 1 bit),
name descs (u32: offset 24 bits | size 8 bits), chunk descs (u32 typeNameId, u32 offset);
each chunk: u16 fieldCount, fieldCount x (u16 nameId, u16 typeId, u32 offset relative to chunk start).
"""
import os
import pickle
import struct
from .rdar import fnv1a64

PRIM = {'Uint8': '<B', 'Int8': '<b', 'Uint16': '<H', 'Int16': '<h', 'Uint32': '<I', 'Int32': '<i', 'Uint64': '<Q',
        'Int64': '<q', 'Float': '<f', 'Double': '<d', 'Bool': '<B'}

_hash_paths = None


def hash_to_path(h, work):
    """Resolve a depot-path hash using the research inventory's path list (cached as a pickle)."""
    global _hash_paths
    if _hash_paths is None:
        cache = os.path.join(work, 'pipeline_cache', 'hash_paths.pkl')
        if os.path.exists(cache):
            _hash_paths = pickle.load(open(cache, 'rb'))
        else:
            _hash_paths = {}
            with open(os.path.join(work, 'inventory', 'path_to_archive.tsv'), encoding='utf-8') as f:
                for line in f:
                    p = line.split('\t', 1)[0]
                    _hash_paths[fnv1a64(p)] = p
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            pickle.dump(_hash_paths, open(cache, 'wb'))
    return _hash_paths.get(h)


class Package:
    def __init__(self, data, work=None, imports_as_hash=True):
        self.d = d = data
        ver, unk, nsec, ncomp = struct.unpack_from('<BBHI', d, 0)
        o = 8
        if nsec == 7:
            ref_desc, ref_data = struct.unpack_from('<II', d, o); o += 8
        else:
            ref_desc = ref_data = 0
        name_desc, name_data, chunk_desc, chunk_data = struct.unpack_from('<IIII', d, o); o += 16
        self.cruid_index, ncr = struct.unpack_from('<hH', d, o); o += 4
        self.cruids = list(struct.unpack_from(f'<{ncr}Q', d, o)); o += 8 * ncr
        base = self.base = o
        self.version, self.sections = ver, nsec
        self.imports = []
        for i in range((ref_data - ref_desc) // 4):
            bf = struct.unpack_from('<I', d, base + ref_desc + 4 * i)[0]
            off, size = bf & ((1 << 23) - 1), (bf >> 23) & 0xFF
            raw = d[base + off: base + off + size]
            if imports_as_hash and size == 8:
                h = struct.unpack('<Q', raw)[0]
                self.imports.append(hash_to_path(h, work) if work else None or f'#{h:016x}')
            else:
                self.imports.append(raw.decode('utf-8', 'replace'))
        self.names = []
        for i in range((name_data - name_desc) // 4):
            bf = struct.unpack_from('<I', d, base + name_desc + 4 * i)[0]
            off = bf & 0x00FFFFFF
            end = d.index(b'\0', base + off)
            self.names.append(d[base + off:end].decode('utf-8', 'replace'))
        self.chunk_heads = [struct.unpack_from('<II', d, base + chunk_desc + 8 * i) for i in range((chunk_data - chunk_desc) // 8)]
        self.classes = [self.names[t] for t, _ in self.chunk_heads]

    def fields(self, i):
        """{name: (type, value-or-raw)} for chunk i. Simple types are decoded; others returned as raw bytes."""
        d, base = self.d, self.base
        start = base + self.chunk_heads[i][1]
        end = base + self.chunk_heads[i + 1][1] if i + 1 < len(self.chunk_heads) else len(d)
        n = struct.unpack_from('<H', d, start)[0]
        heads = [struct.unpack_from('<HHI', d, start + 2 + 8 * k) for k in range(n)]
        out = {}
        for k, (ni, ti, off) in enumerate(heads):
            a = start + off
            b = start + heads[k + 1][2] if k + 1 < n else end
            name, typ = self.names[ni], self.names[ti]
            out[name] = (typ, self._value(typ, a, b))
        return out

    def _value(self, typ, a, b):
        d = self.d
        try:
            if typ in PRIM:
                return struct.unpack_from(PRIM[typ], d, a)[0]
            if typ == 'CName':
                return self.names[struct.unpack_from('<H', d, a)[0]]
            if typ.startswith(('rRef:', 'raRef:')):
                i = struct.unpack_from('<h', d, a)[0]
                return self.imports[i] if 0 <= i < len(self.imports) else None
            if typ.startswith(('handle:', 'whandle:')):
                return {'handle': struct.unpack_from('<i', d, a)[0]}
            if typ in ('String', 'CString'):
                n = struct.unpack_from('<H', d, a)[0]
                return d[a + 2:a + 2 + n].decode('utf-8', 'replace')
            if b - a == 2 and not typ.startswith(('array:', 'static:', '[')):
                v = struct.unpack_from('<H', d, a)[0]       # enum value as CName index
                return self.names[v] if v < len(self.names) else v
        except struct.error:
            pass
        return {'raw': d[a:b]}
