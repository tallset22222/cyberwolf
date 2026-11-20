# EXPERIMENTAL: DQS corrective-joint system, consolidated technical specification (research draft)

**Status:** research draft, 17 Nov 2026.
- **Not part of the character standard**, and changes nothing in it, in the skeleton, sockets, seams or region map.
- It describes what two offline prototypes (elbow, knee) mathematically require. It is the primary research candidate
  (owner decision, 17 Nov 2026); scaled-LBS correctives are secondary research.

**What this establishes:** the mathematical requirements for reproducing the accepted offline corrective shapes with
joints, under our DQS skinning, on the hm08 base mesh with v3 weights.
**What it does not establish:**
- that Cyberwolf's eventual renderer can implement this efficiently;
- the GPU/CPU cost of the extra joints and influences (unmeasured; only exact counts are given);
- REDengine's RBF behaviour;
- quality against a real human knee or elbow in motion (the targets are offline approximations).

Evidence: `oi20_elbow.md`, `oi20_elbow_interp.md`, `oi20_knee.md`, `oi20_knee_runtime.md`,
`../evidence_transfer.md`.

## 1. Framework (shared by every corrective)

| Element | Requirement | Evidence |
|---|---|---|
| Driver | One scalar per corrective: the twist-free swing angle between the proximal and distal segment | Both joints; poses with twist not yet tested |
| Activation | Exactly zero up to the authored threshold (30°). A runtime threshold set 5° early leaks 0.13–0.16 mm; late is harmless | Elbow tested; knee uses the same rule |
| Curve | Smoothstep from the threshold to the first key, then linear between keys. Curve shape matters little (≤ 0.3 mm); smoothstep is kept for smooth activation | Both |
| Key blending | Piecewise between **adjacent** keys only. A generic inverse-distance RBF over key angles fails: it leaks below the threshold or sags between keys | Both, tested independently |
| Beyond the last key | Hold the last key's offset | Both |
| Corrective joint | Leaf joint parented to the deforming bone it takes weight from; identity at rest; rigid offset (rotation + translation) per key, relative to its parent | Both |
| Weights | A corrective takes a share of its parent's weight on the vertices it drives, so inactive poses are unchanged exactly | Both: 0.000 mm on all inactive library poses |
| Influences | At most 5 per vertex (4 base + 1 corrective); a second 4-slot set on affected vertices only | Both |
| Symmetry | Right side = mirrored left (joints, offsets, weights); each side activates from its own driver | Both: mirror error ≤ 1e-12 mm, other limb unmoved |
| Validation | Six criteria against the offline reference: surface error throughout the movement; clean crease; smooth activation; exact rest; no unwanted deformation 30–90°; symmetry. Plus: no new intersections or fold-overs, no visible bumps, inactive poses unchanged, each limb tested alone | Established practice |

## 2. Per-region specifications

### Elbow (reference: offline 90° shape, no bulge)

- **Keys:** rest → 90°. The 50° and 70° intermediate keys bring no gain under DQS and can be omitted.
- **Rotation blending: quaternion (slerp or nlerp) required.** A component-wise matrix blend adds 0.38 mm, because one
  joint rotates 31.9°.
- **Joints:** 5 working joints per arm. The fit made 6, but `crj_elbow_prox0` drives no vertices and can be dropped
  without change.
  The empty joint is a property of this fit, not of the elbow: re-read working-joint counts from every refit.

| Joint | Parent | Vertices | Rotation | Translation |
|---|---|---|---|---|
| crj_elbow_prox1 | upperarm_twist_02 | 86 | 0.05° | 14.3 mm |
| crj_elbow_prox2 | upperarm_twist_02 | 20 | 31.9° | 3.1 mm |
| crj_elbow_dist0 | lowerarm | 55 | 0.2° | 10.6 mm |
| crj_elbow_dist1 | lowerarm_twist_01 | 6 | 0.46° | 1.4 mm |
| crj_elbow_dist2 | lowerarm | 7 | 1.44° | 18.7 mm |

- **Fidelity:** 2.08 mm at 90° (35–85°: 2.03 mm); constant past 90°; 0 intersections at 90°.
- **Influences:** 340 vertices need a 5th (both arms).

### Knee (reference: offline shape, keys 90° and 135°, DQS variant without radial restore)

- **Keys:** rest → 90° → 135°, adjacent-key blending; hold beyond 135° (150° is outside scope until a gameplay need).
- **Fit:** shares fitted to both keys at once (one offset per key). Fitting at 135° alone gives a poor 90°.
- **Rotation blending:** any method (slerp, nlerp, matrix within 0.01 mm); every rotation is ≤ 3.7°.
- **Joints:** 8 per leg.

| Joint | Parent | Vertices | Rotation | Translation |
|---|---|---|---|---|
| crj_knee_prox0 | thigh_twist_02 | 58 | 0.08° | 11.4 mm |
| crj_knee_prox1 | thigh_twist_02 | 5 | 3.68° | 3.2 mm |
| crj_knee_prox2 | thigh_twist_02 | 17 | 0.87° | 5.8 mm |
| crj_knee_prox3 | thigh_twist_01 | 6 | 0.53° | 1.4 mm |
| crj_knee_dist0 | calf | 7 | 0.75° | 3.0 mm |
| crj_knee_dist1 | calf | 10 | 0.04° | 2.8 mm |
| crj_knee_dist2 | calf | 31 | 1.16° | 24.6 mm |
| crj_knee_dist3 | calf_twist_01 | 36 | 0.50° | 9.8 mm |

- **Fidelity:** 1.08 mm at 90°, 1.89 mm at 135°; bumps ≤ 0.94 mm; 0 new intersections or fold-overs.
- **Known difference:** the crease line at 135° is 66.4 mm long (prototype: 49.7 mm).
- **Influences:** 330 vertices need a 5th (both legs).

## 3. Totals (exact counts; not performance measurements)

| Item | Count |
|---|---|
| Working corrective joints, both sides | 26 (elbow 10, knee 16) |
| Vertices needing a 5th influence | 670 of 13,380 (5.0%); elbow and knee sets verified disjoint; 688 vertices touched |
| Extra vertex data, second set on affected vertices only | 5,360 bytes (UByte4 + UByte4N) |
| Skinning arithmetic (DQS, multiply-adds per vertex) | about 62 with 4 slots → about 94 with 8 slots, on the vertices carrying the second set |
| Per-frame work | 26 offset interpolations (quaternion + translation) + 26 matrix products |
| GPU/CPU time | **unmeasured**; needs a runtime |

## 4. Per-region parameters each corrective must declare

- driver: joint triple (proximal, mid, distal) and side;
- threshold;
- keys: angles and their joint offsets;
- blending: quaternion required or optional;
- hold behaviour;
- joints: parent, rest centre, and per-vertex share;
- reference shape (offline prototype ID) and its validation results.

## 5. Open before this could become a specification for Cyberwolf

- Runtime implementation and measured cost.
- Driver behaviour with joint twist.
- Behaviour of quantised positions and weights in the runtime format.
- LOD handling: correctives at LOD0 only?
- Interaction with the attachment and cuff system at the elbow and knee seams.
- The skeleton review (OI-17) and any further correctives (groin, shoulder), each needing its own region specification.

## Process notes

- Some parallel runs overwrote each other's result files; those were set aside (`_oi20_overwritten/`) and rerun singly.
- An elbow background run died when its launching command ended. A cleanup command that included a file deletion was
  refused (deletion isn't permitted in the workspace), and the file it targeted had never been created.
- All results cited here come from clean reruns. The elbow LBS reference (0.08 mm at 90°) was reproduced after every
  script change.
