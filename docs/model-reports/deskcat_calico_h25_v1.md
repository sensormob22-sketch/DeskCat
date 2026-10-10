# First Tripo Studio model — 2026-10-11

Source: user-uploaded `deskcat_calico_h25_v1.glb`, generated in Tripo Studio H2.5 from `assets/references/DeskCat_Calico_Standing_Side.png`. Studio task URL shown by the user: https://studio.tripo3d.ai/ru/workspace/generate/765801a4-e98e-4514-a438-eaac94f29589 . The screenshot shows 200 → 160 Studio credits: one generation, 40 credits. No API generation, rigging, retargeting or reroll was performed by Codex.

Original file stored unchanged at `assets/3d/tripo/deskcat_calico_h25_v1.glb`:

- 9,898,016 bytes; SHA-256 `ff2a9e1d7280e4784913413fb45b10a2bdeadc125c80791a50f918a3ae646150`.
- GLB 2.0; one mesh/material, 100,796 triangles, 58,450 vertices reported by Khronos validator.
- Three embedded 4096×4096 maps: base color JPEG, metallic/roughness JPEG, normal PNG. No external resources, skin, animations or morph targets.
- Khronos glTF Validator: 0 errors, 1 warning (normal map without explicit tangents; runtime tangent generation may differ), 1 informational message (validator does not support optional `FB_ngon_encoding`). See adjacent validation JSON. Structural validity does not certify anatomy or animation readiness.

## Application compatibility

The prior loader rejected unskinned models. The renderer now supports static NodePath scenes while retaining Actor skeletal animation for rigged models. All seven animation states are reported unavailable; requests are explicitly logged as NOT played. Mouse dragging, model positioning and scale use the existing Qt window.

The existing fixed-function renderer does not evaluate glTF metallic PBR correctly: this model's imported material produced zero foreground alpha. Static preview therefore disables imported material and non-base-color texture stages in memory. It retains base color and ordinary lighting; original PBR maps in GLB are unchanged. This is a preview fallback, not full PBR fidelity. A shader-based PBR renderer and consistent tone mapping remain work items. The preview is darker than Studio.

## Executed checks

Environment: Linux, Python 3.12, PySide6 6.8.3, Panda3D 1.10.15, panda3d-gltf 1.3.0, Mesa llvmpipe LLVM 19.1.7 (software GPU).

- Real import, geometric bounds, render and RGBA → QImage tested on uploaded asset.
- Linux EGL suite: 35 tests passed; includes visible static geometry, transparent background, explicit missing animation reporting, restoration of animated model, existing skeletal deformation and window interaction tests.
- Linux TinyDisplay software-renderer suite: 35 tests passed. This backend is also used by the existing Windows CI, but running it here does not establish a Windows result.
- Qt offscreen smoke with this asset at simulated DPR 1.5: succeeded, 360×330 physical render for 240×220 logical window, corner alpha 0. These simulated Qt values are not a real Windows DPI check.
- 60-frame benchmark at 240×220 after fallback: median 8.525 ms, p95 16.487 ms, mean throughput 95.25 fps. Covers frame work + readback + QImage, excludes Qt painting, DWM and event-loop pacing. Short sample on shared Linux hardware, not Windows performance.
- Four rotated preview frames were rendered and front/opposite screenshots visually inspected. Basic silhouette and identity are recognizable, but paws, tail attachment, underside and whisker mesh still require close interactive examination; no riggability claim.

Windows CI for this change and visual Windows 11 checks have not yet been run. Real DWM transparency, topmost behavior, mouse interaction and actual DPI 100%/150% remain unverified.

## Windows 11 launch

From the repository root in PowerShell, with Python 3.11+ installed:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,three-d]"
.\.venv\Scripts\python.exe -m deskcat --renderer panda --model assets/3d/tripo/deskcat_calico_h25_v1.glb --scale 2 --diagnostics diagnostics/tripo-h25
```

Use the existing documented controls in README. Test over a contrasting wallpaper; look for rectangular opaque regions and capture screenshot + diagnostics. Do not set `QT_QPA_PLATFORM=offscreen` for visual verification. Keep the animated test model as the default until skeletal animation is separately approved and implemented for this asset.

## Use conditions

The user's Studio Free plan screenshot specifies public models and noncommercial use. Treat this generated asset as noncommercial; commercial distribution rights have not been established. Do not describe it as freely licensed or rigged.
