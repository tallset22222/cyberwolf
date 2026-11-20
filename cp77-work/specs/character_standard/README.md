# Cyberwolf character standard v0.2 (draft)

**v0.2 records the results of the three base-body validation tests.** It is not a freeze: every unresolved decision
is listed as an open item below. There is no v1.0, no further concept generation and no production implant work until
the base-body standard passes its remaining validation.

| part | file | what it fixes |
|---|---|---|
| 1 | `01_skeleton.md`, `skeleton.json`, `skeleton_overview.png` | joints, layers, naming, rest pose (open), deformation requirements |
| 2 | `02_attachment_standard.md` | implant kinds, cuff rules, per-seam status and overlap, sockets, validation, budgets |
| 3 | `03_body_hiding_map.md`, `hiding_regions.json`, `hiding_map.png` | 33 regions, hide masks, boundary types, topology migration |
| 4 | `04_base_mesh_makehuman.md` | base mesh: MakeHuman hm08, licence, validation status |
| data | `topology/hm08/seams.json`, `regions.json`, `boundaries.json` | the standard bound to hm08 vertex and face ids (mesh SHA-256 `8e761e66…`) |
| history | `versions/v0.1-draft/` | the complete v0.1 draft, frozen, with `SHA256SUMS` |

`build_spec.py` generates the JSON (with structural checks: unique names, parents first, sockets are leaves, left/right
mirror symmetry). `diagrams.py` and `write_docs.py` generate the drawings and the part 1–3 tables from it.
`basebody/export_topology_binding.py` generates `topology/hm08/`. Edit the generators, never the JSON or tables by hand.

Evidence: `basebody/reports/test1_topology.md`, `test2_deformation.md`, `test3_regions.md` (with their JSON and renders).

## v0.2 decisions (review of tests 1–3, 17 Nov 2026)

| area | decision |
|---|---|
| 33 hiding regions | **Retained as the validated baseline.** IDs and bits unchanged; all separate cleanly, with no body-to-body gaps at rest or posed |
| hand-drawn boundaries | **Explicit, versioned vertex lists** bound to the mesh checksum; a topology change requires explicit migration |
| ears | special treatment: the boundary is a placeholder until authored (no natural loop on hm08) |
| overlap | **Per seam** (15 mm for mid-limb, mid-neck and wrist; 20 mm for ankle, neck base and waist); provisional starting points |
| cuff attachment | **Skin-weighted is the preferred candidate** for deforming cuffs, not mandatory. Cuffs must both *follow* and *clear*; difficult joints need extra clearance handling |
| elbow / knee | **Move the seams off the crease and retest** |
| hip | **Option A remains a candidate.** The skin-weighted cuff passed (clearance ≥ +1.25 mm, both sides), unchanged by the symmetric-weight re-run; confirm after the helper-joint tests |
| shoulder | **Revisit after helper joints** (option A is not rejected) |
| skinning | **LBS vs DQS undecided**; compare with working helpers |
| rest pose | **50.4° candidate**, adopted consistently if accepted |
| face | **Separate required validation** before v1.0 |
| ribcage | **Horizontal ring vs V-shaped boundary undecided** |
| test condition | **Seam-motion and deformation tests run on both sides.** Mirroring is not validation |

## Changes from v0.1 (17 Nov 2026)

**Seams:**
- Seam positions are now the measured hm08 loops: `neck_base` 0.35 → 0.121 and `shin_mid` 0.50 → 0.582 (test 1).
  `shoulder` 0.00 → 0.305 and `hip` 0.00 → 0.254 (option A). The other seams were re-measured within ±0.06.
- Each seam gains `status`, `overlap_mm`, `cuff` (binding rules) and `evidence`, plus a reference to its hm08 loop.
- The global 15 mm overlap rule is withdrawn in favour of per-seam values.
- "Cuff weighted to the proximal joint" is withdrawn: it fails at the limb roots (159–168 mm slide). It is replaced
  by the follow/clear cuff rules.

**Hiding map:**
- Region IDs and bits are unchanged. Two boundary types are added (edge loop, drawn).
- The `bounded_by` descriptions were corrected to match the validated split:
  - back mid line → ribcage line;
  - gluteal folds → hip seams plus pelvis side lines;
  - the chest/back boundaries with the shoulder are now shoulder cap lines;
  - ear outline and nape line are added.
