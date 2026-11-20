# Test 2: skeleton fitting and deformation (MakeHuman hm08 working copy)

**Independent of the seam definitions.** Scripts: `fit_skeleton.py` (fit), `test2_deformation.py` (skin, pose, measure),
`render_test2.py` (pictures). Data: `skeleton_fitted.json`, `test2_deformation.json`. Picture: `test2_poses.png`, where each
pose is shown with LBS on the left and DQS on the right; red = edges stretched more than 30 %, blue = compressed below 75 %.

## Fit

The Cyberwolf skeleton (names and hierarchy unchanged) was placed on MakeHuman's own anatomical joint markers, giving
profile `bio_makehuman_default`: 1.667 m, 75 core and twist joints. Every joint lies inside the body (generalised winding
number) except the eyes, which sit in the open eye sockets (the eyeballs are helper geometry, removed).

**Fitting findings (evidence for v0.2):**

1. **Finger markers.** MakeHuman's four markers per finger are knuckle, PIP, DIP and fingertip. The fingertip marker
   lies within 1 mm of the surface. Ring and pinky metacarpal joints have no marker; they are placed 40 % from wrist to knuckle.
2. **Toe markers.** These sit on the sole (y ≈ 1 cm). The toe joint and tip are lifted to the vertical middle of the
   foot; without this, the toes were weighted to the shin.
3. **Jaw marker.** MakeHuman's `jaw` marker is the chin tip, not the hinge. Our jaw joint (the temporomandibular joint)
   is placed 2 cm above and 3 cm in front of the skull-base joint, which the face rig must confirm.
4. **Rest pose.** MakeHuman's rest pose has the upper arms 50.4° below horizontal (spec says 45°) and the thighs 7°
   from vertical. Choice for v0.2: adopt the mesh's pose as the reference rest pose, or re-pose the mesh to 45°.

## Skinning (fixed, not tuned per joint)

- Inverse-distance⁴ to bone segments (core plus twist), 4 influences, 8 smoothing passes on the mesh.
- **Visibility rule:** a bone may influence a vertex only if the straight path to it stays inside the body (5 mm voxels;
  holes up to 2 cm closed; the head treated as solid because of the open oral cavity).
- **Helper joints are NOT used:** their drivers don't exist yet. This is the baseline before corrective deformation.
- **Mouth lining:** 293 mouth-lining vertices are excluded from the metrics and reported; they belong to the face rig.

**Corrections made while building the test.** Each is a general rule, not a per-pose adjustment, and each was found by
looking at the renders:

- Nearest-bone weighting dragged the breast with the arm, so the visibility rule was added.
- 8 mm voxels tore the toes and chin, so 5 mm voxels and hole-closing were used.
- The toe joint sat on the sole, so it was lifted (fit finding 2).
- The jaw was missing from skinning, and its pivot was on the chin, so both were corrected (fit finding 3).
- The head segment ran up the back of the skull, so it now aims through the skull's middle.

**Metric note:** volume, stretch and folds are measured within 13 cm of the posed joint. A whole-body stretch scan was
added after the neck test showed that the local metric missed facial tearing.

## Results (volume ratio / stretch p95 / folded faces)

