# OI-19: the vertex-influence limit (4 vs 8), investigated

Status: **evidence gathered; no change adopted.**
- The setting is `CW_INFLUENCES` (default 4, which is unchanged).
- v3 at 4 influences reproduces exactly.
- The attachment standard v0.2 (part 2, validation) still says "at most 4 influences per vertex". Adopting 8 would amend it.

## 1. What the engine supports, from shipped game data

`tools/influence_survey.py` (read-only) surveys the 55 Cyberpunk 2077 meshes already extracted in the workspace
(`basebody/reports/oi19_influence_survey.json`). Skin influences are declared in **sets of 4** (`PS_SkinIndices` /
`PS_SkinWeights`, `PT_UByte4` / `PT_UByte4N`), and a chunk declares one or two sets: 4 or **8 influences**.

| LOD | chunks | declare 8 | vertices actually using more than 4 |
|---|---|---|---|
| 0 | 119 | 93 | **27.5 %** |
| 1 | 93 | 12 | 0.0 % |
| 2 | 77 | 6 | 0.0 % |
| 3 | 56 | 9 | 0.0 % |

**At LOD0, CDPR ships bodies, heads and garments with 8 influences:**
- Judy's body: 17 % of vertices use more than 4;
- heads: about 35 %;
- Judy's pants: 23 %; the gangster jacket: 43 %.

**From LOD1 down, everything is reduced to 4.** Small rigid parts (nails, shoes, shadow meshes) use 4 throughout.

## 2. Import vs runtime

- **Runtime:** shipped meshes render with 8, so runtime skinning supports 8.
- **Import:** the community WolvenKit workflow supports 8. The redmodding wiki's weight-painting guide has modders set
  Blender's *Limit Total* from 4 to 8 before export and import (wiki.redmodding.org, "Weight Painting for Gonks").
  Our export would write two glTF sets (`JOINTS_0/1`, `WEIGHTS_0/1`). **Still to confirm** with an actual
  WolvenKit import of a Cyberwolf test mesh, which needs the owner's PC.

## 3. Through the complete rendering pipeline

The evidence that 8 works end to end is CDPR's own use of it on hero-character LOD0 meshes. Their LOD policy (8 at
LOD0, 4 below) shows where they budgeted it.

## 4. Performance

**Not measured in-engine.** That needs in-game profiling on the owner's PC; it is optional, and RenderDoc is not a blocker.

- **Structure of the cost:**
  - influences come in sets of 4 per chunk, so 5 to 8 costs the same as 8;
  - each vertex stores 8 more bytes;
  - the skinning shader blends 8 matrices for every vertex of a chunk that declares 8.
- **The modding documentation's warning:** 8 influences on skinned meshes with physics take significantly longer per
  frame to compute in the modding tools.
- **Mitigation that CDPR already uses:** 8 at LOD0 only, 4 at LOD1 and below. Because the count is set per chunk, 8
  could also be limited to the chunks that need it.
- **How much of our body needs it:**
  - 886 of 13,380 vertices (6.6 %) carry more than 5 % of their weight beyond the fourth influence (hands, upper back, neck);
  - beyond a sixth influence, only 4 vertices.

## 5. Does 8 improve the deformation? (v3 weights, everything else identical)

| measure | v3 at 4 | v3 at 8 |
|---|---|---|
| **neck turn 70 pinch** (LBS / DQS) | 298 / 323 mm | **0 / 0** |
| neck turn stretch p95 | 1.37 | 1.28 |
| neck flexion 40 pinch | 46 / 34 mm | **0 / 0** |
| total pinch length, 26 poses × 2 | 1,263 mm | **639 mm** |
| fold-over edges | 23 | 18 |
| self-intersection vertices | 1,084 | 1,073 (deep flexion is not an influence problem) |
| **neck_mid skin-weighted cuff** (LBS / DQS) | −0.11 / −0.28 mm | **+1.69 / +1.82 mm** (closes OI-15) |

**Costs and regressions at 8:**
- **hip flexion, DQS:** pinch 52 → 130 mm;
- **paced across-chest:** pinch 13 → 33 mm (LBS) and 2 → 20 mm (DQS);
- **shoulder overhead, DQS:** stretch 2.06 → 2.14, and the rigid-cuff bulge 39.6 → 44.1 mm;
- **wrist:** rigid overlap needed 14.4 → 15.1 mm, just over the 15 mm value.

All of these stay symmetric: left and right agree exactly, and the symmetry gate passes with 8.

## Recommendation (for decision; nothing adopted)

8 influences at LOD0, matching CDPR's practice, is **justified for the throat and neck**. It removes the v3 regression
and closes OI-15.

Before adopting it:
1. Confirm a WolvenKit import of an 8-influence test mesh on the owner's PC.
2. Decide whether to accept the hip-flexion DQS and wrist side-effects or address them.
3. If adopted, amend part 2's "at most 4 influences" rule to "8 at LOD0, 4 at LOD1 and below".
