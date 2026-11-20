# Helper joints, pass 2: anatomical landmark helpers, a new deformation measure, and paced shoulder poses

Status: **experimental; pass 2 not adopted; the standard is unchanged.**

**Isolation.**
- The helper layer is behind `CW_HELPERS`: `0` = off (the v2 baseline), `1` = pass 1, `2` = pass 2.
- With helpers off, the original 22 poses reproduce the v2 record exactly.
- Every comparison here uses the same mesh, skeleton, base weights and pose set.
- With pass 2 on, the weights pass the symmetry gate (worst vertex 1.7e-16), and test 3 agrees exactly on both sides.
- Every pass-2 driver returns exactly to rest: helper transforms are identity and the rest pose reproduces the mesh within 4e-13 mm.

## 1. A new deformation measure (`metrics2.py`), replacing the folded-face count for judging

Events are counted relative to the rest pose (touching fingers at rest don't count), within 25 cm of the pose's
focus joint, with the head cavities excluded.

| category | definition | meaning |
|---|---|---|
| **crease contact** | a vertex comes within 2 mm in front of skin that was more than 20 mm away at rest | normal; informational |
| **self-intersection** | a mesh edge passes through a distant triangle (exact test); depth is measured only for vertices connected to a real crossing | skin passing through skin |
| **fold-over** | neighbouring quads face nearly opposite ways (> 150°) | surface doubled back |
| **abnormal pinch** | a new sharp bend (dihedral +60° or more) *outside* any contact zone; count and length | pinching that isn't a crease |
| **crease line** | the same sharp bend *inside* a contact zone | the normal line of a crease; informational |
| **stretch / volume** | strain p95/p5, area growth and shrink, volume ratio | as before |

**Validation:**
- The rest pose gives exactly zero events.
- Benign poses (wrist, ankle, hip extension) give zero intersections.
- A first version that used "behind a distant plane" gave false hits at the ankle and wrist; the exact edge/triangle test removed them.
- Renders (`../metrics2_validation.png`) put the flags where anatomy says: forearm into biceps, arm into chest, calf into thigh, groin pinch.

**What it changes in the reading of the baseline:**
- **Elbow and knee:** almost no abnormal pinching or fold-over (0–4 edges). Their real problem is **self-intersection at
  deep flexion**: the forearm 32 mm or more into the biceps at 90° and 50 mm or more at 135°; the calf into the thigh at
  50 mm or more under LBS. The old fold count was mostly measuring this contact.
- **Shoulder:** no intersections or pinching in the stress poses except across-chest (the arm 48 mm into the chest). The
  shoulder problem is **volume and contour plus stretch**.
- **Hip flexion:** a real **groin pinch** (126 mm of pinched edges under LBS, 39 mm under DQS) plus buttock stretch (1.48–1.52).
- **New finding, automatic-weight defects:**
  - the navel carries thigh weight (up to 8 %), so it pinches in hip flexion;
  - 42 right-breast vertices carry *left*-clavicle weight (up to 23 %), so they pinch in the spine twist;
  - ~~the olecranon skin follows the upper arm (local blend 0.21)~~ **Corrected (weights v3 report):** the 0.21 was averaged over the 45 mm helper patch, which includes upper-arm skin. At the elbow tip itself v2 gives the forearm 0.93.

## 2. Anatomically paced shoulder poses (the 22 stress poses unchanged)

Four `_paced` poses reach the **same final arm direction** as their stress twins. One documented rule shares the
motion with the clavicle: elevation = arm elevation ÷ 6 (about 30° at full overhead), and protraction = 0.2 ×
horizontal adduction, weighted by how horizontal the arm is.

| pose | clavicle: stress → paced | shoulder joint: stress → paced |
|---|---|---|
| horizontal | 0° → 15° | 50° → 37° |
| overhead | 20° → 30° | 121° → 113° |
| forward | 0° → 22° | 81° → 74° |
| across-chest | 0° → 28° | 103° → 98° |

**Skeleton limitation:** there is no scapula joint, so the scapula's own upward rotation (about 30° more at full
elevation) can't be shared. That is why overhead only drops to 113°.

**Results without helpers:**
- **Across-chest self-intersection** drops from 110 vertices at 48 mm to 14 at 2 mm under LBS, and to 0 under DQS. It was
  mostly the unrealistic pose.
- **The shoulder cuff clears in paced movement:** skin-weighted clearance +0.31 mm (LBS) and +0.87 mm (DQS), against −1.35
  and −1.27 mm in the stress poses. The pierce-through came from the beyond-anatomical stress poses. The outward bulge
  under a rigid cuff stays at 25–39 mm in both sets.
- **But paced movement exposes a new weakness:** clavicle elevation stretches the trapezius and neck skin (across-chest
  stretch 1.45 → 1.71 under LBS), and DQS overshoots volume (1.29 forward, 1.32 across-chest). The weights between
  clavicle, spine and neck now matter.

## 3. Pass 2 helpers: design and results

Each helper owns a skin patch around its spec landmark, projected to the skin along its anatomical direction. The
weight falls off as (1 + cos)/2 over an anatomical radius: deltoid 80 mm, olecranon 45, patella 50, hip crease 60,
glute 80. One rule for all 26 poses; every driver is zero at rest.

