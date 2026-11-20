#!/usr/bin/env python3
"""Cyberwolf research pipeline: archive -> CR2W -> mesh/rig decode -> glTF -> validation.

Two input modes:
  --extracted <mesh>            use a mesh already extracted to disk (with .bufferN files beside it)
  --archive-dir <dir> --path <depot path> --kraken <libkraken.so>
                                read the mesh straight from the game's archives (read-only),
                                writing the resource into the workspace cache first

Usage examples:
  python3 -I run_pipeline.py --extracted ../extract/raw/.../t0_001_mb_body__jackie_welles.mesh \
      --rig ../extract/raw/.../man_big.rig --rig ../extract/raw/.../man_big_deformations.rig --all-lods
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cyberwolf import rdar                       # noqa: E402
from cyberwolf.mesh import Mesh                  # noqa: E402
from cyberwolf.rig import Rig                    # noqa: E402
from cyberwolf.gltf import export_mesh           # noqa: E402
from cyberwolf.validate import validate          # noqa: E402

WORK = os.path.normpath(os.path.join(HERE, '..'))
CACHE = os.path.join(WORK, 'pipeline_cache')
OUT = os.path.join(WORK, 'pipeline_out')


def fetch(archive_dir, depot_path, backend):
    """Locate a resource in the archives and write it (plus buffers) into the cache. Archives are opened read-only."""
    archives = sorted(a for d in archive_dir for a in glob.glob(os.path.join(d, '*.archive')))
    hit = rdar.locate(archives, depot_path, backend)
    if hit is None:
        raise SystemExit(f'not found in {len(archives)} archives: {depot_path}')
    arch, cr2w, bufs = hit
    dst = os.path.join(CACHE, depot_path.replace('\\', '/'))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(cr2w)
    for i, b in enumerate(bufs):
        open(f'{dst}.buffer{i}', 'wb').write(b)
    print(f'  located in {os.path.basename(arch)}: {len(cr2w)} bytes + {len(bufs)} buffers')
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted')
    ap.add_argument('--archive-dir', action='append', default=[], help='repeatable, e.g. archive/pc/content and archive/pc/ep1')
    ap.add_argument('--path')
    ap.add_argument('--kraken')
    ap.add_argument('--rig', action='append', default=[], help='extracted rig file (or depot path in archive mode)')
    ap.add_argument('--all-lods', action='store_true')
    ap.add_argument('--materials', action='store_true', help='resolve material chains and embed textures (needs archive access)')
    ap.add_argument('--appearance', default='default')
    ap.add_argument('--pose', choices=['bind', 'rig', 'ref'], default='bind',
                    help='bind: mesh bind pose; rig: rig A-pose (or reference pose if none); ref: rig reference pose')
    ap.add_argument('--reference', default=os.path.join(WORK, 'docs', 'mesh_geometry.json'))
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    if a.extracted:
        mesh_path, rig_paths = a.extracted, a.rig
    else:
        kraken = a.kraken or os.path.expanduser('~/lib/libkraken.so')
        backend = rdar.KrakenBackend(kraken) if os.path.exists(kraken) else None
        mesh_path = fetch(a.archive_dir, a.path, backend)
        rig_paths = [fetch(a.archive_dir, r, backend) for r in a.rig]

    mesh = Mesh(mesh_path)
    rigs = [Rig(p) for p in rig_paths]
    lods = mesh.lods if a.all_lods else [0]
    stem = os.path.basename(mesh_path).rsplit('.', 1)[0]
    stem += '' if a.pose == 'bind' else f'.{a.pose}pose'
    out = os.path.join(OUT, stem + '.glb')
    mats = chunk_mats = None
    if a.materials:
        from cyberwolf.source import Source
        from cyberwolf.material import mesh_materials, gltf_spec
        src = Source(a.archive_dir or None, a.kraken or os.path.expanduser('~/lib/libkraken.so'))
        slots, apps = mesh_materials(mesh_path, src)
        app = next((x for x in apps if x['name'] == a.appearance), apps[0] if apps else None)
        chunk_mats = app['chunkMaterials'] if app else None
        used = set(chunk_mats or [])
        mats = {n: gltf_spec(n, s, src) for n, s in slots.items() if n in used}
        stem += f'.{app["name"]}' if app else ''
        out = os.path.join(OUT, stem + '.glb')
    exp = export_mesh(mesh, out, rigs, lods, pose=a.pose, materials=mats, chunk_materials=chunk_mats)
    if mats:
        exp['materials'] = {n: {'shader': m['shader'], 'approximation': m['approximation'],
                                'textures': [k for k in ('baseColor', 'normal', 'metallicRoughness') if m.get(k)],
                                'bake': m.get('bakeReport')}
                            for n, m in mats.items()}

    ref = None
    if os.path.exists(a.reference):
        for r in json.load(open(a.reference)):
            if os.path.basename(r['file']) == os.path.basename(mesh_path):
                ref = r
    val = validate(out, ref)
    report = {'export': exp, 'validation': val,
              'rigs': [{'file': r.path, 'bones': len(r.names), 'tailConsumed': r.tail_consumed,
                        'hasAPose': r.apose_local is not None} for r in rigs]}
    rp = os.path.join(OUT, stem + '.report.json')
    json.dump(report, open(rp, 'w'), indent=1, default=str)
    print(json.dumps({'output': out, 'bytes': exp['bytes'], 'materials': exp.get('materials'), 'lods': val['lods'], 'checks': val['checks'],
                      'skeleton': exp.get('skeleton'), 'skinStats': exp['skinStats'][:3]}, indent=1, default=str))


if __name__ == '__main__':
    main()
