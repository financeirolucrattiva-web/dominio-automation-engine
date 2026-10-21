@echo off
cd /d "%~dp0..\.."
echo Compara o caminho classico e o otimizado do OCR sobre capturas ja salvas.
echo Nao opera o Dominio, nao mexe no mouse nem no teclado e nao mostra texto das capturas.
echo Pode demorar varios minutos: cada captura passa pelas duas versoes de cada leitura.
echo Para rodar so uma parte: "Comparar Otimizacoes.bat" --funcoes selecao campos
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\comparar_otimizacoes.py %*
) else (
  python scripts\comparar_otimizacoes.py %*
)
set "RESULTADO_COMPARACAO=%errorlevel%"
echo.
pause
exit /b %RESULTADO_COMPARACAO%