| variant | base motion | correction |
|---|---|---|
| **2a** | anatomical fraction of the joint rotation: deltoid 0.5, olecranon 1.0, patella 0.5, hip crease 0.5, glute 0.25 | muscle thickness for deltoid (20 mm) and glute (30 mm): t = T0·(√(L0/L) − 1) from origin–insertion length |
| **2b** | the *local blend* read from the existing weights at the landmark, so the patch moves like its surroundings | the landmark moved to its anatomical position (olecranon on the ulna; patella at half the knee angle; hip crease anchored to the pelvis), plus the muscle term |

**Results** (volume / intersection vertices and depth / pinch length mm / stretch p95):

| pose | method | baseline | pass 2a | pass 2b |
|---|---|---|---|---|
| shoulder overhead | LBS | 0.77 / 0 / 0 / 1.76 | 0.80 / 0 / 140 / 1.76 | 0.80 / 0 / 139 / 1.76 |
| shoulder overhead | DQS | 1.43 / 0 / 0 / 2.06 | 1.43 / 0 / 56 / 2.06 | 1.43 / 0 / 56 / 2.06 |
| elbow 90 | LBS | 0.76 / 62 at 50 / 0 / 1.16 | 0.86 / 62 / 40 / **1.71** | 0.84 / 62 / 56 / **1.76** |
| elbow 135 | DQS | 0.83 / 280 / 0 / 1.41 | 1.00 / 293 / 148 / **2.40** | 0.78 / 282 / 222 / **2.10** |
| hip flexion 90 | LBS | 0.61 / 0 / 126 / 1.31 | 0.68 / 0 / **329** / 1.48 | 0.66 / 0 / **349** / 1.50 |
| hip flexion 90 | DQS | 1.03 / 0 / 39 / 1.52 | 1.01 / 0 / 65 / 1.60 | 0.97 / 0 / **241** / 1.71 |
| knee 135 | LBS | 0.41 / 116 at 50 / 0 / 1.20 | 0.46 / 116 / 0 / 1.27 | 0.46 / 116 / 0 / 1.27 |

**Follow/clear** (pass 2b, both sides, stress and paced):
- Every seam is unchanged except the elbow (clearance −0.50 → −1.41 mm LBS; rigid overlap 26 → 46 mm) and the knee
  (rigid overlap 38 → 47 mm LBS).
- Left and right agree exactly.

**Verdict: pass 2 does not improve any of the four targets, and it makes the elbow and the groin worse.** The muscle
term works as designed (deltoid +6 mm overhead, glute −2 mm in hip flexion) but is too small to matter.

**Why.** The renders (`compare_base_pass2b.png`) show the mechanism. A landmark helper whose motion differs from the
skin around it creates a discontinuity at its patch edge: stretch, a pinch, and at the elbow a spike. In pass 2b this
is worst exactly where the anatomical correction is largest, and that is where the **helper's target differs most from the surrounding blend**: the 45 mm olecranon patch averages
0.21 forearm (the tip itself is 0.93), and the groin crease is a 0.55 blend rather than anchored. *(Wording corrected
after the v3 work; see weights_v3.md.)* On these weights, local helpers fight the weighting instead of refining it.

## 4. What this means for the four targets

1. **Shoulder:** the cuff pierce-through is a stress-pose artefact (paced movement clears). The remaining problems,
   rigid-cuff bulge, DQS volume overshoot and neck/trapezius stretch under clavicle motion, are about how the
   girdle region is weighted. The missing scapula joint limits how far paced movement can go.
2. **Hip:** the groin pinch is real, and no helper variant reduced it. It sits where the weights blend pelvis and thigh
   across the crease and the navel picks up thigh weight.
3. **Elbow and knee:** volume loss is an LBS issue (DQS keeps 0.83–0.90). The main problem is **self-intersection at
   deep flexion**, which helper joints can't solve: no rigid transform keeps two surfaces from passing through each
   other. It needs pose-space corrective shapes or a contact-flattening step, or acceptance with limits.
4. **LBS vs DQS (OI-06):** still not decidable. Neither helper pass changes the relationship between them.

## 5. Recommendation (needs your decision)

1. **Anatomical base weights next (weights v3), before any further helper pass.** Build the weights from anatomical
   rules instead of pure distance and visibility:
   - bony landmarks belong to their bone (olecranon to the forearm, patella to the knee mechanism, malleoli and so on);
   - no contralateral influence (no left clavicle on the right breast);
   - no limb weight beyond its anatomical boundary (no thigh weight above the inguinal ligament or on the navel);
   - blend zones sized to each joint.

   v2 stays reproducible and archived, and v3 must pass the symmetry gate and the same tests on both pose sets. This
   changes the weights, so it is your call.
2. **Then one more helper pass on v3**, reusing pass 2's machinery. It is isolated, symmetric and exact at rest, and
   only its interaction with the weights failed.
3. **Elbow and knee self-intersection:** decide how deep flexion is handled: corrective shapes, contact flattening, or
   an animation-side flexion limit. Helper joints alone won't do it.
4. **Skeleton (later, at the v0.2 review):** the missing scapula joint limits anatomical shoulder motion; recorded as
   an open item, not changed now.
