# Read-only material analysis: entries, per-appearance assignments, CMaterialInstance base + parameter tail.
import sys, os, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
def inst_params(r, ci):
    c=r.meta['chunks'][ci]; o=c['dataOffset']; end=o+c['dataSize']; props,stop=r.props(o+1,end)
    t=r.d[stop:end]; out={}
    if len(t)>=4:
        n=struct.unpack_from('<I',t,0)[0]; p=4
        for _ in range(n):
            sz,ni,ti=struct.unpack_from('<IHH',t,p); val=t[p+8:p+sz]; nm=r.names[ni]; ty=r.names[ti]
            if ty.startswith('rRef:') and len(val)>=2:
                i=struct.unpack_from('<H',val,0)[0]; v=r.meta['imports'][i-1]['path'] if 0<i<=len(r.meta['imports']) else None
            else:
                a=stop+p+8
                try: v=r.val(ty,a,stop+p+sz)
                except Exception as ex: v={'undecoded':val.hex(),'error':str(ex)}
            out[nm]={'type':ty,'value':v}; p+=sz
    return {'baseMaterial':props.get('baseMaterial',{}).get('ref'),'enableMask':props.get('enableMask',0),'params':out}
def analyse(path):
    r=R(path); cm=r.chunk(0); rep={'file':os.path.relpath(path),'entries':[],'appearances':[]}
    ents=cm.get('materialEntries',[])
    lmb=cm.get('localMaterialBuffer'); local=[]
    if lmb:
        B=open(f"{path}.buffer{lmb['rawData']['buffer']-1}",'rb').read()
        for h in lmb['rawDataHeaders']:
            o=h.get('offset',0); blk=B[o:o+h['size']]; tmp='/tmp/_mi.cr2w'; open(tmp,'wb').write(blk); rr=R(tmp)
            local.append(inst_params(rr,0))
    else:
        local=[inst_params(r,i) for i,c in enumerate(r.meta['chunks']) if c['class']=='CMaterialInstance']
    for e in ents:
        i=e.get('index',0); rep['entries'].append({'slot':i,'name':e['name'],'local':bool(e.get('isLocalInstance')),**(local[i] if i<len(local) else {})})
    for c in r.meta['chunks']:
        if c['class']=='meshMeshAppearance':
            a=r.chunk(c['index']); rep['appearances'].append({'name':a.get('name','default'),'chunkMaterials':a.get('chunkMaterials',[])})
    return rep
if __name__=='__main__':
    out=[analyse(p) for p in sys.argv[2:]]; json.dump(out,open(sys.argv[1],'w'),indent=1)
    for r_ in out:
        print('=====',os.path.basename(r_['file']))
        for e in r_['entries']:
            print(f"  slot {e['slot']}: {e['name']}  base={e.get('baseMaterial')}")
            for k,v in e.get('params',{}).items(): print(f"      {k} ({v['type']}): {v['value']}")
        for a in r_['appearances']: print('  appearance',a['name'],'->',a['chunkMaterials'])
