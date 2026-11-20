# 03 — Structure of the extracted resources

Source: `extract\raw\`, produced by one run of `extract.py` from the main GOG archives.
All five are CR2W version 195. Machine-readable detail: `cr2w_structure.json`.

## CR2W layout (common to all)
- Header 40 bytes: `CR2W`, u32 version, u32 flags, u64 timestamp, u32 buildVersion, u32 objectsEnd, u32 buffersEnd,
  u32 crc32, u32 numChunks. (In these files the "buildVersion" slot holds the size of the largest buffer.)
- 10 table headers × 12 bytes (u32 offset, u32 itemCount, u32 crc32). Tables used: strings, names, imports,
  properties, chunks (exports), buffers, embedded.
- names: u32 string offset + u32 hash (8 bytes). imports: u32 path offset, u16 class name index, u16 flags.
- chunks: u16 class, u16 flags, u32 parent, u32 dataSize, u32 dataOffset, u32 template, u32 crc (24 bytes).
- buffers: u32 flags, u32 index, u32 offset, u32 diskSize, u32 memSize, u32 crc (24 bytes). The archive stores each
  buffer as its own segment; `extract.py` wrote them decompressed as `.bufferN` (memSize matches file size).

## Per resource

### man_big.rig — 43,718 bytes
- Chunks: `animRig`, `animRigIkLeftFootSetup`, `animRigIkRightFootSetup`. No buffers; bone data is inline in the
  `animRig` chunk.
- Import: `base\characters\base_entities\man_base\man_base.rig` (parent rig).
- 99 bone-like names in its name table (Hips, Spine*, Left*/Right* limbs, fingers, IK helpers).

### t0_001_mb_body__jackie_welles.mesh — 65,378 bytes + 2 buffers
- Chunks: `CMesh`, `meshMeshParamGarmentSupport`, 2× `meshMeshAppearance`, `rendRenderMeshBlob`.
- Buffers: #0 2,003 bytes (local material buffer, `meshMeshMaterialBuffer`), #1 905,164 bytes (render blob: vertex
  and index streams; `IBCT_IndexUShort` = 16-bit indices).
- Imports: none. Materials are embedded in the local material buffer rather than referenced by path.
- Skinning: the mesh name table contains ~177 bone-like names. 61 match `man_big.rig`. The rest are `*_JNT`
  deformation/muscle joints (e.g. `l_deltoid_front_top_out_JNT`, `l_Wrist_1_JNT`, `l_calf_0_JNT`), which belong to a
  separate deformation rig. The inventory shows `man_big\deformations_rigs\man_big_deformations.rig` exists; it was not
  extracted. So this mesh binds to two rigs: the main skeleton plus a deformation layer.
- Contains `boneRigMatrices`, `lodBoneMask`, `renderLODs`, `quantizationOffset` → skinned, LOD'd, quantized positions.

### a0_003_wa__mantisblade_left_arm.mesh — 33,670 bytes + 1 buffer
- Chunks: `CMesh`, 6× `CMaterialInstance`, `meshMeshAppearance`, `rendRenderMeshBlob`.
- Buffer #0: 1,574,179 on disk → 5,134,464 decompressed (render blob).
- 12 imports: base material `engine\materials\multilayered.mt`; skin instance
  `base\characters\common\skin\character_mat_instance\female\arms\female_arm_01_ca_pale.mi`; 5 `.mlsetup` + 5
  `.mlmask` pairs (midpoly1, midpoly2, misc, nails, decals) under `...\a0_003__mantisblade\textures\`.
- Skinned (`boneRigMatrices` present). Materials are multilayered: final look comes from mlsetup layer stacks +
  masks, not from single texture files.

### shop_vending_machine_b_w300_h400_aa.mesh — 8,949 bytes + 4 buffers
- Chunks: `CMesh`, `meshMeshParamOccluderData`, `visOccluderMeshResource`, 3× `meshMeshAppearance`,
  `rendRenderMeshBlob`.
- Buffers: 448 (local materials), 108, 4,072 (occluder data), 105,536 (render blob).
- Imports: none (materials local). Appearance names include `off` and `off_terracognita` (power-state variants).
- Static, with a separate occluder mesh for visibility culling.

### rancho_coroonado_building3.mesh — 6,679 bytes + 1 buffer
- Chunks: `CMesh`, `meshMeshParamPhysics`, `physicsSystemResource`, `physicsSystemBody`, `physicsColliderBox`,
  `CMaterialInstance`, `meshMeshAppearance`, `rendRenderMeshBlob`.
- Buffer #0: 147,030 on disk → 1,609,582 decompressed.
- Import: `engine\materials\metal_base.remt`. Static, with an embedded box collider.
- Path is under `architecture\_temp\` and the filename is misspelled (`coroonado`), which suggests a placeholder asset.

## Not yet decoded
`rendRenderMeshBlob` header fields (vertex counts, stream layouts, quantization scale/offset, LOD ranges) and the
`animRig` bone arrays (parent indices, reference pose) are not parsed. Doing so needs RTTI property decoding of chunk
data (type-tagged property streams); no geometry counts are claimed above for that reason.
