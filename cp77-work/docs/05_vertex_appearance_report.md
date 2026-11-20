# 05 — Vertex attributes, appearance chain, and coverage

Analysis only. Nothing examined here was converted, exported or installed anywhere. At the end of the investigation,
the installation's modification times were checked against the initial manifest (see document 02, "Principles").
This check does not independently establish that file contents were unchanged.

Findings rest on the sample described in document 02: four meshes (a character body, a cyberware arm, a static prop
and a building) and three rigs. Machine-readable results and analysis scripts are kept in the author's private
workspace and are not included in this repository.

## 1. Vertex attributes
| Attribute | Encoding | Decode |
|---|---|---|
| Normal (stream 2, +0) | `Dec4`: 3×10-bit unsigned + 2-bit w | `c/1023·2−1` per axis |
| Tangent (stream 2, +4) | `Dec4` | as above; top 2 bits = handedness (0 → +1, 3 → −1) |
| UV0 (stream 1) | 2× float16 | direct |
| UV1 (stream 3, +4) | 2× float16 | direct |
| Colour (stream 3, +0) | RGBA8 | direct |
| Skin indices / weights (stream 0) | 4×u8 / 4×u8 normalized, one or two sets | weight/255 |
The 10-bit mapping follows the reference in WolvenKit's source (`MeshTools.cs`, `StructFunctions.cs`). It was then
checked independently against the data:

| Check | Jackie | Mantis Blade | Vending | Building |
|---|---|---|---|---|
| Normal raw length | 0.997–1.003 | 0.997–1.003 | 0.997–1.002 | 0.991–1.30 ¹ |
| Mean \|n·t\| | 0.0014–0.0017 | 0.0014–0.0018 | 0.0003–0.0032 | 0.0015–0.0029 |
| Vertex normals agree with face winding | 100% | 99.7–100% | 99.7–100% | 99.4–99.98% |
| Tangent follows +U | 99.2–100% | 99.9–100% | 99.6–100% | 83–86% ² |
| UV NaN | 0 | 0 | 0 | 0 |
Winding: consistent single sign across every mesh. The source data is right-handed and Z-up, with clockwise front
faces: in the decoded rigs, characters face +Y and the model's left side is at −X (e.g. `LeftFoot` x = −0.180,
`LeftToeBase` y > `LeftFoot` y). The WolvenKit source consulted documents a conversion to Y-up coordinates.
Vertex colour: one constant value per chunk in all four meshes (unused). UV1: Jackie LOD0–1 only (separate layout,
v range −0.99…0.53); zero elsewhere.
¹ Building LOD1–2 contain some non-unit normals (direction still consistent). ² Building: likely mirrored/rotated UV
islands without handedness flags — **uncertain**.

Skinning: indices always < mesh bone count; up to 8 influences; weight totals were checked
against the expected 255. 37 of 15,158 vertices (Jackie) and 6 of 103,501 (Mantis Blade) do not sum to 255; these are
recorded as exceptions, not as passing results. All other examined vertices sum to 255. `boneRigMatrices` are inverse bind matrices in row-vector form (W row =
translation): Jackie binds in the **A-pose** (172/172 bones within 0.23 mm; the reference pose is off by 0.38 m mean),
Mantis Blade binds in its rig's **reference pose** (64/64 within 0.022 mm).

## 2. How sections, slots, appearances and textures connect
```
mesh  renderChunkInfos[i] (section, lodMask)
  └─ appearance.chunkMaterials[i] ──► materialEntries[name] (slot → local instance)
        └─ CMaterialInstance { baseMaterial, params }
              ├─ base .mi  ──► … (child params override parent; chain ends at a .mt/.remt shader)
              ├─ textures (.xbm)  ── CBitmapTexture + rendRenderTextureBlobPC (BCn, mips)
              └─ multilayered.mt:  MultilayerSetup (.mlsetup) + MultilayerMask (.mlmask)
                     ├─ layer[k] ──► .mltemplate (colour/normal/rough/metal .xbm, tiling, preset tables)
                     │               + preset names (colorScale, rough/metal levels, normalStrength) → values
                     └─ mask[k]  ──► BC4 atlas tiles via tile table
```

### Jackie skin (4-level chain, all extracted and decoded)
`male_big_01_ca_pale.mi` (DetailNormal `t0_000_mb_base__nd01`) → `default_male_body_01_ca_pale.mi` (Albedo
`t0_000_ma__c_base_d03`, Normal `…_n03`, Roughness `…_rm03` — **man_average** textures) →
`default_body_01_ca_pale.mi` (TintColorMask, micro-detail scales 45/20) → `01_ca_pale.mi` (TintColor 171/155/150,
detail influences 0.8) → `base\materials\skin.mt`. Tattoo slot: `mesh_decal.mt` + `tattoo_mb__arm_l_01_jackie_welles.xbm`
(1024², BC7, alpha 0.85). Hologram appearance: `hologram.mt` with 23 scalar/colour parameters.

