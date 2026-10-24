@echo off
setlocal
for %%I in ("%~dp0..") do set "JARVIS_ROOT=%%~fI"
set "JARVIS_API_KEYS=%JARVIS_ROOT%\config\api_keys.json"
set "STUDIO_PYTHON=%JARVIS_ROOT%\Python\pythoncore-3.14-64\python.exe"
if not exist "%STUDIO_PYTHON%" set "STUDIO_PYTHON=%JARVIS_ROOT%\Python\bin\python.exe"
if not exist "%STUDIO_PYTHON%" set "STUDIO_PYTHON=%JARVIS_ROOT%\.venv\Scripts\python.exe"
if not exist "%STUDIO_PYTHON%" (
    echo [NVIDIA LAB] Python do Jarvis nao encontrado nesta instalacao.
    pause
    exit /b 1
)
cd /d "%~dp0"
"%STUDIO_PYTHON%" "%~dp0art_studio.py" --tab camera
if errorlevel 1 pause
exit /b %ERRORLEVEL%
