@echo off
cd /d "%~dp0"
git pull origin main
echo.
echo Conferindo dependencias (so instala o que mudou)...
pip install -r requirements.txt
echo.
pause
