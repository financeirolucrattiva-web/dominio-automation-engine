@echo off
cd /d "%~dp0"

echo ================================================
echo  Instalando o Automacao Fiscal Dominio
echo ================================================
echo.

rem Python de verdade (o "python" falso da Microsoft Store abre a loja e nao roda nada).
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python 3.10 ou mais novo nao encontrado.
    echo.
    echo Instale o Python antes de continuar:
    echo   https://www.python.org/downloads/
    echo Na instalacao, marque a opcao "Add Python to PATH".
    echo Se o Windows abrir a Microsoft Store ao digitar "python", desligue os aliases em:
    echo   Configuracoes ^> Aplicativos ^> Configuracoes avancadas de aplicativos
    echo   ^> Aliases de execucao de aplicativo ^> "python.exe" e "python3.exe".
    echo Depois rode este instalador de novo.
    echo.
    pause
    exit /b 1
)

set "TESSERACT_OK="
where tesseract >nul 2>nul
if not errorlevel 1 set "TESSERACT_OK=1"
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" set "TESSERACT_OK=1"
if exist "%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe" set "TESSERACT_OK=1"
if exist "data\tesseract_caminho.txt" set "TESSERACT_OK=1"
if not defined TESSERACT_OK (
    echo AVISO: Tesseract OCR nao encontrado.
    echo.
    echo Esta automacao so consegue ler a tela do Dominio com o
    echo Tesseract instalado, com o idioma portugues:
    echo   https://github.com/UB-Mannheim/tesseract/wiki
    echo Marque o pacote de idioma "Portuguese" na instalacao.
    echo.
    echo Se ja instalou mas o caminho for diferente do padrao
    echo ^(C:\Program Files\Tesseract-OCR^), crie um arquivo de texto
    echo em data\tesseract_caminho.txt com o caminho completo do
    echo tesseract.exe - nao precisa mexer em codigo nenhum.
    echo.
    echo Continuando a instalacao mesmo assim - sem o Tesseract, a
    echo automacao nao vai funcionar ate ele ser instalado.
    echo.
)

echo Instalando dependencias Python (requirements.txt)...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERRO: a instalacao das dependencias Python falhou. Confira a internet e o erro acima.
    echo Se citar "Microsoft Visual C++" ou "wheel", atualize o Python para a versao 3.12 ou 3.13 de 64 bits.
    pause
    exit /b 1
)
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
echo   1. Rode "Instalar Servidor.bat" (componentes do painel e acesso em rede).
echo   2. Siga o guia "1 - Instalar em outro PC.txt" da pasta do instalador.
echo.
pause
exit /b 0
