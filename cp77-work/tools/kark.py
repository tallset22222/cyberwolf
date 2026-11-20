import ctypes, struct, os
_lib = ctypes.CDLL(os.path.expanduser('~/lib/libkraken.so'))
_lib.Kraken_Decompress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
_lib.Kraken_Decompress.restype = ctypes.c_int
def unkark(blob, size=None):
    if blob[:4] == b'KARK':
        size = struct.unpack_from('<I', blob, 4)[0]; blob = blob[8:]
    if size is None: raise ValueError('need size')
    if len(blob) == size: return blob
    out = ctypes.create_string_buffer(size + 64)
    n = _lib.Kraken_Decompress(blob, len(blob), out, size)
    if n != size: raise RuntimeError(f'kraken returned {n}, expected {size}')
    return out.raw[:size]
def fnv1a64(s):
    h = 0xcbf29ce484222325
    for b in s.encode('utf-8'):
        h ^= b; h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h
