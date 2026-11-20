# Read-only: validate skin weights/indices and boneRigMatrices (inverse bind) against decoded rigs.
import sys, os, json, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
from rig_decode import compose
def rig_ms(js):
    H=json.load(open(js))['hierarchy']; ms={}
    comp=[None]*len(H)
    for b in H:
        loc=(tuple(b['refT']),tuple(b['refQ']))
        comp[b['i']]=loc if b['parent']<0 else compose(comp[b['parent']],loc); ms[b['name']]=comp[b['i']][0]
    return ms
def check(mesh, rigs):
    r=R(mesh); cm=r.chunk(0); names=cm['boneNames']; mats=cm['boneRigMatrices']
    ms={}
    for j in rigs: ms.update({k:v for k,v in rig_ms(j).items() if k not in ms})
    errs=[]
    for n,M in zip(names,mats):
        if n not in ms: continue
        p=ms[n]; row=lambda a:(M['X'][a],M['Y'][a],M['Z'][a],M['W'][a])
        # row-vector convention: p' = p*M  (W row = translation)
        q=[p[0]*M['X'][k]+p[1]*M['Y'][k]+p[2]*M['Z'][k]+M['W'][k] for k in 'XYZ']
        errs.append(math.sqrt(sum(x*x for x in q)))
    bi=[i for i,c in enumerate(r.meta['chunks']) if c['class']=='rendRenderMeshBlob'][0]; blob=r.chunk(bi); h=blob['header']
    B=open(f"{mesh}.buffer{blob['renderBuffer']['buffer']-1}",'rb').read()
    wsum_bad=idx_bad=total=0; maxinf=0
    for c in h['renderChunkInfos']:
        lay=c['chunkVertices']['vertexLayout']; els=lay['elements']; st=lay['slotStrides'][0]; base=c['chunkVertices']['byteOffsets'][0]
        si=[e for e in els if e.get('usage')=='PS_SkinIndices']; sw=[e for e in els if e.get('usage')=='PS_SkinWeights']
        # stream-0 order: position(8) then SkinIndices*, SkinWeights* in element order
        order=[e for e in els if e.get('streamIndex',0)==0 and e.get('usage')!='PS_Invalid']
        off={}; o=0
        for e in order: off[id(e)]=o; o+={'PT_Short4N':8,'PT_UByte4':4,'PT_UByte4N':4,'PT_Float16_4':8}.get(e['type'],0)
        for v in range(c['numVertices']):
            a=base+v*st; ids=[];ws=[]
            for e in si: ids+=list(struct.unpack_from('<4B',B,a+off[id(e)]))
            for e in sw: ws+=list(struct.unpack_from('<4B',B,a+off[id(e)]))
            s=sum(ws); total+=1
            if abs(s-255)>len(ws)//2+1: wsum_bad+=1
            if any(i>=len(names) for i,w in zip(ids,ws) if w): idx_bad+=1
            maxinf=max(maxinf,sum(1 for w in ws if w))
    return {'mesh':os.path.basename(mesh),'bones':len(names),'bonesWithRigPosition':len(errs),
            'inverseBindMaxError_m':round(max(errs),6) if errs else None,'inverseBindMeanError_m':round(sum(errs)/len(errs),6) if errs else None,
            'vertices':total,'weightSumOff':wsum_bad,'indexOutOfRange':idx_bad,'maxInfluences':maxinf}
if __name__=='__main__':
    D='docs/'; res=[
     check('extract/raw/base/characters/main_npc/jackie_welles/t0_001_mb_body__jackie_welles.mesh',[D+'rig_man_big.json',D+'rig_man_big_deformations.json']),
     check('extract/raw/base/characters/cyberware/player/a0_003__mantisblade/a0_003_wa__mantisblade_left_arm.mesh',[D+'rig_mantisblade_wa.json'])]
    json.dump(res,open(D+'skinning_check.json','w'),indent=1)
    for x in res: print(x)
