# Header-only texture survey: extracts segment 0 (metadata) of each .xbm, reports logical vs PC size, mips, compression.
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locate, extract
from cr2w_props import R
extract.HEADER_ONLY=True
BPP={'TCM_QualityColor':'BC7 (1 B/px)','TCM_Normalmap':'BC5 (1 B/px)','TCM_NormalsHigh':'BC5','TCM_QualityR':'BC4 (0.5 B/px)',
     'TCM_QualityRG':'BC5','TCM_DXTNoAlpha':'BC1','TCM_DXTAlpha':'BC3','TCM_None':'uncompressed','TCM_Normals':'BC5'}
def info(work,install,paths,logf):
    m=locate.load(work); out=os.path.join(work,'extract','headers'); log=[]; res={}
    for p in sorted(set(paths)):
        a=m.get(p)
        if not a: res[p]={'missing':True}; continue
        dst=os.path.join(out,p.replace('\\','/'))
        if not os.path.exists(dst):
            ap=os.path.join(install,a); extract.extract(ap,[p],out); log.append([ap,p])
        r=R(dst); t=r.chunk(0); b=[r.chunk(i) for i,c in enumerate(r.meta['chunks']) if c['class']=='rendRenderTextureBlobPC'][0]['header']
        st=t.get('setup',{}); comp=st.get('compression','TCM_None')
        res[p]={'archive':a,'logical':[t.get('width'),t.get('height')],'pc':[b['sizeInfo'].get('width'),b['sizeInfo'].get('height')],
                'mips':b['textureInfo'].get('mipCount'),'slices':b['textureInfo'].get('sliceCount'),'dataBytes':b['textureInfo'].get('textureDataSize'),
                'compression':comp,'format':BPP.get(comp,comp),'gamma':bool(st.get('isGamma')),'rawFormat':st.get('rawFormat'),'group':st.get('group'),
                'pcMipBias':st.get('platformMipBiasPC',0)}
    if logf: json.dump(log,open(logf,'w'),indent=1)
    return res
if __name__=='__main__':
    work,install,logf,outf=sys.argv[1:5]; paths=[l.strip() for l in open(sys.argv[5]) if l.strip()]
    res=info(work,install,paths,logf); json.dump(res,open(outf,'w'),indent=1)
    for p,v in res.items():
        if v.get('missing'): print('MISSING',p); continue
        print(f"{v['logical'][0]}x{v['logical'][1]} -> PC {v['pc'][0]}x{v['pc'][1]} mips {v['mips']} {v['format']:<14} gamma={int(v['gamma'])} {v['dataBytes']:>9}  {p.split(chr(92))[-1]}")
