# Read-only animRig decoder: bone names, parent indices (binary tail), reference pose, A-pose; validates hierarchy.
import sys, os, struct, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
def qmul(a,b):
    ax,ay,az,aw=a; bx,by,bz,bw=b
    return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx, aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)
def qrot(q,v):
    p=qmul(qmul(q,(v[0],v[1],v[2],0.0)),(-q[0],-q[1],-q[2],q[3])); return p[:3]
def compose(parent,local):  # (t,q) model-space of child
    pt,pq=parent; lt,lq=local; rt=qrot(pq,lt); return ((pt[0]+rt[0],pt[1]+rt[1],pt[2]+rt[2]), qmul(pq,lq))
def tq(x): return ((x['Translation']['X'],x['Translation']['Y'],x['Translation']['Z']),
                   (x['Rotation']['i'],x['Rotation']['j'],x['Rotation']['k'],x['Rotation']['r']))
def decode(path):
    r=R(path); c=r.meta['chunks'][[i for i,x in enumerate(r.meta['chunks']) if x['class']=='animRig'][0]]
    o=c['dataOffset']; end=o+c['dataSize']; props,stop=r.props(o+1,end)
    names=props['boneNames']; n=len(names)
    parents=list(struct.unpack_from(f'<{n}h',r.d,stop)); p=stop+2*n
    ref=[]
    for i in range(n):
        t=struct.unpack_from('<4f',r.d,p); q=struct.unpack_from('<4f',r.d,p+16); s=struct.unpack_from('<4f',r.d,p+32); p+=48
        ref.append({'t':t[:3],'q':q,'s':s[:3]})
    tailOK=(p==end)
    order_ok=all(parents[i]<i for i in range(1,n)) and parents[0]==-1
    # validate: compose aPoseLS along parents and compare with aPoseMS
    refTQ=[(x['t'],x['q']) for x in ref]
    if 'aPoseLS' in props and 'aPoseMS' in props:
        LS=[tq(x) for x in props['aPoseLS']]; MS=[tq(x) for x in props['aPoseMS']]
    else:
        LS=refTQ; MS=None
    comp=[None]*n; maxerr=None if MS is None else 0.0
    for i in range(n):
        comp[i]=LS[i] if parents[i]<0 else compose(comp[parents[i]],LS[i])
        if MS is not None: maxerr=max(maxerr,max(abs(a-b) for a,b in zip(comp[i][0],MS[i][0])))
    if MS is None: MS=comp
    lodStart=props.get('levelOfDetailStartIndices')
    return {'file':os.path.relpath(path),'bones':n,'tailFullyConsumed':tailOK,'parentsTopologicallyOrdered':order_ok,
            'aPoseRecomposeMaxTranslationError_or_None_if_no_aPose':maxerr,'levelOfDetailStartIndices':lodStart,
            'distanceCategoryToLodMap':props.get('distanceCategoryToLodMap'),'tags':props.get('tags'),
            'retargetSource':[x['sourceRig'] for x in props.get('retargets',[])],
            'trackNames':props.get('trackNames'),'parts':[{'name':x['name'],'roots':[t.get('rootBone') for t in x.get('treeBones',[])]} for x in props.get('parts',[])],
            'ragdollBodies':len(props.get('ragdollNames',[])),
            'hierarchy':[{'i':i,'name':names[i],'parent':parents[i],'parentName':names[parents[i]] if parents[i]>=0 else None,
                          'refT':[round(v,5) for v in ref[i]['t']],'refQ':[round(v,5) for v in ref[i]['q']],
                          'modelSpaceT':[round(v,5) for v in MS[i][0]]} for i in range(n)]}
if __name__=='__main__':
    d=decode(sys.argv[2]); json.dump(d,open(sys.argv[1],'w'),indent=1)
    print({k:v for k,v in d.items() if k not in ('hierarchy','parts','trackNames')})
    kids={}
    for b in d['hierarchy']: kids.setdefault(b['parent'],[]).append(b['i'])
    def tree(i,dep=0):
        b=d['hierarchy'][i]; print('  '*dep+b['name'], 'z=%.3f'%b['modelSpaceT'][2] if dep<9 else '')
        for k in kids.get(i,[]):
            if dep<8: tree(k,dep+1)
    tree(0)
