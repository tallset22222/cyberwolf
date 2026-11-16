# 02 — Research methodology

This document describes how the archive and resource structures in documents 01 and 03–05 were examined and
validated. It describes the method, not a tool: the scripts used during the investigation are kept in the author's
private workspace and are not part of this repository.

## Principles

- **Read-only.** Game archives were only ever opened for reading. Nothing was written into the installation, and
  nothing was converted, exported or installed elsewhere.
- **Checked afterwards.** At the end of the investigation, file modification times in the installation were checked
  against the initial installation manifest, which also records file sizes. No file had been modified since the
  inventory was taken. A modification-time check shows that nothing was written to the installation; it does not
  verify file contents byte for byte.
- **Small samples.** Structural findings come from a small, deliberately chosen set of resources (see "Sample"),
  not from bulk extraction.
- **Provenance recorded.** Every resource examined was logged: its source archive, its depot path, its index entry,
  its segment offsets and sizes, and SHA-256 hashes of both the stored (compressed) bytes and the decompressed output.
  At the time of this report, the investigation comprised 9 logged runs and 120 provenance records.

## Steps

### 1. Archive inventory
The header and index of every `.archive` file in the installation were read (format in document 01). Each archive's
declared size was checked against its size on disk. Unexpected magic values or truncated files were recorded as
findings rather than treated as errors, which is how the damaged duplicate archives described in document 01 were
found.

### 2. Resolving resource names
Archives identify resources only by a 64-bit FNV-1a hash of the lower-case depot path, so names have to be recovered
by hashing candidate paths and matching them against the index. The candidate list was WolvenKit's published
used-hash list (1,735,646 paths). 23,615 hashes (1.3%) did not match any candidate and are recorded without a path.

### 3. Reading resource segments
Compressed segments use a `KARK` wrapper around a Kraken (Oodle-family) stream. Decompression used the Kraken
library bundled with WolvenKit, called directly. No decompressor was written or reimplemented as part of this work.
Uncompressed segments (audio, video) were identified by having identical stored and decompressed sizes.

### 4. Choosing the sample
The examined samples cover several different structural cases, allowing the investigation to compare resource
layouts, decoding requirements and validation methods:

- a character skeleton (`.rig`), followed later by its deformation rig
- a skinned character body mesh that uses two rigs and has several LODs
- a cyberware mesh with multilayered materials and its own skeleton
- a static prop with an occluder mesh and appearance variants
- a static building with an embedded physics collider

Later rounds added only resources that these five referenced and that were needed to resolve a structure (the
deformation rig, the cyberware skeleton, and the referenced `.mlsetup` / `.mlmask` files).

### 5. Decoding structure in layers
Each layer was decoded and checked before moving on to the next:

1. CR2W container: header, table headers, and the strings, names, imports, chunks and buffers tables.
2. The generic property stream inside each chunk (typed, size-prefixed properties, nested structs, arrays, handles,
   references, enums, bitfields).
3. Class-specific data: the mesh render-blob header and vertex streams, the binary tail of the rig (parent indices
   and reference pose), the material-instance parameter tail, multilayer setups, and mask tile tables.

### 6. Validation
A finding was accepted only once it passed checks within the data itself:

- **Containers:** declared sizes, offsets and counts consume their region exactly, with no unexplained bytes left
  over.
- **Geometry:** every index is below the vertex count; every stream lies within the declared vertex buffer; the index
  region lies within the buffer.
- **Vertex attributes:** normal lengths, normal/tangent orthogonality, agreement between vertex normals and face
  winding, tangent direction relative to +U, and UV validity were checked. Deviations and uncertain results are
  recorded in document 05.
- **Skeletons:** parents are topologically ordered; composing local A-pose transforms up the hierarchy reproduces the
  stored model-space A-pose.
- **Skinning:** bone indices and weight totals were checked against the expected ranges (indices below the mesh's
  bone count; totals of 255 for the examined encoding). Exceptions were recorded separately (document 05). Inverse
  bind matrices were compared against a known pose of the matching rig.
- **Materials:** preset names in examined layer setups were checked against their templates. Layer counts were
  compared between setups and masks where both contained usable layer data; incomplete and stub cases are documented
  separately (document 04).

Results that did not fully pass are reported as **uncertain** in document 05, not presented as settled.

## Prior work

The archive format, path hashing and much of the CR2W naming used here build on the WolvenKit project's earlier
reverse-engineering. WolvenKit's hash list and Kraken library were used as inputs (steps 2 and 3), and its source was
consulted as a reference for the normal/tangent encoding. The structural decoding, validation checks and conclusions in these
documents are the author's own.

## Known limits

- 1.3% of resource hashes have no known path.
- Findings rest on the sample in step 4. They describe what was observed in these resources and may not hold for every
  resource class or game build.
- Shader behaviour, animation data (`.anims`) and entity/appearance files (`.ent` / `.app`) were not examined (see
  document 05).
