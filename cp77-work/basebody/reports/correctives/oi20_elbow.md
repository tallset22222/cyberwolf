# OI-20 stage 2: the elbow with corrective joints (offline fit)

17 Nov 2026. Weights v3. The reference target is the accepted offline elbow shape (90° key, no bulge), unchanged.
Script: `basebody/oi20_joints.py` (isolated; no change to the skeleton, weights, shapes or game files).
Data: `oi20_elbow_{LBS,DQS}_{share,replace}.json`; intermediate-key variants `*_mk60.json`, `*_mk50-70.json`.

## What was built

REDengine's correctives are joint poses (`animAnimNode_ApplyCorrectivePoseRBF`), so the shape has to be expressed
as extra joints. Each corrective joint:

- is parented to one deforming bone (upper arm, its twist bones, or forearm), rests at the centre of a skin patch, and is
  identity at rest;
- takes a share of that same parent's weight on the vertices it drives, so whenever the corrective is inactive the skin
  follows exactly the bone it followed before;
- receives one rigid offset (rotation plus translation, relative to its parent), fitted together with the shares to the
  offline shape's posed displacement at 90°, separately for LBS and DQS;
- is mirrored for the right arm (joint, offset and weights).

Off the key, the offset is interpolated (rotation slerp, translation linear) along the offline shape's activation curve:
zero up to 30°, smoothstep to 90°. The engine's real RBF curve is unknown (Ghidra or an in-game test); this measures the
mechanism, not the kernel.

Two ways to fit the influence budget were tested:
- **share**: the joint is an extra influence;
- **replace**: the joint takes its parent's whole slot, so no extra influence is needed.

## The six criteria, best configuration (LBS, share, 6 joints per arm, budget 8)

| Criterion | Result |
|---|---|
| Surface error against the offline shape at 90° | mean 0.00, p95 0.02, **max 0.08 mm** |
| Clean crease at 90° | 0 intersections, pinch 60.6 mm (offline 60.7), 0 fold-overs |
| Smooth activation, 35–85° | max error **1.01 mm** at 65° (offline correction there: 7.2 mm). With intermediate keys at 50° and 70°: **0.50 mm** |
| Exact return to rest | 4 × 10⁻¹³ mm (numerical zero); exactly zero at 0–30° |
| No unwanted deformation | 0.000 mm outside the patch at every angle; **0.000 mm** on all non-elbow poses of the 22-pose library |
| Left/right symmetry | mirror error 9 × 10⁻¹³ mm |

Beyond the key (105–135°) the joints hold their 90° offset, and so does the offline shape. Error grows to 2.86 mm at
135°, and the deep-flexion contact matches the offline result (291 vs 290 intersecting vertices), as accepted.

## Fidelity vs joint count and budget (max error mm at 90° / worst 35–85° / worst change on other poses)

| | LBS share, budget 8 | LBS share, budget 4 | LBS replace | DQS share, budget 8 | DQS share, budget 4 | DQS replace |
|---|---|---|---|---|---|---|
| 2 joints/arm | 5.46 / 5.57 / 0 | 7.46 / 7.13 / 3.9 | 8.23 / 8.21 / 0 | 2.08 / 2.03 / 0 | 7.59 / 7.23 / 3.3 | 7.04 / 6.91 / 0 |
| 4 joints/arm | 2.65 / 2.70 / 0 | 7.46 / 7.13 / 4.4 | 7.39 / 7.38 / 0 | 2.08 / 2.03 / 0 | 7.59 / 7.23 / 5.1 | 5.91 / 5.81 / 0 |
| 6 joints/arm | **0.08 / 1.01 / 0** | 7.46 / 7.13 / 3.9 | 5.94 / 5.97 / 0 | **2.08 / 2.03 / 0** | 6.41 / 6.11 / 4.2 | 4.49 / 4.42 / 0 |

Crease at 90° (intersecting vertices; offline: 0 in every case):
- LBS share, budget 8: 0 / 21 / 0 for 2 / 4 / 6 joints per arm.
- DQS share, budget 8: 0 at every joint count.
- Every budget-4 and every replace configuration: 20–50 intersecting vertices.

## Findings

1. **The mechanism can reproduce the elbow shape**, given enough joints and influences. LBS with 6 joints per arm is
   effectively exact at the key. DQS stays at 2.1 mm at every joint count. That is a structural limit: DQS blends the
   joint's rotation non-linearly with the arm bones, so a share cannot scale the offset the way it does in LBS. 2.1 mm
   still keeps the crease clean.
2. **At budget 4, no configuration passes.** The v3 vertices at the elbow already use all 4 slots (334–390 vertices
   overflow).
   - Trimming them changes poses that don't bend the elbow by 3.3–5.1 mm, fails the "no unwanted deformation"
     criterion, and the crease intersects again (20–40 vertices).
   - Taking a whole slot instead (replace) keeps other poses exact, but the joint is then too coarse (4.5–8.2 mm), and the crease
     intersects again (27–50 vertices).
   - **Elbow delivery therefore needs budget 8 on the elbow chunk.** That depends on the WolvenKit import test, and it
     matches the proposed per-chunk budget (OI-19) with the elbow added to the "complex LOD0 areas".
3. **Matching at the key is not enough.** LBS with 2 joints per arm shows the same crease numbers as the offline shape at
   90° (0 intersections, 60.7 mm pinch) while being 5.5 mm off elsewhere in the patch. LBS with 4 joints per arm is closer
   (2.65 mm) but has 21 intersecting vertices. Only the surface error tells these apart.
4. **The activation path is the remaining fidelity gap.** A rigid joint offset in the parent's frame doesn't follow the
   same path as a rest-space shape faded in, so mid-activation error (1.0 mm at 65°) is larger than key error.
   Intermediate keys at 50° and 70° halve it (0.50 mm); one key at 60° gives 0.56 mm. Each intermediate key is one more
   corrective pose entry (`correctives[]`) in the RBF node. DQS gains nothing from them, since its error is set at the
   key itself.
5. The piecewise interpolation used here has kinks at the intermediate keys. The engine's RBF interpolation will be
   smooth, but its actual curve must be measured before the activation numbers can be trusted in-game.

## Bugs found and fixed during this stage

- **Wrong parent:** the first fit took weight from each vertex's own twist bone, but parented the joint to the group's
  dominant bone. As a result, forearm pronation moved the skin by up to 6.7 mm. Fixed: each joint is parented to the bone
  it takes weight from.
- **Correction applied twice:** filling the delta cache switched the authoring flag off. So the first fit in every process
  had its target built with the correction applied twice. Those results were invalidated and moved to
  `_oi20_invalid_firstfit/`; every number above comes from the corrected script.

## Influence count (added 17 Nov 2026)

The accepted fits (6 joints per arm) need at most **5 influences** per vertex: the 4 v3 base influences plus 1
corrective. That applies to 390 vertices (LBS) / 340 (DQS) of 13,380. "Budget 8" above means a second 4-slot set,
needed because 5 don't fit in one set of 4. Budget 4 fails because there's no free slot.
(`oi20_elbow_influence_count.jsonl`, `basebody/oi20_influence_count.py`)

## Open

- **Knee:** two keys (90°, 135°), with a radial LBS restore; next in order.
- **RBF kernel:** `rbfCoefficient`, `rbfPowValue` (Ghidra or an in-game test).
- **Joint naming and attachment:** how new corrective joints are added to the rig (`.rig` / `.animgraph` authoring).
  This needs a WolvenKit-side study.
- **In-game comparison** against this offline reference.
