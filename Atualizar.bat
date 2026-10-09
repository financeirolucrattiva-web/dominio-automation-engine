@echo off
cd /d "%~dp0"
python scripts\atualizar_projeto.py
if errorlevel 1 goto atualizacao_falhou
echo.
echo Conferindo dependencias (so instala o que mudou)...
python -m pip install -r requirements.txt
if errorlevel 1 goto atualizacao_falhou
if not exist "data\ocr_paddle_instalado.json" goto conferir_servidor
echo.
echo Conferindo OCR Paddle opcional ja instalado...
python scripts\instalar_ocr_paddle.py
if errorlevel 1 goto atualizacao_falhou

:conferir_servidor
if not exist "data\servidor_instalado.json" goto atualizacao_concluida
echo.
echo Conferindo interface conectada ja instalada...
python -m pip install -r requirements-servidor.txt
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
