"""Resolve mesh material slots through CMaterialInstance chains to a flat parameter set.

Child instances override parents; the chain ends at a .mt/.remt shader template, whose name is kept
(shader behaviour itself is not in the data; see docs/05 coverage).
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from cr2w_props import R            # noqa: E402
import material_decode              # noqa: E402


def instance(path):
    r = R(path)
    ci = [i for i, c in enumerate(r.meta['chunks']) if c['class'] == 'CMaterialInstance'][0]
    return material_decode.inst_params(r, ci)


def resolve_chain(start_info, src, max_depth=16):
    """start_info: {'baseMaterial', 'params'} of a local instance. Returns (params, chain, shader)."""
    params = {}
    chain = []
    info = start_info
    for _ in range(max_depth):
        for k, v in info.get('params', {}).items():
            params.setdefault(k, v)            # nearest definition wins
        base = info.get('baseMaterial')
        if not base:
            return params, chain, None
        chain.append(base)
        if not base.endswith('.mi'):
            return params, chain, base
        loc = src.get(base)
        if loc is None:
            return params, chain + ['(missing)'], None
        info = instance(loc)
    return params, chain, None


def mesh_materials(mesh_path, src):
    """Resolve every material slot of a mesh. Local slots index the mesh's local instances; external slots index
    CMesh.externalMaterials (a list of .mi paths). index / isLocalInstance are omitted at their defaults (0 / False)."""
    rep = material_decode.analyse(mesh_path)          # local instances + appearances (research decoder)
    cm = R(mesh_path).chunk(0)
    raw_entries = cm.get('materialEntries', [])
    external = [x.get('ref') if isinstance(x, dict) else None for x in (cm.get('externalMaterials') or [])]
    lmb = cm.get('localMaterialBuffer')
    if lmb:
        import struct as _st
        B = open(f"{mesh_path}.buffer{lmb['rawData']['buffer'] - 1}", 'rb').read()
        local = []
        for h in lmb['rawDataHeaders']:
            o = h.get('offset', 0)
            tmp = mesh_path + '.local_mi.cr2w'
            open(tmp, 'wb').write(B[o:o + h['size']])
            local.append(material_decode.inst_params(R(tmp), 0))
    else:
        r = R(mesh_path)
        local = [material_decode.inst_params(r, i) for i, c in enumerate(r.meta['chunks']) if c['class'] == 'CMaterialInstance']
    slots = {}
    for e in raw_entries:
        idx = e.get('index', 0)
        is_local = bool(e.get('isLocalInstance', False))
        if is_local:
            start = local[idx] if idx < len(local) else {'baseMaterial': None, 'params': {}}
        else:
            start = {'baseMaterial': external[idx] if idx < len(external) else None, 'params': {}}
        problem = None
        if is_local and idx >= len(local):
            problem = f'dangling local material reference (index {idx}, {len(local)} local instances)'
        elif not is_local and idx >= len(external):
            problem = f'dangling external material reference (index {idx}, {len(external)} external materials)'
        params, chain, shader = resolve_chain(start, src)
        slots[e['name']] = {'slot': idx, 'local': is_local, 'chain': chain, 'shader': shader, 'params': params, 'problem': problem}
    return slots, rep['appearances']


# ---- glTF material approximation (shader logic is not in the data; these are documented approximations) ----
import io as _io
import sys as _sys
import numpy as _np
from PIL import Image as _Image
from .texture import Texture as _Texture

_png_cache = {}
texture_errors = {}


def _tex(src, depot, transform=None):
    key = (depot, transform.__name__ if transform else None)
    if key not in _png_cache:
        loc = src.get(depot) if depot else None
        if loc is None:
            _png_cache[key] = None
        else:
            try:
                a = _Texture(loc).decode(0)
            except Exception as e:                      # unsupported format etc.: record, don't abort
                texture_errors[depot] = f'{type(e).__name__}: {e}'
                _png_cache[key] = None
                return None
            if transform:
                a = transform(a)
            buf = _io.BytesIO()
            _Image.fromarray(a).save(buf, 'PNG')
            _png_cache[key] = buf.getvalue()
    return _png_cache[key]


_png_by_id = {}


def _png(a):
    if id(a) in _png_by_id:
        return _png_by_id[id(a)][1]
    buf = _io.BytesIO()
    _Image.fromarray(a).save(buf, 'PNG')
    _png_by_id[id(a)] = (a, buf.getvalue())     # keep array alive so id stays unique
    return _png_by_id[id(a)][1]


def rm_to_gltf(a):
    """CDPR 'rm' map (inferred: R = roughness, G = metalness) -> glTF metallicRoughness (G = rough, B = metal)."""
    out = _np.zeros_like(a)
    out[..., 1] = a[..., 0]
    out[..., 2] = a[..., 1]
    out[..., 3] = 255
    return out


def _ref(p, k):
    v = p.get(k, {}).get('value')
    return v if isinstance(v, str) else None



def _arr(src, depot):
    """Decoded RGBA float array (0-1) of a texture, or None."""
    loc = src.get(depot) if depot else None
    if loc is None:
        return None
    try:
        return _Texture(loc).decode(0).astype(_np.float64) / 255
    except Exception as e:
        texture_errors[depot] = f'{type(e).__name__}: {e}'
        return None


def _resize(a, shape):
    if a.shape[:2] == shape:
        return a
    return _np.asarray(_Image.fromarray((_np.clip(a, 0, 1) * 255).astype(_np.uint8)).resize((shape[1], shape[0]), _Image.BILINEAR)).astype(_np.float64) / 255


def _u8(a):
    return _np.clip(_np.round(a * 255), 0, 255).astype(_np.uint8)


def _val(p, k, default=None):
    return p.get(k, {}).get('value', default)


def _gradient(entries):
    """Piecewise-linear colour ramp from [{'value', 'color'}] entries -> function(t)."""
    pts = sorted(((e.get('value', 0.0), [e['color'].get(c, 0) / 255 for c in ('Red', 'Green', 'Blue')]) for e in entries), key=lambda x: x[0])
    xs = _np.array([x for x, _ in pts]); cs = _np.array([c for _, c in pts])
    return lambda t: _np.stack([_np.interp(t, xs, cs[:, i]) for i in range(3)], -1)


def gltf_spec(name, slot, src):
    shader = (slot['shader'] or '').split('\\')[-1]
    p = slot['params']
    spec = {'name': name, 'shader': slot['shader'], 'chain': slot['chain'], 'approximation': None}
    if shader == 'skin.mt':
        spec.update(baseColor=_tex(src, _ref(p, 'Albedo')), normal=_tex(src, _ref(p, 'Normal')),
                    metallicRoughness=_tex(src, _ref(p, 'Roughness'), rm_to_gltf),
                    approximation='skin.mt -> PBR: Albedo, Normal, Roughness(R)/Metalness(G inferred); '
                                  'detail normals, tint mask and subsurface not represented')
    elif shader == 'mesh_decal.mt':
        c = p.get('DiffuseColor', {}).get('value') or {}
        spec.update(baseColor=_tex(src, _ref(p, 'DiffuseTexture')), alphaMode='BLEND',
                    baseColorFactor=[c.get('Red', 255) / 255, c.get('Green', 255) / 255, c.get('Blue', 255) / 255,
                                     float(p.get('DiffuseAlpha', {}).get('value', 1.0))],
                    roughnessFactor=1.0, metallicFactor=0.0,
                    approximation='mesh_decal.mt -> alpha-blended base colour; decal normal/roughness alphas not represented')
    elif shader == 'multilayered.mt' and _ref(p, 'MultilayerSetup'):
        from .multilayer import bake
        setup = src.get(_ref(p, 'MultilayerSetup'))
        mask = src.get(_ref(p, 'MultilayerMask')) if _ref(p, 'MultilayerMask') else None
        if setup is None:
            spec['approximation'] = 'multilayered.mt: setup not found in archives; placeholder'
        else:
            base, normal, mr, rep = bake(setup, mask, src)
            gn = _tex(src, _ref(p, 'GlobalNormal')) if _ref(p, 'GlobalNormal') else None
            spec.update(baseColor=_png(base), normal=gn or _png(normal), metallicRoughness=_png(mr), bakeReport=rep,
                        approximation='multilayered.mt baked to UV0: layers composited with mask*opacity; colour = '
                                      'template colour x colorScale; rough/metal = levelsOut remap; microblends omitted'
                                      + ('; normal = mesh GlobalNormal' if gn else '; normal = blended template normals')
                                      + ('' if mask else '; mask missing in archives, base layer only'))
    elif shader == 'metal_base.remt':
        sc = _val(p, 'BaseColorScale') or {}
        fac = [sc.get('X', 1.0), sc.get('Y', 1.0), sc.get('Z', 1.0), sc.get('W', 1.0)] if isinstance(sc, dict) else [1, 1, 1, 1]
        r_t, m_t = _arr(src, _ref(p, 'Roughness')), _arr(src, _ref(p, 'Metalness'))
        mr = None
        if r_t is not None or m_t is not None:
            shape = (r_t if r_t is not None else m_t).shape[:2]
            r = (_resize(r_t, shape)[..., 0] if r_t is not None else _np.full(shape, 0.5)) * float(_val(p, 'RoughnessScale', 1.0)) + float(_val(p, 'RoughnessBias', 0.0))
            m = (_resize(m_t, shape)[..., 0] if m_t is not None else _np.zeros(shape)) * float(_val(p, 'MetalnessScale', 1.0)) + float(_val(p, 'MetalnessBias', 0.0))
            z = _np.zeros(shape); mr = _png(_u8(_np.dstack([z, _np.clip(r, 0, 1), _np.clip(m, 0, 1), _np.ones(shape)])))
        spec.update(baseColor=_tex(src, _ref(p, 'BaseColor')), baseColorFactor=fac, normal=_tex(src, _ref(p, 'Normal')),
                    metallicRoughness=mr, metallicFactor=1.0 if mr else float(_val(p, 'MetalnessScale', 0.0)),
                    roughnessFactor=1.0 if mr else float(_val(p, 'RoughnessScale', 0.5)),
                    approximation='metal_base.remt -> PBR: BaseColor x BaseColorScale, Roughness/Metalness x scale + bias, Normal')
        ec, ev = _val(p, 'EmissiveColor') or {}, float(_val(p, 'EmissiveEV', 0.0) or 0.0)
        if ev > 0 and isinstance(ec, dict):
            spec['emissiveFactor'] = [ec.get('Red', 0) / 255, ec.get('Green', 0) / 255, ec.get('Blue', 0) / 255]
            spec['emissive'] = _tex(src, _ref(p, 'Emissive'))
            spec['approximation'] += f'; emissive colour (EV {ev:.1f} not representable, intensity clamped)'
        if _val(p, 'AlphaThreshold') is not None and spec.get('baseColor'):
            spec['alphaMode'], spec['alphaCutoff'] = 'MASK', float(_val(p, 'AlphaThreshold'))
    elif shader == 'hair.mt':
        grad_t, alpha_t = _arr(src, _ref(p, 'Strand_Gradient')), _arr(src, _ref(p, 'Strand_Alpha'))
        hp = src.get(_ref(p, 'HairProfile')) if _ref(p, 'HairProfile') else None
        if grad_t is not None and hp:
            from cr2w_props import R as _R
            prof = _R(hp).chunk(0)
            col = _gradient(prof.get('gradientEntriesRootToTip', []))(grad_t[..., 0])
            a = _resize(alpha_t, grad_t.shape[:2])[..., 0] if alpha_t is not None else _np.ones(grad_t.shape[:2])
            spec.update(baseColor=_png(_u8(_np.dstack([col, a]))), alphaMode='MASK', alphaCutoff=0.5, metallicFactor=0.0,
                        roughnessFactor=float(_val(p, 'RoughnessBias', 0.15)) + 0.35,
                        approximation='hair.mt -> strand gradient mapped through the hair profile root-to-tip colours, '
                                      'alpha-tested on Strand_Alpha; anisotropic hair shading not represented')
        else:
            spec['approximation'] = 'hair.mt: gradient or hair profile missing; placeholder'
    elif shader == 'eye.mt':
        spec.update(baseColor=_tex(src, _ref(p, 'Albedo')), metallicFactor=0.0, roughnessFactor=0.1,
                    approximation='eye.mt -> albedo only; refraction, iris depth and wetness not represented')
    elif shader == 'eye_shadow.mt':
        m = _arr(src, _ref(p, 'Mask'))
        c = _val(p, 'ShadowColor') or {}
        if m is not None:
            rgb = _np.ones(m.shape[:2] + (3,)) * _np.array([c.get('Red', 0), c.get('Green', 0), c.get('Blue', 0)]) / 255
            spec.update(baseColor=_png(_u8(_np.dstack([rgb, m[..., 0] * float(_val(p, 'Intensity', 1.0))]))), alphaMode='BLEND',
                        metallicFactor=0.0, roughnessFactor=0.3, approximation='eye_shadow.mt -> ShadowColor with Mask x Intensity as alpha')
    elif shader == 'mesh_decal_gradientmap_recolor.mt':
        d, gm, mk = _arr(src, _ref(p, 'DiffuseTexture')), _arr(src, _ref(p, 'GradientMap')), _arr(src, _ref(p, 'MaskTexture'))
        if d is not None and gm is not None:
            row = gm[gm.shape[0] // 2, :, :3]
            idx = _np.clip((d[..., 0] * (len(row) - 1)).astype(int), 0, len(row) - 1)
            a = (_resize(mk, d.shape[:2])[..., 0] if mk is not None else d[..., 3]) * float(_val(p, 'DiffuseAlpha', 1.0))
            spec.update(baseColor=_png(_u8(_np.dstack([row[idx], a]))), alphaMode='BLEND', metallicFactor=0.0, roughnessFactor=0.8,
                        approximation='gradient-map decal -> diffuse value looked up in GradientMap, MaskTexture as alpha')
    elif shader == 'mesh_decal_emissive.mt':
        c = _val(p, 'DiffuseColor') or {}
        col = [c.get('Red', 255) / 255, c.get('Green', 255) / 255, c.get('Blue', 255) / 255] if isinstance(c, dict) else [1, 1, 1]
        spec.update(baseColor=_tex(src, _ref(p, 'DiffuseTexture')), alphaMode='BLEND', metallicFactor=0.0, roughnessFactor=1.0,
                    baseColorFactor=col + [float(_val(p, 'DiffuseAlpha', 1.0))], emissiveFactor=col,
                    emissive=_tex(src, _ref(p, 'DiffuseTexture')),
                    approximation='mesh_decal_emissive.mt -> alpha-blended DiffuseTexture x DiffuseColor, also emissive (EV not representable)')
    elif shader in ('mesh_decal_double_diffuse.mt', 'mesh_decal_parallax.mt') and _ref(p, 'DiffuseTexture'):
        spec.update(baseColor=_tex(src, _ref(p, 'DiffuseTexture')), alphaMode='BLEND', metallicFactor=0.0, roughnessFactor=1.0,
                    baseColorFactor=[1, 1, 1, float(_val(p, 'DiffuseAlpha', 1.0))],
                    approximation=f'{shader} -> alpha-blended DiffuseTexture only')
    elif slot.get('problem'):
        spec['approximation'] = f"source data: {slot['problem']}; untextured placeholder (no substitute applied)"
    else:
        spec['approximation'] = f'{shader or "unknown"}: no PBR mapping yet; untextured placeholder'
    spec['params'] = {k: (v['value'] if isinstance(v['value'], (str, int, float)) else v['value']) for k, v in p.items()}
    return spec
