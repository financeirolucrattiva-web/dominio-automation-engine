@echo off
cd /d "%~dp0..\.."
echo ATENCAO: se houver lote rodando, ele sera INTERROMPIDO.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\scripts\servidor_permanente.ps1" -Acao reiniciar -Forcar
pause
