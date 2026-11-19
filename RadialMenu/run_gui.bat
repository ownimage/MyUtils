@echo off
"%~dp0..\venv\Scripts\python.exe" -X utf8 "%~dp0radial_gui.py" %*
exit /b %errorlevel%
