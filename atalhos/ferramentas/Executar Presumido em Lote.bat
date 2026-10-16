@echo off
cd /d "%~dp0..\.."
title Presumido em Lote - Resumo, EFD e Livros Fiscais
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -u scripts\explorar_presumido.py
) else (
  python -u scripts\explorar_presumido.py
)
set "DOMINIO_RESULTADO_LOTE=%errorlevel%"
pause
exit /b %DOMINIO_RESULTADO_LOTE%
