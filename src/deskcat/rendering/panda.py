"""Live offscreen Panda3D → RGBA → Qt. No native child rendering window."""
import math
import os
import time
import sys
import json
import struct
from pathlib import Path

from PySide6.QtGui import QImage
from panda3d.core import (AmbientLight, DirectionalLight, Texture, TextureStage,
                          GraphicsOutput, GraphicsPipe, WindowProperties, FrameBufferProperties,
                          OrthographicLens, loadPrcFileData)
from direct.actor.Actor import Actor
from direct.showbase.ShowBase import ShowBase

from deskcat.states import State
from .playback import ClipClock
from .gltf_scene import load_scene

DEFAULT_MODEL = Path(__file__).resolve().parents[3] / 'assets/3d/test_cat.glb'


def read_contact_gait(path):
    """Read only our optional walk stride contract from the actual GLB JSON."""
    try:
        with Path(path).open('rb') as fh:
            if fh.read(4) != b'glTF':
                return None
            fh.seek(12)
            length, chunk = struct.unpack('<II', fh.read(8))
            if chunk != 0x4e4f534a or length > 4_000_000:
                return None
            meta = json.loads(fh.read(length)).get('extras', {}).get('deskcat_gait', {})
        if meta.get('clip') != 'walk' or meta.get('forward_source_axis') != '-X':
            return None
        stride = float(meta['toe_stance_travel_source_units'])
        stance = float(meta['stance_fraction'])
        period = float(meta['period_seconds'])
        if not (0 < stride < 1 and 0 < stance < 1 and 0 < period < 60):
            return None
        return {'stride': stride, 'stance': stance, 'period': period}
    except (ValueError, KeyError, OSError, TypeError, struct.error, AttributeError):
        return None


class ModelError(RuntimeError):
    pass


