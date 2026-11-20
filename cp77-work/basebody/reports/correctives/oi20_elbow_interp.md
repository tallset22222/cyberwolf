# OI-20: elbow interpolation requirements (tested independently of the knee)

17 Nov 2026. The accepted elbow fits are unchanged: 6 joints per arm, the 90° key, intermediate keys at 50° and 70°.
Script: `basebody/oi20_interp_check.py`. Data: `oi20_elbow_interp_{DQS,LBS}.json`.
- Errors are the maximum distance from the offline prototype on the elbow region, swept 0–150° in 5° steps.
- Each arm was bent alone; **left and right gave identical results in every variant.**
- No variant created intersections or fold-overs at 60° or 90°, on either arm.

| Runtime behaviour | DQS (primary): to 90° (35–85°) | DQS: up to 30° | LBS: to 90° (35–85°) | LBS: up to 30° |
|---|---|---|---|---|
| As fitted: smoothstep 30→90°, piecewise over 50/70/90° keys, slerp | 2.08 (2.03) mm | exact | 0.50 (0.50) mm | exact |
| Normalised quaternion lerp | 2.08 (2.03) | exact | 0.50 (0.50) | exact |
| Component-wise matrix blend | 2.46 (2.46) | exact | 0.50 (0.50) | exact |
| Linear activation | 2.08 (2.03) | exact | 0.69 (0.69) | exact |
| Without the 50/70° intermediate keys | 2.08 (2.03) | exact | 1.01 (1.01) | exact |
| Runtime threshold 25° (authored 30°) | 2.08 | **0.13 mm early** | 0.50 | **0.16 mm early** |
| Runtime threshold 35° | 2.08 | exact | 0.51 | exact |
| Inverse-distance RBF over key angles, power 1 | 2.19; 4.01 at 135° | **1.68 mm** | 2.65; 4.01 at 135° | **2.03 mm** |
| … power 2 | 2.08; 2.55 at 135° | **0.59 mm** | 1.23; 2.50 at 135° | **0.72 mm** |
| … power 4 | 2.08 | 0.07 mm | 1.32; 2.44 at 135° | 0.08 mm |

## How the elbow's requirements differ from the knee's

1. **DQS doesn't use the intermediate keys.**
   - Its error is set at the 90° key itself (2.08 mm) and stays there through the movement. Dropping the 50/70° keys
     changes nothing. A DQS runtime needs only rest → 90° for the elbow.
   - Unlike the knee, DQS here is sensitive to the blend method. A component-wise matrix blend adds 0.38 mm (2.46 vs
     2.08), so nlerp or slerp is required.
2. **LBS does use the intermediate keys:** 1.01 mm without them, 0.50 mm with. Its blend method doesn't matter.
3. **Activation threshold.** A runtime threshold set 5° *early* activates the corrective below 30° (0.13–0.16 mm).
   That is small, but it breaks the exact-rest criterion. 5° late costs ≤ 0.01 mm. The threshold must match the
   authored 30°, or err on the late side.
4. **Hold beyond the last key.** The prototype holds the 90° correction past 90°. An RBF that keeps weight on the rest
   key releases it: at 135° the error rises to 4.01 mm with power 1. So the runtime must hold the last key, as with
   the knee.
5. **Generic inverse-distance RBF fails here too.** Low powers activate below 30° (up to 2 mm), and high powers sag
   between keys for LBS (1.3 mm). Same conclusion as the knee, reached independently.

## Requirements common to both joints (tested separately)

- Interpolation between *adjacent* keys along one flexion driver.
- An exact zero up to the authored threshold.
- Holding the last key beyond it.
- Smooth activation is preferred; the curve shape itself matters little.

## Requirements that differ per joint

- **Intermediate keys:** elbow LBS needs them; elbow DQS doesn't; the knee uses its two real keys.
- **Blend method:** elbow DQS needs quaternion blending; the knee doesn't care.
