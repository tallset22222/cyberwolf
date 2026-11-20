# OI-19 import test: 8 skin influences through WolvenKit (isolated test asset)

**Purpose:** confirm that 8 influences survive glb → WolvenKit → `.mesh`, and that the result deforms correctly in
the game. This is a test only. Nothing here touches the Cyberwolf character or any original game file.

**Files:**
- `l1_003_ma_pants__jeans.glb`: the test mesh. It is a 24-segment tube around the left knee plus one sentinel band,
  skinned to the vanilla jeans' own 32 bones, single LOD (`submesh_00_LOD_1`). The file name matches the template so
  WolvenKit maps it.
- `expected.json`: per-vertex expected bone names and weight bytes.
- Generator: `tools/infl8_test_asset.py`. Verifier: `tools/verify_infl8_import.py`.

**What the weights test:**

| vertices | influences | design |
|---|---|---|
| 48 / 48 / 48 / 168 | 4 / 5 / 6 / 8 | exact n/255 weights summing to 255; WolvenKit must keep every byte |
| 48 (sentinel band) | 8 | eight equal weights of 0.125, which isn't representable in bytes |

WolvenKit's source (`WolvenKit.Modkit/RED4/Tools/MeshImportTools.cs`) rounds each weight separately without
renormalising, so the sentinel is predicted to come out as 32 × 8 = **256**. The test shows whether that actually
happens, and the in-game step shows whether it matters.

**Pre-checked here (simulating WolvenKit's documented conversions):** positions exact within 0.0005 mm, bind matrices
exact, joint order equal to the template, all 312 exact vertices reproduce their bytes, sentinel sums 256. A dry run
of the verifier against the vanilla jeans correctly fails (0 of 360 vertices found).

## Steps on your PC

1. **WolvenKit project.** Create a new throwaway project, for example `cw_infl8_test`.
2. **Template.** Add `base\characters\garment\citizen_casual\legs\l1_003_pants__jeans\l1_003_ma_pants__jeans.mesh`
   to the project. This makes a *copy* in the project; the game files are untouched.
3. **Import.** Copy `l1_003_ma_pants__jeans.glb` into the project's `raw\` folder at the same relative path. Then use
   the Import tool: import it onto the mesh, with default options and no garment support. Note any warnings WolvenKit shows.
4. **Return the result.** Copy the imported `l1_003_ma_pants__jeans.mesh` (plus any `.buffer` files written beside
   it) into `cp77-work\tests_assets\infl8_import\imported\`. I then run
   `python tools/verify_infl8_import.py tests_assets/infl8_import/imported/l1_003_ma_pants__jeans.mesh`.
5. **In game (last step, optional until steps 1–4 pass).**
   - Pack the project as a mod and install it to `archive\pc\mod`. This replaces the jeans' appearance with the tube
     while the mod is installed.
   - Wear the jeans on a male V and crouch or sit.
   - **Expected:** the band bends smoothly with the knee, with no spikes, no detachment and no vertices left at the origin.
   - Look closely at the sentinel band below the knee: if a 256 sum matters, it sits slightly off the leg compared
     with the main tube.
   - Remove the mod afterwards.

## Pass criteria

- The layout has a second skin-index and skin-weight set (`PS_SkinIndices1` / `PS_SkinWeights1`).
- 360 of 360 vertices are found.
- All 312 exact vertices have identical bone names and bytes, with 0 dropped influences.
- The bind matrices are unchanged from the template.
- In game, the tube deforms smoothly with the knee.

**Not a pass criterion:** the sentinel band's byte sum. A sum of 256 is the expected *diagnostic* of WolvenKit's
per-weight rounding, and the in-game step shows whether it matters. Real Cyberwolf exports never rely on it: they
are pre-quantised to exactly 255 by `pipeline/cyberwolf/quantize.py`.
