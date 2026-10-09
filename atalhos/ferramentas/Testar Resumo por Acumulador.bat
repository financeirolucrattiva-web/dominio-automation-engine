@echo off
cd /d "%~dp0..\.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\explorar_resumo_acumulador.py
) else (
  python scripts\explorar_resumo_acumulador.py
)
set "DOMINIO_RESULTADO_RESUMO=%errorlevel%"
pause
exit /b %DOMINIO_RESULTADO_RESUMO%
