# Read-only geometry analysis of extracted CR2W meshes: layouts, counts, LODs, validation. Writes JSON report only.
import sys, os, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
PSIZE={'PT_Short4N':8,'PT_Float16_2':4,'PT_Dec4':4,'PT_Color':4,'PT_UByte4':4,'PT_UByte4N':4,'PT_Float3':12,
       'PT_Float4':16,'PT_Float2':8,'PT_Float16_4':8,'PT_Short2N':4,'PT_UShort4':8,'PT_UShort4N':8,'PT_Float1':4}
def v4(x): return [x.get(k,0.0) for k in ('X','Y','Z','W')]
def analyse(path):
    r=R(path); rep={'file':os.path.relpath(path),'chunks':[]}
    bi=[i for i,c in enumerate(r.meta['chunks']) if c['class']=='rendRenderMeshBlob'][0]
    blob=r.chunk(bi); h=blob['header']
    bufno=blob['renderBuffer']['buffer']; bpath=f'{path}.buffer{bufno-1}'; B=open(bpath,'rb').read()
    qs=v4(h['quantizationScale']); qo=v4(h['quantizationOffset'])
    vbs=h['vertexBufferSize']; ibs=h['indexBufferSize']; ibo=h['indexBufferOffset']
    rep.update(blobVersion=h['version'],renderLODs=h['renderLODs'],quantScale=qs,quantOffset=qo,
               vertexBufferSize=vbs,indexBufferSize=ibs,indexBufferOffset=ibo,renderBufferFile=os.path.basename(bpath),
               renderBufferBytes=len(B),buffersAddUp=(ibo+ibs<=len(B) and vbs<=ibo))
    lods={}
    for ci,c in enumerate(h['renderChunkInfos']):
        lay=c['chunkVertices']['vertexLayout']; offs=c['chunkVertices']['byteOffsets']; strides=lay['slotStrides']
        els=[(e.get('usage'),e.get('usageIndex',0),e.get('type'),e.get('streamIndex',0)) for e in lay['elements']]
        nv=c['numVertices']; ni=c['numIndices']; te=c['chunkIndices'].get('teOffset',0)
        idx=struct.unpack_from(f'<{ni}H',B,ibo+te)
        # position stream: element with PS_Position, stream s
        pe=[e for e in els if e[0]=='PS_Position'][0]; s=pe[3]; st=strides[s]; base=offs[s]
        mn=[1e9]*3; mx=[-1e9]*3
        for v in range(nv):
            x,y,z,w=struct.unpack_from('<4h',B,base+v*st)
            p=[x/32767*qs[0]+qo[0], y/32767*qs[1]+qo[1], z/32767*qs[2]+qo[2]]
            for k in range(3): mn[k]=min(mn[k],p[k]); mx[k]=max(mx[k],p[k])
        used={e[3] for e in els}; streams_fit=all(offs[sl]+nv*strides[sl]<=vbs for sl in used if sl<len(offs) and strides[sl]); unplaced=sorted(sl for sl in used if sl>=len(offs))
        ch={'chunk':ci,'lodMask':c['lodMask'],'vertices':nv,'indices':ni,'triangles':ni//3,
            'maxIndex':max(idx) if idx else None,'indicesValid':(max(idx)<nv) if idx else True,
            'streamsFitInVertexBuffer':streams_fit,'streamsWithoutOffset':unplaced,'vertexFactory':c['vertexFactory'],
            'renderMask':c.get('renderMask'),'layout':[f'{u}{ui if ui else ""}:{t}@s{sI}' for u,ui,t,sI in els],
            'strides':strides[:max(e[3] for e in els)+1],'bboxMin':[round(a,4) for a in mn],'bboxMax':[round(a,4) for a in mx]}
        rep['chunks'].append(ch)
        for b in range(8):
            if c['lodMask']>>b & 1:
                L=lods.setdefault(b,{'chunks':0,'vertices':0,'triangles':0}); L['chunks']+=1; L['vertices']+=nv; L['triangles']+=ni//3
    rep['lods']={f'LOD{k}':v for k,v in sorted(lods.items())}
    return rep
if __name__=='__main__':
    out=[analyse(p) for p in sys.argv[2:]]
    json.dump(out,open(sys.argv[1],'w'),indent=1)
    for r_ in out:
        print('='*90); print(os.path.basename(r_['file']), '| blob v',r_['blobVersion'],'| LOD dist',r_['renderLODs'],'| buffers add up:',r_['buffersAddUp'])
        print(' quant scale',[round(x,4) for x in r_['quantScale'][:3]],'offset',[round(x,4) for x in r_['quantOffset'][:3]])
        print(' LODs:',r_['lods'])
        bad=[c['chunk'] for c in r_['chunks'] if not (c['indicesValid'] and c['streamsFitInVertexBuffer'])]
        print(' chunks:',len(r_['chunks']),' failing validation:',bad)
        layouts=sorted({' '.join(c['layout']) for c in r_['chunks']})
        for l in layouts: print('  layout:',l)
        mn=[min(c['bboxMin'][k] for c in r_['chunks']) for k in range(3)]; mx=[max(c['bboxMax'][k] for c in r_['chunks']) for k in range(3)]
        print(' bbox min',mn,'max',mx)
