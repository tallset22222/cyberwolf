"""Step 6 (1-4): reconstruct Judy's deformation + breast graphs, decode constraint nodes, dependency order,
and evaluate the procedural layer at the reference pose against the rig's joint positions.

No dynamic simulation is run here. Writes pipeline_out/deformation/<name>.json and .md.
"""
import argparse
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyberwolf.source import Source, WORK  # noqa: E402
from cyberwolf.animgraph import AnimGraph, dependency_cone, reads  # noqa: E402
from cyberwolf.rig import Rig  # noqa: E402
from cyberwolf import deform  # noqa: E402
from cyberwolf import assemble as A  # noqa: E402
from cr2w_props import R  # noqa: E402

DIR = r'base\characters\base_entities\woman_base\deformations_rigs' + '\\'


def graph_summary(g):
    live = g.post_order(2)
    ls = set(live)
    init = {r['handle'] for r in g.x[0].get('nodesToInit', [])}
    data_reach = set(ls)
    stack = list(ls)
    while stack:
        h = stack.pop()
        for _, c in g.links[h] + g.data[h]:
            if c not in data_reach:
                data_reach.add(c)
                stack.append(c)
    init_nodes = {h for h in init if not g.cls[h].startswith('animAnimNodeSourceChannel')}
    return {
        'chunks': len(g.cls),
        'live_nodes': len(live),
        'live_by_class': dict(collections.Counter(g.short(h) for h in live).most_common()),
        'unreachable_from_output': len(g.cls) - len(data_reach),
        'nodesToInit': len(init),
        'nodesToInit_equals_live_plus_root_and_data_nodes': init_nodes - {g.root} == (init_nodes & data_reach) - {g.root} and ls <= init,
        'nodesToInit_minus_live': sorted(g.short(h) for h in init - ls),
    }


def dangles(g):
    live = set(g.post_order(2))
    consumed = {c for l in g.links for _, c in l}
    out = []
    for h, c in enumerate(g.cls):
        if c != 'animAnimNode_Dangle':
            continue
        sh = g.x[h]['dangleConstraint']['handle']
        sim = g.x[sh]
        pc = sim['particlesContainer']
        inner = []
        for _, d in g.data[sh]:
            inner += [g.short(i) for _, i in g.data[d]] if g.cls[d] == 'animDyngConstraintMulti' else [g.short(d)]
        sinks = [s for s in range(len(g.cls)) if s not in consumed and h in set(g.post_order(s))]
        out.append({
            'node': h, 'simulation': sh, 'live': h in live,
            'reached_from': [f'{s} {g.short(s)}' for s in sinks],
            'particles': [{'bone': p['bone']['name'], 'damping': p.get('damping'), 'pullForceFactor': p.get('pullForceFactor'),
                           'isFree': p.get('isFree', 'default(true)')} for p in pc['particles']],
            'constraints': dict(collections.Counter(inner)),
            'substepTime': sim.get('substepTime', 'default (not in data)'),
            'solverIterations': sim.get('solverIterations', 'default (not in data)'),
            'externalForce': ('MathExpressionVector(' + g.x[pc['externalForceWsLink']['node']['handle']]['expressionString'].split('\x00')[0] + ') of VectorInput DangleExternalInput.fictitiousAccelerationWs') if 'externalForceWsLink' in pc else None,
            'HACK_checkDangleTeleport': sim.get('HACK_checkDangleTeleport'),
            'rotateParentToLookAtDangle': sim.get('rotateParentToLookAtDangle'),
        })
    return out


def chain(g, start=2):
    rows = []
    for h in g.post_order(start):
        x, c = g.x[h], g.short(h)
        row = {'node': h, 'class': c, 'writes': g.targets(h)[:8]}
        if c == 'StaticSwitch':
            row['condition'] = g.x[x['condition']['handle']]
            row['true'], row['false'] = x['True']['node']['handle'], x['False']['node']['handle']
        if c == 'StackTransformsExtender':
            row['adds'] = [(t['name'], t['parentName']) for t in x['transformInfos']]
            row['snap'] = list(zip(x.get('snapMethods', []), [b.get('name') for b in x.get('snapTargetBones', [])]))
        if c == 'SetBoneTransform':
            row['entries'] = [(e['transformToChange']['name'], e.get('setMethod', 'default'), e['sourceBone']['name']) for e in x['entries']]
        if c == 'BlendOverride':
            row['weightNode'] = f"{x['weightNode']['node']['handle']} {g.short(x['weightNode']['node']['handle'])} {g.x[x['weightNode']['node']['handle']] or '(value omitted: engine default, not in data)'}"
        if c == 'Drag':
            row['params'] = {k: x.get(k) for k in ('simulationFps', 'sourceSpeedMultiplier', 'hasOvershoot')}
        rows.append(row)
    return rows


