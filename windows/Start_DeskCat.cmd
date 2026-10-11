@echo off
setlocal
cd /d "%~dp0"
title DeskCat - calico walking cat
echo.
echo DeskCat - animated calico desktop cat (experimental)
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python 3.11 environment...
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Python 3.11 could not be started. Please install Python 3.11 for Windows.
    pause
    exit /b 1
  )
)
if not exist ".venv\deskcat_ready.txt" (
  echo Installing PySide6 and Panda3D, only needed on first run...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -e ".[three-d]"
  if errorlevel 1 (
    echo Dependency installation failed. Check your internet connection, then retry.
    pause
    exit /b 1
  )
  echo ready> ".venv\deskcat_ready.txt"
)
if not exist "assets\3d\deskcat_belly_skinned_trial.glb" (
  echo Missing animated calico 3D model in the extracted package.
  pause
  exit /b 1
)
echo Launching animated calico. Right click: Walk or Idle. Press W: toggle Walk.
".venv\Scripts\python.exe" -m deskcat --renderer panda --model "assets\3d\deskcat_belly_skinned_trial.glb" --scale 1.5 --model-scale 0.9 --start-walking --initial-direction left --forward-heading 180 --walk-speed 28
if errorlevel 1 (
  echo DeskCat stopped with an error. You can send a screenshot of this window.
  pause
  exit /b 1
)
endlocal
