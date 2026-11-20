#!/usr/bin/env python3
"""Decide the normal-map green-channel convention from the data.
(1) Map convention: a height-derived normal map is curl-free in its own convention. With x right / y down image axes,
    'green = up' (OpenGL) maps satisfy dnx/dy + dny/dx ~ 0; 'green = down' (DirectX) maps satisfy dnx/dy - dny/dx ~ 0.
(2) Mesh frame: sign of B = cross(N, T) * w along dP/dv on the exported triangles (+1: B points to increasing v).
glTF applies green along B, so the export is correct when the map's green direction equals B's direction."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from cyberwolf.source import Source
from cyberwolf.texture import Texture
from cyberwolf.mesh import Mesh

def map_convention(a):
    n = a[..., :2].astype(np.float64) / 255 * 2 - 1
    nx, ny = n[..., 0], n[..., 1]
    nx_y = np.diff(nx, axis=0)[:, :-1]; ny_x = np.diff(ny, axis=1)[:-1, :]
    e_gl = float(np.mean((nx_y + ny_x) ** 2)); e_dx = float(np.mean((nx_y - ny_x) ** 2))
    return ('green=+v (DirectX)' if e_dx < e_gl else 'green=-v (OpenGL)'), round(max(e_gl, e_dx) / max(min(e_gl, e_dx), 1e-12), 2)

def mesh_b_sign(m):
    pos = neg = 0
    for c in m.lod_chunks(0):
        if c.tangent is None or c.uv0 is None: continue
        I = c.indices.reshape(-1, 3); P = c.position; uv = c.uv0.astype(np.float64)
        e1, e2 = P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]]
        d1, d2 = uv[I[:, 1]] - uv[I[:, 0]], uv[I[:, 2]] - uv[I[:, 0]]
        det = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]; ok = np.abs(det) > 1e-12
        dpdv = (e2 * d1[:, :1] - e1 * d2[:, :1]) / np.where(ok, det, 1)[:, None]
        a = I[:, 0]
        B = np.cross(c.normal[a], c.tangent[a]) * c.tangent_w[a][:, None]
        s = np.einsum('ij,ij->i', B, dpdv)[ok]
        pos += int((s > 0).sum()); neg += int((s < 0).sum())
    return pos, neg

src = Source()
maps = {'skin body n03 (BC5)': 'base\\characters\\common\\base_bodies\\man_average\\textures\\t0_000_ma__c_base_n03.xbm',
        'jacket GlobalNormal': 'base\\characters\\main_npc\\jackie_welles\\textures\\t2_001_full__jackie_welles_n01.xbm',
        'template steel normal': 'base\\surfaces\\materials\\metal\\steel_hq\\steel_hq_brushed_01_10_n.xbm',
        'template metal_generic_brushed': 'base\\surfaces\\materials\\metal\\metal_generic\\metal_generic_brushed_01_300_n.xbm',
        'garment decal normal': 'base\\characters\\common\\textures\\decals\\garment_decals_n01.xbm'}
print('map convention (curl test; ratio = how decisive):')
for k, p in maps.items():
    loc = src.get(p)
    if not loc: print('  ', k, 'not found'); continue
    t = Texture(loc); conv, ratio = map_convention(t.decode(0)); print(f'   {k:32s} {t.compression:16s} {conv:22s} x{ratio}')
print('mesh bitangent direction (B = cross(N,T)*w vs dP/dv):')
for k, p in {'jackie body': 'base\\characters\\main_npc\\jackie_welles\\t0_001_mb_body__jackie_welles.mesh',
             'jackie jacket': 'base\\characters\\main_npc\\jackie_welles\\t2_001_full__jackie_welles.mesh',
             'jackie head': 'base\\characters\\main_npc\\jackie_welles\\h0_001_mb_c__jackie_welles\\h0_001_mb_c__jackie_welles.mesh',
             'vending machine': 'base\\environment\\architecture\\common\\shop\\shop_vending_machine_b_w300_h400_aa.mesh'}.items():
    pos, neg = mesh_b_sign(Mesh(src.get(p))); print(f'   {k:16s} B toward +v: {pos/(pos+neg):.1%}   toward -v: {neg/(pos+neg):.1%}')
