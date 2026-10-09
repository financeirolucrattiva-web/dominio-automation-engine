@echo off
cd /d "%~dp0..\.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\configurar_destino_livros.py
) else (
  python scripts\configurar_destino_livros.py
)
set "DOMINIO_CODIGO_DESTINO=%errorlevel%"
pause
exit /b %DOMINIO_CODIGO_DESTINO%
