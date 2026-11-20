# Cyberwolf character standard, part 4: base body mesh source, MakeHuman assessment (v0.1 draft)

**Decision so far:** the skeleton is Cyberwolf's own (parts 1–3). The base body *mesh* may start from a CC0 source,
and MakeHuman is the candidate. The MakeHuman skeletons are not used.

## Licensing (checked 17 Nov 2026, primary sources)

- **The asset licence covers the base mesh and everything we'd use.** MakeHuman's licence lists the base mesh and
  proxies, targets and modifiers, and textures as assets "released under CC0 1.0 Universal" (LICENSE.md, section C).
- **Exports are ours.** The same licence regards exported output as "your data", and says that because the assets
  are CC0 there is no limitation on the combined output (section D).
- **Third-party assets are the one exception.** Assets downloaded separately carry their own licences; the user
  repositories contain both CC0 and CC-BY assets. **Rule: Cyberwolf uses only the core base mesh. No community
  clothes, hair or skins without separate review.**
- **History.** Before September 2020 the base mesh counted as AGPL source code unless exported through the GUI.
  The 2020 change made the base mesh, targets and proxies CC0 graphical assets. Older forum threads describing
  AGPL complications predate that change.
- The MakeHuman *software* stays AGPL, and MPFB (the Blender plugin) is GPL. We use the program; we don't ship its
  code, so this doesn't affect Cyberwolf.

**To do when the mesh is downloaded:** save the exact LICENSE.md and the asset version alongside it in the workspace,
as we did for the concepts, and record its SHA-256.

Sources:
[MakeHuman LICENSE.md](https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md) ·
[License page](https://static.makehumancommunity.org/about/license.html) ·
[What changed in 2020](https://static.makehumancommunity.org/oldsite/faq/what_changed_regarding_the_license_in_2020.html) ·
[CC-BY assets FAQ](https://static.makehumancommunity.org/oldsite/faq/what_do_i_need_to_do_when_i_use_a_ccby_asset.html)

## Topology (from MakeHuman's documentation; to be verified on the actual mesh)

**What the documentation says:**
- **Mesh.** The base mesh "hm08" has been unchanged for more than a decade. It is described as quads-only, built for
  animation and sculpting, with a minimal number of poles of at most 5 edges.
- **Vertex counts.** The visible body is vertices 0–13,379. Vertices 13,380–19,157 are helper geometry (tongue,
  joint cubes, eyes, eyelashes, teeth, genitals, clothing helpers), which we would delete before use.
- **MakeHuman 2.** One source says its base mesh is triangle-based, unlike MakeHuman 1, so the source should be
  hm08 from MakeHuman 1.x / MPFB.

[Basemesh concept](https://static.makehumancommunity.org/about/concepts/basemesh.html) ·
[Professional mesh topology](https://static.makehumancommunity.org/makehuman/docs/professional_mesh_topology.html) ·
[Basemesh and helpers (MPFB)](https://static.makehumancommunity.org/mpfb/docs/assets/concept_basemesh_and_helpers.html)

**Assessment for our modular regions:**

| requirement | expectation | status |
|---|---|---|
| licence allows shipping in a closed game | CC0 core assets | **met** (above) |
| about 13k-vertex quad body, a reasonable game base | yes | documented; verify |
| edge loops at all 23 seam rings and the torso cuts (part 3) | likely at joints (animation topology); mid-segment loops uncertain | **must be verified on the mesh**: the decisive test |
| helper geometry removable cleanly | separate vertex ranges | documented; verify |
| A-pose export, compatible with our 45° rest pose | MakeHuman exports A-pose | verify the angle; refit our joint positions to the mesh, not the reverse |
| no MakeHuman skeleton dependence | we discard its rigs | by design |

**Alternative if the loops don't fit:** Blender Studio's *Human Base Meshes* bundle is also CC0. It is sculpt-oriented
(multiresolution-ready closed volumes), so it would need retopology for game use.
[Blender asset bundles](https://www.blender.org/download/demo-files/)

## Next step (needs one download on your PC; my sandbox has no internet access)

Export the default hm08 body from MakeHuman 1.x, or MPFB, as OBJ or FBX, with no clothes, hair or proxies. Put it in
`cp77-work\concepts\base_mesh\` with the LICENSE.md. I'll then:

1. Strip the helper geometry.
2. Test every seam ring and torso cut against the mesh's edge loops, and report which regions split cleanly and which need loops added.
3. Fit the `bio_reference` joint positions to that body.
