@echo off
cd /d "%~dp0"
git pull origin main
if errorlevel 1 goto atualizacao_falhou
echo.
echo Conferindo dependencias (so instala o que mudou)...
python -m pip install -r requirements.txt
if errorlevel 1 goto atualizacao_falhou
if not exist "data\ocr_paddle_instalado.json" goto atualizacao_concluida
echo.
echo Conferindo OCR Paddle opcional ja instalado...
python scripts\instalar_ocr_paddle.py
if errorlevel 1 goto atualizacao_falhou

:atualizacao_concluida
echo.
echo Atualizacao concluida.
pause
exit /b 0

:atualizacao_falhou
echo.
echo Atualizacao nao concluida. Confira o erro acima antes de rodar o motor.
pause
exit /b 1
