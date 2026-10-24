@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
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
set "JARVIS_EXTERNAL_EDITION=1"
if not exist ".venv\Scripts\python.exe" (
    echo Execute INSTALAR.bat antes de iniciar.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
echo Assistente encerrado. Codigo: %ERRORLEVEL%
pause
