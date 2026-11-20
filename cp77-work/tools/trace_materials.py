# Follow material-instance chains (.mi -> base .mi/.mt) from starting refs; extract each .mi (read-only on archives),
# record every parameter, collect texture (.xbm) references. Logs extraction list to the given JSON.
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locate, extract
from material_decode import inst_params
from cr2w_props import R
work, install, logf = sys.argv[1], sys.argv[2], sys.argv[3]; starts=sys.argv[4:]
m=locate.load(work); out=os.path.join(work,'extract','raw'); log=[]; graph={}
def get(p):
    dst=os.path.join(out,p.replace('\\','/'))
    if not os.path.exists(dst):
        a=m.get(p)
        if not a: return None
        ap=os.path.join(install,a); extract.extract(ap,[p],out); log.append([ap,p])
    return dst
todo=list(starts); seen=set()
while todo:
    p=todo.pop()
    if p in seen: continue
    seen.add(p)
    if not p.endswith('.mi'): continue
    f=get(p)
    if not f: graph[p]={'missing':True}; continue
    rr=R(f); ci=[i for i,c in enumerate(rr.meta['chunks']) if c['class']=='CMaterialInstance'][0]
    info=inst_params(rr,ci); graph[p]=info
    if info['baseMaterial']: todo.append(info['baseMaterial'])
    for k,v in info['params'].items():
        if isinstance(v['value'],str) and v['value'].endswith('.mi'): todo.append(v['value'])
json.dump(log,open(logf,'w'),indent=1)
json.dump(graph,open(os.path.join(work,'docs','material_chains.json'),'w'),indent=1)
def show(p,d=0):
    g=graph.get(p,{}); print('  '*d+p.split('\\')[-1], '(missing)' if g.get('missing') else '')
    for k,v in g.get('params',{}).items():
        val=v['value']
        if isinstance(val,str): print('  '*(d+2)+f'{k} = {val}')
        else: print('  '*(d+2)+f'{k} = {json.dumps(val)[:80]}')
    b=g.get('baseMaterial')
    if b: print('  '*(d+1)+'base:'); (show(b,d+2) if b.endswith('.mi') else print('  '*(d+2)+b))
for s in starts: print('====='); show(s)
print('extracted',len(log),'material instances')
