# OI-20: runtime requirements of the two knee candidates

17 Nov 2026. Approved scope: technical only. No skeleton or standard changes; both candidates and their reference
results are preserved. Script: `basebody/oi20_runtime_reqs.py`. Data: `oi20_knee_runtime_{DQS,LBS}.json`.

Candidates, refitted deterministically and identical to `oi20_knee.md`:
- **D**: DQS, 8 rigid joints per leg (leading);
- **L**: LBS, 6 scaled joints per leg (secondary).

Errors are the maximum distance from the offline prototype on the knee region, swept 0–135° in 5° steps.

## 1. Interpolation: what the fitted joints require

| Runtime behaviour | D: 0–135° max (35–85°) | L: 0–135° max (35–85°) | Rest (≤ 30°) | New defects at 110/135° |
|---|---|---|---|---|
| As fitted: smoothstep 30→90°, linear 90→135°, slerp + lerp | 1.89 (1.08) mm | 2.82 (1.99) mm | exact | none |
| Normalised quaternion lerp instead of slerp | 1.89 (1.08) | 2.82 (1.99) | exact | none |
| Component-wise matrix blend | 1.89 (1.08) | 2.83 (1.98) | exact | none |
| Linear activation instead of smoothstep | 1.89 (1.03) | 2.82 (2.27) | exact | none |
| RBF-style inverse-distance weights over key angles, power 1 | 4.47 | 8.02 | **0.78 / 1.60 mm: active below 30°** | none |
| … power 2 | 3.02 | 4.30 | 0.11 / 0.29 mm | none |
| … power 4 | 4.87 | 7.69 | 0.002 / 0.009 mm | none |

**Requirements found:**
1. **The rotation blend method doesn't matter.** Slerp, nlerp and plain matrix blending agree within 0.17 mm, because the
   offsets are small (≤ 11°). Any common method is acceptable.
2. **The activation curve's shape matters little:** linear instead of smoothstep changes errors by at most 0.3 mm. A
   linear ramp has a kink at 30°, though, so smooth activation, one of the six criteria, still favours smoothstep.
3. **What does matter is how weights are spread between keys.** The corrective needs piecewise blending between
   *adjacent* keys along a single driver (the knee's twist-free flexion angle), with an exact zero up to 30°.
   - A generic RBF over key angles fails both ways. Low powers leak activation below 30°, so the knee no longer returns
     exactly to rest. High powers sag between keys (up to 4.9 mm D, 7.7 mm L at 110°).
   - REDengine's `ApplyCorrectivePoseRBF` kernel (`rbfCoefficient`, `rbfPowValue`) is still unknown. Its exact
     behaviour decides whether it can meet this requirement; an explicit rest key or a compact kernel would be needed.
4. **The driver signal** is the twist-free swing angle between thigh and shin. For the hinge poses tested it equals the
   knee's flexion; poses with knee twist weren't tested.

## 2. Influences: what is actually needed

| | D | L |
|---|---|---|
| Vertices that gain a corrective influence | 330 of 13,380 | 484 of 13,380 |
| Influence histogram with correctives (count → vertices) | 3 → 1,539; 4 → 11,511; **5 → 330** | 3 → 1,539; 4 → 11,357; **5 → 484** |
| Maximum influences per vertex | **5** | **5** |

**Correction to earlier wording.** The corrective joints need **5 influences** on the affected vertices (the 4 v3
base influences plus 1 corrective), not 8. Budget 4 failed because there is no free slot, not because 8 are needed.
Vertex formats usually come in sets of 4, so 5 means carrying a second set: 8 slots, 3 of them unused on those vertices.

**Exact data cost** (UByte4 indices + UByte4N weights, 8 bytes per set):
- second set only on the vertices that need it: D 2,640 bytes, L 3,872 bytes;
- second set on the whole mesh: 107,040 bytes.
- A per-chunk budget would sit between the two, depending on how chunks are cut.

**Exact arithmetic** (multiply-adds per vertex):
- LBS: 66 with 4 influences, 114 with 8 (12 per influence + 18 to apply).
- DQS: about 62 with 4, about 94 with 8.
- Per frame: 16 (D) or 12 (L) extra corrective joints across both legs, each one key interpolation plus one 4×4 multiply.

**Not measured:** GPU and CPU time. They depend on a runtime that doesn't exist yet.

## 3. Non-uniform scale (candidate L)

- **Data format:** REDengine can carry it. A corrective entry names a `correctivePose` stored in an animation, and
  animation joint transforms are `QsTransform`s with a per-axis `Scale`.
- **No shipped evidence it is used:** of 967 decoded animations in the 48 cached animation sets, 278 carry scale keys,
  and every value is exactly 1. The sample is small, so this doesn't prove the engine lacks support; it just shows no
  sign of it.
- **The fitted scales need a different scale frame at each key.**
  - A standard joint (translate, rotate, scale) scales along a frame fixed by the joint's bind orientation.
  - The fitted 90° stretches lie 30–87% outside the 135° key's frame.
  - Forcing one fixed frame per joint (the 135° frame) raises L's error to **5.4 mm at 90°**. That is worse than rigid
    LBS (3.49 mm), though still with no new intersections or fold-overs.
  - So **L's 2 mm result needs per-key scale frames, which ordinary joints can't express.** Refitting under a
    fixed-frame constraint is possible future work and hasn't been tested.
- **Normals:** under LBS, transforming normals with the plain blended matrix differs from the correct inverse-transpose
  by up to 48° in the knee crease *even without correctives* (base weights only). With the scaled joints it is 49°, so
  scale adds no new normal-handling requirement. Inverse-transpose normals are already an LBS question at the knee.

## Summary for each candidate

- **D (DQS, rigid):** needs
  - DQS skinning with ≥ 5 influences on about 330 vertices per mesh (a second 4-slot set);
  - 16 extra joints;
  - piecewise interpolation between adjacent keys driven by knee flexion, exactly zero up to 30°.

  The rotation blend method is free. An RBF-only interpolator would not meet the requirements unless its kernel can.
- **L (LBS, scaled):** needs everything above (484 vertices, 12 joints), plus non-uniform joint scale **with a separate
  scale frame per key**. Standard joints don't provide that. With a fixed frame, L is worse than rigid LBS. Its status
  as secondary candidate is weakened, and the reason is recorded here.

Neither candidate is promoted. The character standard and skeleton are unchanged.
