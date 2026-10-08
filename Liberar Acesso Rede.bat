@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\liberar_rede.ps1"
set "DOMINIO_CODIGO_REDE=%errorlevel%"
pause
exit /b %DOMINIO_CODIGO_REDE%
