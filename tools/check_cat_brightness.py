"""Guard photographic fur brightness while preserving the transparent background."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def verify(path, report_path):
    arr = np.asarray(Image.open(path).convert('RGBA'), dtype=np.uint8)
    alpha = arr[:, :, 3]
    if int(alpha[0, 0]) != 0:
        raise AssertionError('Opaque background after color grading')
    nontransparent = alpha > 230
    rgb = arr[:, :, :3][nontransparent].astype(np.float32)
    if len(rgb) < 200:
        raise AssertionError('Cat has fewer than 200 solid RGBA pixels')
    bright = np.mean(rgb, axis=1)
    percentile80 = float(np.percentile(bright, 80))
    percentile95 = float(np.percentile(bright, 95))
    if percentile80 < 205.0:
        raise AssertionError(f'Fur still too dark: p80 RGB luminance {percentile80:.1f}')
    detail = {'solid_pixels': int(len(rgb)), 'rgb_luminance_p80': percentile80,
              'rgb_luminance_p95': percentile95,
              'background_corner_alpha': int(alpha[0, 0]),
              'status': 'computer-rendered brightness PASS; physical monitor untested'}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(detail, indent=2), encoding='utf-8')
    print(json.dumps(detail, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--image', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    verify(a.image, a.out)
