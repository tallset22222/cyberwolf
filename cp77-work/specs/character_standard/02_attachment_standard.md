# Cyberwolf character standard, part 2: attachment points and implant kinds (v0.2 draft)

Sockets and seam rings are defined in `skeleton.json` and drawn in `skeleton_overview.png` (orange diamonds, red seam lines).
Evidence: `basebody/reports/test1_topology.md`, `test2_deformation.md`, `test3_regions.md`.

## Three kinds of implant

| kind | how it attaches | skin weights | hides body? | examples |
|---|---|---|---|---|
| **overlay** | skinned over the visible body | to core, twist and helper joints under it | optionally a patch (e.g. `chest`) | chest plate, subdermal armour, spinal ridge |
| **replacement** | replaces everything beyond a **seam ring**, with a cuff over the remaining body | the replaced segment's joints; the cuff follows the cuff rules below | yes: every region beyond the seam | military leg from `thigh_mid`, cyber-arm from `shoulder`, hand from `wrist` |
| **rigid** | parented to a `sock_` frame | none (may carry `ext_` joints for moving parts) | optionally (helmet hides `scalp`, `ears`) | helmet, mask, shoulder pod, optics, backpack, held weapon |

A **full-borg chassis** is a set of replacements and overlays that together hide every region except the ones it
chooses to keep. The chassis declares exposure flags (`face_exposed`, `neck_exposed`), which drives your three options:
human face, mask or full helmet.

The attachment rules below are deliberately **not** one method for everything. Small implants, mechanical limbs and
full chassis behave differently, and the standard records per seam what has been measured to work.

## Cuff rules (v0.2)

A replacement's cuff must meet **two separate requirements**. Test 3 showed they are not interchangeable: at the elbow
and knee a cuff can follow the skin perfectly and still be pierced by the folding skin.

1. **Follow:** the body's open edge at the seam stays covered by the cuff in every pose; no gap opens.
2. **Clear:** the body skin never passes through the cuff in any pose.

**Binding methods:**

- **Skin-weighted (preferred candidate for deforming cuffs).** The cuff carries the body's own skin weights at the
  seam, so it moves with the skin (zero slide by construction). It must still meet *clear*: where the skin folds, the
  cuff needs additional handling (corrective shapes, helper-driven deformation, local stand-off or a rigid
  articulated shell). Thickening the cuff does not help: under LBS the clearance scales with thickness, so a fold
  pierces any thickness.
