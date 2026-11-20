# Read-only: decode Multilayer_LayerTemplate and resolve every .mlsetup layer's preset names against its template.
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cr2w_props import R
def tmpl(work,p):
    f=os.path.join(work,'extract','raw',p.replace('\\','/'))
    if not os.path.exists(f): return None
    c=R(f).chunk(0); o=c.get('overrides',{})
    return {'textures':{k:c[k]['ref'] for k in ('colorTexture','normalTexture','roughnessTexture','metalnessTexture') if k in c},
            'tilingMultiplier':c.get('tilingMultiplier',1.0),
            'presets':{k:{e['n']:e.get('v') for e in o.get(k,[])} for k in ('colorScale','roughLevelsIn','roughLevelsOut','metalLevelsIn','metalLevelsOut','normalStrength')}}
if __name__=='__main__':
    work=sys.argv[1]; L=json.load(open(os.path.join(work,'docs','material_layers.json'))); T={}; report=[]
    for s in L['setups']:
        rows=[]
        for l in s['layers']:
            t=T.setdefault(l['template'],tmpl(work,l['template']))
            row={'layer':l['layer'],'template':l['template']}
            if t is None: row['templateMissing']=True; rows.append(row); continue
            for key in ('colorScale','roughLevelsOut','metalLevelsOut','normalStrength'):
                name=l.get(key)
                if name is None: continue
                row[key]={'name':name,'resolved':name in t['presets'][key],'value':t['presets'][key].get(name)}
            row['textures']=t['textures']; row['tiling']=t['tilingMultiplier']*l['matTile'] if l['matTile'] else None
            rows.append(row)
        report.append({'setup':s['file'],'layers':rows})
    json.dump({'templates':T,'setups':report},open(os.path.join(work,'docs','material_templates.json'),'w'),indent=1)
    tot=ok=0; unresolved=[]
    for s in report:
        for r_ in s['layers']:
            for k in ('colorScale','roughLevelsOut','metalLevelsOut','normalStrength'):
                if k in r_:
                    tot+=1
                    if r_[k]['resolved']: ok+=1
                    else: unresolved.append((os.path.basename(s['setup']),r_['layer'],k,r_[k]['name']))
    print('templates decoded',sum(1 for v in T.values() if v),'of',len(T)); print('preset references',tot,'resolved',ok)
    print('unresolved:',unresolved[:20])
    for p,v in list(T.items())[:4]:
        if v: print(p.split('\\')[-1],{k:x.split('\\')[-1] for k,x in v['textures'].items()},'tiling',round(v['tilingMultiplier'],2),{k:len(x) for k,x in v['presets'].items()})
    ex=report[1]['layers'][0]; print('example', os.path.basename(report[1]['setup']), json.dumps({k:ex[k] for k in ('colorScale','roughLevelsOut')}))
    tex=sorted({x for v in T.values() if v for x in v['textures'].values()}); open('/tmp/tmpl_tex.txt','w').write('\n'.join(tex)); print('distinct template textures',len(tex))
