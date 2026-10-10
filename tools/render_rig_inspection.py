"""Render original geometry, never synthesized or repaired inspection images.

Uses DeskCat's documented base-color preview fallback. No Tripo calls.
Camera directions refer to the visually verified X-negative head of this asset.
"""
import argparse
import json
import hashlib
from pathlib import Path
from panda3d.core import OrthographicLens, Point3, Vec3, Point2, TextNode, LineSegs, TextureStage
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State


def render(path, output, landmarks=None, geometry_review=None, geometry_only=False, reference_model=None, wireframe=False, base_color_preview=False, bone_guides=None, pose=None):
    output.mkdir(parents=True, exist_ok=True)
    renderer = PandaRenderer(path, width=1400, height=1100)
    try:
        if reference_model:
            from rig_readiness_audit import read_glb, accessor
            doc, binary, _ = read_glb(reference_model)
            primitive = doc['meshes'][0]['primitives'][0]
            positions = accessor(doc, binary, primitive['attributes']['POSITION'])
            low = [min(p[i] for p in positions) for i in range(3)]
            high = [max(p[i] for p in positions) for i in range(3)]
            factor = 2 / max(high[i]-low[i] for i in range(3))
            renderer.actor.setScale(factor)
            renderer.actor.setPos(-(low[0]+high[0])/2*factor,
                                  (low[2]+high[2])/2*factor, -low[1]*factor)
        if base_color_preview:
            renderer.actor.setMaterialOff(20)
            for stage in renderer.actor.findAllTextureStages():
                if stage.getMode() != TextureStage.MModulate:
                    renderer.actor.setTextureOff(stage, 20)
        if wireframe:
            renderer.actor.setRenderModeWireframe()
        renderer.base.setBackgroundColor(.72, .72, .72, 1)
        if geometry_only:
            renderer.actor.setTextureOff(20)
            renderer.actor.setMaterialOff(20)
            renderer.actor.setColor(.8,.8,.8,1,20)
        lens = OrthographicLens()
        lens.setNearFar(.01, 100)
        renderer.base.cam.node().setLens(lens)
        if bool(landmarks) != bool(geometry_review):
            raise ValueError('Annotations require both landmarks and geometry review')
        labels = json.loads(landmarks.read_text()) if landmarks else None
        review = json.loads(geometry_review.read_text()) if labels else None
        if labels:
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if sha not in labels['accepted_geometry_sha256'] or sha != review['sha256']:
                raise ValueError('Annotation/review source SHA does not match model')
        feet = review['paw_surface_segmentation']['feet'] if labels else {}
        overlay = None
        if labels:
            renderer.base.makeCamera2d(renderer.base.win)
        factor = renderer.actor.getScale().x
        def marker(root, name, p, color):
            world = Point3(p[0]*factor, -p[2]*factor, p[1]*factor) + renderer.actor.getPos()
            projected = Point2()
            if not lens.project(renderer.base.cam.getRelativePoint(renderer.base.render, world), projected):
                return
            x, z = projected
            lines = LineSegs()
            lines.setColor(*color)
            lines.setThickness(2)
            lines.moveTo(x-.01, 0, z); lines.drawTo(x+.01, 0, z)
            lines.moveTo(x, 0, z-.012); lines.drawTo(x, 0, z+.012)
            root.attachNewNode(lines.create())
            text = TextNode(name)
            text.setText(name)
            text.setTextColor(*color)
            node = root.attachNewNode(text)
            node.setScale(.03)
            node.setPos(x+.015, 0, z+.016)
        if bool(bone_guides) != bool(pose):
            raise ValueError('Bone guides require a matching pose')
        if bone_guides:
            guides = json.loads(bone_guides.read_text())
            if hashlib.sha256(path.read_bytes()).hexdigest() != guides['model_sha256_by_pose'][pose]:
                raise ValueError('Bone guides do not match snapshot SHA')
            lines = LineSegs(); lines.setThickness(2)
            lines.setColor(1,.85,.05,1)
            for name, bone in guides['poses'][pose].items():
                if name == 'root': continue
                def point(key):
                    p = bone[key]
                    return Point3(p[0]*factor, -p[2]*factor, p[1]*factor) + renderer.actor.getPos()
                lines.moveTo(point('head_gltf')); lines.drawTo(point('tail_gltf'))
            node = renderer.base.render.attachNewNode(lines.create())
            node.setDepthTest(False); node.setDepthWrite(False); node.setLightOff()
        # Positions/targets are in normalized Panda scene coordinates (Z-up).
        views = {
            'front': ((-4, 0, .64), (0, 0, .64), (0, 0, 1), (2.5, 1.96)),
            'back': ((4, 0, .64), (0, 0, .64), (0, 0, 1), (2.5, 1.96)),
            'side_y_minus': ((0, -4, .64), (0, 0, .64), (0, 0, 1), (2.5, 1.96)),
            'side_y_plus': ((0, 4, .64), (0, 0, .64), (0, 0, 1), (2.5, 1.96)),
            'underside': ((0, 0, -4), (0, 0, .4), (-1, 0, 0), (3.0, 2.36)),
            'paws_front': ((-3, -1, .18), (-.4, 0, .16), (0, 0, 1), (1.15, .9)),
            'paws_hind': ((3, 1, .18), (.28, 0, .18), (0, 0, 1), (1.15, .9)),
            'paws_underside': ((0, 0, -4), (-.08, 0, .1), (-1, 0, 0), (1.75, 1.37)),
            'tail_base': ((2, -3, .75), (.43, 0, .65), (0, 0, 1), (1.05, .82)),
        }
        for name, (camera, target, up, film) in views.items():
            lens.setFilmSize(*film)
            renderer.base.camera.setPos(*camera)
            renderer.base.camera.lookAt(Point3(*target), Vec3(*up))
            if overlay:
                overlay.removeNode()
            if labels:
                overlay = renderer.base.render2d.attachNewNode('landmark-overlays')
                colors = {'front_left':(1,.2,.7,1), 'front_right':(.1,.4,1,1),
                          'hind_left':(1,.6,.1,1), 'hind_right':(.1,.85,.7,1)}
                for key, foot in feet.items():
                    marker(overlay, labels['foot_labels'][key], foot['downward_bottom_band_area_centroid'], colors[key])
                for key, region in labels['regions'].items():
                    if name == 'side_y_minus' and key.endswith(('FR','HR')):
                        continue
                    if name == 'side_y_plus' and key.endswith(('FL','HL')):
                        continue
                    if name in ('front', 'back', 'underside', 'paws_underside'):
                        continue  # Foot labels stay readable in these views.
                    marker(overlay, key, region['center'], (1,.85,.2,1))
            for _ in range(2):
                frame = renderer.frame(0, {State.IDLE: 1}, 1400, 1100)
            if not frame.save(str(output / (name + '.png'))):
                raise RuntimeError('Cannot save inspection frame')
        metadata = {'model': str(path), 'driver': renderer.driver,
                    'backend': renderer.backend, 'projection': 'orthographic',
                    'resolution': [1400, 1100], 'preview': 'base color + simple lighting; not full PBR',
                    'anatomical_mapping': 'head toward Panda -X, up +Z; sides labelled by camera Y, not inferred anatomical left/right',
                    'views': views}
        metadata['annotations'] = {'landmarks':str(landmarks), 'geometry_review':str(geometry_review),
                                   'status':'provisional joint centers; foot labels measured from actual surface'} if labels else None
        metadata['geometry_only'] = geometry_only
        metadata['wireframe'] = wireframe
        metadata['forced_base_color_preview'] = base_color_preview
        metadata['bone_guides'] = {'path':str(bone_guides),'pose':pose,'status':'unverified diagnostic overlay'} if bone_guides else None
        metadata['reference_model'] = str(reference_model) if reference_model else None
        metadata['fixed_model_scale'] = factor
        metadata['fixed_model_offset'] = list(renderer.actor.getPos())
        (output / 'cameras.json').write_text(json.dumps(metadata, indent=2) + '\n')
    finally:
        renderer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--landmarks', type=Path)
    parser.add_argument('--geometry-review', type=Path)
    parser.add_argument('--geometry-only', action='store_true')
    parser.add_argument('--reference-model', type=Path, help='Lock normalization to rest model for comparable poses')
    parser.add_argument('--wireframe', action='store_true')
    parser.add_argument('--base-color-preview', action='store_true')
    parser.add_argument('--bone-guides', type=Path)
    parser.add_argument('--pose')
    args = parser.parse_args()
    render(args.model, args.output, args.landmarks, args.geometry_review, args.geometry_only, args.reference_model, args.wireframe, args.base_color_preview, args.bone_guides, args.pose)
