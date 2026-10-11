# Tripo preflight — DeskCat character identity (NO PAID GENERATION)

## Status and source integrity

Prepared on 2026-10-10 for `feature/tripo-cat`. **No Tripo generation, rigging, retarget, or billable operation has been authorized or performed by this stage.**

The user has a separate `DeskCat_Tripo_Reference_Pack_v1.zip` prepared in ChatGPT; upload its actual image files to the Codex task. This repository document does **not** contain the binary reference images yet. Do not assume the archive is already present in the Codex workspace.

The reference set has two **not independently verified to be the same individual cat**:
- `character_identity_seated_original.png` — 1312×1199, RGBA. **Primary appearance/identity reference:** white-based short-haired calico/torbie-and-white cat; white face blaze, green-looking eyes, white chest and legs, orange and dark tabby-patched torso, banded dark/orange tail. This is a **seated** pose; not directly animation-ready.
- `standing_side_lowres_original.png` — 380×300, RGBA. **Secondary posture/silhouette reference only.** Its face/pattern may differ, and detail lost at this resolution cannot be inferred reliably.
- `head_detail_exact_crop.png` and `fur_detail_exact_crop.png` are crops, **not additional camera angles**.
- `reference_review_sheet.jpg` is a review aid, **not a multi-view generation input**.

Do **not** submit these as genuine front/back/left/right captures of one animal. Do **not** invent unseen markings or use a text-only tabby prompt in place of these references. If Tripo accepts several image inputs, use only if the feature is compatible with their provenance. It is better to request one image-to-model trial than a pseudo-multiview mix.

## Design goal

One photorealistic four-legged domestic cat, **same character** as the high-resolution identity reference, neutral standing pose on all four paws, short fur, natural proportions, ears and face intact, separate legs with space under abdomen, separate tail, clean mesh and UV/PBR textures, candidate for quadruped rig. No ground/plinth/accessories.

Important tradeoff: **seated photo has superior identity but poor standing-geometry evidence; small standing photo has useful pose but weaker character fidelity.** An image-to-3D generator may preserve one objective at the expense of the other. Do not describe the character fidelity as solved until a model is inspected.

## No-charge actions now

1. In browser Codex, verify Tripo plugin/CLI availability, print its current documentation (`tripo docs --topic commands/make`, if supported) and verify the intended image-input command.
2. Query the **current** model/version, balance and credits/price for *one* image-to-model generation. Prices in older docs are indicative only, not an approval. Obtain a dry-run/plan only **if** the installed CLI actually supports it; otherwise use read-only documentation and pricing.
3. Decide a single reference as generation input; separately state how the other reference informs *manual quality assessment*.
4. Present the exact prospective input file, CLI or plugin action, parameters, name, expected credit cost and likely output file path. **Stop and ask for explicit authorization before any `tripo make`, `tripo ai` execution, model generation, texture refinement, rigging or retargeting.** Do not chain `--then` tasks.
5. Keep private tokens and temporary links out of GitHub and diagnostic logs.

Authoritative developer guidance: https://developers.tripo3d.ai/en/docs/cli and https://developers.tripo3d.ai/en/docs/generation-image-to-model . The CLI documentation supports single-image input but does **not** establish that this pair constitutes a consistent multiview dataset.

## Acceptance gates (once explicitly authorized)

**Gate A — appearance:** high-resolution face reference compared side-by-side; correct white blaze, ears, green eyes, white chest/legs, orange and dark patched/striped fur, tail color; unexplained changes rejected.

**Gate B — geometry:** inspect GLB in freely rotatable 360° preview: four separated paws, feline shoulder/elbow/wrist and hip/knee/hock proportions, visible underside of torso, no fused limbs, clean watertight-enough texture surfaces, separate unfused tail.

**Gate C — runtime:** glTF Validator; one skinned skeleton (only after separately approved auto-rig), consistent transforms and bind pose, Panda3D skinning, all four paw contact and a period-accurate walk clip. Missing animation clips should be reported, not silently fabricated.

**Gate D — Windows visuals:** transparency, shadows, scale, mouse interactions and performance on *real* Windows 11 with this final heavy asset. Previous visual proof applied to the tiny diagnostic GLB only.

Rig, retarget, smoothing/remeshing and additional generations are **separate billable actions requiring separate explicit user approval**, even if the first model passes geometry review.

## Deliverables before paying

- A single clear plan with command, documented parameters, exact input and quoted current expected credits.
- Written risks: sitting-to-standing mismatch; unseen side/back appearance; fur quality/real-time rendering; clean 4-leg topology and rig reliability.
- A visible approval checkpoint: **STOP — awaiting user permission**.
