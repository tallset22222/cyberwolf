# 02 — Inventory and extraction pipeline

Everything runs in the Linux shell attached to this machine, Python 3.10 (`python3 -I`), plus gcc for one helper.
Archives are only ever opened read-only.

## Components (`tools\`)
| File | Role |
|---|---|
| `rdarmap.py` | Walks the install, reads header + index of every `.archive`, writes `summary.json` and per-archive `*.index.json`. Reports bad magic / truncation instead of failing. |
| `kark.py` | ctypes wrapper over `Kraken_Decompress` in WolvenKit's `WolvenKit.Core\lib\libkraken.so`; `unkark()` handles the KARK wrapper; `fnv1a64()` path hash. Expects the .so copied to `~/lib/`. |
| `fnvmap.c` | Hashes the 136 MB path list in ~0.5 s (pure Python would take minutes). Output: `hash<TAB>path`. |
| `extract.py` | Given `[[archive, depotPath], ...]`, writes the CR2W header to `<out>\<depotPath>` and each extra segment to `<depotPath>.bufferN`, decompressed. |
| `cr2w_dump.py` | Read-only structural dump of CR2W files (tables, names, imports, chunks, buffers) to JSON. |
| `cr2w_props.py` | RTTI property-stream decoder (structs, arrays, static arrays, handles, refs, enums, bitfields, buffers). |
| `mesh_decode.py` | Mesh blob header, vertex layouts, counts, LODs, bounds; validates indices and buffer extents. |
| `rig_decode.py` | animRig names, parent tail, reference pose; validates hierarchy against A-pose where present. |
| `material_decode.py` | Material slots, local instances, parameter tails, per-appearance assignments. |
| `layers_decode.py` | .mlsetup layer stacks and .mlmask atlas headers. |

## Reproduce
1. `python3 -I rdarmap.py "<install>" <out>` → summary + hash indexes.
2. Decompress `usedhashes.kark` with `kark.unkark()`; pipe through `fnvmap` → `hashmap.tsv`.
3. Join indexes with `hashmap.tsv` → `inventory\named\`.
4. `python3 -I extract.py extract\sampleN.json extract\raw` (runs 1–4; see each JSON).
5. `python3 -I cr2w_dump.py docs\cr2w_structure.json <files>`.

## Known limits
- 23,615 hashes (1.3%) have no path in the list; they appear with `path: null`.
- Buffer layouts are decoded for analysis by mesh_decode.py (see doc 04); nothing is converted to other formats.
- Background processes do not persist between shell calls; long jobs (hashing) were run in foreground batches.
