# DeskCat calico — rig-readiness checkpoint (read-only)

Source: `assets/3d/tripo/deskcat_calico_h25_v1.glb` (Tripo Studio H2.5), original SHA-256 `ff2a9e1d7280e4784913413fb45b10a2bdeadc125c80791a50f918a3ae646150`.

**Decision: NEEDS REPAIR / MANUAL REVIEW, not APPROVED FOR RIGGING.** Visual inspection of the user's rotating Tripo Studio recording found a recognizable cat silhouette but ambiguous bent/raised legs, rough underside, paw pads and whiskers. Video-based findings are *visual*, not a topology or skin-deformation test. Do not make the source GLB look neutral merely by rotating the whole mesh or adding a skeleton without checking geometry.

## Zero-cost audit package

The accompanying `DeskCat_Rig_Preparation_v1.zip` prepared in ChatGPT (not yet present in GitHub) contains a read-only Python standard-library script `tools/rig_readiness_audit.py` and three synthetic tests. Attach that ZIP in Codex and inspect the files before running them. From repository root:

```powershell
.\.venv\Scripts\python.exe tools/rig_readiness_audit.py assets/3d/tripo/deskcat_calico_h25_v1.glb --output diagnostics/rig-readiness.json
```

Outputs SHA-256, scene-space AABB, triangles/vertices, exact degenerate triangles, normal-map tangent warning and counts of near-ground vertices per **unlabelled** glTF X/Z quadrant. **Not** proof of foot contact: low surface points can be fur/noise, and quadrants are not anatomical leg identification. No paid Tripo operations. Original GLB must remain byte-identical.

## Manual sign-off checklist

- **Silhouette and identity:** compare face, ear, tail and coat markings to approved character reference; preserve original texture maps.
- **Four-paw neutral stance:** name front-left, front-right, hind-left, hind-right using visible anatomy; confirm all intended pads are close to the same ground plane.
- **Joint corridors:** visually locate shoulder/elbow/wrist and hip/stifle/hock, tail base; no fused limbs or skin bridges. Inspect sides, rear, front, underside at close range.
- **Geometry and weights:** mesh must deform smoothly at shoulder, elbow, wrist, hip, stifle, hock and tail. A single mesh is not automatically disqualifying; GLB Validator zero errors is not acceptance.
- **Textures:** any proposed repair is a copy with a new filename, e.g. `deskcat_calico_h25_v1_rigprep.glb`. Preserve reference original and SHA-256. Avoid repainting face/coat.
- **Detail:** inspect whiskers and inner ears. Consider non-deforming whisker rendering if appropriate; never claim automated repair until inspected.

## Proposed conceptual bones — NOT an existing rig

```text
root
  pelvis -> spine -> chest -> neck -> head
  pelvis -> hind_L_upper -> hind_L_lower -> hind_L_hock -> hind_L_paw
  pelvis -> hind_R_upper -> hind_R_lower -> hind_R_hock -> hind_R_paw
  chest -> front_L_upper -> front_L_forearm -> front_L_wrist -> front_L_paw
  chest -> front_R_upper -> front_R_forearm -> front_R_wrist -> front_R_paw
  pelvis -> tail_01 -> tail_02 -> tail_03 -> tail_04
```

This diagram is **not** an anatomically surveyed set of joint coordinates; cat limb kinematics differ from humanoid rigs. Correct anatomical axes before animation.

## Sequential gates

1. Codex runs the read-only audit against the actual repository GLB and archives factual JSON under `docs/model-reports/`; review any error rather than bypassing it.
2. Codex creates five inspection angles and closeups of all four paws. State which assumptions cannot be established from geometry alone.
3. Based on those results, choose **ACCEPT FOR RIGGING**, **REPAIR THEN RETEST**, or **REJECT**. Current verdict is **REPAIR THEN RETEST**.
4. Any remeshing/neutral posing must produce **a new candidate GLB**, never overwrite the original. Compare source and repaired mesh visually and validate UV and normals.
5. Only with *separate explicit approval*, price a Tripo quadruped rig or alternative Blender/Codex cloud pipeline. No `tripo make`, rigging, retargeting or animation generation in this stage.
6. Later, validate deformations, four paw contacts, calibrated in-place walk clip and real Windows 11 performance/PBR+alpha.

Licensing: previous model report records Free-plan public/noncommercial use; commercial distribution rights remain unverified.