### Mantis Blade
Slot 0 skin: `female_arm_01_ca_pale.mi` → woman_average HQ arm textures → same `01_ca_pale.mi` → `skin.mt`.
Slots 1–3: 7 / 16 / 10 layers; 22 distinct templates; **304/304 preset references resolve** to template tables.

### Textures (headers only; pixel data not extracted)
72 textures in total: 16 character textures and 56 template/microblend textures. All resolved. Formats confirmed by size arithmetic
(BC7/BC5 = 1 B/px, BC1/BC4 = 0.5 B/px, ×4/3 for mips). Each texture's metadata records a logical
size, a PC size and a PC mip bias. For 28 of the 72 examined textures the PC size is smaller than the logical size
(e.g. logical 2048² stored at 1024² with bias 1; logical 4096² stored at 1024² with bias 2). Archive entry sizes
confirm that nothing larger than the PC size is stored. The logical size is what the metadata records; it is not
established here as the original authoring size.

### Mask tile tables
Per tile two u32 (decl offset, layer bitmask) for a full-res grid then a low-res grid, followed by declarations
(atlas tile x/y 10 bits each, scale shifts 4 bits each); 14 px tiles with 2 px padding in a BC4 atlas.
Validated on 5 masks: word count = 2×(full+low tiles) + declarations exactly; last declaration is the last word; 0
invalid atlas references; atlas byte sizes = BC4 exactly. Layer 0 never has full-res coverage (base layer).

## 3. Status

All statuses below apply to the examined sample.

**Decoded and validated**
Archive container, path hashing, Kraken segments · CR2W tables and property encoding · mesh blob header, layouts,
positions, indices, LODs · normals, tangents (+ handedness), UV0/UV1, colour · skin indices/weights · rig hierarchies,
reference and A-poses · inverse bind matrices and bind pose · body ↔ deformation rig ↔ cyberware rig relationships ·
material slots, appearances, instance chains and parameters · .mlsetup layers, .mltemplate textures/presets, mask tile
tables · texture formats, sizes, mips.

**Identified but not decoded**
Texture pixel data (BCn) and mask atlas pixels (BC4) — formats known, not decompressed. Shader behaviour of
`skin.mt`, `multilayered.mt`, `mesh_decal.mt`, `hologram.mt` (parameters known; how the shader combines them cannot be
determined from the examined resource data). Microblend application. Garment-support `ExtraData` stream (Jackie). `.anims` animation format — not
extracted. Entity/appearance files (`.ent`/`.app`) that assemble meshes into a character — not extracted.

**Uncertain**
Building tangent agreement (83–86%). The RDAR per-entry SHA-1 does not match the stored or decompressed bytes of a
test entry; what it covers is unknown (recorded as-is). Mantis Blade's 7 upper-arm bones bind to a body rig that was
not extracted (woman_average), so those 7 inverse binds are untested. The referenced decals `.mlmask` is absent from
the install.

## 4. Coverage
What this investigation examined, what it validated, and what remains open.

| Area | Status | Basis |
|---|---|---|
| Geometry: positions, topology, LODs | Validated | Index, stream and buffer bounds; LOD masks (all four meshes) |
| Vertex attributes: normals, tangents, UVs, colour | Validated, one uncertainty | Checks in section 1; building tangents 83–86% |
| Skinning and bind pose | Validated for the main and cyberware rigs | Inverse binds match the A-pose (character body) or the reference pose (cyberware rig); 7 upper-arm bones untested |
| Skeleton hierarchies | Validated | Topological order (all three rigs); A-pose composition (< 0.001 mm, rigs that have an A-pose) |
| Material references and parameters | Resolved | Instance chains to a base shader; 304/304 presets resolve |
| Texture and mask formats | Identified | Headers and size arithmetic; pixel data not decoded |
| Shader behaviour | Not examined | Cannot be determined from the examined resource data |
| Entity / appearance assembly (`.ent`, `.app`) | Not examined | Not extracted |
| Animation (`.anims`) | Not examined | Not extracted |

## 5. Provenance
At the time of this report, the investigation comprised 9 logged runs and 120 provenance records. Each record holds
the source archive, depot path, index SHA-1, per-segment offsets and sizes, a SHA-256 of the stored (compressed)
bytes, and a SHA-256 of each output file. The records are kept in the private workspace (see document 02).
