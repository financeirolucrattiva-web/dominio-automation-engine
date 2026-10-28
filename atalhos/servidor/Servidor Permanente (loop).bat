@echo off
rem Mantem o servidor no ar: se ele fechar ou cair, sobe de novo em 15 s. Usado pela tarefa agendada.
cd /d "%~dp0..\.."
if not exist data mkdir data
:laco
echo [%date% %time%] iniciando servidor >> data\servidor_permanente.log
python scripts\servidor.py --rede-local --executar >> data\servidor_permanente.log 2>&1
echo [%date% %time%] servidor encerrou (codigo %errorlevel%); reiniciando em 15 s >> data\servidor_permanente.log
rem timeout falha sem console (janela oculta) e vira laco em alta velocidade: espera com ping.
ping -n 16 127.0.0.1 >nul
goto laco