def ellipsoid_rest(g, live_dangles):
    """Where each particle sits at rest relative to its ellipsoid under the candidate readings."""
    rows = []
    for dd in live_dangles:
        sh = dd['simulation']
        for _, m in g.data[sh]:
            for _, e in g.data[m]:
                if g.cls[e] != 'animDyngConstraintEllipsoid':
                    continue
                x = g.x[e]
                off = deform.tq(x['ellipsoidTransformLS'])[:3, 3]
                r, s1, s2 = x.get('constraintRadius'), x.get('constraintScale1', 1.0), x.get('constraintScale2', 1.0)
                rel = -off
                cand = {}
                for name, ax in (('xy_scaled', (r * s1, r * s2, r)), ('yz_scaled', (r, r * s1, r * s2)), ('xz_scaled', (r * s1, r, r * s2))):
                    cand[name] = float(np.sqrt(np.sum((rel / np.array(ax)) ** 2)))
                rows.append({'system': sh, 'bone': x['bone']['name'], 'offset_mm': (off * 1000).round(3).tolist(), 'radius_mm': r * 1000,
                             'scales': [s1, s2], '|offset|/radius': float(np.linalg.norm(off) / r),
                             'q_if_offset_is_centre': cand, 'q_if_offset_ignored': 0.0})
    return rows


def rest_eval(gd, rig, bones, cfg):
    order = gd.post_order(2)
    rows, pose, problems = deform.rest_check(gd, rig, order, cfg)
    written = set(t for h in order for t in gd.targets(h))
    per = {}
    for n in rig.names:
        if n in written:
            per[n] = (float(np.linalg.norm(pose.ms[n][:3, 3] - pose.ref_ms[n][:3, 3]) * 1000),
                      deform.rot_err_deg(pose.ms[n], pose.ref_ms[n]))
    a = np.array(list(per.values()))
    unhandled = sorted({r['class'] for r in rows if r.get('status') == 'no handler'})
    return {
        'cfg': cfg,
        'bones_written': len(per),
        'exact_lt_0.1mm_0.1deg': int(((a[:, 0] < 0.1) & (a[:, 1] < 0.1)).sum()),
        'pos_mm': {'median': float(np.median(a[:, 0])), 'p90': float(np.percentile(a[:, 0], 90)), 'max': float(a[:, 0].max())},
        'rot_deg': {'median': float(np.median(a[:, 1])), 'p90': float(np.percentile(a[:, 1], 90)), 'max': float(a[:, 1].max())},
        'breast_rig_bones': {n: {'pos_mm': round(per[n][0], 3), 'rot_deg': round(per[n][1], 3)} for n in bones if n in per},
        'not_evaluated_classes': unhandled,
        'extender_problems': problems,
    }


