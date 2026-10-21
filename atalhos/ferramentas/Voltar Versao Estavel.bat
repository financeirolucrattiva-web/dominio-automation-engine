@echo off
cd /d "%~dp0..\.."
echo Voltar para uma versao estavel (nada e apagado; Atualizar.bat traz a versao mais nova de volta).
echo PARE O SERVIDOR antes e reinicie depois.
echo.
echo Versoes estaveis disponiveis:
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\voltar_versao.py --listar
) else (
  python scripts\voltar_versao.py --listar
)
echo.
set "TAG="
set /p TAG=Digite o nome da versao (ENTER = a mais recente da lista):
if "%TAG%"=="" (
  if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\voltar_versao.py
  ) else (
    python scripts\voltar_versao.py
  )
) else (
  if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\voltar_versao.py --para "%TAG%"
  ) else (
    python scripts\voltar_versao.py --para "%TAG%"
  )
)
set "RESULTADO_VOLTAR=%errorlevel%"
pause
exit /b %RESULTADO_VOLTAR%
