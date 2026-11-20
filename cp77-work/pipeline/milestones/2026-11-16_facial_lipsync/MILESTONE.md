# Milestone 2026-11-16 (b): facial animation and lipsync

Adds to the body-animation milestone:
- Facial setup decode (bakedData, mainPosesData, correctivePosesData): byte-exact for Jackie and Judy.
- Correctives: components verified against names (255/255 face, 4/4 tongue). Combination rule INFERRED (product default, min selectable).
- Envelopes/limits: decoded; neutral when envelope tracks are 0 (idle clips). Active behaviour NOT established.
- Facial clips (generic head rig) apply to Jackie and Judy: identical 414 tracks / 344 joints, verified.
- Lipsync: <pose>LipsyncPoseOutput tracks drive the poses. Evidence: 22 Jackie lines (q000_kid_03_back_to_bar, en-us),
  durations within 16 ms of audio, best offset 0 ms (17/22), loudness vs lip opening r = 0.81 pooled, closures in 7% of speech frames.

Unresolved (deliberately not defaulted):
- AnimOverrideWeight tracks (86, values -1.2..0): purpose unknown; default 'ignore'.
- Lipsync generality: only Jackie, one scene, en-us tested. Judy, another character and another language still to test.

Baselines frozen here: regression (8), anim (21 clips), facial (10 checks).
