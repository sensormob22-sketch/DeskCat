"""Render original geometry, never synthesized or repaired inspection images.

Uses DeskCat's documented base-color preview fallback. No Tripo calls.
Camera directions refer to the visually verified X-negative head of this asset.
"""
import argparse
import json
from pathlib import Path
from panda3d.core import OrthographicLens, Point3, Vec3
from deskcat.rendering.panda import PandaRenderer
from deskcat.states import State


def render(path, output):
    output.mkdir(parents=True, exist_ok=True)
    renderer = PandaRenderer(path, width=1400, height=1100)
    try:
        renderer.base.setBackgroundColor(.72, .72, .72, 1)
        lens = OrthographicLens()
        lens.setNearFar(.01, 100)
        renderer.base.cam.node().setLens(lens)
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
            for _ in range(2):
                frame = renderer.frame(0, {State.IDLE: 1}, 1400, 1100)
            if not frame.save(str(output / (name + '.png'))):
                raise RuntimeError('Cannot save inspection frame')
        metadata = {'model': str(path), 'driver': renderer.driver,
                    'backend': renderer.backend, 'projection': 'orthographic',
                    'resolution': [1400, 1100], 'preview': 'base color + simple lighting; not full PBR',
                    'anatomical_mapping': 'head toward Panda -X, up +Z; sides labelled by camera Y, not inferred anatomical left/right',
                    'views': views}
        (output / 'cameras.json').write_text(json.dumps(metadata, indent=2) + '\n')
    finally:
        renderer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    render(args.model, args.output)
