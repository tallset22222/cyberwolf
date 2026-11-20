# What transfers: classification of the evidence so far

17 Nov 2026. A standing note, updated as results come in. It changes nothing in the character standard.
**Baseline:** the classification as first completed is frozen in `evidence_baseline/evidence_transfer_2026-11-17.md`
(SHA-256 in `SHA256SUMS`). Later additions are listed under *Added after the baseline*.

**Engine-independent does not mean production-ready.** Every result in section 1 is conditional on Cyberwolf using
the same topology, skeleton and deformation assumptions.

**Roles.**
- **Cyberpunk 2077 and REDengine are the research subject.** Their extracted assets (the jeans mesh, the `man_base`
  rigs, shipped meshes surveyed for influence counts) are used here for technical research and preservation only.
  They never ship in Cyberwolf.
- **Cyberwolf (CyberUN) is the independent game being built.** It has its own character standard, skeleton,
  attachment system and eventual renderer. Its assets are created or appropriately licensed for it. The base body
  comes from the MakeHuman source distribution.

**Three categories.**
- **Engine-independent:** mathematics on our own mesh, skeleton and weights, computed by our own skinning code. It
  transfers to any runtime that implements the same skinning formula with the same data. That condition is the
  assumption to verify; it is not automatic.
- **REDengine-specific:** facts about REDengine, its file formats or WolvenKit. They say nothing about Cyberwolf's
  runtime, except as a reference design.
- **Requires validation in Cyberwolf's runtime:** anything that depends on how Cyberwolf will actually store, skin
  and drive characters, which doesn't exist yet.

## 1. Engine-independent

Each result holds provided the runtime meets the condition in the second column.

| Result | Holds provided the runtime… |
|---|---|
| Region map, seams, sockets, option A root loops (Tests 1–3) | uses the hm08 topology unchanged |
| Weight symmetry: v2 mirror-exact; v3 fixes navel, breast and clavicle cross-influence | skins with these weights as given (no re-weighting on import) |
| v3 vs v2 deformation figures (pinch 2,224 → 1,263 mm, fold-overs 95 → 23, waist overlap 22.7 → 16.2 mm) | uses standard LBS. The DQS figures assume our DQS convention (shortest-path quaternion blending, no scale), and other DQS variants differ |
| Influence count effect: 8 vs 4 removes the neck-turn regression, with the side effects measured; the import tube moves up to 28.6 mm when cut to 4 | supports the same number of influences per vertex |
| Offline corrective shapes: elbow 90° key; knee keys 90° and 135° (pose-space shapes with smoothstep activation, 30° to key) | can drive morph targets from joint angles, with the same activation curve |
| Corrective joints fitted to those shapes (6 joints/arm, budget 8: LBS 0.08 mm at 90°, DQS 2.1 mm; intermediate keys 0.50 mm) | uses standard LBS/DQS with ≥ 8 influences on the elbow, and interpolates the corrective joints the way the fit assumed (slerp + linear along the activation curve) |
| Quantiser: sum exactly 255, valid bytes, deterministic, slot-order independent, float weights authoritative, every dropped assignment recorded | stores weights as 8-bit normalised (UNORM8). With float or 16-bit weights, the quantiser isn't needed (or needs a different bit depth); the export-record rules still apply |
| Measurement tooling: metrics2 categories, the six corrective criteria, determinism proof method | (method only; re-run on the runtime's output) |

### 1b. Earlier findings, also engine-independent

These carry the same condition: the runtime uses the hm08 topology, our skeleton and standard skinning.

| Result | Notes |
|---|---|
| Per-seam overlap (15 mm mid-limb, mid-neck and wrist; 20 mm ankle, neck base and waist) and the seam-motion figures (Test 3) | Provisional (OI-01). The waist measured 22.7 mm under LBS on v2 and 16.2 mm on v3 (OI-10) |
| Skin-weighted cuff vs rigid cuff behaviour; `neck_mid` cuff grazing (OI-15) | Depends on the skinning method (OI-06) |
| Helper joints: pass 1 fixes LBS volume only; pass 2 didn't fix weight-caused defects | A negative result about local helpers on faulty weights; it holds in any LBS/DQS runtime |
| Skeleton findings: no scapula joint (OI-17); paced-shoulder rule (clavicle elevation = arm elevation / 6, protraction 0.2 × horizontal adduction) | Skeleton design, independent of engine |
| Rest pose 50.4° (OI-07), hip/shoulder option A root loops (OI-04) | Candidates; topology- and skeleton-level |
| Region map boundary types, the topology binding (`topology/hm08`), migration procedure (OI-11, not yet exercised) | Data contract of our own standard |
| Face cavity list (1,155 vertices) used to exclude the inner mouth and eyes from metrics | Measurement setup |

## 2. REDengine-specific (research findings)

| Finding | Status |
|---|---|
| Shipped meshes use 8 influences at LOD0 (93 of 119 surveyed chunks), 4 at LOD1 and below | Observed in Cyberpunk 2077's files. It is a *reference design* for Cyberwolf's per-chunk/LOD budget, not a requirement |
| Mesh format: `PS_SkinIndices1` / `PS_SkinWeights1` second set, UByte4N weights, Short4N positions, Kraken-compressed embedded buffers | Format fact; our reader handles both embedded and extracted buffers |
| WolvenKit import: weights remapped by bone name, glTF→RED axes (x, −z, y), node transforms ignored, each weight rounded to a byte separately with **no renormalisation** (8 × 0.125 → 256) | Read from source and confirmed by the import test |
| **8-influence import through WolvenKit 10.0.0-beta.2:** 360/360 vertices, 312/312 exact, 0 dropped, bind matrices unchanged | Verified for this build only; re-check later builds |
| Offline deformation of the imported mesh: exact vertices 0.000 mm from authored at 0–135° | Verifies the *data*. It assumes REDengine's shader reads bytes/255 without renormalising, which is **not observed in REDengine itself** (Cyberpunk 2077 can't run on this PC) |
| REDengine face and garment systems (garment support data in the import options) are not used or tested here | Out of scope |
| Correctives: `animAnimNode_ApplyCorrectivePoseRBF` (joint poses chosen by RBF), `animAnimNode_SetDrivenKey`; no node found that drives morph targets from joint angles | From type data; the RBF kernel (`rbfCoefficient`, `rbfPowValue`) is still unknown |

