@echo off
setlocal
pushd "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo The project Python environment was not found. See README.md for setup.
    pause
    popd
    exit /b 1
)
"venv\Scripts\python.exe" "reorg_gui.py"
set "gui_exit_code=%errorlevel%"
if not "%gui_exit_code%"=="0" (
    echo.
    echo Camera Import could not finish. See the error above.
    pause
)
popd
exit /b %gui_exit_code%
