@echo off
cd /d "%~dp0..\.."
echo Requer Windows, sessao ativa, Dominio visivel e calibrado.
echo A empresa e o periodo serao conferidos antes de cada tarefa.
python scripts\servidor.py --executar
set "DOMINIO_CODIGO_SERVIDOR=%errorlevel%"
pause
exit /b %DOMINIO_CODIGO_SERVIDOR%
