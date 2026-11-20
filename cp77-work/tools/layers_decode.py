# Read-only summary of Multilayer_Setup (.mlsetup) and Multilayer_Mask (.mlmask) resources.
import sys, os, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
def setup(p):
    c=R(p).chunk(0); L=[]
    for i,l in enumerate(c.get('layers',[])):
        L.append({'layer':i,'template':l.get('material',{}).get('ref'),'colorScale':l.get('colorScale'),
                  'matTile':round(l.get('matTile',1.0),3),'microblend':l.get('microblend',{}).get('ref'),
                  'mbTile':round(l.get('mbTile',1.0),3),'opacity':l.get('opacity',1.0),
                  'roughLevelsOut':l.get('roughLevelsOut'),'metalLevelsOut':l.get('metalLevelsOut'),'normalStrength':l.get('normalStrength')})
    return {'file':os.path.relpath(p),'layers':L}
def mask(p):
    r=R(p); h=[r.chunk(i) for i,c in enumerate(r.meta['chunks']) if c['class'].startswith('rendRenderMultilayerMaskBlob')][0]['header']
    bufs=sorted(glob.glob(p+'.buffer*')); return {'file':os.path.relpath(p),'header':h,'buffers':[(os.path.basename(b),os.path.getsize(b)) for b in bufs]}
if __name__=='__main__':
    root=sys.argv[2]
    S=[setup(p) for p in sorted(glob.glob(root+'/**/*.mlsetup',recursive=True))]
    M=[mask(p) for p in sorted(glob.glob(root+'/**/*.mlmask',recursive=True))]
    json.dump({'setups':S,'masks':M},open(sys.argv[1],'w'),indent=1)
    for s in S:
        cats=collections.Counter(l['template'].split('\\')[3] if l['template'] else None for l in s['layers'])
        print(f"{os.path.basename(s['file'])}: {len(s['layers'])} layers  families={dict(cats)}")
        for l in s['layers']: print(f"    L{l['layer']}: {l['template'].split(chr(92))[-1] if l['template'] else None}  color={l['colorScale']} tile={l['matTile']}")
    for m in M:
        h=m['header']; print(f"{os.path.basename(m['file'])}: {h['numLayers']} masks {h['maskWidth']}x{h['maskHeight']} atlas {h['atlasWidth']}x{h['atlasHeight']} tile={h.get('maskTileSize')} buffers={m['buffers']}")
