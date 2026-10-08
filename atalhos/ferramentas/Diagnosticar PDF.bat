@echo off
cd /d "%~dp0..\.."
python scripts\diagnosticar_pdf.py
set "diagnostico_status=%errorlevel%"
echo.
pause
exit /b %diagnostico_status%
