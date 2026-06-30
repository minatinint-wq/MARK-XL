@echo off
title JARVIS API Key Manager
color 0A

echo ==========================================
echo     JARVIS API Key Manager
echo ==========================================
echo.
echo  1. Listar API keys
echo  2. Adicionar nova key
echo  3. Trocar para outra key
echo  4. Testar todas as keys
echo  5. Abrir Google AI Studio
echo  6. Ver modelos disponiveis
echo  0. Sair
echo.
echo ==========================================
echo.

set /p choice=Digite a opcao:

if "%choice%"=="1" goto list
if "%choice%"=="2" goto add
if "%choice%"=="3" goto use
if "%choice%"=="4" goto test
if "%choice%"=="5" goto studio
if "%choice%"=="6" goto models
if "%choice%"=="0" goto end

:list
python "%~dp0api_key_manager.py" list
pause
goto menu

:add
python "%~dp0api_key_manager.py" add
pause
goto menu

:use
python "%~dp0api_key_manager.py" use
pause
goto menu

:test
python "%~dp0api_key_manager.py" test
pause
goto menu

:studio
python "%~dp0gemini_keygen.py" studio
pause
goto menu

:models
python "%~dp0gemini_keygen.py" models
pause
goto menu

:end
exit
