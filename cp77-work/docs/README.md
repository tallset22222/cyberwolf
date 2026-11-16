# Cyberpunk 2077 Archive and Resource Format Research

Independent technical research into Cyberpunk 2077 archive formats and resource structures.

## Research scope

The investigation examined:

- RDAR archive structure and resource identification
- CR2W resource headers, chunks, and properties
- Mesh geometry, vertex attributes, and LOD structures
- Skeleton hierarchies and deformation rigs
- Skinning weights and bind-pose validation
- Material instances, templates, layers, and texture references
- Texture metadata and resource relationships
- Research methodology and validation

Findings rest on a small sample examined in one installation of the game (GOG build, with Phantom Liberty): four
meshes, three rigs, and the material and texture files they reference. They describe what was observed in those
resources and may not hold for every resource class or game build.

## Documents

| Document | Contents |
|---|---|
| `01_archive_format.md` | RDAR container: header, index, file entries, segments, path hashing, observed distribution |
| `02_extraction_pipeline.md` | Research methodology: principles, steps, sample, validation checks, known limits |
| `03_extracted_resources.md` | CR2W container layout and first-pass structure of the five initial resources |
| `04_geometry_skeleton_materials.md` | CR2W property encoding, mesh geometry and LODs, skeletons and deformation rigs, materials and multilayer setups |
| `05_vertex_appearance_report.md` | Vertex attributes, skinning and bind poses, material chains, texture metadata, mask tile tables, coverage and open questions |

## Repository contents

This initial public release contains technical documentation only: the investigation's method, the structures
observed, and the validation results.

It does not include the local extraction workspace, extracted game resources, archive inventories, analysis
scripts, or machine-readable reports. Where the documents mention results from those, they summarise them in the
text.

## Prior work

This research builds on the [WolvenKit](https://github.com/WolvenKit/WolvenKit) project's earlier
reverse-engineering of Cyberpunk 2077's file formats. In particular:

- the RDAR container layout and many CR2W field names follow WolvenKit's prior work;
- path hashes were resolved using WolvenKit's published used-hash list;
- compressed segments were read using the Kraken decompression library distributed with WolvenKit;
- WolvenKit's source was consulted as a reference for the normal/tangent encoding.

The structural decoding, validation checks, measurements and conclusions in these documents are the author's own.
No WolvenKit code is reproduced here.

## Research integrity and limitations

The game installation was treated as read-only throughout. At the end of the investigation, file modification
times were checked against the initial installation manifest; this does not by itself establish that file contents
were unchanged.

The findings describe observed structures and validation results. They do not claim a complete reconstruction of
the game's rendering, animation, material, or asset systems. Open questions and unexamined systems are listed in
document 05.

This repository documents technical research. It does not distribute game assets.

## Licence

A licence for this documentation has not yet been chosen. Until one is added, all rights are reserved by the
author. No licence applies to any game content referenced here.

## Trademark and affiliation

Cyberpunk 2077 is a trademark of CD PROJEKT S.A. This project is independent and is not affiliated with or
endorsed by CD PROJEKT RED or by the WolvenKit project.
