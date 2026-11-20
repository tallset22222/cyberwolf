# 01 — RDAR archive format (as observed, game build with Phantom Liberty, archive version 12)

This document describes the RDAR archive container as observed in one installation of the game (GOG build, with
Phantom Liberty). The container layout and field names follow the WolvenKit project's earlier reverse-engineering of
the format; the observations, counts and checks below come from reading the archives in that installation (method in
document 02).

All integers little-endian.

## Header (40 bytes at offset 0)
| Off | Type | Field | Notes |
|---|---|---|---|
| 0 | char[4] | magic | `RDAR` |
| 4 | u32 | version | 12 in every archive examined |
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
u32 resourceDependenciesStart, u32 resourceDependenciesEnd, u8[20] SHA-1. In a test entry this hash matched
neither the stored nor the decompressed bytes; what it covers was not determined (document 05).

**Segment (16 bytes)**: u64 offset, u32 zSize (on disk), u32 size (decompressed).

**Dependency (8 bytes)**: u64 path hash.

## Path hashing
`nameHash` = FNV-1a 64 (offset basis 0xcbf29ce484222325, prime 0x100000001b3) over the lower-case depot path with
backslashes, e.g. `base\characters\base_entities\man_big\man_big.rig`. Paths are not stored in the archive; they are
recovered by hashing a list of known paths and matching the results against the index. The list used was WolvenKit's
published used-hash list (`usedhashes.kark`, 1,735,646 paths); 23,615 hashes (1.3%) matched no path.

## Segments
- Segment `segmentsStart` is the resource header (a CR2W file). Further segments are its buffers, in buffer-table order.
- A segment whose zSize ≠ size, or that begins with `KARK`, is compressed: `KARK` (4) + u32 decompressed size + Kraken
  (Oodle-family) stream. Uncompressed segments (audio .wem, video .bk2) have zSize == size.

## Observed distribution
Counts below are from the installation examined.

- Asset-heavy archives (`basegame_3_nightcity`, `basegame_4_appearance`, `basegame_4_gamedata`, `ep1_1_nightcity`,
  `ep1_2_gamedata`): 60–95% of entries carry extra buffer segments (meshes, textures, sectors).
- `*_gi` and `*_terrain`: 100% of entries carry buffers (baked GI / terrain data).
- Audio, video, text and voice archives: entries are single segments, mostly uncompressed.
- Top resolved extensions: .wem 1,227,970 · .mesh 107,014 · .anims 84,549 · .json 74,183 · .xbm 56,791 ·
  .streamingsector 47,987 · .gidata 23,916 · .ent 22,309 · .mi 19,512 · .mlsetup 17,969.

## Appendix: installation-specific observation
This describes the examined installation, not the format. A nested duplicate folder
(`Cyberpunk 2077\archive\pc\content\`) held 8 archive files. 7 were zero from offset 0 (no header).
`basegame_3_nightcity_gi.archive` had a valid header declaring 11,290,980,352 bytes but was 9,156,165,632 bytes on
disk, so its index (at offset 11,288,973,312) was missing. This is consistent with an interrupted copy or install.
Comparing a header's declared `fileSize` with the size on disk is a simple way to detect truncated archives.
