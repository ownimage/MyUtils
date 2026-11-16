@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "slideshow_python=python"
if exist "..\Import\venv\Scripts\python.exe" set "slideshow_python=..\Import\venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "slideshow_python=venv\Scripts\python.exe"
"%slideshow_python%" "slideshow_gui.py" %*
set "slideshow_exit_code=%errorlevel%"
if not "%slideshow_exit_code%"=="0" (
    echo Slideshow could not finish. See the error above and README.md for setup.
    pause
)
popd
exit /b %slideshow_exit_code%
