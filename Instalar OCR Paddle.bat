@echo off
cd /d "%~dp0"
python scripts\instalar_ocr_paddle.py
set "paddle_instalacao_status=%errorlevel%"
echo.
pause
exit /b %paddle_instalacao_status%
