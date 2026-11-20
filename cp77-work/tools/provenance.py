# Provenance for every extraction log (extract/sample*.json): archive entry metadata, SHA-256 of the compressed source
# segments as stored, SHA-256 of each extracted output file. Also writes a size/mtime manifest of the install.
import sys, os, json, glob, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kark
work, install = sys.argv[1], sys.argv[2]
def sha(b): return hashlib.sha256(b).hexdigest()
idxcache={}
def index(ap):
    if ap not in idxcache:
        with open(ap,'rb') as fh:
            _,_,ipos,isz,_,_,_=struct.unpack('<4sIQIQIQ',fh.read(40)); fh.seek(ipos); idx=fh.read(isz)
        _,_,_,nf,ns,nd=struct.unpack_from('<IIQIII',idx); ent={}; o=28
        for i in range(nf):
            h,ts,ninl,s0,s1,_,_=struct.unpack_from('<QqIIIII',idx,o); ent[h]=(ts,s0,s1,idx[o+36:o+56].hex()); o+=56
        segs=[struct.unpack_from('<QII',idx,28+56*nf+16*k) for k in range(ns)]
        idxcache[ap]=(ent,segs)
    return idxcache[ap]
recs=[]
for logf in sorted(glob.glob(os.path.join(work,'extract','sample*.json'))):
    run=os.path.basename(logf)
    for ap,p in json.load(open(logf)):
        ent,segs=index(ap); ts,s0,s1,sha1=ent[kark.fnv1a64(p)]
        header_only='header' in run
        out_root='headers' if header_only else 'raw'; base=os.path.join(work,'extract',out_root,p.replace('\\','/'))
        seginfo=[]
        with open(ap,'rb') as fh:
            for k in range(s0, s0+1 if header_only else s1):
                off,z,sz=segs[k]; fh.seek(off); seginfo.append({'offset':off,'zsize':z,'size':sz,'sha256_stored':sha(fh.read(z))})
        outs=[base]+[f'{base}.buffer{j}' for j in range(len(seginfo)-1)]
        recs.append({'run':run,'archive':os.path.relpath(ap,install),'path':p,'indexSha1':sha1,'segmentsTotal':s1-s0,
                     'segmentsExtracted':seginfo,'outputs':[{'file':os.path.relpath(o,work),'sha256':sha(open(o,'rb').read())} for o in outs]})
json.dump(recs,open(os.path.join(work,'docs','provenance.json'),'w'),indent=1)
man=[]
for dp,dn,fn in os.walk(install):
    for f in fn:
        q=os.path.join(dp,f); st=os.stat(q); man.append((os.path.relpath(q,install),st.st_size,st.st_mtime_ns))
man.sort()
with open(os.path.join(work,'inventory','install_manifest.tsv'),'w') as fh:
    for r in man: fh.write('%s\t%d\t%d\n'%r)
print('provenance records',len(recs),'runs',sorted({r['run'] for r in recs}),'install files',len(man))
