# DeskCat — artist brief and acceptance specification

## Scope and inputs

Manually validate a feline quadruped rig and paint topology-aware skin weights on the existing photorealistic calico cat. Preserve the character. **Do not create locomotion, sitting or grooming clips yet.** Start from `assets/rigging/deskcat_v6_weight_handoff.blend` (Blender 4.3.2): rest pose, 17 unverified bones, pre-export v6 weights, six review masks and packed original textures. V6 is a rejected production rig, not a validated starting result.

The immutable appearance original is `assets/3d/tripo/deskcat_calico_h25_v1.glb`. The scene and stable source vertex/face IDs use the separately included `deskcat_calico_h25_v1_localprep.glb`; IDs must not be interpreted as original/exported GLB indices. Save all work under new agreed names. File integrity is recorded in MANIFEST.json.

Two standing reference PNGs are available, but they are synthetic interpretations, not verified photographs/orthographic views. The original seated identity reference is missing from the repository and not supplied. Existing model/packed textures are the primary appearance baseline; do not invent unseen markings. Preserve face, eyes, ears, white blaze/chest/paws, orange/dark markings, banded tail, tail length, proportions and stance asymmetry. No texture replacement, UV edits, global remesh or new generation.

## Rig and manual weight requirements

Validate cat-specific shoulder/scapula → elbow → wrist/paw and pelvis → hip → stifle → hock/paw chains. Cats are digitigrade; do not impose human leg anatomy. Review root/thoracic/lumbar/pelvis hierarchy and tail attachment. Existing anatomical landmarks and bone pivots are hypotheses. Additional scapular/paw/tail segments, rest-pose changes or topology corrections require an explicit plan and approval; retain the bind surface and provide a correspondence map. Authoring constraints are not a substitute for exportable deform joints.

Coordinates: glTF Y-up, head −X, anatomical left +Z; Blender conversion (x,−z,y). FL/FR = front left/right; HL/HR = hind left/right. Diagnostic rotations use Blender world +Y / glTF −Z relative to rest, transformed into each bone's rest-local axis. New rigs must reproduce equivalent physical motions and explain any changed axes.

Six regions: tail/pelvis, thoracic/abdomen, left hip/groin, right shoulder/front paw, wrists/soles and hocks/soles. Use stage9 EDIT/REVIEW/PROBLEM groups and region_masks.json. Read WEIGHT_PAINT_SPEC.md and weight_paint_spec.json. **10,459 protected head/sole vertices remain frozen** in rest geometry, UV and baseline bone weights. GUI locks are only aids; verify source IDs. Existing pre-export weights are authoritative; tiny influences reconstructed from exported GLB are not exact baseline values.

Paint transitions along actual anatomy and topology, not global coordinate envelopes or blindly mirrored limbs. Keep unrelated baseline influences and other regions unchanged during each approved local operation. Weights: finite, nonnegative, ≤1, up to four deform influences, sum 1±1e−6. Exact-position UV-seam aliases must have matching weight rows within 1e−7 and remain coincident when deformed. Do not let tail weights pull rump/legs, or one limb drive another. Protected paw contact patches retain shape; spread wrist/hock transitions above them. Mask overlap does not authorize additive independent edits.

The scene's embedded `DESKCAT_REVIEW_UI.py` may be explicitly run from Scripting to select masks/poses; no auto-run required. Return to rest before saving. Existing HEAT colors show baseline diagnostic weights and must not be exported as unwanted COLOR_0 replacing the coat. The Blender GUI painting workflow has not been visually certified on this cloud machine.

## Evidence and controlled poses

Stage8 v6 retained thoracic and left-hip failures. Stage10 C2 was only a proposal; stage11's 21-row trial did not improve intersections. Stage12's fixed local cages worsened tail +15° 44→228 new pairs and combined positive 147→389, with inconsistent masks across 21 UV-alias sets. These are **rejected examples**, not baselines or instructions to apply another trial. They do not prove that every cage approach fails or that retopology is mandatory.

CONTROL_POSES.json contains explicit angles and baseline counts: rest, isolated ±10°/±15° for tail, thoracic, left hip and right shoulder, wrist/hock probes, each stage9 region's positive/negative holdouts, additional front/hind chain controls and stage12 combined controls. These are diagnostic movements, not certified anatomical limits. No new poses or animations were generated when assembling this package.

For every agreed region, deliver matched rest/positive/negative/combined views: side, rear, underside and close-up. Include base-color and untextured surface views with identical camera/scale/light settings, plus a short deformation review video. Do not substitute a walk clip or a single flattering rest image. Preserve editable mask/source IDs; if export splits/reorders vertices, provide an explicit mapping.

