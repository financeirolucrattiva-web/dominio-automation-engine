@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar_interface.ps1"
set "DOMINIO_CODIGO_INTERFACE=%errorlevel%"
pause
exit /b %DOMINIO_CODIGO_INTERFACE%
