# 8-influence import test: data stage, PASSED (17 Nov 2026, 18:21 local)

WolvenKit 10.0.0-beta.2 (owner's Debug build of the WolvenKit main branch; WolvenKit 9.1.1 refuses this game version).
Scratch project `wk_project/cw_infl8_test` (inside the workspace); the game files were not modified.
Template: vanilla `l1_003_ma_pants__jeans.mesh` added from the installed game. It is identical to `pipeline_cache` in
bones, bind matrices and positions; only the container differs (WolvenKit embeds compressed buffers).
Import: right-click the .glb, Import, defaults except **Import Garment Support unticked**. Log: "Rebuilt with
buffers ... (as Mesh)", "Successfully imported 1 file"; no warnings.

| Check | Result |
|---|---|
| Layout carries the second skin-index and skin-weight set (`PS_SkinIndices1` / `PS_SkinWeights1`) | yes |
| Vertices found | 360 / 360 |
| Exact vertices: bone names and bytes identical | 312 / 312, 0 dropped, 0 byte mismatches, 0 bone mismatches |
| Bind matrices vs template | max difference 2.4e-7 (float32 rounding), no bones added |
| Sentinel band byte sums | 256 on all 48 vertices: WolvenKit's per-weight rounding, as predicted (diagnostic only) |

Verdict: eight influences survive the import with correct bone assignments, no discarding and no renormalisation.
Full report: `imported/l1_003_ma_pants__jeans.mesh.infl8_report.json`.
Tooling change: `pipeline/cyberwolf/mesh.py` now also reads buffers embedded in the .mesh file (Kraken-decompressed).

## Stage 2: offline deformation, PASSED (17 Nov 2026)

Cyberpunk 2077 is the research subject, not the target game, so the deformation stage runs offline on the imported
mesh itself (`tools/infl8_deform_test.py`; data in `deform_test.json`, picture in `deform_test.png`).
Bind pose comes from the imported mesh's own bind matrices. The LeftLeg subtree of `man_base_deformations.rig`
rotates about the knee, 0–135°. The skins compared:
- **A**, imported: joints, plus bytes/255, no renormalisation, as a renderer reads UByte4N;
- **B**, intended: float weights from the .glb;
- **C**, imported bytes cut to 4 influences.

| Knee | A vs intended, 312 exact vertices | A vs intended, 48 sentinel vertices | 4-influence cut vs intended (max / mean) |
|---|---|---|---|
| 0° | 0.000 mm | 1.67 mm | 0.0 mm |
| 30° | 0.000 mm | 1.82 mm | 8.0 / 1.5 mm |
| 60° | 0.000 mm | 1.99 mm | 15.5 / 2.9 mm |
| 90° | 0.000 mm | 2.13 mm | 21.9 / 4.2 mm |
| 120° | 0.000 mm | 2.22 mm | 26.8 / 5.1 mm |
| 135° | 0.000 mm | 2.23 mm | 28.6 / 5.4 mm |

- **Exact vertices deform identically to the authored weights at every angle**: edge stretch matches to 0.0, and no
  triangles flip.
- **Exact return to rest.** Every vertex stays finite, and none collapses toward the origin (the minimum distance from
  the origin is ≥ 0.31 m).
- The edge stretch range (down to 0.19×, up to 2.45× at 135°) is the plain test tube's own uncorrected LBS crease. It
  is identical in the intended skin, so it is not import damage.
- **Sentinel band:** the 256 byte sum scales its skinned position by 256/255. That shows as a 1.7 mm offset at rest,
  growing to 2.2 mm at 135°, exactly as predicted. The band also hangs back in the bend by design, because its eight
  equal weights deliberately include thigh and hip bones. Diagnostic only; real Cyberwolf exports are pre-quantised
  to 255.
- **The 8 influences matter:** cutting the same bytes to 4 moves the surface up to 28.6 mm at 135° (21.9 mm at 90°).

**Gate result: the eight-influence import path is validated** for this WolvenKit build (10.0.0-beta.2), in data and in
offline deformation. A later WolvenKit release should be re-checked with the same .glb and verifier.
