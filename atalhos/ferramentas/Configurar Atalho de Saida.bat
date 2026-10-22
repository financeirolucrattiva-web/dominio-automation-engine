@echo off
cd /d "%~dp0..\.."
echo Atalho curto da pasta de saida: o Procurar Pasta do Dominio anda 1 nivel em vez de 4 (menos ~35 s por empresa nos Livros).
echo Cria a juncao C:\saida apontando para a pasta saida do projeto (mesma pasta; nada e copiado nem apagado) e passa a usa-la.
echo Depois rode "Testar Seletor de Pasta.bat" para ensaiar sem emitir. Para desligar: "Remover Atalho de Saida.bat".
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\configurar_atalho_saida.py
) else (
  python scripts\configurar_atalho_saida.py
)
set "RESULTADO_ATALHO=%errorlevel%"
echo.
pause
exit /b %RESULTADO_ATALHO%
