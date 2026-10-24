@echo off
setlocal
cd /d "%~dp0"

rem Edicao leve: apenas o brilho de voz, sem WebEngine ou cerebro 3D.
set "MARK_XL_GLOW_ONLY=1"
set "MARK_XL_LOW_MEMORY=1"
set "MARK_XL_BOOT_ANIMATION=0"
set "MARK_XL_PRELOAD_NEURAL=0"
set "MARK_XL_CLAP_DETECTION=0"
set "MARK_XL_CALL_PRIVACY_AUTOSTART=0"
set "MARK_XL_CALL_WAKE=0"
set "MARK_XL_WINDOWS_NOTIFICATIONS_AUTOSTART=0"
set "MARK_XL_IPHONE_SHORTCUTS_AUTOSTART=0"
set "MARK_XL_JARVIS_BRIDGE_AUTOSTART=0"

set "JARVIS_LITE_PYTHON=%~dp0Python\pythoncore-3.14-64\python.exe"
if not exist "%JARVIS_LITE_PYTHON%" set "JARVIS_LITE_PYTHON=%~dp0Python\bin\python.exe"
if not exist "%JARVIS_LITE_PYTHON%" set "JARVIS_LITE_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%JARVIS_LITE_PYTHON%" (
    "%JARVIS_LITE_PYTHON%" "%~dp0tools\migrate_lite_credentials.py"
) else (
    py -3 "%~dp0tools\migrate_lite_credentials.py"
)
if errorlevel 1 (
    echo [JARVIS] Falha ao importar as credenciais da edicao leve.
    pause
    exit /b 1
)

call "%~dp0INICIAR_JARVIS_AUTOATUALIZAVEL.bat"
exit /b %ERRORLEVEL%
