@echo off
setlocal
for %%I in ("%~dp0..\..") do set "MARK_XL_ROOT=%%~fI"
cd /d "%MARK_XL_ROOT%"
"%MARK_XL_ROOT%\Python\pythoncore-3.14-64\python.exe" -m actions.animation_editor
if errorlevel 1 pause
