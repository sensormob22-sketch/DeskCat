DeskCat - walking calico cat for Windows 11 (experimental)
====================================================================

FIRST START (Windows 11, Python 3.11)
1. Extract ALL files from this ZIP into a normal folder, e.g. Desktop\DeskCat.
2. Double-click Start_DeskCat.cmd.
3. The first launch creates a local .venv and installs PySide6 and Panda3D from
   PyPI. Internet connection is required once. No Blender, Tripo, or Ollama needed.
4. A transparent frameless cat appears and starts walking from right to left.

CONTROLS
Right-click the cat: switch between walk / idle, or Exit.
W: switch walk / idle (after focusing the cat window).
Left mouse button + drag: move the window. Wheel: resize the cat AND its transparent rendering window (no cropping).
The maximum zoom is bounded by usable screen size; R restores the original size.
Space: pause; Esc: close.

TROUBLESHOOTING
- If Windows warns about an unrecognised .cmd, inspect the readable batch
  file before running. This is SOURCE distribution, not a signed executable.
- Requires working OpenGL and Windows display driver. Rendering may be slow
  on integrated GPUs; try smaller --scale in Start_DeskCat.cmd.
- If the cat faces backwards, edit --forward-heading 180 in Start_DeskCat.cmd.
- Right-click control is only available when you click an opaque part of the cat.
- If it does not launch, do not close the command window. Copy its final error
  message into your ChatGPT conversation.

STATUS
Real skinned 3D glTF with idle/walk; this is an experimental four-beat gait.
Camera is orthographic and strictly side-on, not three-quarter perspective.
Desktop speed is automatically matched to each paw's planted toe backstroke.
Use --walk-speed 28 in Start_DeskCat.cmd ONLY to override this matching manually.
Windows 11 transparent DWM presentation has NOT been tested on a physical
user desktop. Some contact/sliding and skin deformations still need polish.
No startup registration, no ads, no paid subscriptions, no external model calls.
Source: https://github.com/sensormob22-sketch/DeskCat (PR #2)

REFERENCE-BRIGHT CALICO AND SOFT MOTION
The photographic original base-color texture is shown without dark fixed-function
PBR shading; press '=' or '+' to brighten slightly, '-' to dim when focused.
Right rear lower leg has a local trial skin correction. Lumbar, chest, neck,
and head have new tiny motions. Original fur, geometry, UV and tail clip remain.

The monitor-bright preview now uses RGB-only gamma correction. Alpha is
unchanged and the GLB original diffuse images are still preserved.

ZOOM READBACK REPAIR / EXTRA BRIGHTNESS
The renderer now maintains one fixed-resolution Panda RGBA buffer for its
entire lifetime. Zoom changes the transparent Qt window and display scale,
without resizing any Panda3D graphics buffer. This prevents the observed
Windows OpenGL "Unexpected RGBA readback dimensions" resize race.
Since frames are scaled by Qt, extreme zoom can soften fine fur details.
Brightness is +50% on the previous calibrated RGB tone curve (values are
clamped to 255/monitor white); original GLB textures and alpha are unchanged.

STAGE 19: NATIVE SHARP ZOOM + SYMMETRIC RIGHT-HIND LEG
Each zoom wheel click now enlarges the actual 3D model; Qt crops a preallocated
native-resolution RGBA render. Onscreen window geometry expands only to keep
the cat visible. No low-res bitmap upscaling, no Panda buffer resize on wheel.
The larger offscreen surface may need more GPU bandwidth on older systems.

Right hind skin weights are based on mirrored LEFT hind skin with longitudinal
alignment to the original asymmetric leg mesh. All source textures/geometry
and tail motion remain preserved; contact quality still requires video review.
New four-beat IK gait compensates front paws for gentle spine flexion.

STAGE 20 — CONTINUOUS DESKTOP LOOP AND MIRRORED LEG REST
The cat never reverses automatically at the screen edges: it walks all the way
outside the chosen monitor, then enters from the opposite side with the same
walking direction and uninterrupted animation phase.
The RIGHT fore and hind rest joint chains are exact Z-plane mirrors of the
LEFT chains, including glTF inverse-bind translations. The source mesh, UV,
photo coat and original tail motion are not changed. The right lower hind-leg
skinning uses a mirrored left-side donor. These remain experimental weights.
The lumbar/chest back bend is more apparent, with a small left/right yaw in
the head and neck. Visual confirmation on real Windows is still necessary.
