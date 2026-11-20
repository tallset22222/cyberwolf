"""Voice audio: Wwise .wem -> Ogg (WolvenKit's bundled wwtools library, credited) -> PCM (ffmpeg)."""
import ctypes
import os
import subprocess
import numpy as np

_lib = None


def wem_to_ogg(data, lib=os.path.expanduser('~/lib/libwwtools.so')):
    global _lib
    if _lib is None:
        _lib = ctypes.CDLL(lib)
        _lib.get_wem_to_ogg_size.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
        _lib.get_wem_to_ogg_size.restype = ctypes.c_uint64
        _lib.wem_to_ogg.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.c_char_p]
    n = _lib.get_wem_to_ogg_size(data, len(data))
    out = ctypes.create_string_buffer(int(n))
    _lib.wem_to_ogg(data, len(data), out)
    return out.raw[:n]


def decode(ogg, rate=16000):
    """Mono float PCM at `rate` Hz."""
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-f', 'f32le', '-ac', '1', '-ar', str(rate), 'pipe:1'],
                       input=ogg, capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype='<f4'), rate


def rms_envelope(x, rate, times, window=0.04):
    half = int(window * rate / 2)
    out = np.empty(len(times))
    for i, t in enumerate(times):
        c = int(t * rate); seg = x[max(0, c - half):c + half]
        out[i] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0.0
    return out
