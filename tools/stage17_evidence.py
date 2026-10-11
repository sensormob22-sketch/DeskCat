"""Compact final Cycles comparisons, model checksums and tested-run record."""
import os,json,hashlib,re
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QFont,QColor
ROOT=Path.cwd();OUT=ROOT/'docs/model-reports/stage17';app=QGuiApplication([])
for view,name in [('profile','belly_profile_before_after'),('left','belly_left_closeup_before_after'),('right','belly_right_closeup_before_after'),('oblique','belly_oblique_left_before_after')]:
 a=QImage(str(OUT/f'images/blender_before_{view}.png'));b=QImage(str(OUT/f'images/blender_after_{view}.png'));assert not a.isNull() and not b.isNull()
 canvas=QImage(2400,840,QImage.Format_RGB32);canvas.fill(QColor('#ededed'));p=QPainter(canvas);p.setPen(QColor('black'));p.setFont(QFont('Sans',20));p.drawText(20,30,'BEFORE — raw source / Blender Cycles');p.drawText(1220,30,'AFTER — curved profile repair / Blender Cycles');p.drawImage(0,40,a);p.drawImage(1200,40,b);p.end();assert canvas.save(str(OUT/f'images/{name}.png'))
assert QImage(str(OUT/'images/blender_after_profile.png')).save(str(OUT/'images/side_profile_result.png'))
audit=json.loads((OUT/'geometry_audit.json').read_text());paths=[ROOT/'assets/3d/retopo/deskcat_calico_retopo_16460.glb',ROOT/'assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend',ROOT/'assets/3d/retopo/deskcat_belly_profile_fix_01.glb',ROOT/'assets/rigging/deskcat_belly_profile_fix_01.blend']
hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(OUT/'SHA256SUMS.txt').write_text(''.join(f'{h}  {p}\n' for p,h in hashes.items()))
test_log=Path('/tmp/stage17-tests.log').read_text();passed=re.search(r'\d+ passed in [\d.]+s',test_log);assert passed and 'failed' not in test_log
(OUT/'test_results.json').write_text(json.dumps({'environment':'Linux Python 3.12 / PySide6 / Panda3D; Blender 4.3.2 headless','command':'QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q','result':passed.group(0),'Windows_tested':False,'source_and_result_sha256':hashes,'visual_review_scope':'Cycles profile, two sides and oblique; Panda underside and opposite oblique. No deformation/animation tests.'},indent=2)+'\n')
# Standalone inputs are reproducible intermediates; keep only final comparisons.
for pattern in ['before_*.png','after_*.png','blender_before_*.png','blender_after_*.png']:
 for file in (OUT/'images').glob(pattern):file.unlink()
checksums={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ['artifact_checksums.json','README.md']}
(OUT/'artifact_checksums.json').write_text(json.dumps(checksums,indent=2)+'\n')
