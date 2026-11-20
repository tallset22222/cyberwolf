# Test 3: region separation and seam motion (MakeHuman hm08, fitted Cyberwolf skeleton v0.1-draft)

Status: **evidence only.** Nothing in the standard has been changed. Inputs: `base_working.obj` (body group), test-1 loops, test-2 fitted skeleton, weights and 22-pose library (LBS and DQS, no helpers). Scripts: `test3_regions.py`, `test3_run.py`, `test3_report.py`. Renders: `test3_regions.png`, `test3_seam_motion.png`.

## 1. Which regions separate cleanly

Cutting the mesh only along real closed edge loops (test-1 PASS seams, the two MOVE seams at their measured loops, option A first loops for shoulder and hip, plus forearm 15 %, shin 15 % and a ribcage ring) splits the body into **29 connected pieces**. All **33/33** hiding regions are populated; none missing. Hiding any single region leaves a clean, manifold open edge (no T-junctions) for **all 33** regions.

| Separation | Regions |
|---|---|
| **Clean: every boundary is a real edge loop** | all limb regions (shoulder cap→upperarm, upperarm upper/lower, elbow, forearm, hand, thigh upper/lower, knee, shin, foot), neck_lower, the neck_mid / neck_base / waist / ribcage rings |
| **Separate, but part of the boundary is a geometric rule, not topology** | chest ↔ back_upper and abdomen ↔ back_lower (mid-axillary line), shoulder_cap ↔ chest/back_upper, pelvis_front ↔ pelvis_back (side line + gluteal fold), face ↔ scalp (hairline), face/scalp ↔ neck_upper (jawline), ears |

Face counts per region: abdomen 76, back_lower 50, back_upper 312, chest 538, ears 562, elbow_l 80, elbow_r 80, face 3244, foot_l 1072, foot_r 1072, forearm_l 140, forearm_r 140, hand_l 1638, hand_r 1638, knee_l 100, knee_r 100, neck_lower 126, neck_upper 116, pelvis_back 296, pelvis_front 322, scalp 298, shin_l 180, shin_r 180, shoulder_cap_l 149, shoulder_cap_r 149, thigh_lower_l 120, thigh_lower_r 120, thigh_upper_l 80, thigh_upper_r 80, upperarm_lower_l 120, upperarm_lower_r 120, upperarm_upper_l 40, upperarm_upper_r 40.

## 2. Do the cuts follow actual topology?

Jaggedness = boundary length ÷ length after light smoothing (1.0 = perfectly smooth). Real loops measure **1.04–1.13**. Rule-based boundaries:

| Boundary | Edges | Length mm | Jaggedness |
|---|---|---|---|
| abdomen | back_lower | 8 | 114.7 | 2.52 |
| back_upper | chest | 22 | 482.8 | 1.95 |
| chest | shoulder_cap_r | 22 | 413.2 | 1.77 |
| chest | shoulder_cap_l | 22 | 413.2 | 1.77 |
| back_upper | shoulder_cap_r | 18 | 331.4 | 1.66 |
| back_upper | shoulder_cap_l | 18 | 331.4 | 1.66 |
| ears | face | 72 | 256.8 | 1.47 |
| ears | scalp | 40 | 408.0 | 1.46 |
| face | scalp | 38 | 472.5 | 1.44 |
| face | neck_upper | 40 | 317.5 | 1.37 |
| pelvis_back | pelvis_front | 44 | 830.4 | 1.34 |
| neck_upper | scalp | 20 | 211.8 | 1.16 |

Reading: no torso or head subdivision follows an edge flow on hm08. They are cuttable, but only as staircase paths through the quads. Each needs an **authored edge path (a fixed vertex list per boundary)** rather than a rule.

Specific findings:

