@echo off
cd /d "%~dp0"
call "Avaliar OCR Paddle.bat" --tela %*
exit /b %errorlevel%