- **Rigid to one bone.** This is allowed only where the table permits it. The cuff overlap must be at least the
  seam's value, and the cuff must declare a stand-off at least the stated outward bulge. v0.1's wording ("weighted to
  the proximal joint") is withdrawn: at the limb-root seams the proximal joint (clavicle, pelvis) is not what the
  skin follows (159–168 mm slide).
- **Skin-weighted is not yet mandatory** for every implant (OI-02). Rigid mechanical cuffs remain valid where they measure clean.

**Overlap is per seam, not global** (v0.1's single 15 mm rule is withdrawn). The values are provisional starting
points from measurement, not final production values.

## Seam rings (where replacements may start)

A seam ring is a fixed closed edge loop on the base body. Its v0.2 position is the measured hm08 loop, bound by
vertex ids in `topology/hm08/seams.json`; the fraction is along the bone segment of the fitted skeleton. Right-side
seams mirror the left (`_r`), and **both sides were measured independently**.

| seam | between joints | at (v0.1 → v0.2) | status | overlap | rigid (one-bone) cuff | skin-weighted cuff (preferred) | use |
|---|---|---|---|---|---|---|---|
| `neck_base` | `neck_01` → `spine_03` | 0.35 → 0.121 | provisional | 20 mm | permitted with stand-off >= 28 mm | permitted (clearance +1.06 mm) | head + neck replacement starts here (collar) |
| `neck_mid` | `neck_01` → `neck_02` | 0.50 → 0.447 | provisional | 15 mm | permitted with stand-off >= 4 mm | permitted only with clearance handling (-0.32 mm) | head replacement (keeps the neck) |
| `waist` | `spine_01` → `spine_02` | 0.40 → 0.455 | provisional | 20 mm | not permitted: needs 22.7 mm overlap > 20 mm | permitted (clearance +1.59 mm) | lower-body chassis boundary (abdomen / pelvis) |
| `shoulder_l` | `upperarm_l` → `lowerarm_l` | 0.00 → 0.305 | **retest after helpers** | TBD | not permitted: seam not yet usable | seam not yet usable (measured -1.35 mm) | full-arm replacement (includes the deltoid cap) |
| `upperarm_mid_l` | `upperarm_l` → `lowerarm_l` | 0.50 → 0.466 | provisional | 15 mm | permitted with stand-off >= 8 mm | permitted (clearance +1.85 mm) |  |
| `elbow_l` | `upperarm_l` → `lowerarm_l` | 0.90 → 0.915 | **relocate and retest** | TBD | not permitted: seam not yet usable | seam not yet usable (measured -1.57 mm) | forearm replacement (cuff covers the elbow) |
| `forearm_mid_l` | `lowerarm_l` → `hand_l` | 0.50 → 0.440 | provisional | 15 mm | permitted with stand-off >= 6 mm | permitted (clearance +1.86 mm) |  |
| `wrist_l` | `lowerarm_l` → `hand_l` | 0.92 → 0.937 | provisional | 15 mm | permitted with stand-off >= 5 mm | permitted (clearance +1.64 mm) | hand replacement |
| `hip_l` | `thigh_l` → `calf_l` | 0.00 → 0.254 | **candidate** | 15 mm | not permitted: candidate seam: skin-weighted only | permitted (clearance +1.25 mm) | full-leg replacement (from the hip crease) |
| `thigh_mid_l` | `thigh_l` → `calf_l` | 0.50 → 0.501 | provisional | 15 mm | permitted with stand-off >= 7 mm | permitted (clearance +1.94 mm) | mid-thigh replacement (the military-leg default) |
| `knee_l` | `thigh_l` → `calf_l` | 0.92 → 0.936 | **relocate and retest** | TBD | not permitted: seam not yet usable | seam not yet usable (measured -0.15 mm) | lower-leg replacement (cuff covers the knee) |
| `shin_mid_l` | `calf_l` → `foot_l` | 0.50 → 0.582 | provisional | 15 mm | permitted with stand-off >= 4 mm | permitted (clearance +1.96 mm) |  |
| `ankle_l` | `calf_l` → `foot_l` | 0.92 → 0.938 | provisional | 20 mm | permitted with stand-off >= 6 mm | permitted (clearance +1.77 mm) | foot replacement |

Status meanings:
- **provisional:** measured, and usable for production prototypes at the stated overlap;
- **candidate:** passes with the stated binding only, and needs confirmation;
- **retest after helpers:** not judgeable until the helper joints work;
- **relocate and retest:** the current position is unsuitable; candidate positions are to be measured.

### Measured evidence per seam (both sides with symmetric v2 weights, which agree exactly; worst of LBS/DQS; 22 poses; no helper joints)

| seam | rigid overlap needed | rigid max outward bulge | skin-weighted min clearance (2 mm shell) | note |
|---|---|---|---|---|
| `neck_base` | 18.3 mm | 27.9 mm | 1.06 mm | moved from 0.35 to the measured loop (test 1) |
| `neck_mid` | 12.0 mm | 3.9 mm | -0.32 mm | skin-weighted cuff grazes at neck flexion 40 (needs clearance handling) |
| `waist` | 22.7 mm | 5.6 mm | 1.59 mm | 20 mm set by review; LBS measured 22.7 mm (open item) |
| `shoulder_l` | 17.0 mm | 39.6 mm | -1.35 mm | option A root loop; armpit deformation fails with both cuff bindings |
| `upperarm_mid_l` | 10.1 mm | 7.7 mm | 1.85 mm |  |
| `elbow_l` | 36.2 mm | 11.2 mm | -1.57 mm | on the flexion crease: rigid cuffs slide, skin-weighted cuffs are pierced |
| `forearm_mid_l` | 12.4 mm | 5.6 mm | 1.86 mm |  |
| `wrist_l` | 14.4 mm | 5.0 mm | 1.64 mm | tight: 14.4 mm needed |
| `hip_l` | 30.1 mm | 19.9 mm | 1.25 mm | option A root loop; skin-weighted cuff only |
| `thigh_mid_l` | 11.7 mm | 6.5 mm | 1.94 mm | military-leg default |
| `knee_l` | 57.1 mm | 7.2 mm | -0.15 mm | on the flexion crease: rigid cuffs slide, skin-weighted cuffs are pierced |
| `shin_mid_l` | 8.4 mm | 4.0 mm | 1.96 mm | moved from 0.50 to the measured loop (test 1) |
| `ankle_l` | 20.0 mm | 5.5 mm | 1.77 mm |  |

### Seams needing work (open items)

- **Elbow and knee (OI-03).** The seams sit on the flexion crease. Candidate positions away from the crease are to be
  measured with the same motion test, aiming for a boundary with less extreme compression and expansion. A knee
  replacement must not need a custom workaround per implant.
- **Shoulder (OI-04).** Option A's root loop works as a hiding boundary, but the armpit deformation fails with both
  cuff bindings. Retest after the helper joints work. This is not evidence against option A.
- **Hip (OI-04).** Option A remains a **candidate**. The initial skin-weighted cuff passed (clearance at least
  +1.25 mm in every pose, both sides); confirm after the symmetric-weight rerun (OI-08) and the helper tests (OI-05).
  Rigid cuffs are not allowed there: they need 30.1 mm of overlap and bulge 19.9 mm.
- **Waist (OI-10).** The skin-weighted cuff is permitted and passes (clearance at least +1.59 mm). A **rigid** cuff is
  not permitted, because the rigid case measured 22.7 mm of overlap needed under LBS, more than the 20 mm set by
  review (DQS needs 17.2 mm). If OI-06 selects DQS, a rigid waist cuff can be reconsidered. The 20 mm value itself is
  also resolved with OI-06.

## Rules every replacement follows

1. Geometry starts at the seam and adds a cuff with at least the seam's overlap, bound by a permitted method.
2. The far end is closed: no open edges anywhere on a shipped implant.
3. The implant hides exactly the regions beyond the seam (listed in part 3); never fewer, never more.
4. A seam whose status is *relocate and retest* or *retest after helpers* is not used for production implants.

## Sockets (rigid attachment frames)

Socket frames take their parent's orientation, offset to the stated position. They are always leaves and never carry skin weights.

| joint | parent | rest position (m, x y z) | note |
|---|---|---|---|
| `sock_head_top` | `head` | +0.000 +1.750 -0.010 | helmets, headgear |
| `sock_face` | `head` | +0.000 +1.635 +0.100 | masks, face plates, visors |
| `sock_eye_l` | `eye_l` | +0.032 +1.645 +0.088 | optic replacement (left) |
| `sock_neck_port` | `neck_01` | +0.000 +1.490 -0.060 | spinal / neural port; helmet cable terminus |
| `sock_spine_upper` | `spine_03` | +0.000 +1.330 -0.110 | back-mounted cyberware (upper) |
| `sock_spine_lower` | `spine_01` | +0.000 +1.070 -0.100 | back-mounted cyberware (lower) |
| `sock_chest_core` | `spine_03` | +0.000 +1.300 +0.020 | internal implants (logical location; life support, processors) |
| `sock_waist` | `pelvis` | +0.000 +1.000 +0.000 | belt hardware, waist implants |
| `sock_hip_l` | `pelvis` | +0.100 +0.930 +0.000 | hip joint (full-leg replacement anchor) |
| `sock_shoulder_l` | `clavicle_l` | +0.200 +1.465 -0.010 | shoulder pods / plates (do not twist with the arm) |
| `sock_elbow_l` | `lowerarm_l` | +0.387 +1.208 -0.010 | elbow hardware |
| `sock_wrist_l` | `lowerarm_l` | +0.571 +1.024 +0.000 | wrist hardware, forearm-mounted tools |
| `sock_hand_grip_l` | `hand_l` | +0.626 +0.949 +0.000 | held items / weapons |
| `sock_palm_l` | `hand_l` | +0.611 +0.964 +0.000 | palm implants |
| `sock_thigh_mid_l` | `thigh_l` | +0.095 +0.710 +0.004 | mid-thigh hardware |
| `sock_knee_l` | `calf_l` | +0.100 +0.500 +0.058 | knee hardware |
| `sock_ankle_l` | `foot_l` | +0.105 +0.085 -0.012 | ankle hardware |
| `sock_sole_l` | `foot_l` | +0.105 +0.000 +0.030 | ground contact (feet replacements, footstep effects) |

## Validation every implant must pass (automated, before it enters the library)

- Every joint it is weighted to exists and is core, twist or helper (or the implant's own `ext_` joints).
- At most 4 influences per vertex; weights sum to 1.
- **Replacements:**
  - geometry starts within ±5 mm of its seam ring;
  - the cuff overlap meets **that seam's** value;
  - the cuff binding is one the seam permits (rigid only with its stated stand-off);
  - the hide mask equals the seam's distal regions.
- **Rigid items:** attached to an existing `sock_`; no skin weights.
- **Mesh:** no open edges; scale within the target profile's tolerance; triangle budget per slot (proposal below).
- **Deformation test, on both sides.** Loaded on the base body and posed through the standard range-of-motion set on
  the **left and the right** independently; a mirrored result is not accepted. It must meet *follow* (no
  hidden-region seam opens) and *clear* (no skin passes through the cuff, and no hidden region shows through).

**Proposed triangle budgets (LOD0):**

| slot | budget |
|---|---|
| full leg | 20k |
| leg below the knee | 12k |
| full arm | 15k |
| hand | 6k |
| helmet | 8k |
| chest overlay | 12k |
| full chassis | 90k |

## Open points carried from v0.1

1. Shoulder pods attach to `clavicle` (they shrug but do not twist with the arm). Alternative: upper-arm-mounted pods.
2. Triangle budgets above are proposals.
3. Should held weapons use `sock_hand_grip` only, or also a two-handed secondary grip socket?