- **Ears:** hm08 has no closed loop at the root of the ear; the only closed loops there are small concentric rings inside the concha. An automatic protrusion test (medial ray hits the head within 25 mm) did not isolate the auricle either. The current ear region is a box rule (562 faces) that also takes temple and mastoid skin (visible in the side render). **The ear boundary must be authored.**
- **Ribcage line:** the ring nearest the spine_02 joint sits at y = 1092 mm, only 48 mm above the waist seam (1044 mm). Abdomen is therefore a thin band (76 faces). Clean horizontal rings exist at 1057, 1073, 1092, 1115, 1139, 1193, 1250 mm. The anatomical costal margin is an inverted V, so no horizontal ring matches it. Choosing between a ring and an authored V is a v0.2 decision (relevant to crop tops and abdominal implants).
- **neck_upper:** at the front the neck_mid loop runs just under the chin, so neck_upper is mostly a band at the sides and nape (116 faces). It exists, but it is thin at the front.
- **Mid-axillary:** approximated here by the coronal plane through the shoulder joints. Its 1.95 jaggedness at chest|back_upper is the worst on the torso.

## 3. Gaps and intersections, rest and posed

- **Body ↔ body:** regions share vertices on every boundary, so hiding cannot open a gap between body regions, either at rest or in any pose. **0 gaps at rest and in every pose by construction** (checked: every hide leaves a manifold open edge). Self-intersection of the skin itself in poses is the test-2 result (armpit, groin, elbow/knee folds) and is unchanged here.
- **Implant ↔ body** is where gaps and intersections can occur. At rest the overlap is 0 by construction. In poses, the gap and poke-through depend on how the cuff is bound to the skeleton (section 4).

## 4. Maximum seam displacement during movement, and is 15 mm enough per seam

Measured on the body skin under the cuff, across all 22 poses. Left side shown here; the right side was measured separately with its own poses (section 4b). Three cuff bindings were compared:

- **rigid/spec:** rigid to the "proximal joint" exactly as v0.1 words it;
- **rigid/best:** rigid to whichever single bone influencing that skin gives the least slide (the best case for any rigid cuff);
- **weight-transfer:** a 2 mm cuff shell that carries the body's own skin weights at the seam.

*Slide* is measured at the seam loop; the body's open edge must stay under the cuff, so the overlap needed is slide + 5 mm. *Outward* is the bulge in the 0–15 mm overlap band; it pokes through a close-fitting rigid cuff. *Inward* is the sink at the cuff's proximal edge (12–18 mm), which shows as a visible gap. *Clearance* is how far the weighted 2 mm shell stays outside the skin; below 0 the skin pokes through.

| Seam | rigid/spec slide mm (bone) | rigid/best bone | best: overlap needed LBS / DQS mm | 15 mm OK? | outward LBS / DQS mm | inward LBS / DQS mm | weight-transfer clearance LBS / DQS mm |
|---|---|---|---|---|---|---|---|
| shoulder_l (opt A) | 159.0 (clavicle_l) | upperarm_l | 17.0 / 11.9 | ⚠️ one method | 23.1 / 39.6 | 71.2 / 74.8 | **-1.35** / **-1.27** |
| upperarm_mid_l | 5.1 (upperarm_l) | upperarm_twist_01_l | 10.1 / 7.0 | ✅ | 3.0 / 7.7 | 2.2 / 2.0 | 1.85 / 1.96 |
| elbow_l | 21.2 (upperarm_l) | upperarm_twist_02_l | 26.2 / 36.2 | ❌ | 4.0 / 11.2 | 20.4 / 16.6 | **-0.5** / **-1.57** |
| forearm_mid_l | 7.4 (lowerarm_l) | lowerarm_l | 12.4 / 6.8 | ✅ | 2.7 / 5.6 | 0 / 0 | 1.86 / 1.94 |
| wrist_l | 9.4 (lowerarm_l) | lowerarm_twist_02_l | 14.4 / 14.2 | ✅ | 2.3 / 5.0 | 7.5 / 6.2 | 1.64 / 1.92 |
| hip_l (opt A) | 164.7 (pelvis) | thigh_l | 30.1 / 22.9 | ❌ | 5.9 / 19.9 | 29.0 / 24.2 | 1.25 / 1.43 |
| thigh_mid_l | 6.7 (thigh_l) | thigh_twist_01_l | 11.7 / 7.5 | ✅ | 2.6 / 6.5 | 0 / 0 | 1.94 / 1.94 |
| knee_l | 33.2 (thigh_l) | thigh_twist_02_l | 38.2 / 57.1 | ❌ | 4.0 / 7.2 | 38.6 / 34.6 | **-0.01** / **-0.15** |
| shin_mid_l | 3.4 (calf_l) | calf_twist_01_l | 8.4 / 6.4 | ✅ | 3.3 / 4.0 | 0 / 0 | 1.96 / 1.99 |
| ankle_l | 12.9 (calf_l) | calf_twist_01_l | 17.9 / 20.0 | ❌ | 4.1 / 5.5 | 11.2 / 9.8 | 1.77 / 1.91 |
| neck_mid | 6.9 (neck_01) | neck_01 | 11.9 / 12.0 | ✅ | 3.2 / 3.9 | 12.0 / 8.3 | **-0.15** / **-0.32** |
| neck_base | 12.4 (spine_03) | clavicle_r | 17.4 / 18.3 | ❌ | 22.9 / 27.9 | 10.5 / 15.6 | 1.06 / 1.22 |
| waist | 17.7 (spine_01) | spine_01 | 22.7 / 17.2 | ❌ | 4.7 / 5.6 | 15.5 / 15.9 | 1.65 / 1.59 |

