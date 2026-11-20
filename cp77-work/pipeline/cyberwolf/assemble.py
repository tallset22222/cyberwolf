"""Assemble a character from its entity (.ent) and appearance (.app) resources into one glTF file.

- Components come from the appearance definition's compiledData package (mesh, meshAppearance, binding).
- Each mesh component's skinning binding names an animated component; its rig comes from the appearance
  package or the base entity's package.
- Rigs are merged by bone name. Every bone shared between rigs, and every joint shared between meshes,
  is compared and the discrepancies are reported rather than assumed away.
- Each mesh keeps its own skin (its own inverse bind matrices) over the shared joint nodes.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R  # noqa: E402
from .package import Package  # noqa: E402
from .source import WORK  # noqa: E402
from .mesh import Mesh  # noqa: E402
from .rig import Rig  # noqa: E402
from .gltf import GltfBuilder, ROOT_ROTATION, FLOAT, mat_to_trs, add_materials, add_mesh_nodes  # noqa: E402

MESH_CLASSES = ('entSkinnedMeshComponent', 'entGarmentSkinnedMeshComponent', 'entMorphTargetSkinnedMeshComponent')


def _package(path, buffer_ref):
    return Package(open(f"{path}.buffer{buffer_ref['buffer'] - 1}", 'rb').read(), WORK)


def _components(pk):
    rigs, meshes = {}, []
    for i, c in enumerate(pk.classes):
        if c == 'entAnimatedComponent':
            f = pk.fields(i)
            if isinstance(f.get('rig', (0, None))[1], str):
                rigs[f['name'][1]] = f['rig'][1]
            if isinstance(f.get('facialSetup', (0, None))[1], str):
                rigs.setdefault('__facialSetup__', f['facialSetup'][1])
    for i, c in enumerate(pk.classes):
        if c in MESH_CLASSES:
            f = pk.fields(i)
            bind = None
            h = f.get('skinning', (0, None))[1]
            if isinstance(h, dict) and 'handle' in h and 0 <= h['handle'] < len(pk.classes):
                bind = pk.fields(h['handle']).get('bindName', (0, None))[1]
            cm = f.get('chunkMask', (0, None))[1]
            meshes.append({'name': f['name'][1], 'class': c, 'mesh': f.get('mesh', (0, None))[1],
                           'meshAppearance': f.get('meshAppearance', (0, None))[1],
                           'chunkMask': cm if isinstance(cm, int) else None, 'binding': bind})
    return rigs, meshes


def character_components(src, ent_path, appearance=None):
    er = R(src.get(ent_path))
    ent = er.chunk(0)
    ent_rigs, _ = _components(_package(src.get(ent_path), ent['compiledData']))
    apps = ent.get('appearances', [])
    want = appearance or ent.get('defaultAppearance')
    a = next((x for x in apps if x.get('name') == want), apps[0])
    app_path = a['appearanceResource']['ref']
    app_name = a.get('appearanceName', a.get('name'))
    ar = R(src.get(app_path))
    defs = [ar.chunk(i) for i, c in enumerate(ar.meta['chunks']) if c['class'] == 'appearanceAppearanceDefinition']
    d = next((x for x in defs if x.get('name') == app_name), None)
    if d is None:
        raise SystemExit(f'appearance {app_name!r} not in {app_path}; available: {[x.get("name") for x in defs]}')
    app_rigs, meshes = _components(_package(src.get(app_path), d['compiledData']))
    rigs = dict(ent_rigs)
    rigs.update(app_rigs)
    facial = rigs.pop('__facialSetup__', None)
    return {'entity': ent_path, 'entityAppearance': a.get('name'), 'appearanceResource': app_path,
            'appearance': app_name, 'rigs': rigs, 'meshes': meshes, 'facialSetup': facial}


def assemble(src, ent_path, out_path, appearance=None, materials=True, skip=('AppearanceProxyMesh',), log=print):
    info = character_components(src, ent_path, appearance)
    rep = {'entity': ent_path, 'appearance': info['appearance'], 'appearanceResource': info['appearanceResource'],
           'components': [], 'rigs': {}, 'skipped': []}
    # rigs: body ('root') first, then the others
    order = sorted(info['rigs'], key=lambda k: (k != 'root', k != 'deformations', k))
    rigs = {}
    for k in order:
        loc = src.get(info['rigs'][k])
        if loc:
            rigs[k] = Rig(loc)
            rep['rigs'][k] = {'path': info['rigs'][k], 'bones': len(rigs[k].names), 'aPose': rigs[k].apose_local is not None}
    parent_of, world, owner = {}, {}, {}
    for k in order:
        if k not in rigs:
            continue
        r = rigs[k]
        ms = r.model_space('apose' if r.apose_local else 'ref')
        shared = []
        for i, n in enumerate(r.names):
            if n in parent_of:
                shared.append(float(np.linalg.norm(ms[i][:3, 3] - world[n][:3, 3])))
                continue
            parent_of[n] = r.names[r.parents[i]] if r.parents[i] >= 0 else None
            world[n] = ms[i]
            owner[n] = k
        rep['rigs'][k]['sharedWithEarlierRigs'] = len(shared)
        rep['rigs'][k]['sharedBoneMaxOffset_mm'] = round(max(shared) * 1000, 4) if shared else None
    # meshes
    loaded = []
    for comp in info['meshes']:
        if comp['name'] in skip or not comp['mesh']:
            rep['skipped'].append(comp['name']); continue
        loc = src.get(comp['mesh'])
        if loc is None:
            rep['skipped'].append(comp['name'] + ' (mesh not found)'); continue
        loaded.append((comp, Mesh(loc)))
        log(f"  {comp['name']}: {comp['mesh'].split(chr(92))[-1]} -> {comp['binding']}")
    # Joint placement: each joint takes its bind pose from a mesh bound to the rig that OWNS the joint (e.g. face
    # joints from face-rig meshes). Meshes bound through another rig may carry a different bind for shared joints
    # (Judy: body and shared hair were bound against a generic face, ~5 mm off); in-game they are skinned to the
    # owning rig, so they show their real deviation instead of displacing the owning rig's meshes.
    # Fallback order when no owning-rig mesh has the joint: body-rig meshes first, then appearance order.
    loaded.sort(key=lambda cm: (cm[0]['binding'] != 'root', 't0_' not in cm[1].path))
    candidates = {}
    for comp, m in loaded:
        ibm = np.transpose(m.ibm_rowvec, (0, 2, 1))
        for k, n in enumerate(m.bone_names):
            candidates.setdefault(n, []).append((comp['binding'], comp['name'], np.linalg.inv(ibm[k])))
    bind_world, disagreement, source_of = {}, {}, {}
    for n, cands in candidates.items():
        own = owner.get(n)
        pick = next((c for c in cands if c[0] == own), cands[0])
        bind_world[n], source_of[n] = pick[2], pick[1]
        d = [float(np.linalg.norm(c[2][:3, 3] - pick[2][:3, 3])) for c in cands]
        if len(cands) > 1:
            disagreement[n] = max(d)
    rig_vs_bind = {n: float(np.linalg.norm(bind_world[n][:3, 3] - world[n][:3, 3])) for n in bind_world if n in world}
    unresolved = sorted(n for n in bind_world if n not in parent_of)
    for n in unresolved:
        parent_of[n] = None
    world.update(bind_world)
    # glTF
    b = GltfBuilder()
    root = b.add_node({'name': 'cyberwolf_root (Z-up to Y-up)', 'rotation': ROOT_ROTATION})
    needed = set()
    for n in bind_world:
        while n is not None and n not in needed:
            needed.add(n)
            n = parent_of[n]
    skel = b.add_node({'name': 'skeleton', 'extras': {'pose': 'bind'}}, parent=root)
    node_of = {}

    def visit(n):
        if n in node_of:
            return
        p = parent_of[n]
        if p is not None:
            visit(p)
        local = np.linalg.inv(world[p] if p is not None else np.eye(4)) @ world[n]
        t, q, s = mat_to_trs(local)
        nd = {'name': n, 'translation': [float(x) for x in t], 'rotation': [float(x) for x in q],
              'extras': {'rig': owner.get(n, 'mesh-only')}}
        if np.abs(s - 1).max() > 1e-6:
            nd['scale'] = [float(x) for x in s]
        node_of[n] = b.add_node(nd, parent=node_of[p] if p is not None else skel)
    for n in sorted(needed):
        visit(n)
    b.doc['skins'] = []
    if materials:
        from .material import mesh_materials, gltf_spec
    for comp, m in loaded:
        joints = [node_of[n] for n in m.bone_names]
        acc = b.add_accessor(m.ibm_rowvec.astype(np.float32).reshape(len(m.bone_names), 16), FLOAT)
        b.doc['skins'].append({'name': comp['name'], 'joints': joints, 'inverseBindMatrices': acc, 'skeleton': skel})
        mat_index, chunk_mats, mats_rep = {}, None, {}
        if materials:
            slots, apps = mesh_materials(m.path, src)
            app = next((x for x in apps if x['name'] == comp['meshAppearance']), None) or next((x for x in apps if x['name'] == 'default'), apps[0] if apps else None)
            chunk_mats = app['chunkMaterials'] if app else None
            used = [n for n in slots if n in set(chunk_mats or [])]
            specs = [gltf_spec(f"{comp['name']}:{n}", slots[n], src) for n in used]
            for n, i in zip(used, add_materials(b, specs)):
                mat_index[n] = i
            mats_rep = {s_['name']: s_['approximation'] for s_ in specs}
        crep = {'lods': {}, 'skinStats': []}
        mask = comp['chunkMask']
        if mask is not None and mask != (1 << 64) - 1:
            keep = [c for c in m.chunks if mask >> c.index & 1]
            crep['chunkMaskHidden'] = [c.index for c in m.chunks if c not in keep]
            m.chunks = keep
        add_mesh_nodes(b, m, root, (0,), comp['name'], len(b.doc['skins']) - 1, mat_index, chunk_mats, crep, True)
        rep['components'].append({'name': comp['name'], 'mesh': comp['mesh'], 'binding': comp['binding'],
                                  'meshAppearance': (app['name'] if materials and app else comp['meshAppearance']),
                                  'bones': len(m.bone_names), 'lod0': crep['lods'].get('LOD0'),
                                  'chunkMaskHidden': crep.get('chunkMaskHidden'), 'materials': mats_rep})
    rep['skeleton'] = {'jointNodes': len(node_of), 'meshOnlyBones': unresolved,
                       'jointsSharedByMeshes': len(disagreement),
                       'jointPlacementRule': 'bind pose from a mesh bound to the owning rig; else body meshes, then appearance order',
                       'meshBindDisagreementMax_mm': round(max(disagreement.values()) * 1000, 4) if disagreement else None,
                       'worstMeshBindDisagreements_mm': {k: round(v * 1000, 3) for k, v in sorted(disagreement.items(), key=lambda x: -x[1])[:5]},
                       'bindVsRigPoseMax_mm': round(max(rig_vs_bind.values()) * 1000, 4) if rig_vs_bind else None,
                       'worstBindVsRigPose_mm': {k: round(v * 1000, 3) for k, v in sorted(rig_vs_bind.items(), key=lambda x: -x[1])[:5]}}
    rep['bytes'] = b.write(out_path)
    rep['output'] = out_path
    return rep