def isolated(gd, rig, cfg):
    rows, _, _ = deform.rest_check(gd, rig, gd.post_order(2), cfg, isolated=True)
    by = collections.defaultdict(list)
    for r in rows:
        if 'pos_mm' in r and r['target'] != 'targets_weighted_average':
            by[r['class']].append((r['pos_mm'], r['rot_deg']))
    return {k: {'writes': len(v), 'exact': int(sum(p < 0.05 and q < 0.05 for p, q in v)),
                'pos_max_mm': round(max(p for p, _ in v), 3), 'rot_max_deg': round(max(q for _, q in v), 3)} for k, v in by.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entity', default=r'base\characters\entities\main_npc\judy.ent')
    ap.add_argument('--name', default='judy')
    a = ap.parse_args()
    src = Source()
    out_dir = os.path.join(WORK, 'pipeline_out', 'deformation')
    os.makedirs(out_dir, exist_ok=True)

    # component binding chain (which graph drives which rig, bound to which component)
    comps = []
    ent = R(src.get(a.entity)).chunk(0)
    info = A.character_components(src, a.entity)
    for path, ref in [(a.entity, ent['compiledData'])]:
        pk = A._package(src.get(path), ref)
        comps += _anim_components(pk)
    ar = R(src.get(info['appearanceResource']))
    for i, ch in enumerate(ar.meta['chunks']):
        if ch['class'] == 'appearanceAppearanceDefinition':
            dd = ar.chunk(i)
            if dd.get('name') == info.get('appearanceName', dd.get('name')):
                comps += _anim_components(A._package(src.get(info['appearanceResource']), dd['compiledData']))
                break

    gb = AnimGraph(src.get(DIR + 'woman_base_breasts.animgraph'))
    gd = AnimGraph(src.get(DIR + 'woman_base_deformations.animgraph'))
    rig_d = Rig(src.get(DIR + 'woman_base_deformations.rig'))
    rig_b = Rig(src.get(DIR + 'woman_base_breasts.rig'))
    dmd = rig_d.model_space('ref')
    bmd = rig_b.model_space('ref')
    rig_consistency = max(float(np.linalg.norm(bmd[i][:3, 3] - dmd[rig_d.index(n)][:3, 3]) * 1000) for i, n in enumerate(rig_b.names))

    dl = dangles(gb)
    order_d = gd.post_order(2)
    cone, need = dependency_cone(gd, order_d, rig_b.names)
    written_in_cone = set(t for h in cone for t in gd.targets(h))
    cone_inputs = sorted(n for n in need if n not in written_in_cone)

    rest = [rest_eval(gd, rig_d, rig_b.names, cfg) for cfg in (
        {}, {'orient.reverse': 1}, {'setbone.defaultMethod': 'TranslationOnly'}, {'spline.rule': 'through'},
        {'aimrot.worldUpAxis': [0, 0, 1]}, {'aimrot.worldUpAxis': [1, 0, 0]})]

    report = {
        'entity': a.entity,
        'animated_components': comps,
        'breast_rig_vs_deformation_rig_ref_max_mm': rig_consistency,
        'breasts_graph': graph_summary(gb),
        'breasts_live_chain': chain(gb),
        'dangle_systems': dl,
        'ellipsoids_at_rest': ellipsoid_rest(gb, [d for d in dl if d['live']]),
        'deformation_graph': graph_summary(gd),
        'deformation_graph_is_linear_chain': all(len(gd.links[h]) <= 1 for h in order_d),
        'breast_rig_dependency_cone': {'nodes': len(cone), 'by_class': dict(collections.Counter(gd.short(h) for h in cone)),
                                       'order': [f'{h} {gd.short(h)} -> {",".join(gd.targets(h)[:2])}' for h in cone],
                                       'inputs_not_written': cone_inputs},
        'decode_defaults': deform.DEFAULTS,
        'rest_sequential': rest,
        'rest_isolated_default_cfg': isolated(gd, rig_d, {}),
    }
    jp = os.path.join(out_dir, f'{a.name}_deformation.json')
    json.dump(report, open(jp, 'w'), indent=1, default=str)
    print('wrote', jp)
    r0 = rest[0]
    print('breasts graph: chunks', report['breasts_graph']['chunks'], 'live', report['breasts_graph']['live_nodes'],
          'dangles live', sum(d['live'] for d in dl), '/', len(dl))
    print('deformation graph: live', report['deformation_graph']['live_nodes'], 'cone for breast rig', len(cone))
    print('rest (default cfg): exact', r0['exact_lt_0.1mm_0.1deg'], '/', r0['bones_written'], 'pos', r0['pos_mm'], 'rot', r0['rot_deg'])
    for r in rest[1:]:
        print('   ', r['cfg'], 'exact', r['exact_lt_0.1mm_0.1deg'], 'pos p90 %.2f rot p90 %.2f' % (r['pos_mm']['p90'], r['rot_deg']['p90']))


def _anim_components(pk):
    out = []
    for i, c in enumerate(pk.classes):
        if c != 'entAnimatedComponent':
            continue
        f = pk.fields(i)
        cb = f.get('controlBinding', (0, None))[1]
        bind = pk.fields(cb['handle']).get('bindName', (0, None))[1] if isinstance(cb, dict) and 'handle' in cb else None
        out.append({'name': f['name'][1], 'rig': f.get('rig', (0, None))[1], 'graph': f.get('graph', (0, None))[1], 'controlBinding': bind})
    return out


if __name__ == '__main__':
    main()
