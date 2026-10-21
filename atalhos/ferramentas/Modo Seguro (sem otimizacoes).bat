@echo off
cd /d "%~dp0..\.."
echo Modo seguro: as rotinas voltam ao caminho classico (mais lento, o que ja rodou antes).
echo Vale na proxima leitura; nao precisa reiniciar o servidor. Para voltar ao rapido: "Modo Rapido (otimizacoes ligadas).bat".
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\modo_otimizacoes.py seguro
) else (
  python scripts\modo_otimizacoes.py seguro
)
set "RESULTADO_MODO=%errorlevel%"
pause
exit /b %RESULTADO_MODO%
