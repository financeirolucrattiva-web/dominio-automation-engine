@echo off
cd /d "%~dp0..\.."
call "%~dp0Avaliar OCR Paddle.bat" --tela %*
exit /b %errorlevel%