class PandaRenderer:
    def __init__(self, model_path=DEFAULT_MODEL, width=240, height=220, clip_map=None):
        self.base = None
        self.actor = None
        self.texture = None
        self._size = None
        self.elapsed = 0.0
        self.clip_overrides = dict(clip_map or {})
        self.direction = 1
        self.heading = 0.0
        self.forward_heading = 0.0
        self.last_frame_ms = 0.0
        self.unavailable_active = []
        self.model_scale = 1.0
        self.brightness = 1.12
        self.offset = (0.0, 0.0)
        self.ortho_height = 2.35
        self.viewport_height_scale = 1.0
        self.camera_height_scale = 1.0
        self._lens_resize_scale = None
        self.source_unit_scale = 1.0
        self.contact_gait = read_contact_gait(model_path)
        if not Path(model_path).is_file():
            raise ModelError(f'Model not found: {model_path}')
        config = ('window-type offscreen\nframebuffer-alpha true\n'
                  'alpha-bits 8\naudio-library-name null\nsync-video false\n'
                  'notify-level warning\n')
        default_backend = ('p3headlessgl' if sys.platform.startswith('linux') and
                           not os.environ.get('DISPLAY') else 'pandagl')
        self.backend = os.environ.get('DESKCAT_PANDA_DISPLAY', default_backend)
        if self.backend not in ('pandagl', 'p3headlessgl', 'p3tinydisplay'):
            raise ModelError('Unsupported DESKCAT_PANDA_DISPLAY backend')
        config += f'load-display {self.backend}\n'
        loadPrcFileData('deskcat', config)
        try:
            self.base = ShowBase(windowType='none')
            self.base.makeDefaultPipe()
            props = WindowProperties()
            props.setSize(width, height)
            fb = FrameBufferProperties()
            fb.setRgbColor(True)
            fb.setRgbaBits(8,8,8,8)
            fb.setDepthBits(24)
            buffer = self.base.graphicsEngine.makeOutput(
                self.base.pipe, 'deskcat-rgba', 0, fb, props,
                GraphicsPipe.BFRefuseWindow | GraphicsPipe.BFResizeable)
            self.base.win = buffer
            if self.base.win is None:
                raise RuntimeError('No offscreen graphics context')
            self.base.winList.append(buffer)
            self.base.makeCamera(buffer)
            self.base.disableMouse()
            self.base.setBackgroundColor(0, 0, 0, 0)
            # No elevated/oblique perspective: a side camera normal to the
            # sagittal X/Z plane after glTF Y-up -> Panda Z-up conversion.
            # Orthographic projection keeps all four leg lengths unchanged.
            lens = OrthographicLens()
            lens.setNearFar(.01, 100)
            self.base.cam.node().setLens(lens)
            self.base.camLens = lens
            self.base.camera.setPos(0, -6.0, .83)
            self.base.camera.lookAt(0, 0, .83)
            ambient = AmbientLight('ambient')
            ambient.setColor((.88,.88,.88,1))
            self.base.render.setLight(self.base.render.attachNewNode(ambient))
            key = DirectionalLight('key')
            key.setColor((.42,.42,.42,1))
            light = self.base.render.attachNewNode(key)
            light.setHpr(-35,-45,0)
            self.base.render.setLight(light)
            fill = DirectionalLight('fill')
            fill.setColor((.20,.20,.20,1))
            fill_node = self.base.render.attachNewNode(fill)
            fill_node.setHpr(155,-30,0)
            self.base.render.setLight(fill_node)
            self.load(str(model_path))
            self._resize(width, height)
        except Exception as exc:
            self.close()
            raise ModelError(f'Cannot initialize 3D renderer: {exc}') from exc

    def load(self, model_path):
        if not Path(model_path).is_file():
            raise ModelError(f'Model not found: {model_path}')
        candidate = None
        try:
            model = load_scene(Path(model_path).resolve())
            characters = list(model.findAllMatches('**/+Character'))
            if len(characters) > 1:
                raise ValueError('Prototype supports exactly one animated skeleton')
            character = characters[0] if characters else None
            # glTF mesh and skeleton can be sibling roots. Actor extracts only
            # Character; retain the skinned geometry and its joint bindings.
            for geom in model.findAllMatches('**/+GeomNode'):
                if character is not None and not character.isAncestorOf(geom):
                    geom.wrtReparentTo(character)
            candidate = Actor(model, copy=False) if character is not None else model
            # Panda's Qt-offscreen framebuffer does not use a glTF PBR shader.
            # Imported metallic/roughness materials may produce alpha=0 on
            # fixed-function drivers, *including when geometry is skinned*.
            # Keep the actual base-color texture but disable unsupported PBR
            # stages/material for BOTH static NodePaths and animated Actors.
            # This changes preview shading only; the embedded GLB remains intact.
            candidate.setMaterialOff(10)
            # Use the original photographic base-color texture at near-white
            # studio brightness. The fixed-function PBR fallback was too dark;
            # source GLB image bytes, fur pattern and materials stay untouched.
            candidate.setLightOff(10)
            candidate.setColorScale(self.brightness, self.brightness, self.brightness, 1)
            for stage in candidate.findAllTextureStages():
                if stage.getMode() != TextureStage.MModulate:
                    candidate.setTextureOff(stage, 10)
            # TinyDisplay's software rasterizer cannot upload sRGB textures.
            # Re-label ONLY the in-memory preview textures as 8-bit RGB(A).
            # Preserve pixel payload, UVs and GLB bytes. Real Windows OpenGL
            # retains sRGB so it can perform native gamma-correct sampling.
            if self.backend == 'p3tinydisplay':
                converted = 0
                for tex in candidate.findAllTextures():
                    if tex.getFormat() == Texture.F_srgb:
                        tex.setFormat(Texture.F_rgb8)
                        converted += 1
                    elif tex.getFormat() == Texture.F_srgb_alpha:
                        tex.setFormat(Texture.F_rgba8)
                        converted += 1
                print(f'DeskCat TinyDisplay: {converted} sRGB preview textures converted '
                      'to software-compatible RGB(A)', file=sys.stderr)
            print('DeskCat bright photographic base-color mode: GLB textures unchanged', file=sys.stderr)
            clips = sorted(candidate.getAnimNames()) if character is not None else []
            unknown = set(self.clip_overrides) - {s.value for s in State}
            if unknown:
                raise ValueError('Unknown state mappings: ' + ', '.join(sorted(unknown)))
            mapping = {state: (state.value if state.value in clips else None) for state in State}
            for name, clip in self.clip_overrides.items():
                if clip is not None and clip not in clips:
                    raise ValueError(f'Mapped clip not found: {name} -> {clip}')
                mapping[State(name)] = clip
            durations = {}
            for clip in clips:
                control = candidate.getAnimControl(clip)
                durations[clip] = control.getNumFrames() / control.getFrameRate()
            clock = ClipClock(durations)
            if character is not None:
                candidate.enableBlend()
                candidate.setBlend(frameBlend=True)
            bounds = candidate.getTightBounds()
            if not bounds:
                raise ValueError('Model has no renderable geometry')
            low, high = bounds
            extent = max(high.x-low.x, high.y-low.y, high.z-low.z)
            if extent <= 0:
                raise ValueError('Model bounds are empty')
            candidate.reparentTo(self.base.render)
            self.source_unit_scale = 2.0 / extent
            candidate.setScale(self.source_unit_scale)
            # Parent transform controls model offset and user scale separately.
            pivot = self.base.render.attachNewNode('model-pivot')
            candidate.reparentTo(pivot)
            candidate.setPos(-(low.x+high.x)/2 * 2/extent,
                             -(low.y+high.y)/2 * 2/extent, -low.z * 2/extent)
            if self.actor is not None:
                if isinstance(self.actor, Actor):
                    self.actor.cleanup()
                self.pivot.removeNode()
            self.actor, self.pivot = candidate, pivot
            self.has_skeleton = character is not None
            if not self.has_skeleton:
                print('DeskCat static model: no skeleton; animations unavailable (NOT played)',
                      file=sys.stderr)
            self.clips = clips
            self.clip_map = mapping
            self.clock = clock
            self.missing_states = [s.value for s, clip in mapping.items() if clip is None]
            self.elapsed = 0.0
            self.model_path = str(Path(model_path).resolve())
            self.unavailable_active = []
            if self.missing_states:
                print('DeskCat missing clips (NOT played): ' + ', '.join(self.missing_states),
                      file=sys.stderr)
        except Exception as exc:
            if candidate is not None:
                if isinstance(candidate, Actor):
                    candidate.cleanup()
                candidate.removeNode()
            raise ModelError(f'Cannot load {model_path}: {exc}') from exc

    def _resize(self, width, height):
        if width <= 0 or height <= 0 or width > 4096 or height > 4096:
            raise ValueError('Render dimensions must be within 1..4096')
        if not math.isfinite(self.viewport_height_scale) or self.viewport_height_scale <= 0:
            raise ValueError('Invalid orthographic zoom viewport')
        zoom_lens = (self.viewport_height_scale, self.camera_height_scale)
        if self._size == (width, height) and self._lens_resize_scale == zoom_lens:
            return
        # Widen both the alpha buffer and the orthographic film when the cat
        # grows. A constant world-units-per-screen-pixel ratio lets it actually
        # appear bigger while retaining its complete silhouette.
        visible_height = self.ortho_height * self.viewport_height_scale
        self.base.camLens.setFilmSize(visible_height * width / height, visible_height)
        center_z = .83 * self.camera_height_scale
        self.base.camera.setPos(0, -6.0, center_z)
        self.base.camera.lookAt(0, 0, center_z)
        self._lens_resize_scale = zoom_lens
        if self._size == (width, height):
            return
        self.base.win.setSize(width, height)
        self.base.win.clearRenderTextures()
        self.texture = Texture('rgba-frame')
        self.base.win.addRenderTexture(self.texture, GraphicsOutput.RTMCopyRam,
                                      GraphicsOutput.RTPColor)
        self._size = (width, height)

    def matched_walk_speed(self, logical_height):
        """Logical pixels/sec matching the toe's planted linear backstroke."""
        if not self.contact_gait or self.clip_map.get(State.WALK) != 'walk':
            return None
        g = self.contact_gait
        source_units_per_sec = g['stride'] / (g['stance'] * g['period'])
        pixels_per_source_unit = (logical_height / (self.ortho_height * self.viewport_height_scale)
                                  * self.source_unit_scale * self.model_scale)
        return source_units_per_sec * pixels_per_source_unit * self.clock.speed

    def frame(self, dt, weights, width, height):
        start = time.perf_counter()
        if not math.isfinite(dt) or dt < 0:
            raise ValueError('dt must be finite and nonnegative')
        self._resize(width, height)
        self.elapsed += dt
        self.pivot.setScale(self.model_scale)
        self.pivot.setX(self.offset[0])
        self.pivot.setZ(self.offset[1])
        target = self.forward_heading + (180 if self.direction < 0 else 0)
        delta = (target - self.heading + 180) % 360 - 180
        self.heading = (self.heading + max(-540*dt, min(540*dt, delta)) + 180) % 360 - 180
        self.pivot.setH(self.heading)
        clip_weights = dict.fromkeys(self.clips, 0.0)
        unavailable = []
        for state in State:
            weight = weights.get(state, 0.0)
            clip = self.clip_map[state]
            if clip is not None:
                clip_weights[clip] += weight
            elif weight > 0:
                unavailable.append(state.value)
        if unavailable != self.unavailable_active and unavailable:
            print('DeskCat requested missing clips (NOT played): ' + ', '.join(unavailable),
                  file=sys.stderr)
        self.unavailable_active = unavailable
        times = self.clock.update(dt, clip_weights)
        for clip in self.clips:
            control = self.actor.getAnimControl(clip)
            index = times[clip] * control.getFrameRate()
            self.actor.pose(clip, index)
            self.actor.setControlEffect(clip, clip_weights[clip])
        if self.has_skeleton:
            self.actor.update()
        self.base.graphicsEngine.renderFrame()
        data = bytes(self.texture.getRamImageAs('RGBA'))
        if len(data) != width * height * 4:
            raise RuntimeError('Unexpected RGBA readback dimensions')
        # Panda readback is bottom-up, straight alpha. Copy before the buffer dies.
        image = QImage(data, width, height, width*4, QImage.Format.Format_RGBA8888).mirrored().copy()
        self.last_frame_ms = (time.perf_counter() - start)*1000
        return image

    @property
    def driver(self):
        gsg = self.base.win.getGsg()
        return gsg.getDriverRenderer() or gsg.getType().getName()

    def close(self):
        if self.actor is not None:
            if isinstance(self.actor, Actor):
                self.actor.cleanup()
            self.actor.removeNode()
            self.actor = None
        if self.base is not None:
            self.base.destroy()
            self.base = None
