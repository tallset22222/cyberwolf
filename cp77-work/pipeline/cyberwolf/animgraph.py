"""Generic .animgraph reader: nodes, their pose inputs and data references, and evaluation order.

Pose links are stored as {'node': {'handle': h}} (another node producing a pose or value);
data references are bare {'handle': h} (source channels, dyng constraints, conditions, expressions).
No node semantics are assumed here; this only reconstructs structure.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402

TARGET_KEYS = ('transformIndex', 'constrainedTransform', 'outTargetBone')


def _refs(v, path, links, data):
    if isinstance(v, dict):
        if set(v) == {'node'} and isinstance(v['node'], dict) and 'handle' in v['node']:
            links.append((path, v['node']['handle']))
            return
        if set(v) == {'handle'}:
            data.append((path, v['handle']))
            return
        for k, w in v.items():
            _refs(w, path + (k,), links, data)
    elif isinstance(v, list):
        for i, w in enumerate(v):
            _refs(w, path + (i,), links, data)


class AnimGraph:
    def __init__(self, path):
        r = R(path)
        self.cls = [c['class'] for c in r.meta['chunks']]
        self.x = [r.chunk(i) for i in range(len(self.cls))]
        self.links, self.data = [], []
        for x in self.x:
            l, d = [], []
            _refs(x, (), l, d)
            self.links.append(l)
            self.data.append(d)
        self.root = self.x[0]['rootNode']['handle']

    def short(self, h):
        return self.cls[h].replace('animAnimNodeSourceChannel_', 'Src.').replace('animAnimNode_', '').replace('animDyng', 'Dyng.')

    def targets(self, h):
        """Bones a node writes (its declared output transforms)."""
        x, c, out = self.x[h], self.cls[h], []
        for k in TARGET_KEYS:
            if k in x and 'name' in x[k] and not c.startswith('animAnimNodeSourceChannel'):
                out.append(x[k]['name'])
        for o in x.get('transformOutputs', []) + x.get('outputs', []):
            for k in ('targetTransform', 'twistedTransform'):
                if k in o:
                    out.append(o[k]['name'])
        for e in x.get('entries', []):
            if 'transformToChange' in e:
                out.append(e['transformToChange']['name'])
        if c == 'animAnimNode_Dangle':
            sim = self.x[x['dangleConstraint']['handle']]
            out += [p['bone']['name'] for p in sim['particlesContainer']['particles']]
        return out

    def post_order(self, start):
        """Evaluation order: every pose/value input before the node that consumes it (iterative DFS)."""
        order, state, stack = [], {}, [(start, False)]
        while stack:
            h, done = stack.pop()
            if done:
                order.append(h)
                continue
            if state.get(h):
                continue
            state[h] = 1
            stack.append((h, True))
            for _, c in reversed(self.links[h]):
                if not state.get(c):
                    stack.append((c, False))
        return order


READ_KEYS = ('startTransform', 'endTransform', 'middleTransform', 'targetTransform', 'upTransform', 'sourceBone',
             'offsetSpaceBone', 'parentTransform', 'transformA', 'transformB', 'inputTransformIndex', 'parentTransformIndex',
             'sourceTransform')


def reads(g, h):
    """Transforms a node reads (by name), including through its source channels."""
    out = set()

    def walk(v, key=None):
        if isinstance(v, dict):
            if key in READ_KEYS and 'name' in v:
                out.add(v['name'])
            for k, w in v.items():
                walk(w, k)
        elif isinstance(v, list):
            for w in v:
                walk(w, key)
    x = g.x[h]
    walk({k: v for k, v in x.items() if k not in ('inputLink', 'visMask')})
    for e in x.get('inputWeightedTransforms', []):
        out.add(e['transform']['name'])
    for _, c in g.data[h]:
        stack = [c]
        while stack:
            d = stack.pop()
            for k in ('transformIndex', 'inputTransformIndex'):
                if k in g.x[d] and g.cls[d].startswith('animAnimNodeSourceChannel'):
                    out.add(g.x[d][k]['name'])
            stack += [cc for _, cc in g.data[d]]
    if g.cls[h] == 'animAnimNode_TranslationLimit' or g.cls[h] == 'animAnimNode_SimpleBounce':
        out |= set(g.targets(h))  # read-modify-write of the target's other channels
    return out


def dependency_cone(g, order, bones):
    """Nodes in `order` whose output can reach `bones` through read-after-write chains (sequence semantics)."""
    need, cone = set(bones), []
    for h in reversed(order):
        w = set(g.targets(h))
        if w & need:
            cone.append(h)
            need |= reads(g, h)
    return list(reversed(cone)), need
