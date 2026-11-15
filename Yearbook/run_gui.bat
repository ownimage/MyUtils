@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "yearbook_python=python"
if exist "..\Import\venv\Scripts\python.exe" set "yearbook_python=..\Import\venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "yearbook_python=venv\Scripts\python.exe"
"%yearbook_python%" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Yearbook needs Python with PySide6. See README.md for setup.
    pause
    popd
    exit /b 1
)
"%yearbook_python%" "yearbook_gui.py" %*
set "yearbook_exit_code=%errorlevel%"
if not "%yearbook_exit_code%"=="0" (
    echo.
    echo Yearbook could not finish. See the error above.
    pause
)
popd
exit /b %yearbook_exit_code%