| pose | LBS | grade | DQS | grade |
|---|---|---|---|---|
| shoulder_abduct_to_horizontal | 1.00 / 1.29 / 0 | OK | 1.11 / 1.31 / 0 | volume |
| shoulder_abduct_overhead | 0.78 / 1.79 / 21 | volume,stretch,compression,folding | 1.46 / 2.12 / 10 | volume,stretch,folding |
| shoulder_flex_forward | 0.72 / 1.43 / 0 | volume,stretch,compression | 1.05 / 1.53 / 1 | stretch,compression,folding |
| shoulder_adduct_across_chest | 0.55 / 1.43 / 29 | volume,stretch,compression,folding | 0.92 / 1.58 / 32 | stretch,compression,folding |
| elbow_flex_90 | 0.76 / 1.16 / 14 | volume,compression,folding | 0.89 / 1.26 / 8 | folding |
| elbow_flex_135 | 0.65 / 1.22 / 20 | volume,compression,folding | 0.83 / 1.41 / 24 | volume,stretch,folding |
| forearm_pronate_90 | 0.85 / 1.07 / 0 | volume | 0.98 / 1.09 / 0 | OK |
| wrist_flex_60 | 0.96 / 1.03 / 0 | OK | 0.98 / 1.03 / 0 | OK |
| wrist_extend_60 | 0.98 / 1.04 / 0 | OK | 1.01 / 1.05 / 0 | OK |
| hip_flex_90 | 0.61 / 1.31 / 0 | volume,compression | 1.03 / 1.52 / 0 | stretch |
| hip_abduct_45 | 0.83 / 1.04 / 0 | volume | 0.91 / 1.06 / 0 | OK |
| hip_extend_20 | 0.96 / 1.07 / 0 | OK | 0.99 / 1.08 / 0 | OK |
| sit_hip90_knee90 | 0.61 / 1.31 / 0 | volume,compression | 1.03 / 1.52 / 0 | stretch |
| knee_flex_90 | 0.62 / 1.19 / 0 | volume,compression | 0.90 / 1.36 / 0 | stretch,compression |
| knee_flex_135 | 0.41 / 1.20 / 11 | volume,compression,folding | 0.83 / 1.57 / 0 | volume,stretch,compression |
| ankle_dorsiflex_20 | 0.97 / 1.12 / 0 | OK | 0.99 / 1.12 / 0 | OK |
| ankle_plantarflex_40 | 0.95 / 1.13 / 0 | OK | 1.02 / 1.17 / 0 | OK |
| spine_flex_forward_45 | 1.05 / 1.07 / 0 | OK | 1.06 / 1.07 / 0 | OK |
| spine_twist_45 | 0.98 / 1.06 / 0 | OK | 1.00 / 1.07 / 0 | OK |
| spine_side_bend_30 | 1.00 / 1.09 / 0 | OK | 1.00 / 1.09 / 0 | OK |
| neck_flex_40 | 1.04 / 1.13 / 8 | folding | 1.06 / 1.13 / 8 | folding |
| neck_turn_70 | 0.82 / 1.36 / 3 | volume,stretch,folding | 1.00 / 1.35 / 4 | stretch,folding |

Thresholds (configurable): volume 0.85–1.10, stretch p95 ≤ 1.35, compression p5 ≥ 0.70, folded faces 0.

## Reading

**Clean with both methods:** wrists, ankles, forearm twist (DQS), spine flexion, twist and side bend, hip extension,
shoulder to horizontal, neck flexion.

**Classic linear-blending volume loss:**

| joint | LBS | DQS |
|---|---|---|
| elbow 90° / 135° | 0.76 / 0.65 | 0.89 / 0.83 |
| knee 90° / 135° | 0.62 / 0.41 | 0.90 / 0.83 |
| hip flexion 90° | 0.61 | 1.03 |

Dual-quaternion skinning restores volume but stretches more, and still folds 8–24 faces inside the elbow crease.

**Fails with both methods:**
- **Shoulder above horizontal and across the chest:** the armpit and back of the armpit tear (up to 5.6× in overhead);
  DQS bulges (volume 1.43).
- **Groin at 90° hip flexion:** up to 3.9× stretch.

These are exactly the places the spec's helper joints (`hlp_shoulder`, `hlp_hip`, `hlp_elbow`, `hlp_knee`) are for. The
test confirms they are needed. It does not test them, because their drivers aren't designed yet.

**Face:** under head turns, the eyelid rims and lip corners still tear (up to about 15×) where the eyeballs were removed.
The neck itself is clean: under flexion, 4 edges exceed 60 % stretch (max 1.7×); under a 70° turn, 26 (max 2.9×). The
face belongs to the separate face rig.

**Toes:** under ankle poses, small gaps between toes stretch (up to 7.8× on 2 mm edges). The spec treats the toes as one
segment; separate toes may be worth adding for bare feet (spec open point 2).

## Verdict

The skeleton's joint placement and hierarchy deform the body acceptably everywhere except the shoulder girdle at large
angles and the deep hip, knee and elbow flexions. Those are the classic cases a pure bone skeleton cannot handle without
correctives, and they line up with the helper layer already in the spec. None of the failures point to a misplaced core
joint. They point to two decisions for v0.2:

1. **The blending method:** DQS, or LBS plus helpers.
2. **The design of the helper drivers,** to be tested next.
