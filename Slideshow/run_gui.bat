@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "suite_python=%~dp0..\venv\Scripts\python.exe"
if not exist "%suite_python%" (
    echo The shared MyUtils Python environment is missing. See ..\commands.md for setup.
    pause
    popd
    exit /b 1
)
"%suite_python%" -X utf8 "slideshow_gui.py" %*
set "gui_exit_code=%errorlevel%"
if not "%gui_exit_code%"=="0" (
    echo.
    echo Slideshow could not finish. See the error above and ..\commands.md.
    pause
)
popd
exit /b %gui_exit_code%
