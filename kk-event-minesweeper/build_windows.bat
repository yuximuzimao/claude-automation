@echo off
setlocal
cd /d "%~dp0"
title KBao Helper - Build EXE

if not exist ".venv\Scripts\python.exe" (
  echo Run START.bat successfully once before building the EXE.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install "PyInstaller>=6.11,<7"
if errorlevel 1 goto :fail

python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all z3 --name KBaoHelper app.py
if errorlevel 1 goto :fail

echo.
echo Built: %CD%\dist\KBaoHelper.exe
echo You can use this EXE directly from now on.
pause
exit /b 0

:fail
echo.
echo BUILD FAILED. Please send me a screenshot of this window.
pause
exit /b 1
