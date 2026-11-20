# Base weights v3 (candidate): anatomical rules on top of v2

Status: **candidate, awaiting acceptance.**
- `CW_WEIGHTS=v3` selects it, and v2 remains the default.
- v2 and all its reports are unchanged; with the default settings the v2 baseline reproduces exactly.
- Same mesh, skeleton, sockets, seams, region map and pose set (the 22 stress poses plus 4 paced).
- No helpers.
- Symmetry gate: **pass** (worst vertex 2.1e-16).
- Test 3: left and right agree exactly.

## What v3 changes

v3 is the v2 recipe plus two anatomical rules. Both are **smooth ramps, applied before and after the smoothing passes**,
so no hard cut-off is introduced (`test2_deformation._anatomical_rules`):

1. **Laterality.** A left or right bone's influence on skin of the *opposite* side fades smoothly to zero within 4 cm of
   the midline. The midline itself stays shared equally by both sides.
2. **Thigh boundary on the torso.** Thigh influence fades out above the hip joint:
   - front: +8 cm (the upper end of the inguinal ligament) to +14 cm (just below the navel, at +13.5 cm);
   - back: +10 to +18 cm (the buttock moves with the thigh up to the iliac crest);
   - with a smooth front/back blend.

**Tried and rejected, recorded so they aren't retried blindly:**
- **Olecranon ownership rule.** It wasn't needed: v2 already gives the elbow tip 0.93 forearm, and it added 7 sharp
  weight edges per side. (Correction to the pass-2 report: the "0.21" quoted there was the average over the helper's
  whole 45 mm patch, which includes upper-arm skin, not the olecranon itself.)
- **Thigh fade starting 2 cm above the hip.** It removed thigh weight from the lower abdomen, and the groin pinch grew
  from 126 to 217 mm. The fade was moved up to the inguinal ligament.
- **A continuous four-influence limit** (subtract the fifth weight). It doubled the sharp weight edges, from 57 to 118.
  Reverted; the hard top-4 cut stays.

## Defects fixed

| defect (from the pass-2 measure) | v2 | v3 |
|---|---|---|
| thigh weight on the navel | up to 0.084 | 0.000 |
| left-clavicle weight on the right breast | up to 0.230 | 0.000 |
| opposite-side weight more than 4 cm past the midline | max 0.234 (214 vertices > 0.01) | 0.000 (0 vertices) |

**Smoothness, as the weight jump across mesh edges:** v3 is no worse than v2. The 99th percentile is 0.235 for both,
with 54 edges over 0.3 in v3 against 57 in v2. 521 of 13,380 vertices changed by more than 0.05, at most 0.41; they
are in the pelvis, chest and abdomen.

## Deformation results: v2 → v3

Categorised measure, 26 poses, LBS and DQS:

| measure | v2 | v3 |
|---|---|---|
| total abnormal pinch length | 2,224 mm | **1,263 mm** |
| fold-over edges | 95 | **23** |
| self-intersection vertices | 1,085 | 1,084 (unchanged: deep-flexion contact is not a weights problem) |

| pose | pinch LBS | pinch DQS | other |
|---|---|---|---|
| spine flexion 45 | 437 → **0** | 414 → **0** | |
| spine twist 45 | 160 → **0** | 98 → **0** | the breast pinch from the left-clavicle weight is gone |
| spine side bend | 10 → 0 | 11 → 0 | |
| hip abduction 45 | 8 → 0 | 61 → 0 | volume 0.83 → 0.81 (LBS) |
| hip flexion 90 | 126 → 114 | 39 → 52 | stretch 1.31 → 1.35 (LBS) and 1.52 → 1.54 (DQS), so roughly neutral |
| **neck turn 70** | **211 → 298** | **208 → 323** | **regression**, see below |
| shoulder, elbow, knee, wrist, ankle | unchanged | unchanged | |

**The neck-turn regression.** It sits at the front of the throat, about 1 cm from the midline. Five influences of
similar size compete there (right clavicle 0.39, neck 0.22, spine 0.22, left clavicle and jaw about 0.16 each). The
hard four-influence cut keeps different fourth bones on neighbouring vertices. v3's slight laterality trim tipped one
vertex from the left clavicle to the jaw. The jaw's reach isn't the cause: there is no jaw weight more than 3 cm below
the chin in either version. **The cause is the four-influence limit in a region that genuinely needs five or more.**

**Follow/clear** (test 3, both sides, stress and paced). Every seam is identical to v2 except:
- **waist:** under LBS the rigid overlap needed drops from 22.7 to **16.2 mm**, so 20 mm now holds under both methods
  (resolves the OI-10 concern if v3 is accepted). Skin-weighted clearance rises to +1.95 (LBS) and +1.98 mm (DQS);
- **neck_mid:** −0.32 → −0.28 mm (DQS).

Renders: `events_v2_vs_v3.png` (yellow = abnormal pinch).

## Reassessment of the four areas on v3

- **Elbow:** unchanged. Its weights were already anatomically sound. The problem is deep-flexion self-intersection
  (the forearm 32 mm or more into the biceps at 90°, 50 mm or more at 135°), plus LBS volume loss. **This calls for corrective shapes (OI-18).**
- **Knee:** unchanged. Self-intersection at 135° (50 mm or more under LBS), and front-of-knee stretch under DQS (1.57).
  **Corrective shapes, tested separately from the elbow.**
- **Hip:** the abduction pinch is gone, and flexion is about neutral (groin pinch 114 / 52 mm). The groin crease remains
  the one hip problem. Consider it again after correctives; a helper only if it is still needed.
- **Shoulder:** unchanged by v3. As before, there are two distinct problems that must not be confused:
  1. **Stress-pose deformation.** The cuff pierce-through and the arm in the chest across-chest disappear in paced movement.
  2. **Real attachment geometry.** The rigid-cuff bulge is 25–39 mm in *both* pose sets, the DQS volume overshoots, and
     clavicle motion stretches the trapezius and neck.

  The shoulder-blade joint (OI-17) limits the paced poses.

## Decision needed

1. **Accept v3 as the working base weights** (v2 kept and reproducible), so that corrective shapes are built on it. The
   neck-turn regression is the cost, and it is recorded as OI-19.
2. **OI-19 (new):** the four-influence limit is too few where five or more bones genuinely meet (throat, hands, neck).
   Check what the target engine supports (eight influences would remove it) before designing around four.
