"""Create a self-contained SOURCE+MODEL Windows launcher zip (no Blender/Tripo).
Python 3.11, pip/PyPI connectivity required on FIRST run only.
Not a native EXE; first click creates a .venv and installs Python wheels.
"""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/"assets/3d/deskcat_belly_skinned_trial.glb"
def pack(out):
 if out.exists():raise FileExistsError(out)
 if not MODEL.is_file():raise FileNotFoundError(MODEL)
 files=[(ROOT/"pyproject.toml","pyproject.toml"),
        (ROOT/"windows/Start_DeskCat.cmd","Start_DeskCat.cmd"),
        (ROOT/"windows/README_FIRST.txt","README_FIRST.txt"),
        (MODEL,"assets/3d/deskcat_belly_skinned_trial.glb")]
 for base in ("src/deskcat",):
  for f in sorted((ROOT/base).rglob("*")):
   if f.is_file() and f.suffix in (".py",".json",".txt",".toml") and "__pycache__" not in f.parts:
    files.append((f,f.relative_to(ROOT).as_posix()))
 out.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for file,rel in files:
   if not file.is_file():raise FileNotFoundError(file)
   z.write(file,rel)
  manifest={"package":"DeskCat_Windows_Walking_Calico","status":"EXPERIMENTAL: manual DWM review required",
            "model_sha256":hashlib.sha256(MODEL.read_bytes()).hexdigest(),
            "file_sha256":{rel:hashlib.sha256(file.read_bytes()).hexdigest() for file,rel in files}}
  z.writestr("DESKCAT_FILE_HASHES.json",json.dumps(manifest,ensure_ascii=False,indent=2))
 print(f"Created {out} ({out.stat().st_size} bytes, {len(files)} files); model SHA {manifest['model_sha256']}")
 with zipfile.ZipFile(out) as z:
  bad=z.testzip()
  if bad:raise ValueError(f"Corrupt member: {bad}")
  names=z.namelist()
  if len(names)!=len(set(names)):raise ValueError("Duplicate zip file entries")
  assert "Start_DeskCat.cmd" in names and "src/deskcat/window3d.py" in names
  assert "assets/3d/deskcat_belly_skinned_trial.glb" in names
 return manifest
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=ROOT/"artifacts/windows/DeskCat_Windows_Walking_Calico.zip")
 a=p.parse_args();pack(a.out)
