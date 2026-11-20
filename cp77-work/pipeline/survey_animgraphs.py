"""Corpus survey: explicit field values of selected classes across every .animgraph, to test engine defaults.

CR2W omits a property equal to its class default, so an explicitly stored value equal to a proposed default
contradicts that default. Resumable: per-graph results cached in pipeline_out/research/animgraph_survey.jsonl.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyberwolf.source import Source, WORK
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from cr2w_props import R

CLASSES = {'animDangleConstraint_SimulationDyng', 'animAnimNode_Drag', 'animAnimNode_FloatConstant', 'animAnimNode_BlendOverride',
           'animAnimNode_SimpleBounce', 'animAnimNode_SimpleSpline', 'animAnimNode_AimConstraint_ObjectUp',
           'animAnimNode_AimConstraint_ObjectRotationUp', 'animDyngConstraintEllipsoid', 'animDyngConstraintLink',
           'animDyngConstraintCone', 'animAnimNode_Dangle'}
OUT = os.path.join(WORK, 'pipeline_out', 'research', 'animgraph_survey.jsonl')


def scalars(x, prefix=''):
    out = {}
    for k, v in x.items():
        if isinstance(v, (int, float, str, bool)):
            out[prefix + k] = v
        elif isinstance(v, dict) and set(v) <= {'X', 'Y', 'Z', 'W'}:
            out[prefix + k] = [v.get(a) for a in 'XYZ']
    return out


def survey(path, src):
    r = R(src.get(path))
    rec = []
    for i, c in enumerate(r.meta['chunks']):
        if c['class'] not in CLASSES:
            continue
        x = r.chunk(i)
        rec.append({'class': c['class'], 'fields': scalars(x)})
        if c['class'] == 'animDangleConstraint_SimulationDyng':
            pc = x.get('particlesContainer', {})
            rec.append({'class': 'animDyngParticlesContainer', 'fields': scalars(pc)})
            for p in pc.get('particles', []):
                rec.append({'class': 'animDyngParticle', 'fields': scalars(p)})
    return rec


def main(budget):
    src = Source()
    paths = sorted(l.split('\t')[0] for l in open(os.path.join(WORK, 'inventory', 'path_to_archive.tsv')) if l.split('\t')[0].lower().endswith('.animgraph'))
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)['path'] for l in open(OUT)}
    t0 = time.time(); n = 0
    with open(OUT, 'a') as f:
        for p in paths:
            if p in done:
                continue
            if time.time() - t0 > budget:
                break
            try:
                rec = survey(p, src); err = None
            except Exception as e:  # recorded, not hidden
                rec, err = [], repr(e)[:200]
            f.write(json.dumps({'path': p, 'records': rec, 'error': err}) + '\n'); n += 1
    print(f'processed {n}, total {len(done) + n}/{len(paths)}')


if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 140)
