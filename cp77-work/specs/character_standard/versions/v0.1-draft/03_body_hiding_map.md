# Cyberwolf character standard, part 3: body-hiding map (v0.1 draft, for review)

Machine-readable source: `hiding_regions.json`. Diagram: `hiding_map.png`.

The base body mesh is split into **33 regions**, each a separate sub-mesh with one bit in a 64-bit mask. Every
implant, garment and chassis declares a hide mask. The body draws only regions whose bit is not set by anything worn.
This is the same idea as the chunk masks we decoded in Cyberpunk's character assembly, with our own regions.

**Requirement on the base mesh:** every region boundary must be an existing edge loop of the base mesh, so each
region can be split off cleanly. This is the main topology test for MakeHuman (part 4).

## Regions (left side and centre listed; `_r` mirrors `_l` with its own bit)

| bit | region | bounded by | note |
|---|---|---|---|
| 0 | `scalp` | hairline, ears | hidden by helmets, hair caps |
| 1 | `face` | hairline, jawline | hidden only by full masks; optional per item |
| 2 | `ears` | scalp | both ears |
| 3 | `neck_upper` | jawline, seam neck_mid |  |
| 4 | `neck_lower` | seam neck_mid, seam neck_base |  |
| 5 | `chest` | seam neck_base, ribcage line, mid-axillary lines, seams shoulder_l/r | front torso above the ribcage line |
| 6 | `abdomen` | ribcage line, seam waist, mid-axillary lines |  |
| 7 | `back_upper` | seam neck_base, back mid line, mid-axillary lines |  |
| 8 | `back_lower` | back mid line, seam waist |  |
| 9 | `pelvis_front` | seam waist, seams hip_l/r | includes the groin |
| 10 | `pelvis_back` | seam waist, gluteal folds | glutes |
| 11 | `shoulder_cap_l` | seam shoulder_l, chest, back_upper | deltoid cap |
| 12 | `upperarm_upper_l` | seam shoulder_l, seam upperarm_mid_l |  |
| 13 | `upperarm_lower_l` | seam upperarm_mid_l, seam elbow_l |  |
| 14 | `elbow_l` | seam elbow_l, forearm 15% |  |
| 15 | `forearm_l` | forearm 15%, seam wrist_l | split at forearm_mid allowed later (reserved bit) |
| 16 | `hand_l` | seam wrist_l | hand and fingers |
| 17 | `thigh_upper_l` | seam hip_l, seam thigh_mid_l |  |
| 18 | `thigh_lower_l` | seam thigh_mid_l, seam knee_l |  |
| 19 | `knee_l` | seam knee_l, shin 15% |  |
| 20 | `shin_l` | shin 15%, seam ankle_l | split at shin_mid allowed later (reserved bit) |
| 21 | `foot_l` | seam ankle_l | foot and toes |

Bits 33–63 are reserved, for example to split `forearm` and `shin` at their mid seams later.

## Hide rules

- **Replacements:** hide all regions distal to their seam. Example, the military leg from `thigh_mid_l`, left side:

  ```
  thigh_lower_l | knee_l | shin_l | foot_l
  = bits 18, 19, 20, 21
  = mask 0x00000000003c0000
  ```

- **Garments:** declare masks the same way. Thigh-high boots hide `knee`, `shin` and `foot`.
- **Combining items:** the mask a character renders with is the OR of everything worn.
- **Conflicts:** two items that replace the same region are a slot conflict and can't be worn together. Overlays and
  garments can stack over a replacement if they declare the replacement slot as compatible.
- **Layer order** (for clipping tests): body → replacement implants → overlays → under-layer clothing → outerwear → rigid items.

## Open points for review

1. `face` hidden only by full masks. Half-masks (mouth/jaw plates): split `face` into upper and lower?
2. Torso uses front/back regions split at the mid-axillary line. A chest plate that wraps the sides hides `chest` + `back_upper`.
3. Are hands one region with fingers, or should fingers be separate (for finger-only implants)?
