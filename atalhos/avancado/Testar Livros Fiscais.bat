@echo off
cd /d "%~dp0..\.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\testar_livros_fiscais.py
) else (
  python scripts\testar_livros_fiscais.py
)
set "DOMINIO_RESULTADO_LIVROS=%errorlevel%"
pause
exit /b %DOMINIO_RESULTADO_LIVROS%
