# 01 — RDAR archive format (as observed, game build with Phantom Liberty, archive version 12)

All integers little-endian.

## Header (40 bytes at offset 0)
| Off | Type | Field | Notes |
|---|---|---|---|
| 0 | char[4] | magic | `RDAR` |
| 4 | u32 | version | 12 in every archive here |
| 8 | u64 | indexPosition | index lives at the end of the file |
| 16 | u32 | indexSize | |
| 20 | u64 | debugPosition | |
| 28 | u32 | debugSize | |
| 32 | u64 | fileSize | equals on-disk size for every intact archive |

## Index (at indexPosition)
| Off | Type | Field |
|---|---|---|
| 0 | u32 | fileTableOffset |
| 4 | u32 | fileTableSize |
| 8 | u64 | crc |
| 16 | u32 | fileEntryCount |
| 20 | u32 | fileSegmentCount |
| 24 | u32 | resourceDependencyCount |

Followed by three arrays, back to back:

**File entry (56 bytes)**: u64 nameHash, i64 timestamp, u32 numInlineBufferSegments, u32 segmentsStart, u32 segmentsEnd,
u32 resourceDependenciesStart, u32 resourceDependenciesEnd, u8[20] SHA-1.

**Segment (16 bytes)**: u64 offset, u32 zSize (on disk), u32 size (decompressed).

**Dependency (8 bytes)**: u64 path hash.

## Path hashing
`nameHash` = FNV-1a 64 (offset basis 0xcbf29ce484222325, prime 0x100000001b3) over the lower-case depot path with
backslashes, e.g. `base\characters\base_entities\man_big\man_big.rig`. Paths are not stored in the archive; they are
recovered by hashing a known path list (WolvenKit `usedhashes.kark`, 1,735,646 paths).

## Segments
- Segment `segmentsStart` is the resource header (a CR2W file). Further segments are its buffers, in buffer-table order.
- A segment whose zSize ≠ size, or that begins with `KARK`, is compressed: `KARK` (4) + u32 decompressed size + Kraken
  (Oodle-family) stream. Uncompressed segments (audio .wem, video .bk2) have zSize == size.

## Observed distribution
- Asset-heavy archives (`basegame_3_nightcity`, `basegame_4_appearance`, `basegame_4_gamedata`, `ep1_1_nightcity`,
  `ep1_2_gamedata`): 60–95% of entries carry extra buffer segments (meshes, textures, sectors).
- `*_gi` and `*_terrain`: 100% of entries carry buffers (baked GI / terrain data).
- Audio, video, text and voice archives: entries are single segments, mostly uncompressed.
- Top resolved extensions: .wem 1,227,970 · .mesh 107,014 · .anims 84,549 · .json 74,183 · .xbm 56,791 ·
  .streamingsector 47,987 · .gidata 23,916 · .ent 22,309 · .mi 19,512 · .mlsetup 17,969.

## Damaged duplicates (nested `Cyberpunk 2077\archive\pc\content\`)
7 of 8 files are zero from offset 0 (no header). `basegame_3_nightcity_gi.archive` has a valid header claiming
11,290,980,352 bytes but is 9,156,165,632 bytes on disk, so its index (at 11,288,973,312) is missing. Consistent with an
interrupted copy/install. Details and hashes in `inventory\damaged\`.
