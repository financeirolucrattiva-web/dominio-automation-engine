@echo off
cd /d "%~dp0..\.."
echo Modo rapido: todas as otimizacoes de velocidade ligadas (padrao).
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\modo_otimizacoes.py rapido
) else (
  python scripts\modo_otimizacoes.py rapido
)
set "RESULTADO_MODO=%errorlevel%"
pause
exit /b %RESULTADO_MODO%