- The topology binding (`topology/hm08/`) is new.

**Skeleton:**
- The rest pose changes from a fixed 45° A-pose to open (candidate 50.4°). The joint names, hierarchy and
  reference positions are unchanged.

**New requirements:**
- left/right weight symmetry;
- both-sides deformation and seam tests;
- face validation before v1.0;
- helper joints required.

The complete v0.1 is preserved in `versions/v0.1-draft/`.

**v0.2 draft review corrections (17 Nov 2026):**
- The base-mesh provenance now states the real source (the MakeHuman 1.x source distribution, not an application export).
- Hip option A is consistently a *candidate*.
- The seam table names both cuff columns explicitly and gives the reason whenever a binding is not permitted. For
  example, the waist allows skin-weighted cuffs; only rigid cuffs are excluded there.
- The military leg is worded as the first *planned* production implant, with explicit eligibility conditions.

**Weight-symmetry fix (17 Nov 2026, resolves OI-08):**
- The v2 weight builder is mirror-exact, and tests 2 and 3 were re-run on both sides; left and right agree exactly.
- Evidence values changed only at `shoulder` (17.0 / 39.6 / −1.35 mm), `neck_mid` (12.0 / 3.9 / −0.32 mm) and
  `neck_base` (18.3 / 27.9 / 1.06 mm). Statuses, overlaps, regions and topology binding are unchanged.
- Test 2's report misstated the head-area metric exclusion (293 stated, 1,234 actual, including 18 vertices of real
  under-chin skin). It is corrected, and v2 uses an explicit 1,155-vertex cavity list (`basebody/face_cavities_hm08.json`).

## Open items register

