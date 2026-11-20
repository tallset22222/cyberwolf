# cp77-work — Cyberpunk 2077 Archive Research

Technical research into Cyberpunk 2077 archive formats and resource structures.

## Workstreams

This repository contains the Cyberpunk archive research workstream. The separate X-Ray asset pipeline is maintained in its own project.

## Research scope

The research examines:

- RDAR archive structure and resource identification
- CR2W resource headers, chunks, and properties
- Mesh geometry, vertex attributes, and LODs
- Skeleton hierarchies and deformation rigs
- Skinning weights and bind-pose validation
- Material instances, templates, layers, and texture references
- Research provenance and validation methods

## Repository contents

### Documentation

- `01_archive_format.md` — RDAR container format
- `02_extraction_pipeline.md` — Research methodology
- `03_extracted_resources.md` — Examined resource structures
- `04_geometry_skeleton_materials.md` — Geometry, LODs, skeletons, and materials
- `05_vertex_appearance_report.md` — Vertex attributes, skinning, bind poses, material relationships, and research limitations

The initial public release focuses on technical documentation and research findings.

The full local workspace also contains experimental analysis tools, machine-readable reports, and supporting research data, which are maintained separately.

## Research integrity and limitations

The original game installation was treated as read-only during the documented investigation.

This public repository does not distribute the original game archives or extracted game assets.

The findings document observed structures and validation