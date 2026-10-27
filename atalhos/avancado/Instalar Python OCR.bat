@echo off
cd /d "%~dp0..\.."
python scripts\instalar_ocr_paddle.py --instalar-python
set "python_ocr_instalacao_status=%errorlevel%"
echo.
pause
exit /b %python_ocr_instalacao_status%
