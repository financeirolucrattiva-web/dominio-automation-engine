@echo off
cd /d "%~dp0..\.."
python scripts\gerar_pacote_instalador.py
pause
