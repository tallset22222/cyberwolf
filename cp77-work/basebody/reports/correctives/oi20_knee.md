# OI-20 stage 2: the knee with corrective joints (offline fit)

17 Nov 2026. Weights v3. **Reference target: the accepted offline knee prototype** (keys at 90° and 135°; LBS with the
smoothed radial restore at the front of the knee; DQS without it). The prototype is unchanged; this is an isolated
experiment (`basebody/oi20_joints.py`, `CW_JOINT=knee`).

## Method

- Same corrective-joint model as the elbow. Each joint is parented to the bone it takes weight from, is identity at
  rest, and is mirrored for the right leg.
- **The knee needed a two-key fit.** The first fit set the joint weights on the 135° shape alone, then fitted the 90°
  offset with those weights fixed: LBS was 5.6 mm off at 90°.
  - **Fix** (`CW_OI20_JOINTFIT=1`): the weights are fitted to both keys at once, with one offset per key.
- **Interpolation** follows the prototype's own activation: zero to 30°, smoothstep to the 90° key, linear to the 135°
  key, held beyond. Offsets are slerped (rotation) and blended linearly (translation).
- **Variant `scaled`, LBS only:** joints may also scale, non-uniformly, within 0.7–1.4 per axis.
  - Reason: the prototype's front-of-knee radial restore is an *inflation*, which rotation and translation can't
    produce.
  - DQS can't represent scale, so this variant is LBS-only.
- **Left and right are tested independently.** Each leg is bent alone through a full sweep (0–150° in 5° steps).
  - The other leg is checked for any movement.
  - Right is compared with the mirrored left.
- **Bumps:** surface roughness (umbrella Laplacian) compared with the prototype, plus a shaded render.
- **New defects:** intersections, pinch and fold-over edges, compared with both the prototype and the uncorrected baseline.

## Finalists (budget 8)

| | LBS, 6 joints/leg, rigid | **LBS, 6 joints/leg, with scale** | **DQS, 8 joints/leg, rigid** |
|---|---|---|---|
| Max error vs prototype at 90° / 135° | 3.49 / 3.79 mm | **1.92 / 2.13 mm** | **1.08 / 1.89 mm** |
| Worst during activation, 35–85° / 95–130° | 3.31 / 4.03 mm | 1.99 / 2.82 mm | 1.08 / 1.81 mm |
| Prototype's own correction at 90° / 135° (for scale) | 9.3 / 26.2 mm | 9.3 / 26.2 mm | 2.2 / 14.7 mm |
| Intersecting vertices at 60/90/135° (prototype; baseline at 135°) | 0/0/0 (0; 116) | 0/0/0 (0; 116) | 0/0/0 (0; 58) |
| Fold-over edges at 135° (prototype) | **1 (0): rejected** | 0 (0) | 0 (0) |
| Pinch length at 135° (prototype) | 120.6 (107.6) mm | 120.1 (107.6) mm | 66.4 (49.7) mm |
| Roughness increase vs prototype, max | 1.59 mm | 1.37 mm | 0.94 mm |
| Exact rest; other leg; inactive library poses | exact; 0.0; 0.0 | exact; 0.0; 0.0 | exact; 0.0; 0.0 |
| Left vs right (mirror) | 9e-13 mm | 9e-13 mm | 3e-13 mm |
| `sit_hip90_knee90` vs prototype | 3.64 mm | 1.91 mm | 1.02 mm |
| Beyond the last key (150°) | 4.99 mm | 5.15 mm | 1.95 mm |

The shaded render (`oi20_knee_shaded.png`, roughly 1.2 mm per pixel) shows no visible bumps or shading breaks in any
finalist, and none are visually distinguishable from their prototype. The error maps (`oi20_knee_compare.png`) show
the residual spread smoothly, with no isolated spikes:
- LBS: a broad band over the front and top of the knee, where the radial restore sits;
- DQS: a thin line along the crease.

## Rejected

- **Every budget-4 configuration.** About 320–480 vertices exceed 4 influences, so the joints have to be trimmed to fit.
  - Trimming changes the non-knee pose `hip_flex_90` by 3.1–3.2 mm.
  - Errors are 7.9–12.7 mm.
  - New intersections appear at 135° (20–57 vertices; the prototype has 0).
- **"Replace" mode** (the joint takes its parent's whole slot): new intersections at 135° (LBS 82, DQS 26 vertices).
- **Rigid LBS**: 1 new fold-over edge at 135°, and errors up to 4 mm.
- **10 joints per leg** (LBS): fits worse than 6, because the fit settles on a poorer solution. More joints don't help
  past 6 (LBS) or 8 (DQS).

## Status (review, 17 Nov 2026)

- **Leading candidate: DQS, rigid joints, 8 per leg.** It avoids the unverified joint-scale assumption.
- **Secondary candidate: LBS with scaled joints, 6 per leg.**
- Neither is promoted. Each one's runtime requirements are to be investigated separately.
- The 2 mm figures are measured against the offline prototype. The prototype is itself an approximation, not a
  finished knee in motion.

## Findings

1. **The knee prototype can be reproduced by joint-driven correctives**, within about 2 mm and with no new defects, in
   both skinning methods, given 8 influences on the knee chunk:
   - DQS with rigid joints;
   - LBS only if the joints may scale.
2. **The knee is harder than the elbow.** The elbow LBS fit reached 0.08 mm. The knee's two keys differ in shape, and
   its LBS correction includes a radial inflation.
3. **Scaled corrective joints are an assumption.** REDengine joint transforms carry scale, but whether its corrective
   pose node applies non-uniform scale isn't verified. The fitted scales reach the 0.7/1.4 limits (up to 40% on one
   axis), so the result depends on scale being supported.
4. **Budget 4 fails for the knee as it did for the elbow.** This supports the proposed 8-influence budget at the knee.
   That budget is still only a proposal: Cyberwolf's runtime has to prove it supports 8 influences
   (`basebody/reports/evidence_transfer.md`).
5. **Beyond 135°**, error grows to about 5 mm for LBS. 150° waits for a gameplay need, as decided.

## What this does and doesn't establish

These results are engine-independent and conditional, as defined in `basebody/reports/evidence_transfer.md`. They
hold for a runtime that:
- uses standard LBS/DQS;
- has 8 influences at the knee;
- interpolates corrective joints the way this fit assumes;
- applies joint scale, for the LBS variant only.

They don't establish REDengine's RBF behaviour or Cyberwolf's runtime behaviour. The character standard is unchanged.

## Housekeeping

- Parallel runs first overwrote each other's result files. Those files were moved to `_oi20_overwritten/`, and every
  number here comes from clean single-configuration reruns: `oi20_knee_*_nj*_b*.json`.
- The elbow result was rechecked twice after the script was generalised, and reproduces exactly (0.08 mm at 90°).
