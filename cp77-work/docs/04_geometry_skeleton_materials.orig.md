# 04 — Geometry, skeletons and materials (decoded)

Analysis only. Machine-readable results: `mesh_geometry.json`, `rig_man_big.json`, `rig_man_big_deformations.json`,
`rig_mantisblade_wa.json`, `materials.json`, `material_layers.json`. Tools: `cr2w_props.py`, `mesh_decode.py`,
`rig_decode.py`, `material_decode.py`, `layers_decode.py`.

## 1. CR2W property encoding (v195)
- Chunk data: 1 zero byte, then properties `u16 name, u16 type, u32 size(incl. itself)`, value; ends at name 0.
- Nested structs: same, each starting with a zero byte. Struct array elements: likewise, no size prefix.
- `array:T` and `static:N,T`: u32 count + elements. `handle:T`: i32 chunk index + 1. `rRef:T`: u16 import index (1-based).
- Single enum: u16 name. Bitfield enum (e.g. `EMeshChunkFlags`): u16 names terminated by 0.
- `DataBuffer`: u16 buffer index (1-based) → extracted as `.buffer{n-1}`.
- Some classes append raw binary after the property list (see `animRig`, `CMaterialInstance`).

## 2. Mesh geometry (`rendRenderMeshBlob`, header version 20)
Header: `renderLODs` (LOD switch distances, m), `renderChunkInfos[]`, `quantizationScale/Offset` (Vector4),
`vertexBufferSize`, `indexBufferSize`, `indexBufferOffset`, `renderBuffer` → one buffer holding all vertex streams,
then all indices.

Per render chunk: `vertexLayout.elements[]` (usage, type, streamIndex, usageIndex), `slotStrides[8]`,
`byteOffsets[5]` (start of streams 0–4 for this chunk), `numVertices`, `numIndices`, `chunkIndices.teOffset`
(byte offset within the index region), `lodMask` (bit n = present in LOD n), `renderMask` flags.

Stream layout observed:
| Stream | Contents | Stride |
|---|---|---|
| 0 | Position `Short4N` (+ skin indices `UByte4` ×1–2, weights `UByte4N` ×1–2, garment `ExtraData Float16_4`) | 8 static · 24 skinned (4 influences ×2) · 32 skinned + garment data |
| 1 | UV0 `Float16_2` | 4 |
| 2 | Normal + tangent `Dec4` (10:10:10:2) | 8 |
| 3 | Vertex colour `Color` + UV1 `Float16_2` | 8 |
| 7 | Per-instance transform / skinning data | supplied at runtime; no bytes in the buffer |

Position decode: `p = short/32767 × quantizationScale + quantizationOffset` (metres). Indices: `u16`.

Results (all chunks validated: max index < vertex count, every stream inside `vertexBufferSize`,
`indexBufferOffset + indexBufferSize ≤ buffer`):

| Mesh | LOD distances | LOD0 | LOD1 | LOD2 | LOD3 | Bounds (m) |
|---|---|---|---|---|---|---|
| Jackie body | 0 / 3 / 6 / 9 | 9,373 v · 17,024 t (2 chunks) | 3,609 v · 6,261 t | 1,706 v · 2,529 t | 470 v · 630 t | 1.146 × 0.502 × 1.505 (z 0.139→1.644) |
| Mantis Blade L arm | 0 | 103,501 v · 98,666 t (6 chunks) | — | — | — | 0.464 × 0.493 × 0.488 |
| Vending machine | 0 / 10 / 26 | 1,584 v · 1,979 t (3 chunks) | 1,192 v · 722 t | 360 v · 212 t | — | 3.000 × 1.646 × 4.002 |
| Rancho Coronado bldg 3 | 0 / 39.9 / 138.9 | 19,532 v · 11,630 t | 16,494 v · 8,662 t | 15,450 v · 7,673 t | — | 8.26 × 12.41 × 7.69 |

Notes: Jackie's body has 2 influence sets (8 bone weights per vertex) plus garment-support data in stream 0. The vending machine's
3.0 m × 4.0 m matches `w300_h400` in its name. The Mantis Blade is a single LOD at very high density.

## 3. Skeletons (`animRig`)
Binary tail after the property list: `int16 parent[boneCount]`, then `boneCount × 48 bytes` reference pose
(translation Vec4, rotation quaternion, scale Vec4). Verified: tail fully consumed; parents topologically ordered;
for rigs with an A-pose, composing `aPoseLS` up the parent chain reproduces `aPoseMS` to < 0.001 mm.

**man_big.rig** — 71 bones, retargets from `man_base.rig`, tags `man/big`. Root → {Trajectory, Hips,
reference_joint}; Hips (1.006 m) → Spine…Spine3 → shoulders/arms/neck → Head (1.734 m); Hips → UpLeg → Leg (0.537 m)
→ Foot (0.095 m) → Heel/ToeBase. Fingers 3 segments (thumb 2), plus `*InHand*` and Weapon sockets.
LOD split at bones 27 / 71 (`distanceCategoryToLodMap` 0,1,1,1,2). 37 named body-part masks for animation
layering; 22 ragdoll bodies.

**man_big_deformations.rig** — 181 bones = 65 bones identical to the main rig (same parent, same reference pose)
+ 116 deformation joints (`*_JNT`). 88 attach directly to main-skeleton bones (Spine3 18; each forearm 6; each lower
leg 4; each thigh 3; every finger segment), 28 chain from other deformation joints. Types: muscle (`*_mscl_JNT`),
surface/outer (`*_out_JNT`), twist/segment (`SHL_n`, `Wrist_n`, `calf_n`).