Worst poses: elbow and knee at flexion 135; shoulder at overhead abduction (slide) and across-chest adduction (sink, poke-through); hip and waist at hip flexion 90; neck_base under shoulder flexion and adduction (the trapezius moves with the arm); ankle at plantarflexion 40; wrist at extension 60.

Summary per seam:

- **15 mm holds under both methods:** upperarm_mid, forearm_mid, thigh_mid, shin_mid (moved), neck_mid, and wrist (just, 14.4 / 14.2 mm). These are all mid-segment seams, away from a joint.
- **15 mm is not enough, but a modest increase fixes it:** ankle (needs 18–20 mm), neck_base (17–18 mm, plus a 23–28 mm outward bulge from the trapezius when the arm moves), waist (17–23 mm).
- **No rigid cuff works at joint-line seams:** the elbow (26–36 mm) and knee (38–57 mm) seams sit at 0.90 / 0.92 of the bone, on the flexion crease. Their skin is split between two bones, so a cuff rigid to either one slides. A weight-transfer cuff does not slide but folds into the crease at flexion 135 (clearance −0.5 to −1.6 mm). The crease is exactly where test 2 found folding.
- **Literal v0.1 wording fails at the limb roots:** "cuff weighted to the proximal joint" means clavicle for the shoulder (159–162 mm slide) and pelvis for the hip (165–168 mm). At option-A root loops the skin follows the limb bone, not the proximal joint.

## 4b. Both sides, with symmetric weights (v2)

The pose library was mirrored to the right side and every right seam was measured independently. The central seams (neck_mid, neck_base, waist) were re-measured under right-side poses as well.

**Result: left and right agree exactly** (largest difference across every seam metric: 0.0 mm). The weights pass the symmetry gate (worst vertex 1.7e-16, tolerance 0.02).

**History: why the first right-side run differed.** The first run used the original test-2 weights (v1), which were not symmetric. The mesh mirrors exactly and the joints mirrored to 0.01 mm, but 1657 vertices differed from their mirror partner by more than 0.05 (worst 0.57). The right shoulder then measured worse than the left: DQS clearance −1.4 vs −0.5 mm. Four causes were found, all in the weight builder (`diag_symmetry.py`):

1. **The voxel grid was not centred on the mirror plane.** It started at the mesh minimum and was rounded up, so mirror points fell in differently aligned cells. Combined with the 7-of-8 visibility vote, this was the dominant cause: 2,043 vertices made a different visibility decision from their mirror.
2. **Quads were split along an order-dependent diagonal.** A mirrored quad has reversed vertex order, so its triangles are not the mirror of the original, and the solid differed on non-planar quads.
3. **Ties on the midline were broken by bone order.** A vertex on the midline is its own mirror; left and right bones tie exactly, and the lower index won. Smoothing then spread the bias.
4. **Exact ties at shared joint ends were broken by bone order.** The pelvis segment ends exactly where the thigh segment starts, so the distances tie at the 6-candidate cutoff.

