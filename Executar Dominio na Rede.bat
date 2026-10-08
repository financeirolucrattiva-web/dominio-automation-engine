@echo off
cd /d "%~dp0"
echo Requer Dominio visivel, calibrado, empresa correta e apuracao fechada.
python scripts\servidor.py --rede-local --executar
set "DOMINIO_CODIGO_SERVIDOR=%errorlevel%"
pause
exit /b %DOMINIO_CODIGO_SERVIDOR%
