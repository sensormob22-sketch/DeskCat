"""Live offscreen Panda3D → RGBA → Qt. No native child rendering window."""
import os
import sys
from pathlib import Path

from PySide6.QtGui import QImage
from panda3d.core import (AmbientLight, DirectionalLight, Texture,
                          GraphicsOutput, NodePath, loadPrcFileData)
from direct.actor.Actor import Actor
from direct.showbase.ShowBase import ShowBase
import gltf

from deskcat.states import State

DEFAULT_MODEL = Path(__file__).resolve().parents[3] / 'assets/3d/test_cat.glb'


class ModelError(RuntimeError):
    pass


class PandaRenderer:
    def __init__(self, model_path=DEFAULT_MODEL, width=240, height=220):
        self.base = None
        self.actor = None
        self.texture = None
        self._size = None
        self.elapsed = 0.0
        self.model_scale = 1.0
        self.offset = (0.0, 0.0)
        if not Path(model_path).is_file():
            raise ModelError(f'Model not found: {model_path}')
        config = ('window-type offscreen\nframebuffer-alpha true\n'
                  'alpha-bits 8\naudio-library-name null\nsync-video false\n'
                  'notify-level warning\n')
        if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
            config += 'load-display p3headlessgl\n'
        loadPrcFileData('deskcat', config)
        try:
            self.base = ShowBase(windowType='offscreen')
            if self.base.win is None:
                raise RuntimeError('No offscreen graphics context')
            self.base.disableMouse()
            self.base.setBackgroundColor(0, 0, 0, 0)
            self.base.camLens.setFov(35)
            self.base.camLens.setNearFar(.01, 100)
            self.base.camera.setPos(2.8, -4.5, 2.4)
            self.base.camera.lookAt(0, 0, .65)
            ambient = AmbientLight('ambient')
            ambient.setColor((.65,.65,.65,1))
            self.base.render.setLight(self.base.render.attachNewNode(ambient))
            key = DirectionalLight('key')
            key.setColor((.8,.8,.8,1))
            light = self.base.render.attachNewNode(key)
            light.setHpr(-35,-45,0)
            self.base.render.setLight(light)
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
            model = NodePath(gltf.load_model(str(Path(model_path).resolve())))
            characters = list(model.findAllMatches('**/+Character'))
            if len(characters) != 1:
                raise ValueError('Prototype supports exactly one animated skeleton')
            character = characters[0]
            # glTF mesh and skeleton can be sibling roots. Actor extracts only
            # Character; retain the skinned geometry and its joint bindings.
            for geom in model.findAllMatches('**/+GeomNode'):
                if not character.isAncestorOf(geom):
                    geom.wrtReparentTo(character)
            candidate = Actor(model, copy=False)
            clips = set(candidate.getAnimNames())
            missing = {state.value for state in State} - clips
            if missing:
                raise ValueError('Missing animation clips: ' + ', '.join(sorted(missing)))
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
            candidate.setScale(2.0 / extent)
            # Parent transform controls model offset and user scale separately.
            pivot = self.base.render.attachNewNode('model-pivot')
            candidate.reparentTo(pivot)
            candidate.setPos(-(low.x+high.x)/2 * 2/extent,
                             -(low.y+high.y)/2 * 2/extent, -low.z * 2/extent)
            if self.actor is not None:
                self.actor.cleanup()
                self.pivot.removeNode()
            self.actor, self.pivot = candidate, pivot
            self.elapsed = 0.0
        except Exception as exc:
            if candidate is not None:
                candidate.cleanup()
                candidate.removeNode()
            raise ModelError(f'Cannot load {model_path}: {exc}') from exc

    def _resize(self, width, height):
        if width <= 0 or height <= 0 or width > 4096 or height > 4096:
            raise ValueError('Render dimensions must be within 1..4096')
        if self._size == (width, height):
            return
        self.base.win.setSize(width, height)
        self.base.camLens.setAspectRatio(width / height)
        self.base.win.clearRenderTextures()
        self.texture = Texture('rgba-frame')
        self.base.win.addRenderTexture(self.texture, GraphicsOutput.RTMCopyRam,
                                      GraphicsOutput.RTPColor)
        self._size = (width, height)

    def frame(self, dt, weights, width, height):
        if dt < 0:
            raise ValueError('dt must be nonnegative')
        self._resize(width, height)
        self.elapsed += dt
        self.pivot.setScale(self.model_scale)
        self.pivot.setX(self.offset[0])
        self.pivot.setZ(self.offset[1])
        for state in State:
            clip = state.value
            control = self.actor.getAnimControl(clip)
            index = (self.elapsed * control.getFrameRate()) % control.getNumFrames()
            self.actor.pose(clip, index)
            self.actor.setControlEffect(clip, weights.get(state, 0.0))
        self.actor.update()
        self.base.graphicsEngine.renderFrame()
        data = bytes(self.texture.getRamImageAs('RGBA'))
        if len(data) != width * height * 4:
            raise RuntimeError('Unexpected RGBA readback dimensions')
        # Panda readback is bottom-up, straight alpha. Copy before the buffer dies.
        return QImage(data, width, height, width*4, QImage.Format.Format_RGBA8888).mirrored().copy()

    @property
    def driver(self):
        return self.base.win.getGsg().getDriverRenderer()

    def close(self):
        if self.actor is not None:
            self.actor.cleanup()
            self.actor = None
        if self.base is not None:
            self.base.destroy()
            self.base = None
