@echo off
cd /d "%~dp0..\.."
echo Otimizacoes de velocidade em uso (LIGADA = rapido; desligada = caminho classico):
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\modo_otimizacoes.py status
) else (
  python scripts\modo_otimizacoes.py status
)
set "RESULTADO_MODO=%errorlevel%"
pause
exit /b %RESULTADO_MODO%
