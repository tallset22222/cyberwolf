"""Resolve depot paths to local files: read from the game archives (read-only) into the workspace cache."""
import glob
import os
from . import rdar

WORK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CACHE = os.path.join(WORK, 'pipeline_cache')
DEFAULT_GAME = os.path.expanduser('~/mnt/pc')
DEFAULT_KRAKEN = os.path.expanduser('~/lib/libkraken.so')


class Source:
    def __init__(self, archive_dirs=None, kraken=DEFAULT_KRAKEN, cache=CACHE):
        archive_dirs = archive_dirs or [os.path.join(DEFAULT_GAME, 'content'), os.path.join(DEFAULT_GAME, 'ep1')]
        backend = rdar.KrakenBackend(kraken) if kraken and os.path.exists(kraken) else None
        self.archives = [rdar.Archive(a, backend) for d in archive_dirs for a in sorted(glob.glob(os.path.join(d, '*.archive')))]
        self.cache = cache
        self.where = {}

    def find(self, depot):
        h = rdar.fnv1a64(depot)
        for a in self.archives:
            if h in a.entries:
                return a
        return None

    def get(self, depot):
        """Local path of the CR2W file (buffers beside it as .bufferN), extracting on first use. None if absent."""
        dst = os.path.join(self.cache, depot.replace('\\', '/'))
        if os.path.exists(dst):
            return dst
        a = self.find(depot)
        if a is None:
            return None
        cr2w, bufs = a.read(depot)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        for i, b in enumerate(bufs):
            open(f'{dst}.buffer{i}', 'wb').write(b)
        open(dst, 'wb').write(cr2w)
        self.where[depot] = os.path.basename(a.path)
        return dst
