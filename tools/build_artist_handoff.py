"""Assemble and verify a deterministic, read-only artist package. No Blender execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/artist-handoff'
ARCHIVE=OUT/'DeskCat_Artist_Handoff.zip'
def sha(data):return hashlib.sha256(data).hexdigest()
def encoded(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()

def main():
    if ARCHIVE.exists():raise ValueError('Archive already exists; do not overwrite published package')
    tracked=subprocess.check_output(['git','ls-files','assets','docs/model-reports'],cwd=ROOT,text=True).splitlines()
    frozen={p:sha((ROOT/p).read_bytes()) for p in tracked}
    expected=json.loads((ROOT/'docs/model-reports/stage9/data/scene_audit.json').read_text())
    for name,h in expected['protected_glb_hashes'].items():
        assert frozen['assets/3d/tripo/'+name]==h
    assert frozen['assets/rigging/deskcat_v6_weight_handoff.blend']==expected['scene_sha256']
    selected=['assets/3d/tripo/deskcat_calico_h25_v1.glb','assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb','assets/rigging/deskcat_v6_weight_handoff.blend',
              'assets/references/README.md','assets/references/DeskCat_Calico_Standing_Side.png','assets/references/DeskCat_Calico_Standing_3Views.png',
              'docs/model-reports/stage6/anatomical_landmarks.json',
              'docs/model-reports/stage9/WEIGHT_PAINT_SPEC.md','docs/model-reports/stage9/weight_paint_spec.json',
              'docs/model-reports/stage9/data/region_masks.json','docs/model-reports/stage9/data/pose_review.json',
              'docs/model-reports/stage9/data/scene_audit.json','docs/model-reports/stage9/data/reopened_scene_audit.json',
              'docs/model-reports/stage9/sheets/sheet_metadata.json',
              'docs/model-reports/stage8/v6/deformation.json','docs/model-reports/stage8/v6/diagnostics.json',
              'docs/model-reports/stage10/tail_to_pelvis_proposal.json','docs/model-reports/stage10/proposal_audit.json',
              'docs/model-reports/stage11/weight_diff.json','docs/model-reports/stage11/blender_comparison.json','docs/model-reports/stage11/decision.json',
              'docs/model-reports/stage12/comparison.json','docs/model-reports/stage12/seam_and_runtime_audit.json','docs/model-reports/stage12/decision.json']
    selected += [f'docs/model-reports/stage{i}/README.md' for i in range(8,13)]
    zones=['tail_to_pelvis','thoracic_abdomen','left_hip','right_shoulder_paw','wrist_to_sole','hock_to_sole']
    image_paths=[f'docs/model-reports/stage9/sheets/{z}.png' for z in zones]
    image_paths+=['docs/model-reports/stage11/images/c2_closeup_before_after.png']
    image_paths += [f'docs/model-reports/stage12/images/{n}_matched.png' for n in ['tail','hip','combined']]
    selected+=image_paths
    files={p:(ROOT/p).read_bytes() for p in selected}
    for name in ['BRIEF_RU.md','ACCEPTANCE_EN.md']:files[name]=(OUT/name).read_bytes()
    review=json.loads((ROOT/'docs/model-reports/stage9/data/pose_review.json').read_text())
    stage8=json.loads(files['docs/model-reports/stage8/v6/deformation.json']);stage12=json.loads(files['docs/model-reports/stage12/comparison.json'])
    controls={'axis':'Blender world +Y / glTF -Z, relative to rest; use inverse rest-local bone basis. Not certified feline ROM.',
              'stage9_poses':{k:{'rotations_degrees':v['rotations'],'v6_new_pairs':v['new_pairs']} for k,v in review['poses'].items()},
              'zone_pose_labels':{z:v['poses'] for z,v in review['zones'].items()},
              'stage8_limb_chain_controls':{k:{'rotations_degrees':stage8['poses'][k]['rotations_degrees_about_blender_world_y'],'v6_new_pairs':stage8['poses'][k]['new_pairs']} for k in ['front_bend','front_bend_opposite','hind_bend','hind_bend_opposite']},
              'stage12_additional_combined_controls':{k:{'rotations_degrees':stage12['cases'][k],'v6_new_pairs':stage12['models']['v6'][k]['new_pairs']} for k in ['combined_positive','combined_negative']},
              'baseline_pairs':review['baseline_pairs'],'meaning':'Baseline counts are diagnostic evidence, not acceptable failure quotas. No new poses evaluated for this package.'}
    files['CONTROL_POSES.json']=encoded(controls)
    files['RIG_BASELINE_UNVERIFIED.json']=encoded({'source':'stage8/v6/deformation.json; existing 17 bones, NOT anatomically certified','bones':stage8['bones'],'coordinate_conversion':stage8['coordinate_conversion']})
    index='# Selected images / выбранные изображения\n\n10 diagnostic sheets + 2 synthetic reference PNGs. No individual frame dumps.\n\n'
    for z in zones:index+=f'- [{z}](docs/model-reports/stage9/sheets/{z}.png): v6 rest / both signs / holdouts; texture, solid, wire, heatmap. Blue=0, green=.5, red=1 weights; red contours locate new strict intersections.\n'
    index+='- [C2 rejected trial](docs/model-reports/stage11/images/c2_closeup_before_after.png): exact small correction did not resolve crossing.\n'
    for n in ['tail','hip','combined']:index+=f'- [Rejected cage / {n}](docs/model-reports/stage12/images/{n}_matched.png): matched v6/cage, real Panda baked morph views. Not a starting model.\n'
    index+='\nOpen full PNG and zoom; red crossing overlays can mark occluded triangles. Static base-color/wire views are not full PBR certification. Camera metadata is in stage9/sheets/sheet_metadata.json and historical stage12 report.\n\nReferences: assets/references/DeskCat_Calico_Standing_Side.png and DeskCat_Calico_Standing_3Views.png are synthetic; original seated identity source is NOT included because unavailable in repository.\n'
    files['IMAGE_INDEX.md']=index.encode()
    readme='''# DeskCat Artist Handoff

RU: начните с BRIEF_RU.md. EN: start with ACCEPTANCE_EN.md.
This package prepares an artist handoff only. No model, weight, rig or animation edits were made.

- [Русское ТЗ](BRIEF_RU.md) / [English brief and acceptance](ACCEPTANCE_EN.md)
- [Контрольные позы / exact controls](CONTROL_POSES.json)
- [17 unverified bone pivots, axes and hierarchy](RIG_BASELINE_UNVERIFIED.json)
- [Изображения / selected evidence](IMAGE_INDEX.md)
- Working scene: assets/rigging/deskcat_v6_weight_handoff.blend — START HERE.
- Immutable appearance original: assets/3d/tripo/deskcat_calico_h25_v1.glb.
- localprep GLB: geometry/source-ID indexing baseline for the scene, not an appearance replacement.
- Masks/pre-export weight baseline: docs/model-reports/stage9/data/region_masks.json.
- Historical reports: docs/model-reports/stage8 through stage12. Only selected evidence included; historical links to omitted binaries/images may not resolve. Use this index and supplied file paths.
- MANIFEST.json: SHA-256/size of every payload, repository origin and input commit; no credentials.

Scene is self-contained with three packed images. Blender 4.3.2 recommended. Do not overwrite inputs; open a working copy and save under a new approved name. Embedded review UI may be explicitly run; no automatic scripts or installers required. Rejected C2/cage Blender/GLB assets are intentionally excluded.

No verified original seated identity PNG available in repository; the two standing PNGs are synthetic references. No paid operations, skinprobe_v7, new weights, animations or merge authorized by this package. Pricing is supplied by the artist; milestones/acceptance are in both briefs.
'''
    files['README.md']=readme.encode()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest={'repository':'sensormob22-sketch/DeskCat','branch':'feature/tripo-cat','input_commit':head,
              'review_url':'https://github.com/sensormob22-sketch/DeskCat/pull/2#issuecomment-6107357666',
              'files':{p:{'sha256':sha(data),'bytes':len(data),'source_repository_path':p if p in selected else ('docs/artist-handoff/'+p if p in ['BRIEF_RU.md','ACCEPTANCE_EN.md'] else 'generated from unchanged repository evidence')} for p,data in sorted(files.items())}}
    files['MANIFEST.json']=encoded(manifest)
    with zipfile.ZipFile(ARCHIVE,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('DeskCat_Artist_Handoff/'+name,date_time=(2000,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data,compresslevel=9)
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        for name,entry in manifest['files'].items():assert sha(z.read('DeskCat_Artist_Handoff/'+name))==entry['sha256']
    assert all(sha((ROOT/p).read_bytes())==h for p,h in frozen.items()),'Existing assets/reports modified'
    digest=sha(ARCHIVE.read_bytes());(OUT/'DeskCat_Artist_Handoff.zip.sha256').write_text(digest+'  DeskCat_Artist_Handoff.zip\n')
    report={'input_commit':head,'archive':str(ARCHIVE.relative_to(ROOT)),'archive_sha256':digest,'archive_bytes':ARCHIVE.stat().st_size,'file_count':len(files),'diagnostic_pngs':len(image_paths),'synthetic_reference_pngs':2,'manifest_verified':True,'zip_crc_verified':True,'previous_tracked_assets_reports_sha256_verified':len(frozen),'blender_or_render_experiments_run':False,'new_weights':0,'new_animations':0,'paid_operations':0,'missing_reference':'Original seated identity PNG unavailable in repository','review_url':manifest['review_url'],'verification_environment':'Linux, Python standard-library zipfile/hashlib; package assembly only, no new runtime/Windows tests'}
    (OUT/'package_report.json').write_bytes(encoded(report));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
