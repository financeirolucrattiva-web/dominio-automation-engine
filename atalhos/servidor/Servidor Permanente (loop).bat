@echo off
rem Mantem o servidor no ar: se ele fechar ou cair, sobe de novo em 15 s. Usado pela tarefa agendada.
cd /d "%~dp0..\.."
if not exist data mkdir data
:laco
echo [%date% %time%] iniciando servidor >> data\servidor_permanente.log
python scripts\servidor.py --rede-local --executar >> data\servidor_permanente.log 2>&1
echo [%date% %time%] servidor encerrou (codigo %errorlevel%); reiniciando em 15 s >> data\servidor_permanente.log
timeout /t 15 /nobreak >nul
goto laco
