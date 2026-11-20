# Read-only structural dump of CR2W resources (header, tables, names, imports, chunks, buffers).
import sys, struct, json, os
TABLES=['strings','names','imports','properties','chunks','buffers','embedded']
def parse(path):
    d=open(path,'rb').read()
    magic,ver,flags,ts,build,objEnd,bufEnd,crc,nch=struct.unpack_from('<4sIIQIIIII',d,0)
    o=40; th=[]
    for i in range(10):
        th.append(struct.unpack_from('<III',d,o)); o+=12
    r={'file':path,'size':len(d),'magic':magic.decode(),'version':ver,'flags':flags,'build':build,
       'objectsEnd':objEnd,'buffersEnd':bufEnd,'tables':{TABLES[i]:{'offset':th[i][0],'count':th[i][1]} for i in range(7)}}
    so=th[0][0]
    def s(off):
        e=d.index(b'\0',so+off); return d[so+off:e].decode('utf-8','replace')
    names=[s(struct.unpack_from('<II',d,th[1][0]+8*i)[0]) for i in range(th[1][1])]
    imports=[]
    for i in range(th[2][1]):
        off,cls,fl=struct.unpack_from('<IHH',d,th[2][0]+8*i)
        imports.append({'path':s(off),'class':names[cls] if cls<len(names) else cls,'flags':fl})
    chunks=[]
    for i in range(th[4][1]):
        cls,ofl,par,dsz,doff,tmpl,ccrc=struct.unpack_from('<HHIIIII',d,th[4][0]+24*i)
        chunks.append({'index':i,'class':names[cls],'parent':par,'dataSize':dsz,'dataOffset':doff})
    buffers=[]
    for i in range(th[5][1]):
        fl,idx,off,dsz,msz,bcrc=struct.unpack_from('<IIIIII',d,th[5][0]+24*i)
        buffers.append({'index':idx,'flags':fl,'offset':off,'diskSize':dsz,'memSize':msz})
    r.update(names=names,imports=imports,chunks=chunks,buffers=buffers)
    return r
if __name__=='__main__':
    out=[parse(p) for p in sys.argv[2:]]
    json.dump(out,open(sys.argv[1],'w'),indent=1)
    for r in out:
        print('='*100); print(os.path.basename(r['file']), r['size'],'bytes  v',r['version'],'build',r['build'])
        print(' tables:',{k:v['count'] for k,v in r['tables'].items()})
        from collections import Counter
        print(' chunk classes:',dict(Counter(c['class'] for c in r['chunks'])))
        print(' buffers:',[(b['index'],b['diskSize'],b['memSize']) for b in r['buffers']])
        print(' imports:'); [print('   ',i['class'],i['path']) for i in r['imports']]
