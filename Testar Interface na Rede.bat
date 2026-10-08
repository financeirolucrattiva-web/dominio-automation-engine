@echo off
cd /d "%~dp0"
python scripts\servidor.py --rede-local --simular
set "DOMINIO_CODIGO_SERVIDOR=%errorlevel%"
pause
exit /b %DOMINIO_CODIGO_SERVIDOR%
