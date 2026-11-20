# Cyberwolf character standard, part 4: base body mesh source, MakeHuman assessment (v0.2 draft)

## v0.2 status: hm08 adopted as the working base mesh (validation continuing)

- **Master.** `concepts/base_mesh/makehuman/data/3dobjs/base.obj`, SHA-256 `8e761e6624b8f545…6fb4c`. It is untouched;
  all work happens on `concepts/base_mesh_work/base_working.obj` (identical checksum). The licence files are stored
  alongside, with their checksums in `master_checksums.sha256`.
- **Body.** 13,380 vertices and 13,378 quads in the `body` group, in decimetres in the source (converted to metres).
- **Test 1, topology.** 18 of 26 seam instances sit on a clean closed loop. `shin_mid` and `neck_base` moved to their
  measured loops. Shoulder and hip use option A (the first loop around the limb root).
- **Test 2, deformation.** The skeleton fits and deforms acceptably except at the armpit and groin (helpers needed),
  with LBS/DQS trade-offs at the elbow, knee and hip. The face is a separate problem.
- **Test 3, regions.** All 33 regions separate cleanly; per-seam motion was measured on both sides.
- **Topology binding.** Seam loops, region membership and drawn boundaries are stored in `topology/hm08/` against
  the master checksum. Changing the mesh triggers the migration procedure in part 3.
- **Native pose.** Arms 50.4° below horizontal, thighs 7°. This is the rest-pose candidate (OI-07); the mesh is not re-posed.

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

**Done (17 Nov 2026):** the LICENSE files and the asset are stored in the workspace with SHA-256 checksums (`concepts/base_mesh_PROVENANCE.md`).

Sources:
[MakeHuman LICENSE.md](https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md) ·
[License page](https://static.makehumancommunity.org/about/license.html) ·
[What changed in 2020](https://static.makehumancommunity.org/oldsite/faq/what_changed_regarding_the_license_in_2020.html) ·
[CC-BY assets FAQ](https://static.makehumancommunity.org/oldsite/faq/what_do_i_need_to_do_when_i_use_a_ccby_asset.html)

## Topology: pre-download assessment (kept for the record; superseded by the v0.2 status above)

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

## Remaining base-mesh work (v0.2 open items)

See the open-items register in `README.md`: OI-03 (elbow and knee seams), OI-04 (shoulder retest), OI-05 (helpers),
OI-08 (weight symmetry), OI-09 (face), OI-11 (topology migration), OI-12 (ears) and OI-13 (ribcage line).
