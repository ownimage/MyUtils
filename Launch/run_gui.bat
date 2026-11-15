@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "launcher_python=python"
if exist "..\Import\venv\Scripts\python.exe" set "launcher_python=..\Import\venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "launcher_python=venv\Scripts\python.exe"
"%launcher_python%" -c "import PySide6, PIL, exifread" >nul 2>&1
if errorlevel 1 (
    echo Photo Tools needs its Python dependencies. See README.md for setup.
    pause
    popd
    exit /b 1
)
"%launcher_python%" "launcher.py" %*
set "launcher_exit_code=%errorlevel%"
if not "%launcher_exit_code%"=="0" (
    echo.
    echo Photo Tools could not finish. See the error above.
    pause
)
popd
exit /b %launcher_exit_code%
