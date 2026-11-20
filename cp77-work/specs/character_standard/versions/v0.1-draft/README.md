# Cyberwolf character standard v0.1 (draft for review)

| part | file | what it fixes |
|---|---|---|
| 1 | `01_skeleton.md`, `skeleton.json`, `skeleton_overview.png` | joints, layers, naming, rest pose, full-borg profiles |
| 2 | `02_attachment_standard.md` | implant kinds, seam rings, sockets, validation, budgets |
| 3 | `03_body_hiding_map.md`, `hiding_regions.json`, `hiding_map.png` | body regions and hide masks |
| 4 | `04_base_mesh_makehuman.md` | base-mesh source: licence verified, topology still to verify |

`build_spec.py` generates the JSON (with structural checks: unique names, parents first, sockets are leaves, left/right
mirror symmetry); `diagrams.py` and `write_docs.py` generate the drawings and tables from it. Edit `build_spec.py`,
never the JSON or tables by hand.

**Status:**
- **Joint positions:** a 1.75 m reference proportion, not yet fitted to a real body. They'll be refitted to the base
  mesh once it's chosen; names, hierarchy, seams and regions are what this review should settle.
- **Military leg:** waits for review sign-off and the base-mesh topology test.

## Base-body validation plan (agreed 17 Nov 2026)

**Next milestone: a validated Cyberwolf base body.** The military leg follows only after it passes.

**Source.** The MakeHuman 1.x default body, exported on the owner's PC from the official application. The untouched
export is kept as the reference master, with its SHA-256 recorded and never edited. All cleanup, topology changes,
seam adjustments and rigging happen on working copies.

**Three independent tests,** each with its own report, so a failure points to its own cause:

1. **Topology and seam compatibility.** Do the mesh's edge loops support the seam rings and torso cuts?
2. **Skeleton fitting and deformation.** Do the shoulders, elbows, hips and knees deform acceptably through a
   standard range of motion?
3. **Region separation and hiding.** Can the 33 regions be split without gaps or intersections, at rest and posed?
   The 15 mm cuff rule is measured here, per seam, against actual deformation.

**The standard is revisable.** If the mesh suggests better boundaries than the 23 seams or the 33 regions, the
standard changes (version bump) before any implant is produced against it.

## Compatibility and versioning policy (agreed 17 Nov 2026)

The standard must grow without breaking existing assets. From **v1.0**, these identifiers are contract:

- joint names and hierarchy, and each joint's frame convention (local +Y along the bone, X = flexion axis);
- socket names, positions and orientation frames;
- global conventions: units (metres), axes (+Y up, +Z forward, +X character-left) and the A-pose rest pose;
- seam-ring codes and positions;
- hide-region bit numbers.

**Additive changes (minor version, e.g. 1.0 → 1.1):**
- new joints, sockets or seams;
- new region bits taken from the reserved range;
- new proportion profiles.

Existing implants keep working unchanged.

**Breaking changes (major version, e.g. 1.x → 2.0):**
- renaming, removing or re-parenting a contract identifier;
- changing a joint or socket frame, the units, the axes or the rest pose (a correctly named socket with a changed
  frame still mis-attaches every implant);
- moving a seam;
- reusing or renumbering a bit.

A breaking change requires:
1. a written migration table (old → new);
2. a converter that upgrades existing assets automatically;
3. validation of every library asset against the new version before release.

**Version tagging.** Every asset records the standard version it was built and validated against (`standard_version`
in its manifest). The validator refuses assets that declare a newer major version than it supports.

**Before v1.0** (the current 0.x drafts), identifiers may still change freely. Any change is logged here with its reason.
