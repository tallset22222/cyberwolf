# Helper joints, pass 1: half-angle (partial-rotation) helpers

Status: **experimental, not adopted.** Nothing in the standard changed: core joints, sockets, seams, regions, poses
and the v2 base weights are untouched. The helper layer lives in `basebody/helpers.py`, is off by default
(`CW_HELPERS=1` enables it), and writes only to `reports/helpers_*`. **Isolation check:** with helpers off, test 2
reproduces the v2 baseline exactly. **Symmetry gate with helpers on:** passes (worst vertex 2.9e-16). Test 3 with
helpers: left and right agree exactly.

## Design (one rule for every helper; nothing tuned to a pose)

Helpers driven: the six spec helpers per side that sit at a joint (`hlp_shoulder`, `hlp_elbow`, `hlp_wrist`, `hlp_hip`,
`hlp_glute`, `hlp_knee`). Breast, belly and neck-front helpers are secondary-motion targets and stay out of scope.

- **Driver.** The helper takes a fixed fraction (0.5) of the child bone's rotation relative to its parent, pivoting at
  the core joint. Hip and glute share the hip joint's driver.
- **Weights.** Where a vertex is split between the bones on the two sides of a joint (a on the parent side, b on the
  child side), STRENGTH × 2·min(a, b) moves to the helper, taken half from each side. Hip and glute split that by front
  and back. Every helper reads the same snapshot of the weights, so the result is independent of order and symmetric.
  Midline ties follow the same rule as the base weights. Vertices outside the joint zones keep their v2 weights exactly.
- **One global strength value** (0.25 / 0.5 / 0.75 / 1.0) was swept and judged on all 22 poses together.

## Results

### Test 2 metrics across all 22 poses

| strength | LBS violations | LBS folded faces | LBS worst volume deviation | DQS violations | DQS folded faces | DQS worst volume deviation |
|---|---|---|---|---|---|---|
| none (v2) | 32 | 103 | 0.59 | 23 | 86 | 0.43 |
| 0.25 | 30 | 99 | 0.55 | 24 | 90 | 0.42 |
| 0.5 | 32 | 103 | 0.49 | 25 | 104 | 0.40 |
| 0.75 | 29 | 131 | 0.41 | 25 | 119 | 0.38 |
| 1.0 | 34 | 148 | 0.33 | 27 | 130 | 0.36 |

### Key poses (volume / stretch p95 / folded faces), no helpers → helpers at strength 1.0

| pose | LBS | DQS |
|---|---|---|
| shoulder overhead | 0.77/1.76/17 → 1.12/1.96/20 | 1.43/2.06/6 → 1.36/2.09/16 |
| shoulder across chest | 0.55/1.45/27 → 0.82/1.53/17 | 0.93/1.58/31 → 0.94/1.58/16 |
| elbow 135 | 0.65/1.22/20 → 0.73/1.28/50 | 0.83/1.41/24 → 0.84/1.41/46 |
| hip flexion 90 | 0.61/1.31/0 → 0.95/1.44/2 | 1.03/1.52/0 → 1.03/1.51/2 |
| knee 135 | 0.41/1.20/11 → 0.67/1.38/17 | 0.83/1.57/0 → 0.84/1.54/8 |

### Follow/clear, both sides (strength 1.0): skin-weighted clearance mm, and rigid overlap needed mm

| seam | clearance LBS | clearance DQS | rigid overlap LBS | rigid overlap DQS |
|---|---|---|---|---|
| shoulder | −1.35 → −1.48 | −1.27 → −1.25 | 17.0 → 15.2 | 11.9 → 12.6 |
| elbow | −0.50 → **−1.81** | −1.57 → −1.41 | 26.2 → 32.2 | 36.2 → 36.9 |
| knee | −0.01 → **−1.29** | −0.15 → **+0.26** | 38.2 → 57.3 | 57.1 → 59.4 |
| hip | +1.25 → +1.27 | +1.43 → +1.40 | 30.1 → 28.1 | 22.9 → 24.0 |
| waist | +1.65 → +1.56 | +1.59 → +1.53 | 22.7 → **15.1** | 17.2 → 17.9 |
| neck_base | +1.06 → +1.08 | +1.22 → +1.05 | 17.4 → 20.3 | 18.3 → 20.0 |

All other seams change by less than 2 mm. Render: `compare_base_vs_s1.png` (red = stretch > 1.3×, blue = compression < 0.75×).

## Findings against the four targets

1. **Shoulder: not solved.** Armpit volume is recovered under LBS, but overhead overshoots to a bulge (1.12) and the
   lateral-ribcage stretch is unchanged. DQS's rounded deltoid lump is unchanged. The cuff is still pierced. The
   renders show the problem is *which skin slides where*, the side of the ribcage and the top of the shoulder, which
   a rotation-blend helper cannot address.
2. **Hip: partly.** Under LBS the volume is restored (0.61 → 0.95), but groin stretch rises (1.31 → 1.44), so the
   transition holds volume at the cost of stretch. Under DQS nothing changes, since it already behaved like this. The
   hip cuff still passes.
3. **Elbow and knee: volume yes, folding no.** LBS no longer collapses to a point (visibly better at elbow 135). But
   the extra skin kept in the inner crease is where forearm meets biceps, or calf meets thigh, and the folded-face
   count and the cuff clearance both register that contact as failure. **The folded-face metric cannot tell crease
   contact from bad folding**; a contact-aware measure is needed before the elbow and knee can be judged.
4. **Cuffs:** no seam's status would change. The waist under LBS improves enough that 20 mm would hold under both
   methods.

**LBS + helpers vs DQS + helpers.** Half-angle helpers make LBS behave roughly like DQS (similar volume and stretch)
and barely change DQS. They do not separate the two methods in either direction. The skinning decision (OI-06)
therefore can't rest on this helper type; it depends on what the next helper type does.

**Verdict:** half-angle helpers are a sound, symmetric, isolated LBS volume fix, but they do **not** meet the
deformation goals. They are not proposed for the standard in this form.

## A finding about the test poses (needs a decision)

The shoulder poses put almost all of the motion in the shoulder joint itself:

| pose | total elevation | clavicle/scapula | shoulder joint |
|---|---|---|---|
| overhead | about 180° | 20° | about 160° from arm-down |
| across-chest | 0° protraction | 0° | 103° from rest |
| forward flexion 90 | 0° | 0° | 81° from rest |

Real shoulders move about 2:1, roughly 120° at the shoulder joint and 60° from the shoulder blade, and game animation
normally moves the clavicle. Our shoulder tests are therefore a **worst case beyond anatomical range**. That partly
explains why the shoulder fails everything. It does not make the shoulder fine: the deltoid lump and the side
stretch also appear at horizontal.

## Proposed pass 2 (for review)

1. **Corrective translation helpers** at the spec's anatomical positions:
   - deltoid;
   - olecranon and elbow crease;
   - patella;
   - front hip crease;
   - gluteal fold.

   Each is driven by its joint angle along an anatomically defined direction, with one gain per helper *type* set
   from anatomy (for example, a fraction of the limb radius), not from test results.
2. **A contact-aware crease metric:** separate inner-crease self-contact (expected at deep flexion) from folding of
   free skin, so the elbow and knee can be judged fairly.
3. **Shoulder poses (decision):** either keep the current shoulder poses as a stress test and add
   anatomically-paced variants alongside them (no existing result is invalidated), or define a shoulder-rhythm rule
   (clavicle follows arm elevation) as an animation-side requirement. A procedural clavicle driver would move a
   *core* joint, which the standard reserves for animation, so it is not proposed.
