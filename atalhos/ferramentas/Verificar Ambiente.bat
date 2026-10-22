@echo off
cd /d "%~dp0..\.."
echo Pre-voo: confere o ambiente antes de rodar um lote. Nao opera o Dominio nem usa mouse/teclado.
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\verificar_ambiente.py
) else (
  python scripts\verificar_ambiente.py
)
set "RESULTADO_AMBIENTE=%errorlevel%"
echo.
pause
exit /b %RESULTADO_AMBIENTE%
