@echo off
cd /d "%~dp0..\.."
echo Modo seguro: desliga as otimizacoes de velocidade (OCR em paralelo etc.); fica mais lento.
echo Para voltar exatamente a versao que ja rodava, use Voltar Versao Estavel.bat.
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
