@echo off
cd /d "%~dp0"
set DOMINIO_MODO=operador
python scripts\gui.py
echo.
pause
