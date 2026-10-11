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
