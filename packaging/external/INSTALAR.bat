@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "config\api_keys.json" copy /y "config\api_keys.example.json" "config\api_keys.json" >nul
if not exist ".venv\Scripts\python.exe" (
    py -3.14 -m venv .venv
    if errorlevel 1 py -3 -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo Python 64 bits nao encontrado. Instale Python 3.14 e execute novamente.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Instalacao concluida. Preencha config\api_keys.json e execute INICIAR.bat.
pause
exit /b 0
:failed
echo Falha ao instalar dependencias. Veja o erro acima; nada foi removido.
pause
exit /b 1
