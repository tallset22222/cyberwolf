# Read-only decode + validation of multilayer mask tile tables (format per WolvenKit MlmaskTools.cs).
import sys, os, struct, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
def dc(a,b): return (a+b-1)//b
def analyse(p):
    r=R(p); blob=[r.chunk(i) for i,c in enumerate(r.meta['chunks']) if c['class'].startswith('rendRenderMultilayerMaskBlob')][0]
    h=blob['header']; aw,ah,mw,mh,ts,nl=h['atlasWidth'],h['atlasHeight'],h['maskWidth'],h['maskHeight'],h['maskTileSize'],h['numLayers']
    atlas=open(f"{p}.buffer{blob['atlasData']['buffer']-1}",'rb').read(); tb=open(f"{p}.buffer{blob['tilesData']['buffer']-1}",'rb').read()
    tiles=struct.unpack(f'<{len(tb)//4}I',tb)
    full=dc(mw,ts)*dc(mh,ts); lw,lh=h.get('maskWidthLow',0),h.get('maskHeightLow',0)
    ats=ts+2; agw,agh=aw//ats,ah//ats
    cov=[0]*nl; covLow=[0]*nl; bad=0; decls=0; maxOff=0
    def scan(start,count,acc):
        nonlocal bad,decls,maxOff
        for t in range(start,start+count):
            if 2*t+1>=len(tiles): bad+=1; continue
            off,bits=tiles[2*t],tiles[2*t+1]
            for L in range(nl):
                if bits>>L&1:
                    acc[L]+=1; k=off+bin(bits&((1<<L)-1)).count('1')
                    if k>=len(tiles): bad+=1; continue
                    d=tiles[k]; dx,dy=d&0x3ff,(d>>10)&0x3ff; decls+=1; maxOff=max(maxOff,k)
                    if dx>=agw or dy>=agh: bad+=1
    scan(0,full,cov)
    # low-res grid: WolvenKit derives scale from header; size inferred from remaining pair region
    low_count=0
    if lw and lh:
        small=max(1,mw//lw) if lw else 1
        low_count=dc(mw//small,ts)*dc(mh//small,ts) if small>1 else 0
        scan(full,low_count,covLow)
    return {'file':os.path.basename(p),'layers':nl,'mask':[mw,mh],'tile':ts,'atlas':[aw,ah],'atlasTiles':[agw,agh],
            'atlasBytes':len(atlas),'atlasBytesExpectedBC4':aw*ah//2,'tileWords':len(tiles),'fullResTiles':full,
            'lowResTiles':low_count,'declarations':decls,'maxDeclIndex':maxOff,'invalidRefs':bad,
            'layerCoverageFullRes':[round(c/full,3) for c in cov],'layerHasLowRes':[c>0 for c in covLow]}
if __name__=='__main__':
    res=[analyse(p) for p in sorted(glob.glob(sys.argv[2]+'/**/*.mlmask',recursive=True))]
    json.dump(res,open(sys.argv[1],'w'),indent=1)
    for x in res:
        print(f"{x['file']}: layers {x['layers']} mask {x['mask']} atlas {x['atlas']} ({x['atlasTiles'][0]}x{x['atlasTiles'][1]} tiles) BC4 size ok={x['atlasBytes']==x['atlasBytesExpectedBC4']} tiles full={x['fullResTiles']} low={x['lowResTiles']} decls={x['declarations']} words={x['tileWords']} maxDecl={x['maxDeclIndex']} invalid={x['invalidRefs']}")
        print('    coverage:',x['layerCoverageFullRes'])
