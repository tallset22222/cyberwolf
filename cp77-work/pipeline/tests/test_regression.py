#!/usr/bin/env python3
"""Regression guard. Re-runs the pipeline from the game archives and compares content fingerprints of the
exports against tests/regression_baseline.json:
  - geometry/skin: SHA-256 of every vertex attribute, index and inverse-bind accessor, plus joint transforms
  - Jackie's resolved materials: SHA-256 of embedded skin and tattoo textures
  - validation checks (counts, bounds, skinning error, orientation)
Multilayer bakes are deliberately excluded: they are approximations expected to change.
Usage: test_regression.py [--update]"""
import hashlib, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.join(HERE, '..')
sys.path.insert(0, PIPE)
from cyberwolf.validate import read_glb
OUT = os.path.normpath(os.path.join(PIPE, '..', 'pipeline_out'))
G = os.path.expanduser('~/mnt/pc')
C = 'base\\characters'
RIGS_J = ['--rig', C + '\\base_entities\\man_big\\man_big.rig', '--rig', C + '\\base_entities\\man_big\\deformations_rigs\\man_big_deformations.rig']
RIGS_M = ['--rig', C + '\\cyberware\\player\\a0_003__mantisblade\\a0_003_wa__mantisblade_skeleton.rig'] + RIGS_J
CASES = {
    'jackie_body': (['--path', C + '\\main_npc\\jackie_welles\\t0_001_mb_body__jackie_welles.mesh', '--all-lods'] + RIGS_J, 't0_001_mb_body__jackie_welles.glb'),
    'jackie_body_materials': (['--path', C + '\\main_npc\\jackie_welles\\t0_001_mb_body__jackie_welles.mesh', '--materials'] + RIGS_J, 't0_001_mb_body__jackie_welles.default.glb'),
    'mantis_arm': (['--path', C + '\\cyberware\\player\\a0_003__mantisblade\\a0_003_wa__mantisblade_left_arm.mesh'] + RIGS_M, 'a0_003_wa__mantisblade_left_arm.glb'),
    'vending_machine': (['--path', 'base\\environment\\architecture\\common\\shop\\shop_vending_machine_b_w300_h400_aa.mesh', '--all-lods'], 'shop_vending_machine_b_w300_h400_aa.glb'),
    'jackie_assembled': (('character', 'base\\characters\\entities\\main_npc\\jackie_welles.ent'), 'characters/jackie_welles.geometry.glb'),
    'judy_assembled': (('character', 'base\\characters\\entities\\main_npc\\judy.ent'), 'characters/judy.geometry.glb'),
    'npc_corporat_ma_assembled': (('character', 'base\\characters\\entities\\citizen\\citizen__corporat_ma.ent'), 'characters/citizen__corporat_ma.geometry.glb'),
    'building3': (['--path', 'base\\environment\\architecture\\_temp\\rancho_coronado_buildings\\rancho_coroonado_building3.mesh', '--all-lods'], 'rancho_coroonado_building3.glb'),
}


def fingerprint(glb, checks, with_materials):
    doc, b = read_glb(glb)

    def acc_hash(i):
        a = doc['accessors'][i]; v = doc['bufferViews'][a['bufferView']]
        return hashlib.sha256(b[v['byteOffset']:v['byteOffset'] + v['byteLength']]).hexdigest()[:16]
    fp = {'meshes': {}, 'checks': checks}
    for m in doc['meshes']:
        fp['meshes'][m['name']] = [{k: acc_hash(i) for k, i in sorted(p['attributes'].items())} | {'indices': acc_hash(p['indices'])} for p in m['primitives']]
    for si, s in enumerate(doc.get('skins', [])):
        sfx = '' if si == 0 else f'_{si}'
        fp['ibm' + sfx] = acc_hash(s['inverseBindMatrices'])
        fp['joints' + sfx] = hashlib.sha256(json.dumps([[doc['nodes'][j]['name'], [round(x, 6) for x in doc['nodes'][j].get('translation', [])],
                                                   [round(x, 6) for x in doc['nodes'][j].get('rotation', [])]] for j in s['joints']]).encode()).hexdigest()[:16]
    if with_materials:
        fp['materials'] = {}
        for m in doc.get('materials', []):
            imgs = {}
            for key, t in (('baseColor', m['pbrMetallicRoughness'].get('baseColorTexture')), ('metallicRoughness', m['pbrMetallicRoughness'].get('metallicRoughnessTexture')), ('normal', m.get('normalTexture'))):
                if t:
                    v = doc['bufferViews'][doc['images'][doc['textures'][t['index']]['source']]['bufferView']]
                    imgs[key] = hashlib.sha256(b[v['byteOffset']:v['byteOffset'] + v['byteLength']]).hexdigest()[:16]
            fp['materials'][m['name']] = {'shader': m['extras']['shader'], 'factor': m['pbrMetallicRoughness'].get('baseColorFactor'), 'alphaMode': m.get('alphaMode'), 'images': imgs}
    return fp


def main():
    update = '--update' in sys.argv
    current = {}
    for name, (args, out) in CASES.items():
        if isinstance(args, tuple):      # character assembly (geometry + skins; materials excluded as approximations)
            cmd = [sys.executable, '-I', os.path.join(PIPE, 'assemble_character.py'), args[1], '--no-materials']
        else:
            cmd = [sys.executable, '-I', os.path.join(PIPE, 'run_pipeline.py'), '--archive-dir', G + '/content', '--archive-dir', G + '/ep1'] + args
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode:
            print(name, 'FAILED TO RUN\n', res.stderr[-2000:]); sys.exit(2)
        js = json.loads(res.stdout[res.stdout.index('\n{') + 1:] if not res.stdout.startswith('{') else res.stdout)
        current[name] = fingerprint(os.path.join(OUT, out), js['checks'], 'materials' in name)
    bp = os.path.join(HERE, 'regression_baseline.json')
    if update or not os.path.exists(bp):
        json.dump(current, open(bp, 'w'), indent=1)
        print('baseline written:', ', '.join(current)); return
    base = json.load(open(bp))
    failed = []
    for name in CASES:
        for key in sorted(set(base[name]) | set(current[name])):
            if base[name].get(key) != current[name].get(key):
                failed.append((name, key))
    for name in CASES:
        print(f"{name:24s} {'PASS' if not any(f[0] == name for f in failed) else 'FAIL ' + str([k for n, k in failed if n == name])}")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
