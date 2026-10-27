@echo off
cd /d "%~dp0..\.."
echo Abra o "Procurar Pasta" (Livros Fiscais ^> previa ^> icone PDF ^> um arquivo PDF para cada relatorio).
echo O ensaio navega ate a pasta de saida SEM clicar em OK. Depois feche o dialogo com Cancelar.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\navegar_seletor_pasta.py
) else (
  python scripts\navegar_seletor_pasta.py
)
set "RESULTADO_SELETOR=%errorlevel%"
pause
exit /b %RESULTADO_SELETOR%
