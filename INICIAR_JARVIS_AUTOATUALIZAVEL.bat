@echo off
chcp 65001 >nul
title JARVIS MARK XLIV - LOGS
cd /d "%~dp0"
echo ============================================================
echo  JARVIS MARK XLIV - PROTOCOLO 44
echo  Esta janela deve permanecer aberta enquanto o JARVIS roda.
echo ============================================================
echo.
set "JARVIS_PYTHON=%~dp0Python\pythoncore-3.14-64\python.exe"
if not exist "%JARVIS_PYTHON%" set "JARVIS_PYTHON=%~dp0Python\bin\python.exe"
if not exist "%JARVIS_PYTHON%" set "JARVIS_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%JARVIS_PYTHON%" (
    "%JARVIS_PYTHON%" "%~dp0main.py"
) else (
    py -3 "%~dp0main.py"
)
set "JARVIS_EXIT=%ERRORLEVEL%"
echo.
echo ============================================================
echo  JARVIS encerrado. Codigo de saida: %JARVIS_EXIT%
echo  Os detalhes acima ficam visiveis para diagnostico.
echo ============================================================
pause
exit /b %JARVIS_EXIT%
