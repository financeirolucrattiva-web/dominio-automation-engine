@echo off
cd /d "%~dp0..\.."
call "%~dp0..\..\Atualizar.bat"
if errorlevel 1 (
  echo Atualizacao nao concluida: o servidor NAO foi reiniciado.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\scripts\servidor_permanente.ps1" -Acao reiniciar
pause
