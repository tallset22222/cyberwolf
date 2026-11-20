"""Test WolvenKit RTTI default values against the animgraph corpus survey (survey_animgraphs.py).
A default is contradicted if any explicitly stored value equals it (CR2W omits values equal to the default).
Writes pipeline_out/research/defaults_check.json."""
import json, collections
WK = {  # WolvenKit constructor defaults (fields not set in constructors are the type's zero value)
 'animDyngParticle': {'mass':1.0,'damping':1.0,'pullForceFactor':0.0,'isFree':1,'collisionCapsuleRadius':0.0,'collisionCapsuleHeightExtent':0.0,'projectionType':'ShortestPath'},
 'animDyngParticlesContainer': {'gravityWS':9.81},
 'animDangleConstraint_SimulationDyng': {'substepTime':0.01,'solverIterations':1,'alpha':1.0,'rotateParentToLookAtDangle':1,'HACK_checkDangleTeleport':0,'jsonCollisionShapesLoadedSuccessfully':1},
 'animAnimNode_Drag': {'simulationFps':100.0,'sourceSpeedMultiplier':10.0,'hasOvershoot':1,'overshootDuration':1.0,'overshootDetectionMinSpeed':0.4,'overshootDetectionMaxSpeed':4.0,'useSteps':0,'stepsTargetSpeedMultiplier':10000.0,'timeBetweenSteps':0.1,'timeInStep':0.1},
 'animAnimNode_FloatConstant': {'value':0.0},
 'animAnimNode_SimpleBounce': {'multiplier':1.0,'negativeMultiplier':1.0,'smoothStep':1.0,'offset':0.0,'delay':0.0},
 'animAnimNode_SimpleSpline': {'defaultProgress':0.5},
 'animDyngConstraintEllipsoid': {'constraintRadius':1.0,'constraintScale1':1.0,'constraintScale2':1.0},
 'animDyngConstraintLink': {'lengthLowerBoundRatioPercentage':100.0,'lengthUpperBoundRatioPercentage':100.0},
 'animDyngConstraintCone': {'halfOfMaxApertureAngle':45.0},
}
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline_out", "research")
rows=[json.loads(l) for l in open(os.path.join(OUT, "animgraph_survey.jsonl"))]
result={}
print('graphs',len(rows),'errors',sum(1 for r in rows if r['error']), [r['error'] for r in rows if r['error']][:3])
stat=collections.defaultdict(lambda: collections.defaultdict(list))
ninst=collections.Counter()
for r in rows:
    for rec in r['records']:
        ninst[rec['class']]+=1
        for k,v in rec['fields'].items(): stat[rec['class']][k].append(v)
for c,d in WK.items():
    print('##',c,'instances',ninst[c])
    for k,dv in d.items():
        vals=stat[c].get(k,[])
        eq=sum(1 for v in vals if (abs(v-dv)<1e-6 if isinstance(dv,float) and isinstance(v,(int,float)) else v==dv))
        top=collections.Counter(round(v,4) if isinstance(v,float) else v for v in vals).most_common(5)
        result.setdefault(c, {})[k] = {'default': dv, 'explicit': len(vals), 'explicit_equal_default': eq, 'common': top}
        print('   %-36s default %-12s explicit %5d  explicit==default %3d  common %s'%(k,dv,len(vals),eq,top))
json.dump(result, open(os.path.join(OUT, 'defaults_check.json'), 'w'), indent=1, default=str)
bad = [(c, k) for c, d in result.items() for k, v in d.items() if v['explicit_equal_default']]
print('contradicted defaults:', bad)
