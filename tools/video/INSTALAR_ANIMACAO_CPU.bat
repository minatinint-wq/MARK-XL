@echo off
setlocal
for %%I in ("%~dp0..\..") do set "MARK_XL_ROOT=%%~fI"
cd /d "%MARK_XL_ROOT%"
set "ANIM_PY=%MARK_XL_ROOT%\Python\pythoncore-3.14-64\python.exe"
if not exist "%ANIM_PY%" (
  echo Python do MARK-XL nao encontrado. Instale Python 3.11 ou superior.
  pause
  exit /b 1
)
"%ANIM_PY%" -c "import PyQt6"
if errorlevel 1 (
  "%ANIM_PY%" -m pip install "PyQt6>=6.6,<7"
  if errorlevel 1 goto fail
)
"%ANIM_PY%" -m actions.animation_cpu --check
if errorlevel 1 (
  "%ANIM_PY%" -m pip install "imageio-ffmpeg>=0.6,<0.7"
  if errorlevel 1 goto fail
)
"%ANIM_PY%" -m actions.animation_cpu --check
if errorlevel 1 goto fail
echo Pronto. Abra tools\video\ABRIR_EDITOR_PROPAGANDA.bat
pause
exit /b 0
:fail
echo A instalacao nao terminou. Confira a mensagem acima.
pause
exit /b 1
