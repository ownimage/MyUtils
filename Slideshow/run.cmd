@echo off
setlocal
set "suite_python=%~dp0..\venv\Scripts\python.exe"
if not exist "%suite_python%" (
    echo The shared MyUtils Python environment is missing. See ..\commands.md for setup.
    exit /b 1
)
"%suite_python%" -X utf8 "%~dp0param.py" %*
exit /b %errorlevel%
