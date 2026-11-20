#!/usr/bin/env python3
"""Assemble a character (entity + appearance) from the game archives into one .glb, then validate it.
Example: python3 -I assemble_character.py base\\characters\\entities\\main_npc\\jackie_welles.ent [--appearance NAME] [--no-materials]"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cyberwolf.source import Source, WORK
from cyberwolf.assemble import assemble, character_components
from cyberwolf.validate import validate

ap = argparse.ArgumentParser()
ap.add_argument('entity')
ap.add_argument('--appearance')
ap.add_argument('--no-materials', action='store_true')
ap.add_argument('--list', action='store_true', help='only list components')
a = ap.parse_args()
src = Source()
if a.list:
    print(json.dumps(character_components(src, a.entity, a.appearance), indent=1)); sys.exit()
out_dir = os.path.join(WORK, 'pipeline_out', 'characters'); os.makedirs(out_dir, exist_ok=True)
stem = a.entity.split('\\')[-1].rsplit('.', 1)[0] + (f'.{a.appearance}' if a.appearance else '')
if a.no_materials:
    stem += '.geometry'
out = os.path.join(out_dir, stem + '.glb')
rep = assemble(src, a.entity, out, a.appearance, not a.no_materials)
val = validate(out)
rep['validation'] = val
json.dump(rep, open(out[:-4] + '.report.json', 'w'), indent=1, default=str)
print(json.dumps({'output': out, 'bytes': rep['bytes'], 'appearance': rep['appearance'], 'rigs': rep['rigs'],
                  'skeleton': rep['skeleton'], 'skipped': rep['skipped'], 'checks': val['checks'],
                  'perMeshBindError_mm': val.get('bindPoseSkinningMaxError_mm_perMesh')}, indent=1, default=str))