## 3. Requires validation in Cyberwolf's runtime

| Question | Why it matters | What would settle it |
|---|---|---|
| Skinning method: LBS, DQS or per region; and the DQS variant | Every deformation figure was measured under our formulas | Run the 22-pose suite through the runtime and diff against the offline results (surface error per vertex) |
| Maximum influences per vertex, and whether the budget can vary per chunk/LOD | Elbow correctives need 8 at the elbow; v3 is at 4 | The runtime's vertex format and shader limits; a test mesh like the import tube |
| Weight storage (UNORM8, 16-bit, float) and whether the runtime renormalises | Decides whether the quantiser applies and whether sums matter | Export the tube to the runtime format and re-run the deformation comparison |
| Corrective delivery: morph targets driven by joint angles, corrective joints, or both | The offline shapes are the reference; the delivery method decides which fit applies | Implement one corrective and re-run the six criteria in the runtime |
| Activation curve and interpolation between keys | Activation-path error dominates (1.0 mm vs 0.08 mm at the key) | Measure the runtime's curve; re-run the 30–90° sweep |
| Position and normal precision, LOD switching, attachment/cuff behaviour live | Sub-millimetre results can shift under quantised positions | Seam-motion test (Test 3) re-run in the runtime |
| Performance of 8 influences and corrective joints | Budget decisions | Profiling in the runtime |
| Axis and bind-pose conventions of the Cyberwolf export path | Our offline tests used the hm08/RED conventions | Round-trip test: export, import, compare bind pose |

## Not yet classifiable

Face validation (OI-09), the ribcage line (OI-13), the ear boundary (OI-12) and hand-refined boundaries (OI-14) have no
test results yet.

## Reading the gate results correctly

- The **WolvenKit import test** proves that WolvenKit keeps 8-influence data intact. That matters for the REDengine
  research and for any pipeline that passes through WolvenKit. It does **not** show that Cyberwolf's runtime supports 8
  influences.