| id | item | blocks |
|---|---|---|
| OI-01 | Per-seam overlap values are provisional; confirm after helpers and the skinning decision | production implants at those seams |
| OI-02 | Skin-weighted cuff: preferred, not mandatory. Decide where rigid cuffs stay permitted | attachment standard v1.0 |
| OI-03 | Elbow and knee seams: measure candidate positions off the flexion crease with the same motion test | forearm and lower-leg replacements |
| OI-04 | Shoulder option A: retest after helpers. Hip option A: candidate; the skin-weighted cuff passed both before and after OI-08; confirm after OI-05 | full-arm and full-leg replacements |
| OI-05 | Helper-joint drivers. Pass 1 (half-angle) fixes LBS volume only. Pass 2 (anatomical landmark helpers, two variants) **did not improve the targets and worsened the elbow and groin**: on the current automatic weights, local helpers fight wrongly weighted skin (`basebody/reports/helpers_pass2/helpers_pass2.md`). Proposed next: anatomical base weights (OI-16), then a helper pass on them | OI-03, OI-04, OI-06 |
| OI-06 | Skinning method: LBS+helpers vs DQS+helpers | OI-01, OI-10 |
| OI-07 | Rest pose: adopt hm08's 50.4° consistently, or not | the v1.0 contract |
| ~~OI-08~~ | **Resolved 17 Nov 2026.** Four defects in the weight builder were found and fixed (`test3_regions.md` §4b): an uncentred voxel grid, an order-dependent quad split, and tie-breaking by bone order on the midline and at shared joint ends. The v2 weights are mirror-exact, `check_weight_symmetry.py` is a gate, and tests 2 and 3 were re-run, with left and right now agreeing exactly | — |
| OI-09 | Face validation (jaw, lips, eyelids, expressions) with the face rig | v1.0 |
| OI-10 | Waist overlap: 20 mm set by review, but LBS measured 22.7 mm. Resolve with OI-06 | waist replacements |
| OI-11 | Topology migration: the procedure is defined (part 3) but not yet exercised | any base-mesh change |
| OI-12 | Ear boundary: author it by hand | `ears` region hiding |
| OI-13 | Ribcage line: horizontal ring vs costal V, compared for topology quality and bending/twisting behaviour | `chest` / `abdomen` hiding |
| OI-14 | Drawn boundaries: refine the rule-generated staircase paths by hand | visual quality of hidden edges |
| OI-16 | Automatic base weights had anatomical defects: thigh weight on the navel (up to 8 %), and left-clavicle weight on the right breast (up to 23 %) and on other opposite-side skin. **v3 accepted as the working weights (17 Nov 2026), not final.** It is selected with `CW_WEIGHTS=v3`; v2 stays the code default and fully reproducible. The accepted v3 consists of **two** smooth anatomical rules, laterality and the thigh boundary. **The olecranon rule was tried and rejected** (it is not part of v3), and the earlier olecranon defect claim was a measurement error. Results: pinch 2,224 → 1,263 mm, fold-overs 95 → 23, waist LBS overlap 22.7 → 16.2 mm. Open before final: the neck regression (OI-19) and the corrective shapes (OI-18). Report: `basebody/reports/weights_v3/weights_v3.md` | OI-05 |
| OI-17 | The skeleton has no scapula joint, so the shoulder girdle can't share its full anatomical motion (paced overhead still puts 113° in the shoulder joint) | shoulder deformation; review at v0.2 |
| OI-18 | Deep-flexion self-intersection. **Corrective shapes first; flexion limits only as a fallback; elbow and knee developed separately.** **Elbow** (`basebody/reports/correctives/elbow_corrective.md`): one 90° shape removes all skin-through-skin contact at 90° (LBS 62 → 0, DQS 47 → 0). **Decision (17 Nov 2026): contact at 110–145° is an accepted limitation**, with the crease cleaned, no hard animation limit and the volume bulge off. Revisit only if gameplay shows it. **Knee** (`.../knee_corrective.md`): keys at 90° and 135°; back-of-knee contact at 135° removed (LBS 116 → 0, DQS 58 → 0); knee-seam skin-weighted cuff now clears (+0.44 / +0.41 mm). Front-of-knee volume under LBS is restored only partly without a bump (0.41 → 0.42 at 135°), an LBS-only limitation. DQS front-of-knee stretch (1.57) is left as anatomical. Beyond 135° not covered | OI-03 |
| OI-19 | Influence limit. **Decision (17 Nov 2026): v3 stays at 4 influences as the working configuration; 8 is a separate experimental configuration** (`CW_INFLUENCES=8`). Evidence (`basebody/reports/weights_v3_k8/oi19_influence_limit.md`): shipped meshes use 8 at LOD0 and 4 at LOD1 and below. On v3, 8 removes the neck-turn regression and halves pinch, but has hip-flexion DQS, wrist and shoulder side-effects. **WolvenKit source** (`MeshImportTools.cs`): it reads `JOINTS_1`/`WEIGHTS_1`, remaps all 8 slots by bone name, and writes the second skin-index and skin-weight set. Each weight is rounded to a byte separately with **no renormalisation**, so sums can drift (8 × 0.125 → 256), and Cyberwolf exports must pre-quantise weights to exact n/255 summing to 255. **Import test prepared** (`tests_assets/infl8_import/`, isolated); it needs a WolvenKit run and an in-game check on the owner's PC. **Proposed architecture:** influence budget per mesh chunk and LOD: up to 8 for complex LOD0 areas (face, neck, hands, cybernetic assemblies), 4 for ordinary LOD0 areas, 4 for LOD1 and below. Adopting it amends part 2's "at most 4 influences" rule. **Export quantiser built** (`pipeline/cyberwolf/quantize.py`, validated in `basebody/reports/quantize_validation.json`): every byte valid, sums exactly 255, assignments kept, deterministic and side-agnostic tie-breaking. It round-trips WolvenKit's rounding exactly. Asymmetry occurs only on midline vertices where a left/right tie is unavoidable (255 is odd): 10 vertices at 4 influences, 19 at 8. Sub-byte weights (below 0.5/255, which WolvenKit would turn into 0) are pruned before quantising, keeping error at 1.5/255 or less (without pruning: up to 2.9/255 at 4 influences, 5.9/255 at 8). **Export record (approved default, 17 Nov 2026):** sub-byte pruning stays on. Each export writes the original float weights alongside the bytes (`.weights.npz`), plus a `.weights.json` listing every dropped assignment, the midline tie vertices and a bytes hash. The quantised bytes are never the only stored representation. **Determinism proven (17 Nov 2026, `basebody/reports/quantize_export/determinism/determinism_proof.json`):** three fresh processes per budget (4 and 8), each with a different hash seed and clock time, each rebuilding v3 from the master. Results: identical float weights, and byte-identical `.npz` and `.json` files. The `.npz` writer now uses a fixed zip timestamp, because numpy's default embeds the current time. Shuffling each vertex's influence slots gives the same bone-to-byte assignment, the same dropped list and the same midline list. **Float weights are the authoritative source; bytes are derived.** **Proposed regional LOD0 budget (17 Nov 2026, a proposal until the import test passes):** ordinary body regions 4; elbows 8; knees 8, pending the knee test; other complex regions 4–8, each validated individually; LOD1 and below 4. v3 stays at 4 as the general working baseline. **Import test is the gate before adopting 8**; the sentinel's 256 is a diagnostic, not a pass criterion | OI-16 |
| OI-20 | Engine delivery of correctives. REDengine's native correctives are **joint-based** (`animAnimNode_ApplyCorrectivePoseRBF`: RBF-chosen corrective joint poses; `animAnimNode_SetDrivenKey`). No animation-graph driver from joint angles to morph weights was found. Shapes are validated as targets, then converted to RBF corrective joints, with fidelity measured. **Elbow fitted offline (17 Nov 2026, `basebody/reports/correctives/oi20_elbow.md`):** with 6 corrective joints per arm and an influence budget of 8, LBS reproduces the 90° shape to 0.08 mm, and DQS to 2.1 mm. At a budget of 4, no configuration meets the criteria: either trimming changes other poses (up to 5 mm) or the crease intersects again. Elbow delivery therefore depends on OI-19. **Status: approved as an offline technical success, not as an engine-validated implementation.** Keep the two intermediate keys (50°, 70°), which halve activation error (1.01 → 0.50 mm). Further keys must each show a measurable gain without unwanted deformation between poses. LBS gives the closest elbow match; **DQS is not abandoned**, and the skinning method may differ per region until the full-body tests. **The accepted offline elbow shape stays the reference target and is not altered to suit the engine.** Next, in this order: WolvenKit 8-influence import test (owner's PC) → knee corrective joints → RBF interpolation and adding joints to the game rig → in-game comparison. Main remaining risk: whether REDengine's RBF node reproduces the offline deformation. **Knee fitted offline (17 Nov 2026, `basebody/reports/correctives/oi20_knee.md`):** DQS with 8 rigid joints per leg matches within 1.1/1.9 mm (90°/135°); LBS needs joints that can also scale (6 per leg, 1.9/2.1 mm), and rigid joints add a fold-over. Neither adds intersections or visible bumps. Both legs were tested independently, the other leg is unmoved, and inactive poses are unchanged. Budget 4 fails again. The prototype remains the reference; nothing promoted | OI-18 |
| OI-15 | `neck_mid` skin-weighted cuff grazes (−0.32 mm with symmetric weights; −0.18 with v1) at neck flexion 40 | head replacements with deforming cuffs |

