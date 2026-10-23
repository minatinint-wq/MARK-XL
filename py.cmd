@echo off
setlocal
set "JARVIS_LOCAL_PYTHON=%~dp0Python\pythoncore-3.14-64\python.exe"
if not exist "%JARVIS_LOCAL_PYTHON%" (
    echo [JARVIS] Python da instalacao nao encontrado em "%JARVIS_LOCAL_PYTHON%".
    exit /b 9009
)
"%JARVIS_LOCAL_PYTHON%" %*
exit /b %ERRORLEVEL%
