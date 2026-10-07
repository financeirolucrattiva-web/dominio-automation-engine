@echo off
cd /d "%~dp0"
python scripts\calibrar_tela_principal.py
set "calibracao_status=%errorlevel%"
echo.
pause
exit /b %calibracao_status%