**Jackie body ↔ rigs:** 172 mesh bones = 61 from `man_big.rig` + 111 deformation joints. All 172 resolve against
main + deformation rig. `lodBoneMask` drops 80 bones after LOD0 — all 80 are deformation joints; the main skeleton stays at every LOD.

**a0_003_wa__mantisblade_skeleton.rig** — 160 bones, tag `mantisBlades`, no A-pose. Rooted at
`LeftForeArm`/`RightForeArm` (no upper arm). Per side: forearm twist ×3 → wrist suspension chain ×4 → inner wrist →
`wrist01_GRP` → a complete replacement hand (4-segment fingers with knuckle muscle joints) and the blade
assembly (`blade01–05`, `bladePiston01`, `bladeHinge01–03` with `*_target` and pole-vector helpers for IK,
`blade_eff`/`blade_pv` effectors). Animation tracks: `leftBladeIkBlend`, `rightBladeIkBlend`.

**Mantis Blade mesh ↔ rigs:** 71 mesh bones; 64 resolve in the cyberware rig; the other 7 (`LeftArm`,
`l_SHL_0_JNT`, `l_triceps_mscl_JNT`, `l_biceps_A_mscl_JNT`, `l_elbow_bend_A/B_mscl_JNT`, `l_elbow_back_mscl_JNT`) are
body-rig names (present in the man_big main+deformation set; the female variant's own body rig was not extracted).
So the cyberware mesh is skinned across two skeletons: body rig to the elbow, cyberware rig from the forearm down,
joined by name at `LeftForeArm`.

## 4. Materials
Mesh `materialEntries[]` = named slots (`index`, `isLocalInstance`). Local instances live either as
`CMaterialInstance` chunks in the mesh or as small embedded CR2W files in the local material buffer
(`rawDataHeaders` give offset/size). `meshMeshAppearance.chunkMaterials[]` maps each render chunk to a slot name, one
list per appearance. `CMaterialInstance` parameters are a binary tail: `u32 count`, then per entry
`u32 size, u16 name, u16 type, value`.

| Mesh | Slots | Appearances |
|---|---|---|
| Jackie body | `_body` → `male_big_01_ca_pale.mi` (shared skin); `tattoo` → `mesh_decal.mt` with diffuse `tattoo_mb__arm_l_01_jackie_welles.xbm`, alpha 0.85; `hologram` → `jackie_hologram.mi` | `default` (body/tattoo alternating per chunk), `hologram` |
| Mantis Blade | slot 0 skin `female_arm_01_ca_pale.mi`; slots 1–5 `multilayered.mt`, each = MultilayerSetup + MultilayerMask | `default` |
| Vending machine | decals (`generic_tech_01.mi`), multilayered body, neon (`neon_tubes.mt`, EmissiveEV 6, colour 0/197/30), `metal_base.remt`, alternate `terracognita` setup | `default` (neon on), `off`, `off_terracognita` (same mask, different layer setup) |
| Building 3 | 1 slot → `metal_base.remt` | `default` |

### Multilayered materials (`.mlsetup` / `.mlmask`)
`Multilayer_Setup.layers[]`: per layer a material template (`.mltemplate` from `base\surfaces\materials\…`),
`colorScale`/`roughLevelsOut`/`metalLevelsOut` (named presets in the template), `matTile`, microblend texture + tile
+ strength, opacity. `Multilayer_Mask`: one greyscale mask per layer, stored as a tiled atlas
(`rendRenderMultilayerMaskBlobPC`: atlas + tile index buffers).

| Setup | Layers | Template families | Mask |
|---|---|---|---|
| mantisblade midpoly1 | 7 | metal 4, plastic 2, ground (dirt) 1 | 7 × 1024², atlas 1024×2976 |
| mantisblade midpoly2 | 16 | metal 11, plastic 4, dirt 1 | 16 × 1024², atlas 2048×2864 |
| mantisblade misc | 10 | plastic/rubber/carbon 8, fabric 2 | 10 × 1024², atlas 1024×1792 |
| mantisblade nails | 20 | plastic 20 (19 untinted) | 1 × 2×2 placeholder |
| mantisblade decals | 5 | all `special\unused` | referenced mask not present in any archive |
| vending machine | 9 | plastic 4, steel, glass, grime, dust, paint | 9 × 256², atlas 256×400 |
| vending terracognita | 9 | peeling paint 5, steel, glass, grime, dust | shares the vending mask |

Layer count = mask count wherever both are real. The nails and decals slots are effectively stubs. The vending
machine's alternate look is achieved by swapping only the layer setup over the same mask.

## 5. Extraction log for this round (analysis inputs)
- `sample2.json`: `man_big_deformations.rig`
- `sample3.json`: 7 `.mlsetup` + 5 `.mlmask` referenced by the meshes (1 referenced mask absent from the archives)
- `sample4.json`: `a0_003_wa__mantisblade_skeleton.rig`

## 6. Not decoded
Normal/tangent unpacking and UV values are identified by type but not dumped. Mask atlas tile tables are
sized but not unpacked. `.mltemplate` contents, textures (`.xbm`) and animation (`.anims`) are not extracted.
