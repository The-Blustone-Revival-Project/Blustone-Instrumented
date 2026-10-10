@echo off
setlocal

set "JET_VIEWER_ROOT=%~dp0..\.."
set "JET_VIEWER_SCRIPT=%JET_VIEWER_ROOT%\tools\jet-viewer\jet_viewer.py"
set "JET_VIEWER_PYTHON=%JET_VIEWER_ROOT%\tools\python-venv\Scripts\python.exe"

if exist "%JET_VIEWER_PYTHON%" goto run_bundled

where py >nul 2>nul
if not errorlevel 1 goto run_py

where python >nul 2>nul
if not errorlevel 1 goto run_python

echo Python 3 was not found. Install Python 3.10+ or restore tools\python-venv.
pause
exit /b 1

:run_bundled
"%JET_VIEWER_PYTHON%" "%JET_VIEWER_SCRIPT%" --root "%JET_VIEWER_ROOT%"
goto finish

:run_py
py -3 "%JET_VIEWER_SCRIPT%" --root "%JET_VIEWER_ROOT%"
goto finish

:run_python
python "%JET_VIEWER_SCRIPT%" --root "%JET_VIEWER_ROOT%"

:finish
if errorlevel 1 pause
exit /b %errorlevel%

