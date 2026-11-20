# Extract named files from RDAR archives into an output folder. Read-only on archives.
import sys, os, json, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kark
HEADER_ONLY=False
def extract(archive, wanted, outdir):
    with open(archive,'rb') as fh:
        hdr=fh.read(40); _,_,ipos,isz,_,_,_=struct.unpack_from('<4sIQIQIQ',hdr)
        fh.seek(ipos); idx=fh.read(isz)
        _,_,_,nf,ns,nd=struct.unpack_from('<IIQIII',idx); o=28; files={}
        for i in range(nf):
            h,_,ninl,s0,s1,_,_=struct.unpack_from('<QqIIIII',idx,o); o+=56; files[h]=(s0,s1)
        segs=[struct.unpack_from('<QII',idx,o+16*i) for i in range(ns)]
        done=[]
        for path in wanted:
            h=kark.fnv1a64(path)
            if h not in files: continue
            s0,s1=files[h]; parts=[]
            for k in range(s0, s0+1 if HEADER_ONLY else s1):
                off,z,sz=segs[k]; fh.seek(off); blob=fh.read(z)
                parts.append(kark.unkark(blob, sz) if (blob[:4]==b'KARK' or z!=sz) else blob)
            dst=os.path.join(outdir, path.replace('\\','/'))
            os.makedirs(os.path.dirname(dst),exist_ok=True)
            open(dst,'wb').write(parts[0])
            for j,p in enumerate(parts[1:]): open(f'{dst}.buffer{j}','wb').write(p)
            done.append((path,len(parts),parts[0][:4]))
        return done
if __name__=='__main__':
    if '--header-only' in sys.argv: HEADER_ONLY=True; sys.argv.remove('--header-only')
    for a,p in json.load(open(sys.argv[1])):
        for r in extract(a,[p],sys.argv[2]): print(*r)