Acceptance gates:

1. **Identity:** no changed face/eyes/ears, markings, proportions, tail length, paw shape or UV/texture payloads. Differences must be reported, never hidden by lighting or a replacement texture.
2. **Deformation:** no visible seam tears, inward collapses, sharp compression rings, stretched spikes, flattened contact patches or new neighboring-region regressions, in both directions and holdouts. Fewer intersection pairs alone are insufficient.
3. **Measurement:** report exact new triangle pairs separately from the known 16 rest pairs; locate them by source IDs/coordinates and classify visible failures versus tiny decorative fur-shell crossings. The existing strict edge/triangle test excludes shared vertices, tangencies and coplanar overlaps; counts are not a complete collision certificate. Report area/edge ratios (min/max and P1/P5/P50/P95/P99), collapsed/inverted/degenerate triangles and seam gaps. Area <0.5 or >2× rest is a review trigger, not an automatic universal pass/fail threshold. Establish quantitative tolerances with the client before work; explain any remaining extreme values alongside images.
4. **Audit:** full changed weight rows and bone/rest changes; protected and out-of-scope rows checked; geometry/UV/material/image hashes; no unapproved topology edits. Any proposed local retopology is a separately agreed scope, not an assumed necessity.

## Standalone GLB and actual Panda3D requirements

Deliver a separate editable .blend and a standalone glTF 2.0 binary .glb with embedded images/buffers, explicit deform joints, correct inverse bind matrices and normalized skin weights. Bind pose must reproduce the accepted neutral cat without scale/orientation/paw-contact changes. No dependence on Blender-only constraints, cages, drivers, unapplied nonportable modifiers or external textures. No production morph-cage substitution without explicit agreement. Keep scene controls separate from exported deform joints; no animation clips required for this pre-animation gate.

Retain the three original image payloads, UVs and material semantics. Report extension/sampler/normal/tangent/image-order changes and why they occur. Do not leak diagnostic COLOR_0. If an exporter changes material representation, match texture hashes and demonstrate actual appearance; passing schema validation alone is insufficient. Blender 4.3.2 previously dropped influences **≤0.0001** and renormalized the remainder: audit actual exported rows and compare deformation, not just pre-export .blend values. Record exporter/version/options and joint index mapping.

Run Khronos glTF Validator: no errors; review and justify every warning, including generated tangent space. Load the delivered skin with the project's **Panda3D 1.10.15 / panda3d-gltf 1.3.0** path and actually drive the joints at accepted controls, comparing geometry and visuals against Blender. A valid file or successful import is not proof of deformation. Discrete baked cage morph playback from stage12 proves only diagnostic pose portability. Full PBR has not been certified by the prior base-color previews.

Final runtime gate requires a **real Windows 11 graphical session**: transparent frameless always-on-top window, no opaque rectangle, clean alpha/edges/coat appearance, mouse dragging, correct paw placement and scale at DPI 100% and 150%, measured frame-time/FPS on a named GPU/driver/resolution. Define the target frame budget and hardware with the client before acceptance; no invented performance target or CI-derived transparency claim. Agree who supplies/runs that machine. Linux tests and Windows CI must be reported separately from actual Windows visual evidence.

## Deliverables, milestones and payment acceptance

Return: new named .blend and skinned GLB; rig/axis/rest map; complete weight/vertex/UV/image/material/export diff; shot-by-shot pose images and review video; remaining-issue classifications; validator log; actual Panda3D and agreed Windows evidence. No prior input overwrite; no production-ready claim before the gates pass.

1. **Paid/unpaid diagnostic planning**, as agreed before starting: review anatomy, identify risks, propose bounded regions/rig changes and estimate the artist's effort. Diagnostic payment terms must cover a possible recommendation to stop.
2. **One approved local region:** deliver a new copy, both bending directions and holdouts, measurable diff and visual result. Client accepts against the identity/seam/shape gates before extending scope.
3. **Remaining approved regions:** manual work and full regression controls after each milestone. Additional joints or local retopology require a separately approved scope and acceptance criteria.
4. **Export/runtime delivery:** accept only after .blend/GLB, actual deformation, export audits and agreed runtime/Windows gates are satisfied, or the client explicitly documents a deferred gate.

The artist proposes prices, deposit, schedule, revision count and payment terms; **this brief invents no rates**. Tie payments to verifiable milestone deliverables and written acceptance. Agree defect-rework rules and scope-change pricing upfront. Creating bones, screenshots or promising a future export is not acceptance of a finished rig. Walk/sit/groom are a separate later commission after deformation acceptance.