- **Limits of the 8-influence result:**
  - It was measured on a 360-vertex test tube, not the full MakeHuman character.
  - The 48-vertex sentinel band is deliberately invalid diagnostic data, not a production result.
  - Deformation was reconstructed offline, not in Cyberwolf's renderer or a running REDengine.
  - The knee corrective prototype still needs its own validation.
- **Not established:** that Cyberwolf should use REDengine's mesh format. WolvenKit belongs to the research side.
  What is potentially reusable Cyberwolf technology is the skinning method, weight authoring, quantisation, symmetry
  checks and corrective research.
- The **elbow corrective-joint fit** proves that the joint-based mechanism *can* reproduce the shape under our skinning
  formulas. Whether a runtime reproduces it depends on that runtime (section 3).

## Added after the baseline

| Date | Result | Category |
|---|---|---|
| 17 Nov 2026 | Knee corrective joints, offline (`correctives/oi20_knee.md`). **Leading candidate: DQS with 8 rigid joints per leg** (1.08/1.89 mm at 90°/135°), which needs no joint scale. **Secondary candidate: LBS with scaled joints**, 6 per leg (1.92/2.13 mm). Rigid LBS rejected (fold-over). Neither is promoted | Engine-independent, conditional: standard LBS/DQS, 8 influences at the knee, the fitted interpolation; the LBS candidate also needs non-uniform joint scale. Measured against the offline prototype, which is itself an approximation, not a finished knee in motion |
| 17 Nov 2026 | Knee candidates' runtime requirements (`correctives/oi20_knee_runtime.md`). The joints need **5 influences** (4 base + 1 corrective) on 330 (DQS) / 484 (LBS) vertices, not 8. **This corrects how earlier entries describe the knee and elbow corrective-joint results: "8 influences" there means a second 4-slot set, needed because 5 don't fit in one; the earlier wording is left unchanged.** The elbow fit was checked the same day: also 5 (see the next row). The rotation blend method is irrelevant (≤ 0.17 mm). Piecewise interpolation between adjacent keys with an exact zero up to 30° is required, and generic inverse-distance RBF fails it. The scaled LBS candidate needs per-key scale frames that standard joints can't express (5.4 mm with a fixed frame). No non-unit joint scale in 967 sampled REDengine animations | Engine-independent requirements, conditional on the same mesh and skeleton. The REDengine items (QsTransform scale field; no scale use in the sample) are research findings |
| 17 Nov 2026 | Elbow corrective joints, influence count (`correctives/oi20_elbow_influence_count.jsonl`, 6 joints per arm, the accepted fits): **maximum 5 influences** (4 base + 1 corrective) on 390 (LBS) / 340 (DQS) of 13,380 vertices. Second-set data on the affected vertices only: 3,120 / 2,720 bytes. Elbow and knee patches lie on different limbs, so their counts add (DQS: 340 + 330 = 670 vertices). The elbow's interpolation requirements were **not** re-tested here | Engine-independent, conditional (as above) |
| 17 Nov 2026 | Elbow interpolation, tested independently (`correctives/oi20_elbow_interp.md`). Common with the knee: adjacent-key piecewise blending, an exact zero to the authored threshold (5° early leaks 0.13–0.16 mm), hold beyond the last key; generic inverse-distance RBF fails. Different from the knee: DQS gains nothing from the 50/70° keys but needs quaternion (not matrix) blending (+0.38 mm); LBS needs the intermediate keys (1.01 → 0.50 mm). Both arms identical. Elbow and knee corrective vertex sets don't overlap (verified): 670 vertices need a 5th influence (DQS), 688 are touched | Engine-independent, conditional |
| 17 Nov 2026 | **Decision (owner):** DQS with 5 influences is the primary research candidate for elbow and knee correctives; scaled LBS stays secondary research. Neither enters the character standard | Status |
| 17 Nov 2026 | Consolidated research draft: `correctives/EXPERIMENTAL_dqs_corrective_system.md`. Shared framework plus per-region specs. 26 working joints (an empty elbow joint was found and noted), 670 vertices at 5 influences. Elbow quaternion requirement explained by one 31.9° joint | Research draft; not part of the standard |

