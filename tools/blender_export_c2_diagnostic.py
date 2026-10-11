"""Export the already-verified trial with heatmap COLOR_0 disabled; never assign weights."""
import argparse, hashlib, json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from skin_export_audit import audit_export
from rig_readiness_audit import read_glb

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(report_path):
    r=json.loads(report_path.read_text());scene=Path(r['copy_scene']);out=Path(r['export'])
    if out.exists():raise ValueError('Refuse existing output; retain rejected color-layer export under ignored artifacts first')
    if sha(scene)!=r['copy_scene_sha256']:raise ValueError('Trial scene SHA mismatch')
    dry=json.loads((report_path.parent/'dry_run.json').read_text())
    for path,expected in dry['frozen_hashes'].items():
        if sha(Path(path))!=expected:raise ValueError('Frozen input mismatch')
    bpy.ops.wm.open_mainfile(filepath=str(scene.resolve()))
    mesh=bpy.data.objects['WORKING_V6_UNCHANGED_WEIGHTS'];rig=bpy.data.objects['V6_17_BONES_UNVERIFIED'];names=[b.name for b in rig.data.bones]
    def digest():
        weights=np.zeros((len(mesh.data.vertices),len(names)),dtype='<f4')
        for v in mesh.data.vertices:
            for g in v.groups:
                n=mesh.vertex_groups[g.group].name
                if n in names:weights[v.index,names.index(n)]=g.weight
        return hashlib.sha256(weights.tobytes()).hexdigest()
    if digest()!=r['trial_weight_sha256_float32']:raise ValueError('Trial weights mismatch')
    bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(out.resolve()),export_format='GLB',use_selection=True,export_animations=False,
                            export_skins=True,export_all_influences=False,export_texcoords=True,export_normals=True,
                            export_materials='EXPORT',export_yup=True,export_vertex_color='NONE')
    if digest()!=r['trial_weight_sha256_float32'] or sha(scene)!=r['copy_scene_sha256']:raise ValueError('Export changed trial weights or scene')
    d,b,_=read_glb(out)
    if any('COLOR_0' in p['attributes'] for mesh in d['meshes'] for p in mesh['primitives']):raise ValueError('Heatmap color leak')
    old_sha=r['export_sha256'];r['export_sha256']=sha(out);r['export_vertex_color']='NONE'
    report_path.write_text(json.dumps(r,indent=2)+'\n')
    source=Path('assets/3d/tripo/deskcat_calico_h25_v1_localprep.glb')
    (report_path.parent/'export_preservation.json').write_text(json.dumps(audit_export(source,out),indent=2)+'\n')
    (report_path.parent/'export_color_audit.json').write_text(json.dumps({'discarded_first_export_sha256':old_sha,
      'final_export_sha256':sha(out),'vertex_colors_exported':False,'scene_weights_changed':False,'scene_saved':False,
      'reason':'Inherited HEAT_ point attributes were emitted as COLOR_0 by default; disabled export only, preserving scene diagnostic layers and original base-color texture.'},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.report)