**Fix (weights v2, `test2_deformation.build`):**
- a grid with cell edges at x = k·h;
- a centroid-fan quad split for voxelisation and normals;
- midline visibility made pair-symmetric, and top-4 never keeps one bone of a tied pair;
- a tie-aware candidate set;
- joints and tips symmetrised exactly (they were within 0.005 mm).

v1 remains reproducible (`CW_WEIGHTS=v1`; checked identical to the archived test 2), and all v1 reports are archived in `reports/v1_asymmetric_weights/`. `check_weight_symmetry.py` is now a gate.

**What changed from v1 to v2 (worst of both sides):**
- **Shoulder:** clearance −1.35 mm, close to v1's right side. v1's left side (−0.5 mm) was the optimistic outlier.
- **neck_mid:** overlap needed 9.5 → 12.0 mm (still within 15 mm); skin-weighted clearance −0.18 → −0.32 mm.
- **neck_base:** changes by 0.1 mm.
- **Every other seam:** identical.
- **Regions, boundaries and seam loops:** identical.

## 5. Do option A's shoulder and hip boundaries work with the cuff/overlay approach?

- **As a hiding boundary: yes.** Both option-A root loops are real closed loops; the shoulder_cap and thigh_upper regions separate cleanly and hide with clean open edges.
- **Hip (option A) with a cuff: workable with a weight-transfer cuff, not with a rigid one.**
  - Weight-transfer: the shell stays outside the skin in every pose (worst +1.1 / +1.4 mm, at hip flexion 90).
  - Rigid to thigh_l (the best rigid case): needs 30 / 23 mm overlap, and DQS bulges outward by up to 20 mm.
  - Rigid to pelvis (the literal v0.1 wording): fails, with 165 mm of slide.
- **Shoulder (option A) with a cuff: does not work cleanly with either binding without help.**
  - Rigid to upperarm_l: the slide is small (needs 17 / 12 mm), but the skin bulges 21 / 36 mm outward under the cuff (horizontal / overhead abduction) and sinks 70+ mm at its edge in across-chest adduction.
  - Weight-transfer cuff: the skin pokes through (−1.4 / −0.5 mm) in across-chest adduction.
  - This is the armpit and deltoid failure test 2 already showed. It needs the helper joints (or a cuff with real standoff) before the shoulder replacement boundary can be judged fairly.

## 6. Inputs to the combined v0.2 review (not decisions)

Questions this test raises for the three-report review:

1. **Cuff binding.** Should replacement cuffs carry the body's skin weights at the seam (weight-transfer) instead of being rigid to a proximal joint? On this evidence weight-transfer holds at every mid-segment seam and at the hip; rigid holds only at mid-segment seams.
2. **Overlap per seam rather than one global 15 mm?** On the measured values: 15 mm at mid-segment seams; 20 mm at ankle, neck_base and waist; joint-line seams handled by binding or relocation rather than by more overlap.
3. **Elbow and knee seam placement.** Should the seam move proximally off the flexion crease (e.g. to the first clean loop above it), with the cuff covering the joint, or stay put pending helpers?
4. **Shoulder and hip.** Should the decision on option A be re-run after the helper-joint pass, comparing LBS+helpers and DQS+helpers as already agreed?
5. **Authored boundaries.** Should the hiding map store explicit vertex-list boundaries for the mid-axillary line, shoulder cap, pelvis front/back, hairline, jawline and ears? Ears are the clearest case.
6. **Ribcage line.** A horizontal ring (and which one), or an authored costal V?

Caveats: no helper joints were used; weights are the test-2 automatic weights (inverse-distance with visibility), not artist-painted; strip width 30 mm and margin 5 mm are configurable in `test3_run.py`. For LBS the shell clearance scales linearly with thickness, so a thicker weight-transfer cuff does **not** cure a negative clearance: the fold, not the thickness, is the cause.
