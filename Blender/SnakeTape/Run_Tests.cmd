@echo off
setlocal
call "%~dp0tools\launch.cmd" run_tests %*
set "RESULT=%ERRORLEVEL%"
if /i not "%~1"=="--no-pause" pause
endlocal & exit /b %RESULT%
