# Read-only vertex attribute decoding + validation (normals, tangents, UV0, UV1, colour). Writes JSON report only.
import sys, os, struct, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
def half(h): return struct.unpack('<e', struct.pack('<H', h))[0]
def dec4(u):
    x=(u&0x3ff)/1023*2-1; y=((u>>10)&0x3ff)/1023*2-1; z=((u>>20)&0x3ff)/1023*2-1; w=u>>30
    return (x,y,z), w
def sub(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def ln(a): return math.sqrt(dot(a,a))
def analyse(path):
    r=R(path); bi=[i for i,c in enumerate(r.meta['chunks']) if c['class']=='rendRenderMeshBlob'][0]
    blob=r.chunk(bi); h=blob['header']; B=open(f"{path}.buffer{blob['renderBuffer']['buffer']-1}",'rb').read()
    qs=[h['quantizationScale'].get(k,0) for k in 'XYZ']; qo=[h['quantizationOffset'].get(k,0) for k in 'XYZ']; ibo=h['indexBufferOffset']
    out=[]
    for ci,c in enumerate(h['renderChunkInfos']):
        lay=c['chunkVertices']['vertexLayout']; offs=c['chunkVertices']['byteOffsets']; st=lay['slotStrides']; nv=c['numVertices']; ni=c['numIndices']
        els=lay['elements']
        def find(u,ui=0):
            for e in els:
                if e.get('usage')==u and e.get('usageIndex',0)==ui: return e
        # in-stream byte offset of an element = sum of sizes of earlier elements on same stream
        SZ={'PT_Short4N':8,'PT_Float16_2':4,'PT_Dec4':4,'PT_Color':4,'PT_UByte4':4,'PT_UByte4N':4,'PT_Float16_4':8}
        def elem_off(target):
            o=0
            for e in els:
                if e is target: return o
                if e.get('streamIndex',0)==target.get('streamIndex',0): o+=SZ.get(e['type'],0)
        P=[];N=[];T=[];TW=[];UV0=[];UV1=[];nlen=[];col=[]
        pe=find('PS_Position'); s=pe.get('streamIndex',0)
        for v in range(nv):
            x,y,z,_=struct.unpack_from('<4h',B,offs[s]+v*st[s]); P.append((x/32767*qs[0]+qo[0],y/32767*qs[1]+qo[1],z/32767*qs[2]+qo[2]))
        ne=find('PS_Normal'); te=find('PS_Tangent'); u0=find('PS_TexCoord',0); u1=find('PS_TexCoord',1); ce=find('PS_Color')
        for v in range(nv):
            if ne:
                s=ne['streamIndex']; n,_=dec4(struct.unpack_from('<I',B,offs[s]+v*st[s]+elem_off(ne))[0]); nlen.append(ln(n)); L=ln(n) or 1; N.append((n[0]/L,n[1]/L,n[2]/L))
            if te:
                s=te['streamIndex']; t,w=dec4(struct.unpack_from('<I',B,offs[s]+v*st[s]+elem_off(te))[0]); L=ln(t) or 1; T.append((t[0]/L,t[1]/L,t[2]/L)); TW.append(w)
            if u0:
                s=u0['streamIndex']; a,b=struct.unpack_from('<2H',B,offs[s]+v*st[s]+elem_off(u0)); UV0.append((half(a),half(b)))
            if u1:
                s=u1['streamIndex']; a,b=struct.unpack_from('<2H',B,offs[s]+v*st[s]+elem_off(u1)); UV1.append((half(a),half(b)))
            if ce:
                s=ce['streamIndex']; col.append(struct.unpack_from('<4B',B,offs[s]+v*st[s]+elem_off(ce)))
        idx=struct.unpack_from(f'<{ni}H',B,ibo+c['chunkIndices'].get('teOffset',0))
        agree=disagree=0; tuv_pos=tuv_neg=0; degenerate=0
        for k in range(0,ni-2,3):
            a,b,cc=idx[k],idx[k+1],idx[k+2]; e1=sub(P[b],P[a]); e2=sub(P[cc],P[a]); fn=cross(e1,e2)
            if ln(fn)<1e-12: degenerate+=1; continue
            if N:
                vn=(N[a][0]+N[b][0]+N[cc][0],N[a][1]+N[b][1]+N[cc][1],N[a][2]+N[b][2]+N[cc][2])
                if dot(fn,vn)>0: agree+=1
                else: disagree+=1
            if T and UV0:
                du1=UV0[b][0]-UV0[a][0]; dv1=UV0[b][1]-UV0[a][1]; du2=UV0[cc][0]-UV0[a][0]; dv2=UV0[cc][1]-UV0[a][1]
                det=du1*dv2-du2*dv1
                if abs(det)>1e-12:
                    dpdu=tuple((e1[i]*dv2-e2[i]*dv1)/det for i in range(3))
                    if dot(dpdu,T[a])>0: tuv_pos+=1
                    else: tuv_neg+=1
        ortho=[abs(dot(N[i],T[i])) for i in range(len(T))] if N and T else []
        def rng(U): return [round(min(u[0] for u in U),4),round(max(u[0] for u in U),4),round(min(u[1] for u in U),4),round(max(u[1] for u in U),4)] if U else None
        tri=agree+disagree
        out.append({'chunk':ci,'lodMask':c['lodMask'],'vertices':nv,'triangles':ni//3,'degenerateTriangles':degenerate,
            'normalRawLength':[round(min(nlen),4),round(max(nlen),4)] if nlen else None,
            'normalTangentMaxAbsDot':round(max(ortho),4) if ortho else None,
            'normalTangentMeanAbsDot':round(sum(ortho)/len(ortho),5) if ortho else None,
            'tangentW':{str(k):TW.count(k) for k in set(TW)},
            'faceNormalAgreement':round(max(agree,disagree)/tri,4) if tri else None,'windingSign':'+' if agree>=disagree else '-',
            'tangentFollowsU':round(max(tuv_pos,tuv_neg)/(tuv_pos+tuv_neg),4) if (tuv_pos+tuv_neg) else None,
            'uv0Range':rng(UV0),'uv1Range':rng(UV1),'uvNaN':sum(1 for u in UV0+UV1 if u[0]!=u[0] or u[1]!=u[1]),
            'colourDistinct':len(set(col)) if col else None})
    return {'file':os.path.relpath(path),'chunks':out}
if __name__=='__main__':
    res=[analyse(p) for p in sys.argv[2:]]; json.dump(res,open(sys.argv[1],'w'),indent=1)
    for r_ in res:
        print('=====',os.path.basename(r_['file']))
        for c in r_['chunks']:
            print(f"  c{c['chunk']} lod{c['lodMask']} v{c['vertices']} |n|={c['normalRawLength']} n.t max={c['normalTangentMaxAbsDot']} mean={c['normalTangentMeanAbsDot']} w={c['tangentW']} faceAgree={c['faceNormalAgreement']}{c['windingSign']} tFollowsU={c['tangentFollowsU']} uv0={c['uv0Range']} uv1={c['uv1Range']} nan={c['uvNaN']} degen={c['degenerateTriangles']} colours={c['colourDistinct']}")
