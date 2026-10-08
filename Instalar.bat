@echo off
cd /d "%~dp0"

echo ================================================
echo  Instalando o Automacao Fiscal Dominio
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    echo.
    echo Instale o Python antes de continuar:
    echo   https://www.python.org/downloads/
    echo Na instalacao, marque a opcao "Add Python to PATH".
    echo Depois rode este instalador de novo.
    echo.
    pause
    exit /b 1
)

where tesseract >nul 2>nul
if errorlevel 1 (
    echo AVISO: Tesseract OCR nao encontrado no PATH.
    echo.
    echo Esta automacao so consegue ler a tela do Dominio com o
    echo Tesseract instalado, com o idioma portugues:
    echo   https://github.com/UB-Mannheim/tesseract/wiki
    echo Marque o pacote de idioma "Portuguese" na instalacao, e
    echo confirme que ele foi adicionado ao PATH do Windows.
    echo.
    echo Se ja instalou mas o caminho for diferente do padrao
    echo (C:\Program Files\Tesseract-OCR), crie um arquivo de texto
    echo em data\tesseract_caminho.txt com o caminho completo do
    echo tesseract.exe - nao precisa mexer em codigo nenhum.
    echo.
    echo Continuando a instalacao mesmo assim - sem o Tesseract, a
    echo automacao nao vai funcionar ate ele ser instalado.
    echo.
)

echo Instalando dependencias Python (requirements.txt)...
pip install -r requirements.txt
echo.

if not exist "data" (
    echo Criando pasta data\...
    mkdir data
)

echo.
echo ================================================
echo  Instalacao concluida.
echo ================================================
echo.
echo Proximos passos:
echo   1. Copie data\empresas.exemplo.csv para data\empresas.csv
echo      e preencha com as empresas de verdade.
echo   2. No dia a dia, use "atalhos\interface\Abrir Interface Gráfica (Operador).bat".
echo.
pause
