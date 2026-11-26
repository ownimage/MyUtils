@echo off
setlocal
set "TASK=%~1"
set "ROOT=%~dp0.."
set "BLENDER=%SNAKETAPE_BLENDER%"
if defined BLENDER goto found
set "BLENDER=C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
if exist "%BLENDER%" goto found
set "BLENDER="
for /f "delims=" %%B in ('where blender.exe 2^>nul') do if not defined BLENDER set "BLENDER=%%B"
:found
if not exist "%BLENDER%" (
  echo Blender 4.4.3 was not found. Set SNAKETAPE_BLENDER to blender.exe.
  endlocal & exit /b 2
)
set "PYTHONDONTWRITEBYTECODE=1"
set "SNAKETAPE_PROFILE=%TEMP%\SnakeTape-isolated-%RANDOM%-%RANDOM%"
set "BLENDER_USER_CONFIG=%SNAKETAPE_PROFILE%\config"
set "BLENDER_USER_SCRIPTS=%SNAKETAPE_PROFILE%\scripts"
set "BLENDER_USER_EXTENSIONS=%SNAKETAPE_PROFILE%\extensions"
set "BLENDER_USER_DATAFILES=%SNAKETAPE_PROFILE%\datafiles"
mkdir "%BLENDER_USER_CONFIG%" "%BLENDER_USER_SCRIPTS%" "%BLENDER_USER_EXTENSIONS%" "%BLENDER_USER_DATAFILES%" 2>nul
if not exist "%BLENDER_USER_CONFIG%\" (
  echo Could not create an isolated Blender profile in TEMP.
  endlocal & exit /b 2
)
"%BLENDER%" --background --factory-startup --python-exit-code 1 --python "%ROOT%\tools\%TASK%.py" -- %2 %3 %4 %5 %6 %7 %8 %9
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (echo SnakeTape completed successfully.) else (echo SnakeTape failed with exit code %RESULT%.)
endlocal & exit /b %RESULT%
