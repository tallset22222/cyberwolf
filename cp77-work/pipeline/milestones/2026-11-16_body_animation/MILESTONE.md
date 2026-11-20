# Milestone 2026-11-16: assembled characters with body animation

State of the Cyberwolf pipeline at this point (all from the original archives, read-only):

- RDAR reader + Kraken backend; 120/120 provenance records re-extracted byte-identical.
- Mesh, rig, skin decode; glTF export (Z-up right-handed source -> Y-up; clockwise -> CCW; tangent w negated).
- BCn textures (BC1/4/5/7), material chains (local + external), skin/decal/metal_base/hair/eye/multilayer approximations.
- Character assembly from .ent/.app packages: Jackie (man_big), Judy (woman_base), citizen__corporat_ma (man_base).
- Body animation: animAnimationBufferCompressed and animAnimationBufferSimd -> glTF animation channels.

Tests and baselines frozen here:
- tests/test_regression.py  (8 geometry/material cases)  -> regression_baseline.json
- tests/test_anim_regression.py (21 clips)               -> anim_baseline.json

Known open items: NPC jacket multilayer appearance unverified; eyelash/hair-shadow/dangling material slots;
facial animation; dangle rigs; animation events and float tracks not exported.
