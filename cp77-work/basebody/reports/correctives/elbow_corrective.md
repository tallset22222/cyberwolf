# Elbow corrective shape, stage 1 (the shape; engine delivery is stage 2)

Status: **prototype; works at 90°, deep flexion unsolved; not adopted into the standard.**
- Enabled with `CW_CORRECTIVES=elbow` (off by default; with it off, v3 reproduces exactly).
- Built on v3 weights at 4 influences.
- Authored for the left arm and mirrored: the deltas are exact mirrors, and test 3 left/right difference is 0.
- One shape per skinning method.

## How it is made

**Authoring (once, offline, in place of a sculptor).**
1. At the key flexion angle the elbow is posed and skinned without correctives.
2. Inner-crease skin that has crossed the plane bisecting the elbow angle is moved back onto it, 0.75 mm each side,
   so the two sides end in contact:
   - forearm-side skin into the upper-arm half;
   - upper-arm-side skin into the forearm half;
   - the 5 mm crease band onto the plane.
3. Which side a vertex is on is decided by **rest-pose anatomy** (signed distance along the limb axis from the elbow
   joint), not by weights. Weights failed: the deep crease is mixed.
4. Only the arm's own skin takes part (test-3 region map: upper arm, elbow and forearm regions). An early version
   used a distance sphere, reached the torso, and moved it by up to 246 mm.
5. The displacement is smoothed over the surface and re-constrained (12 iterations), then converted to bind space
   through each vertex's own skinning map. That conversion is exact for LBS and DQS, so the result is applied before
   skinning like a morph target.

**Activation.**
- Elbow flexion only: the swing of the forearm relative to the upper arm, so twist and pronation don't trigger it.
- Zero below 30°, smooth ramp to full at 90°, held beyond.
- An earlier flexion measure (the angle between joint positions) mis-read the test poses: "135°" read as 124°.

## Results: v3, elbow flexion sweep (no corrective → with corrective)

| flexion | method | skin through skin (vertices / depth) | abnormal pinch | volume | legacy fold count |
|---|---|---|---|---|---|
| 0°, 30° | both | 0 → 0 | 0 → 0 | unchanged | unchanged |
| 60° | LBS | 0 → 0 | 37 → **0** mm | 0.86 → 0.82 | 0 → 0 |
| 60° | DQS | 0 → 0 | 12 → **0** mm | 0.93 → 0.91 | 0 → 0 |
| **90°** | **LBS** | **62 at 50 mm or more → 0** | 0 → 61 mm | 0.76 → 0.69 | 14 → 1 |
| **90°** | **DQS** | **47 at 32 mm → 0** | 0 → 37 mm | 0.89 → 0.84 | 8 → 0 |
| 110° | LBS | 162 → 162 | 0 → 0 | 0.70 → 0.63 | |
| 135° | LBS | 301 → 290 | 0 → 0 | 0.65 → 0.58 | 20 → 15 |
| 135° | DQS | 280 → 278 | 0 → 0 | 0.83 → 0.78 | 24 → 18 |
| 150° | both | about unchanged | 0 | −0.05 to −0.08 | |

- **Elsewhere:** on the full pose set (22 stress and 4 paced), only the two elbow poses change.
- **Follow/clear:** the elbow seam's worst case is still the 135° pose, slightly better (clearance −0.50 → −0.45 mm
  LBS, −1.57 → −1.28 mm DQS).
- **Render:** `elbow_corrective_compare.png` (top view). At 90° the red band of forearm-in-biceps becomes a clean
  contact crease; at 135° the contact is unchanged.

**Costs at 90°:**
- **Pinch** (61 mm LBS, 37 mm DQS): sharp bends at the edge of the flattened patch, outside the contact zone.
- **Volume** drops by 0.05–0.07, because flattening removes the overlap.
- **The optional volume-conserving bulge** (`CW_ELBOW_BULGE=1`) gives back about 0.03 at 90° (LBS 0.69 → 0.72, DQS
  0.84 → 0.87) at the cost of more pinch (61 → 78 mm LBS). It is off by default.

## Variants tried and rejected, recorded so they aren't retried blindly

| variant | result |
|---|---|
| a second key at 135° | made 110°–150° **worse**: intersections 301 → 343 at 135°, volume 0.65 → 0.28 |
| side decided by weights | missed the mixed crease vertices |
| 1.5 mm gap per side | surfaces ended 3 mm apart, just outside contact range, so the crease line scored as an abnormal pinch |
| distance-sphere region | reached the torso |
| first volume bulge | displacements up to 290 mm (torso in the region); fixed with the arm-only region, now capped at 15 mm |

## Why deep flexion (110° and beyond) is not solved by this method

At 135° the remaining intersections are **not in the elbow crease**:
- the forearm against the upper arm a median 13 cm and up to 24 cm from the elbow;
- the **hand** (62 vertices) reaching the **shoulder** (39 vertices).

That is whole-limb contact at the edge of anatomical range. Flattening onto one plane would remove about half the
arm's volume, because 170–200 cm³ of overlap has almost no surrounding skin to go to.

Options (decision needed; none is proposed as a hard limit):
- a deep-flexion shape built differently (forearm-flexor and biceps compression with redistribution along the limb);
- treating 110°–145° as accepted contact with only the crease line cleaned;
- an animation flexion guideline as a safety boundary (your stated fallback only).

## Engine delivery (stage 2): what REDengine offers, from the RED4 type definitions

| type | what it does |
|---|---|
| `animAnimNode_ApplyCorrectivePoseRBF` | an animation-graph node that applies **corrective joint poses**, chosen by RBF comparison of named joints against reference poses (fields: `correctives[]` with `comparePose`, `correctivePose`, `jointsToCompare`, plus `rbfCoefficient` and `rbfPowValue`) |
| `animAnimNode_SetDrivenKey` | drives joints from other joints' values |
| morph targets (`entMorphTargetSkinnedMeshComponent`, `MorphTargetMesh`) | weights set by the entity or script (character creation, face); **no animation-graph node found that drives a morph from a joint angle** |

Shipped meshes carry dedicated corrective joints (for example `l_knee_mscl_JNT` and `l_leg_back_A_mscl_JNT` in the
jeans). So CDPR's correctives are **joint-based**.

**Implication:** this shape is the validated *target*. Stage 2 converts it into RBF-driven corrective joints (a few
joints with weights in the crease patch, posed at the 90° key) and measures how faithfully joints reproduce it.
That conversion is OI-20.
