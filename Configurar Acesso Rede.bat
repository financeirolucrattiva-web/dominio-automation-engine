@echo off
cd /d "%~dp0"
python scripts\configurar_servidor.py
set "DOMINIO_CODIGO_REDE=%errorlevel%"
pause
exit /b %DOMINIO_CODIGO_REDE%
