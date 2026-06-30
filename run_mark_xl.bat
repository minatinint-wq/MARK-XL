@echo off
setlocal

cd /d "%~dp0"
set "PYTHON_EXE=%~dp0Python\bin\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Portable Python not found: %PYTHON_EXE%
    pause
    exit /b 1
)

"%PYTHON_EXE%" main.py
pause
