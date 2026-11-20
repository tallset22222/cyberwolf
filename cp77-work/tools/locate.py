# Build/load a depot-path -> archive lookup from inventory\named (cached as a TSV).
import os, json, glob
def load(work):
    cache=os.path.join(work,'inventory','path_to_archive.tsv')
    if not os.path.exists(cache):
        m={}
        for f in sorted(glob.glob(os.path.join(work,'inventory','named','*.index.json'))):
            a=os.path.basename(f).replace('.index.json','').replace('__','/')
            if a.startswith('Cyberpunk 2077/'): continue
            for r in json.load(open(f)):
                if r['path'] and r['path'] not in m: m[r['path']]=a
        with open(cache,'w') as fh:
            for p,a in m.items(): fh.write(f'{p}\t{a}\n')
    return dict(l.rstrip('\n').split('\t',1) for l in open(cache))
