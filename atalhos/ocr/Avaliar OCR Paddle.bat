@echo off
cd /d "%~dp0..\.."
if not exist ".venv-ocr-paddle\Scripts\python.exe" (
    echo OCR opcional nao instalado. Rode "atalhos\ocr\Instalar OCR Paddle.bat" primeiro.
    pause
    exit /b 1
)
if "%~1"=="" (
    ".venv-ocr-paddle\Scripts\python.exe" scripts\avaliar_ocr_paddle.py --escolher
) else (
    ".venv-ocr-paddle\Scripts\python.exe" scripts\avaliar_ocr_paddle.py %*
)
set "paddle_avaliacao_status=%errorlevel%"
if not "%paddle_avaliacao_status%"=="0" (
    echo Avaliacao nao concluida. Codigo de saida: %paddle_avaliacao_status%.
    echo Confira as ultimas mensagens acima.
)
echo.
pause
exit /b %paddle_avaliacao_status%
