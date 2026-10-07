@echo off
cd /d "%~dp0"
python scripts\listar_capacidades.py %*
set "catalogo_status=%errorlevel%"
echo.
pause
exit /b %catalogo_status%
