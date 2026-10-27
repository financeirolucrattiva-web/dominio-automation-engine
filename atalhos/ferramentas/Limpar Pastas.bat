@echo off
cd /d "%~dp0..\.."
echo Simulacao (nada e removido ainda):
python scripts\limpar_pastas.py
set /p CONFIRMA=Remover isso agora? (S/N): 
if /i "%CONFIRMA%"=="S" python scripts\limpar_pastas.py --aplicar
pause
