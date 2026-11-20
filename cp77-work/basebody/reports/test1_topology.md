# Test 1: topology and seam compatibility (MakeHuman hm08 body, working copy)

**Independent of our skeleton fit.** Seam positions are placed using MakeHuman's own anatomical joint markers
(shoulder, elbow, hand, upper-leg, knee, ankle, neck, head, spine-1..3) mapped to our joints. Script:
`basebody/test1_topology.py`. Data: `test1_topology.json`. Picture: `test1_seams.png`, coloured green = pass,
orange = move, red = fail.

## The mesh

Body group as documented by MakeHuman:

- 13,380 vertices and 13,378 faces, **all quads**;
- 1.667 m from ground marker to crown;
- the neutral pose has arms about 50° down, which is close to our 45° A-pose;
- **536 closed edge loops**, spaced about 15–20 mm apart along the limbs.

## Rule

For each seam: find closed edge loops that encircle the limb (or neck or torso) axis.

| status | rule |
|---|---|
| PASS | the nearest usable loop is within 15 mm of the seam |
| MOVE | the nearest usable loop is within 60 mm |
| FAIL | otherwise |

A loop is usable if its tilt is at most 22°. Tilt is measured against the cross-section; it is used instead of spread
because spread grows with limb thickness. The first run used a spread limit of 25 mm, which wrongly failed the thigh
and neck; both values are kept in the JSON.

## Results (left and right identical: the mesh is symmetric)

| seam | status | nearest usable loop | note |
|---|---|---|---|
| neck_mid | **PASS** | −3 mm, tilt 20° | |
| waist | **PASS** | +5 mm, tilt 3° | |
| upperarm_mid | **PASS** | −8 mm, tilt 18° | |
| elbow | **PASS** | +3 mm, tilt 15° | |
| forearm_mid | **PASS** | −14 mm, tilt 12° | |
| wrist | **PASS** | +4 mm, tilt 12° | |
| thigh_mid | **PASS** | 0 mm, tilt 16° | military-leg default seam: an exact loop |
| knee | **PASS** | +7 mm, tilt 12° | |
| ankle | **PASS** | +7 mm, tilt 20° | |
| shin_mid | **MOVE** | +31 mm (fraction 0.58, spec 0.50) | loop with only 6° tilt; just move the seam |
| neck_base | **MOVE** | −36 mm (fraction 0.12, spec 0.35) | spec put it on the upper chest; the neck's own root loop is higher |
| shoulder | **FAIL** | first arm loop is +70 mm (31% down the upper arm), tilt 21° | above it, the deltoid's edges flow into the torso: there is no loop at the joint |
| hip | **FAIL** | first leg loop is +107 mm (25% down the thigh), tilt 12° | above it, the groin and buttock edges flow into the pelvis |

**Result: 18 of 26 seam instances pass, 4 need moving, 4 fail.** The four failures are the left and right shoulder
and hip.

## Interpretation (evidence for v0.2, not yet applied)

1. **The topology supports the mid-limb and joint seams well.** It includes the thigh_mid seam the military leg
   needs, which matches an existing loop exactly.
2. **shin_mid and neck_base:** move the seams to the existing loops. No mesh change is needed.
3. **The root seams (shoulder, hip) were mis-specified, not just mis-meshed.** A seam "at the joint centre" is
   inside the torso. The mesh's limb-root boundaries are not straight loops but diagonal edge paths: across the
   deltoid toward the armpit, and along the groin and gluteal fold. Two options:
   - **a.** Define full-arm and full-leg replacements to start at the first limb loop (31% of the upper arm, 25% of
     the thigh), with the shoulder cap and upper hip handled by the implant's cuff and an overlay.
   - **b.** Keep anatomical root seams, but define them as named **edge paths** (closed but non-planar cycles) on
     the base mesh. That's more faithful, but harder to model against.

   Test 3 (region separation) checks whether option b's paths split cleanly. That is the evidence for choosing.
