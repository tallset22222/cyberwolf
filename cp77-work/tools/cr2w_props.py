# Read-only RTTI property decoder for CR2W v195 chunk data.
import struct, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_dump import parse
PRIM={'Uint8':'<B','Int8':'<b','Uint16':'<H','Int16':'<h','Uint32':'<I','Int32':'<i','Uint64':'<Q','Int64':'<q',
      'Float':'<f','Double':'<d','Bool':'<B'}
class R:
    def __init__(s,path):
        s.meta=parse(path); s.d=open(path,'rb').read(); s.names=s.meta['names']
    def val(s,t,o,end):
        d=s.d
        if t in PRIM: return struct.unpack_from(PRIM[t],d,o)[0]
        if t=='CName': return s.names[struct.unpack_from('<H',d,o)[0]]
        if t.startswith('handle:') or t.startswith('whandle:'): return {'handle':struct.unpack_from('<i',d,o)[0]-1}
        if t.startswith('rRef:') or t.startswith('raRef:'):
            i=struct.unpack_from('<H',d,o)[0]; imp=s.meta['imports']
            return {'ref':imp[i-1]['path'] if 0<i<=len(imp) else i}
        if t in ('DataBuffer','serializationDeferredDataBuffer','SharedDataBuffer'):
            return {'buffer':struct.unpack_from('<H',d,o)[0], 'rawlen':end-o}
        if t.startswith('static:'): t='array:'+t.split(',',1)[1]
        if t.startswith('array:'):
            n=struct.unpack_from('<I',d,o)[0]; o+=4; et=t[6:]; out=[]
            for _ in range(n):
                v,o=s.elem(et,o,end); out.append(v)
            return out
        if t.startswith('['):
            k=t.index(']'); et=t[k+1:]; n=struct.unpack_from('<I',d,o)[0]; o+=4; out=[]
            for _ in range(n):
                v,o=s.elem(et,o,end); out.append(v)
            return out
        if t=='String':
            return s.string(o)[0]
        # enum or struct: try struct (property list); enums are a single CName u16
        if d[o]==0 and end-o!=2: return s.props(o+1,end)[0]
        if end-o==2: return s.names[struct.unpack_from('<H',d,o)[0]]
        flags=[]
        while o+2<=end:
            x=struct.unpack_from('<H',d,o)[0]; o+=2
            if x==0: break
            flags.append(s.names[x])
        return flags
    def string(s,o):
        b=struct.unpack_from('<b',s.d,o)[0]; o+=1
        if b<0: n=-b; v=s.d[o:o+n].decode('latin1'); return v,o+n
        n=b; v=s.d[o:o+2*n].decode('utf-16le'); return v,o+2*n
    def elem(s,t,o,end):
        d=s.d
        if t in PRIM: sz=struct.calcsize(PRIM[t]); return struct.unpack_from(PRIM[t],d,o)[0],o+sz
        if t=='CName': return s.names[struct.unpack_from('<H',d,o)[0]],o+2
        if t.startswith('handle:') or t.startswith('whandle:'): return {'handle':struct.unpack_from('<i',d,o)[0]-1},o+4
        if t.startswith('rRef:') or t.startswith('raRef:'):
            i=struct.unpack_from('<H',d,o)[0]; imp=s.meta['imports']
            return {'ref':imp[i-1]['path'] if 0<i<=len(imp) else i},o+2
        if t.startswith('static:'): t='array:'+t.split(',',1)[1]
        if t.startswith('array:'):
            n=struct.unpack_from('<I',d,o)[0]; o+=4; out=[]
            for _ in range(n):
                v,o=s.elem(t[6:],o,end); out.append(v)
            return out,o
        if t=='String': return s.string(o)
        # struct element: property list terminated by name 0; enums inside arrays are u16 names
        if d[o]==0: return s.props(o+1,end)
        return s.names[struct.unpack_from('<H',d,o)[0]],o+2
    def props(s,o,end):
        out={}
        while o+2<=end:
            ni=struct.unpack_from('<H',s.d,o)[0]
            if ni==0: return out,o+2
            ti,sz=struct.unpack_from('<HI',s.d,o+2)
            name=s.names[ni]; t=s.names[ti]; vo=o+8; ve=o+4+sz
            try: out[name]=s.val(t,vo,ve)
            except Exception as e: out[name]={'type':t,'error':str(e),'size':sz-4}
            o=ve
        return out,o
    def chunk(s,i):
        c=s.meta['chunks'][i]; o=c['dataOffset']; end=o+c['dataSize']
        return s.props(o+1,end)[0]   # leading zero byte
def short(v,n=6):
    if isinstance(v,list): return [short(x,n) for x in v[:n]]+(['...(%d)'%len(v)] if len(v)>n else [])
    if isinstance(v,dict): return {k:short(x,n) for k,x in v.items()}
    return v
if __name__=='__main__':
    r=R(sys.argv[1]); idx=int(sys.argv[2]) if len(sys.argv)>2 else None
    for i,c in enumerate(r.meta['chunks']):
        if idx is not None and i!=idx: continue
        print('#',i,c['class']); print(json.dumps(short(r.chunk(i)),indent=1,default=str)[:6000])