**Remaining validation before v1.0:**
1. OI-05, then OI-06, on the symmetric v2 weights.
2. OI-03 and OI-04.
3. Face (OI-09).
4. Decide OI-07 and OI-13.

**The military leg is the first *planned* production implant, subject to final seam and attachment validation.**
Its seam `thigh_mid` is provisional. The 15 mm overlap there is a measurement from automatic, asymmetric weights
without helpers, not an approval for shipping assets. It becomes production-eligible only when:
1. `thigh_mid` is re-measured on both sides with symmetric weights (done 17 Nov: unchanged, 11.7 mm needed for a
   rigid cuff and +1.94 mm clearance for a skin-weighted one) and with the final skinning method (OI-06);
2. its overlap and cuff binding are confirmed (OI-01);
3. the base body has passed its remaining validation.

## Base-body validation plan (agreed 17 Nov 2026)

**Next milestone: a validated Cyberwolf base body.** The military leg follows only after it passes.

**Source (corrected in v0.2).** v0.1 assumed an export from the MakeHuman desktop application; that did not happen.
The reference master is `makehuman/data/3dobjs/base.obj` taken directly from the official MakeHuman 1.x source
distribution (repository snapshot, files dated 4 Nov 2020, after the September 2020 CC0 release), placed by the owner
in `concepts/base_mesh/` on 17 Nov 2026. SHA-256 `8e761e66…6fb4c`; full record in `concepts/base_mesh_PROVENANCE.md`.
The master is never edited. All cleanup, topology changes,
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
- global conventions: units (metres), axes (+Y up, +Z forward, +X character-left) and the rest pose (open in v0.2, OI-07);
- seam-ring codes and positions;
- hide-region bit numbers;
- the topology binding of drawn boundaries (a base-mesh change follows the migration procedure in part 3).

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
