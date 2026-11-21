@echo off
setlocal
set "radial_pythonw=%~dp0venv\Scripts\pythonw.exe"
if not exist "%radial_pythonw%" (
    echo The shared MyUtils Python environment is missing. See commands.md for setup.
    exit /b 1
)
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0RadialMenu\stop_instance.ps1"
if errorlevel 1 exit /b %errorlevel%
"%~dp0venv\Scripts\python.exe" -X utf8 "%~dp0RadialMenu\start_background.py" %*
exit /b %errorlevel%
