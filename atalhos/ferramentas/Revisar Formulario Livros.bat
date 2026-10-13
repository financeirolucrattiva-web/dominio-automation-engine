@echo off
cd /d "%~dp0..\.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\revisar_formulario_livros.py
) else (
  python scripts\revisar_formulario_livros.py
)
set "DOMINIO_REVISAO_LIVROS=%errorlevel%"
pause
exit /b %DOMINIO_REVISAO_LIVROS%
