# Knee corrective shape, stage 1 (the shape; engine delivery is stage 2, OI-20)

Status: **prototype; contact solved through 135°; front-of-knee volume under LBS only partly solved; not adopted into
the standard.**
- Enabled with `CW_CORRECTIVES=knee` (off by default; with it off, v3 reproduces exactly).
- Built on v3 weights at 4 influences, developed independently of the elbow.
- It shares the elbow's authoring code (`correctives.py`, now generic per joint). After that refactor the elbow
  deltas are bit-identical to the validated elbow stage 1.

## How the knee differs from the elbow

- **No contact at 90°:** skin first passes through skin after 110° (at 135°: calf into hamstring, 116 vertices under LBS
  and 58 under DQS). So the knee keys are **90° and 135°**. The 90° contact key alone does nothing (it moves at most 2 mm).
- **The contact stays local** at 135°, so flattening onto the bisector plane works there. At the elbow it didn't,
  because the whole forearm met the biceps and the hand reached the shoulder.
- **The front of the knee differs by method:**
  - LBS collapses (volume 0.62 at 90°, 0.41 at 135°);
  - DQS keeps its volume (0.90 / 0.83) but stretches (1.36 / 1.57).

## Components (all zero at rest, activated by knee flexion only, mirrored to the right leg)

| component | what | used for |
|---|---|---|
| contact | the elbow method: back-of-knee skin flattened onto the bisector plane; side from rest anatomy; thigh, knee and shin skin only | LBS and DQS |
| front radius restore | front-of-knee skin pushed back to its rest distance from the hinge axis, **smoothed over the surface** | LBS only (DQS has no collapse) |
| front relaxation | tangential slide toward rest edge lengths, with the normal removed so the silhouette is kept | LBS only (on DQS it only added area growth: 0.3 → 3.4 % at 90°) |

## Results (v3, knee flexion sweep, no corrective → final corrective)

| flexion | method | skin through skin | abnormal pinch | volume | stretch p95 |
|---|---|---|---|---|---|
| 0°, 30° | both | 0 | 0 | unchanged (0.0 mm moved) | unchanged |
| 60° | LBS | 0 | 0 | 0.79 → 0.82 | 1.15 → 1.18 |
| 90° | LBS | 0 | 0 | 0.62 → 0.68 | 1.19 → 1.22 |
| 90° | DQS | 0 | 0 | 0.90 → 0.90 | 1.36 → 1.36 |
| 110° | LBS | 0 | **75 → 0** mm | 0.51 → 0.56 | 1.20 → 1.23 |
| **135°** | **LBS** | **116 at 50 mm or more → 0** | 0 → 108 mm | 0.41 → 0.42 | 1.20 → 1.21 |
| **135°** | **DQS** | **58 at 15 mm → 0** | 67 → 50 mm | 0.83 → 0.84 | 1.57 → 1.57 |
| 150° | both | about unchanged (past the last key) | | | |

- **Full pose set:** only `knee_flex_90` and `knee_flex_135` change.
- **The sit pose** is scored around the hip, so it didn't show a change. Measured around the knee it behaves like
  `knee_flex_90` (LBS volume 0.62 → 0.75 with the unsmoothed version).
- **Follow/clear, both sides** (left and right identical):
  - the **knee seam's skin-weighted cuff now clears**: −0.01 → **+0.44** mm (LBS), −0.15 → **+0.41** mm (DQS);
  - a rigid cuff under LBS needs more: 38.2 → 43.7 mm overlap, bulge 4.0 → 6.0 mm. The knee seam is already "relocate and retest" (OI-03).
- **Render:** `knee_corrective_compare.png` (side view). The back-of-knee red is gone at 135° under both methods.

## Front of the knee under LBS: the trade-off (no bump vs volume)

| radius restore | volume 90° / 135° | front bump at 135° (added local bump over 2 mm) |
|---|---|---|
| none | 0.62 / 0.37 | none |
| unsmoothed | 0.76 / 0.59 | **26 vertices, up to 12.6 mm** (a visible point on the knee) |
| 4 smoothing passes | 0.72 / 0.49 | 23 vertices, up to 5.3 mm |
| **12 passes (default)** | **0.68 / 0.42** | 5 vertices, up to 5.5 mm; none at 90° |

A visible bump is a defect, so the default is the smooth version. The front-of-knee collapse is an **LBS-only**
limitation that a corrective restores only partly; DQS doesn't have it. This is evidence for the skinning decision
(OI-06).

**Front-of-knee stretch under DQS (1.57 at 135°):** not treated. Tangential relaxation barely moved it (1.57 → 1.55)
and added area growth. Skin over a deeply flexed knee genuinely stretches a lot, so driving this below the generic
1.35 threshold would fight anatomy, not fix a defect. Flagged as a judgement for review.

## Defects found and fixed during development, recorded

- **The unsmoothed radius restore** left a 12.6 mm point at the front of the knee at 135°. It was found with a
  local-bump measure after it showed in the render.
- **The first smoothing** multiplied by the fade on every pass, so the field shrank to almost nothing. It was changed
  to smooth first and fade once.

## Open

- **Beyond 135°** (150°: 154 / 105 vertices of contact) is not covered. Whether deep kneeling needs a 150° key
  depends on actual animation use; it would need a gameplay reason, as you set for the elbow.
- **Engine delivery** (OI-20), shared with the elbow.
