@echo off
cd /d "%~dp0..\.."
echo Deixa de usar o atalho curto: o Procurar Pasta volta ao caminho completo. A juncao em C:\saida fica (nao apaga nada).
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\configurar_atalho_saida.py --remover
) else (
  python scripts\configurar_atalho_saida.py --remover
)
set "RESULTADO_ATALHO=%errorlevel%"
echo.
pause
exit /b %RESULTADO_ATALHO%
