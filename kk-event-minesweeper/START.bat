@echo off
setlocal
cd /d "%~dp0"
title KBao Helper

rem If the final EXE already exists, launch it directly.
if exist "dist\KBaoHelper.exe" (
  start "" "dist\KBaoHelper.exe"
  exit /b 0
)

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)

if not defined PYTHON_CMD (
  echo.
  echo Python was not found.
  echo Install Python for Windows, then double-click START.bat again.
  echo Opening the official Python download page now.
  echo.
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [First run] Preparing the helper environment. This only happens once...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :fail
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  if errorlevel 1 goto :fail
  pip install -r requirements.txt
  if errorlevel 1 goto :fail
) else (
  call .venv\Scripts\activate.bat
)

rem Preflight import check. Keep any error text visible for troubleshooting.
python -c "import cv2,mss,z3; from PySide6.QtWidgets import QApplication; import app"
if errorlevel 1 goto :fail

start "" ".venv\Scripts\pythonw.exe" "app.py"
exit /b 0

:fail
echo.
echo START FAILED. Please send me a screenshot of this window.
pause
exit /b 1
