# Cyberwolf character standard, part 2: attachment points and implant kinds (v0.1 draft, for review)

Sockets and seam rings are defined in `skeleton.json` and drawn in `skeleton_overview.png` (orange diamonds, red seam lines).

## Three kinds of implant

| kind | how it attaches | skin weights | hides body? | examples |
|---|---|---|---|---|
| **overlay** | skinned over the visible body | to core, twist and helper joints under it | optionally a patch (e.g. `chest`) | chest plate, subdermal armour, spinal ridge |
| **replacement** | replaces everything beyond a **seam ring** | only joints of the replaced segment, plus the proximal joint for the cuff | yes: every region beyond the seam | military leg from `thigh_mid`, cyber-arm from `shoulder`, hand from `wrist` |
| **rigid** | parented to a `sock_` frame | none (may carry `ext_` joints for moving parts) | optionally (helmet hides `scalp`, `ears`) | helmet, mask, shoulder pod, optics, backpack, held weapon |

A **full-borg chassis** is a set of replacements and overlays that together hide every region except the ones it
chooses to keep. The chassis declares exposure flags (`face_exposed`, `neck_exposed`), which drives your three options:
human face, mask or full helmet.

## Seam rings (where replacements may start)

A seam ring is a fixed loop on the base body, at a stated fraction along a bone segment. Rules for replacements:

1. Geometry starts at the seam and adds a **cuff** that overlaps the visible body by at least 15 mm proximally, so
   the joint never opens a gap when it bends. The cuff is weighted to the proximal joint.
2. The far end is closed: no open edges anywhere on a shipped implant.
3. The implant hides exactly the regions beyond the seam (listed in part 3); never fewer, never more.

| seam | between joints | at | use |
|---|---|---|---|
| `neck_base` | `neck_01` → `spine_03` | 0.35 | head + neck replacement starts here (collar) |
| `neck_mid` | `neck_01` → `neck_02` | 0.50 | head replacement (keeps the neck) |
| `waist` | `spine_01` → `spine_02` | 0.40 | lower-body chassis boundary (abdomen / pelvis) |
| `shoulder_l` | `upperarm_l` → `lowerarm_l` | 0.00 | full-arm replacement (includes the deltoid cap) |
| `upperarm_mid_l` | `upperarm_l` → `lowerarm_l` | 0.50 |  |
| `elbow_l` | `upperarm_l` → `lowerarm_l` | 0.90 | forearm replacement (cuff covers the elbow) |
| `forearm_mid_l` | `lowerarm_l` → `hand_l` | 0.50 |  |
| `wrist_l` | `lowerarm_l` → `hand_l` | 0.92 | hand replacement |
| `hip_l` | `thigh_l` → `calf_l` | 0.00 | full-leg replacement (from the hip crease) |
| `thigh_mid_l` | `thigh_l` → `calf_l` | 0.50 | mid-thigh replacement (the military-leg default) |
| `knee_l` | `thigh_l` → `calf_l` | 0.92 | lower-leg replacement (cuff covers the knee) |
| `shin_mid_l` | `calf_l` → `foot_l` | 0.50 |  |
| `ankle_l` | `calf_l` → `foot_l` | 0.92 | foot replacement |

Right-side seams mirror the left (`_r`).

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
  - the cuff overlaps the body by at least 15 mm;
  - the hide mask equals the seam's distal regions.
- **Rigid items:** attached to an existing `sock_`; no skin weights.
- **Mesh:** no open edges; scale within the target profile's tolerance; triangle budget per slot (proposal below).
- **Deformation test:** loaded on the base body and posed through a standard range-of-motion set. No body region
  that should be hidden shows through, and no hidden-region seam opens.

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

## Open points for review

1. Shoulder pods attach to `clavicle` (they shrug but do not twist with the arm). Alternative: upper-arm-mounted pods.
2. Cuff overlap of 15 mm; budgets above are proposals.
3. Should held weapons use `sock_hand_grip` only, or also a two-handed secondary grip socket?
