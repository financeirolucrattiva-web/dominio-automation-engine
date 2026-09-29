@echo off
cd /d "%~dp0"

rem Achado real, secao 0.58: parenteses em caminho tipo Program Files
rem x86 quebram a sintaxe do cmd perto de bloco if-else, mesmo dentro
rem de aspas - por isso todo caminho ou nome de arquivo com parenteses
rem vira variavel aqui em cima, sozinho, sem outro comando na mesma
rem linha, e so e referenciado como VARIAVEL dai pra frente. Mesma
rem regra pra nome de arquivo com acento, secao 0.59 - nenhum aqui.
set "URL_GIT=https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.5/Git-2.55.0.5-64-bit.exe"
set "URL_PYTHON=https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe"
set "URL_TESSERACT=https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.3.20260724.exe"
set "URL_PORTUGUES=https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata"
set "URL_REPO=https://github.com/financeirolucrattiva-web/dominio-automation-engine.git"
set "CAMINHO_TESSERACT_PADRAO=C:\Program Files\Tesseract-OCR\tesseract.exe"
set "CAMINHO_TESSERACT_X86=C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
set "TESSDATA_PADRAO=C:\Program Files\Tesseract-OCR\tessdata"
set "TESSDATA_X86=C:\Program Files (x86)\Tesseract-OCR\tessdata"
set "AGENTE_HTTP=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

rem Achado real, secao 0.60: instalar Python/Git/Tesseract pra toda a
rem maquina precisa de permissao de administrador - pede uma vez so,
rem no comeco, e reabre este mesmo arquivo ja elevado.
net session >nul 2>nul
if errorlevel 1 goto precisa_elevar
goto tem_admin
:precisa_elevar
echo Esta instalacao precisa de permissao de administrador.
echo Uma janela do Windows vai pedir sua confirmacao a seguir...
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -WorkingDirectory '%cd%' -Verb RunAs"
exit /b
:tem_admin

echo ================================================
echo  Instalando o Automacao Fiscal Dominio
echo ================================================
echo.

where git >nul 2>nul
if not errorlevel 1 goto tem_git
echo Git nao encontrado - baixando e instalando sozinho...
set "TENTATIVA_GIT=0"
:retry_git
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL_GIT%' -OutFile 'git_instalador_temp.exe' -UserAgent '%AGENTE_HTTP%'"
if exist "git_instalador_temp.exe" goto baixou_git
set /a TENTATIVA_GIT+=1
if %TENTATIVA_GIT% geq 3 goto falha_download_git
echo Falha no download - tentando de novo (%TENTATIVA_GIT%/3)...
timeout /t 3 /nobreak >nul
goto retry_git
:baixou_git
start /wait "" git_instalador_temp.exe /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS
del git_instalador_temp.exe
set "PATH=%PATH%;C:\Program Files\Git\cmd"
goto tem_git
:falha_download_git
echo AVISO: nao consegui baixar o instalador do Git sozinho. Baixe e
echo instale manualmente, depois rode este arquivo de novo:
echo   https://git-scm.com/download/win
:tem_git

if exist "app\dominio.py" goto tem_projeto
echo Baixando o projeto do GitHub...
git clone "%URL_REPO%" dominio-automation-engine
if not exist "dominio-automation-engine\app\dominio.py" goto falha_clone
cd dominio-automation-engine
goto tem_projeto
:falha_clone
echo AVISO: nao consegui baixar o projeto do GitHub. Confira sua conexao
echo com a internet e tente rodar este arquivo de novo.
pause
exit /b
:tem_projeto

where python >nul 2>nul
if not errorlevel 1 goto tem_python
echo Python nao encontrado - baixando e instalando sozinho...
set "TENTATIVA_PYTHON=0"
:retry_python
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL_PYTHON%' -OutFile 'python_instalador_temp.exe' -UserAgent '%AGENTE_HTTP%'"
if exist "python_instalador_temp.exe" goto baixou_python
set /a TENTATIVA_PYTHON+=1
if %TENTATIVA_PYTHON% geq 3 goto falha_download_python
echo Falha no download - tentando de novo (%TENTATIVA_PYTHON%/3)...
timeout /t 3 /nobreak >nul
goto retry_python
:baixou_python
start /wait "" python_instalador_temp.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
del python_instalador_temp.exe
set "PATH=%PATH%;C:\Program Files\Python314;C:\Program Files\Python314\Scripts"
goto tem_python
:falha_download_python
echo AVISO: nao consegui baixar o instalador do Python sozinho. Baixe e
echo instale manualmente, depois rode este arquivo de novo:
echo   https://www.python.org/downloads/
:tem_python

set "TESSERACT_EXE="
where tesseract >nul 2>nul
if not errorlevel 1 set "TESSERACT_EXE=tesseract"
if not defined TESSERACT_EXE if exist "%CAMINHO_TESSERACT_PADRAO%" set "TESSERACT_EXE=%CAMINHO_TESSERACT_PADRAO%"
if not defined TESSERACT_EXE if exist "%CAMINHO_TESSERACT_X86%" set "TESSERACT_EXE=%CAMINHO_TESSERACT_X86%"
if defined TESSERACT_EXE goto tem_tesseract
echo Tesseract nao encontrado - instalando sozinho...

rem Achado real, secao 0.63: o site da UB-Mannheim, digi.bib.uni-
rem mannheim.de, recusa/derruba o download via Invoke-WebRequest, mas
rem o mesmo instalador via winget funcionou de primeira - tenta winget
rem primeiro, so cai pro download direto (abaixo) se winget nao
rem existir ou nao deixar o Tesseract no lugar esperado.
where winget >nul 2>nul
if errorlevel 1 goto sem_winget
echo Tentando instalar via winget...
winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements
if exist "%CAMINHO_TESSERACT_PADRAO%" set "TESSERACT_EXE=%CAMINHO_TESSERACT_PADRAO%"
if not defined TESSERACT_EXE if exist "%CAMINHO_TESSERACT_X86%" set "TESSERACT_EXE=%CAMINHO_TESSERACT_X86%"
if defined TESSERACT_EXE goto tem_tesseract
echo winget nao deixou o Tesseract no lugar esperado - tentando baixar direto...
:sem_winget

set "TENTATIVA_TESSERACT=0"
:retry_tesseract
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL_TESSERACT%' -OutFile 'tesseract_instalador_temp.exe' -UserAgent '%AGENTE_HTTP%'"
if exist "tesseract_instalador_temp.exe" goto baixou_tesseract
set /a TENTATIVA_TESSERACT+=1
if %TENTATIVA_TESSERACT% geq 3 goto falha_download_tesseract
echo Falha no download - tentando de novo (%TENTATIVA_TESSERACT%/3)...
timeout /t 3 /nobreak >nul
goto retry_tesseract
:baixou_tesseract
start /wait "" tesseract_instalador_temp.exe /S
del tesseract_instalador_temp.exe
set "TESSERACT_EXE=%CAMINHO_TESSERACT_PADRAO%"
goto tem_tesseract
:falha_download_tesseract
echo AVISO: nao consegui baixar o instalador do Tesseract sozinho. Baixe
echo e instale manualmente, depois rode este arquivo de novo:
echo   https://github.com/UB-Mannheim/tesseract/wiki
:tem_tesseract

rem Achado real, secao 0.65: a checagem da secao 0.64 comparava
rem TESSERACT_EXE com CAMINHO_TESSERACT_PADRAO como texto - mas quando
rem o Tesseract esta no PATH, TESSERACT_EXE vira so "tesseract", sem
rem caminho nenhum - nunca bate com CAMINHO_TESSERACT_PADRAO mesmo
rem instalado no lugar certo, e cai direto no aviso sem baixar nada.
rem Corrigido: descobre a pasta tessdata verificando os dois caminhos
rem padrao direto no disco, sem depender de como TESSERACT_EXE foi
rem resolvido.
set "TESSDATA_REAL="
if exist "%CAMINHO_TESSERACT_PADRAO%" set "TESSDATA_REAL=%TESSDATA_PADRAO%"
if not defined TESSDATA_REAL if exist "%CAMINHO_TESSERACT_X86%" set "TESSDATA_REAL=%TESSDATA_X86%"
if not defined TESSERACT_EXE goto tem_portugues
if not defined TESSDATA_REAL goto avisa_sem_portugues
if exist "%TESSDATA_REAL%\por.traineddata" goto tem_portugues
echo Idioma portugues do Tesseract nao encontrado - baixando sozinho...
if not exist "%TESSDATA_REAL%" mkdir "%TESSDATA_REAL%"
set "TENTATIVA_PORTUGUES=0"
:retry_portugues
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL_PORTUGUES%' -OutFile '%TESSDATA_REAL%\por.traineddata' -UserAgent '%AGENTE_HTTP%'"
if exist "%TESSDATA_REAL%\por.traineddata" goto tem_portugues
set /a TENTATIVA_PORTUGUES+=1
if %TENTATIVA_PORTUGUES% geq 3 goto falha_download_portugues
echo Falha no download - tentando de novo (%TENTATIVA_PORTUGUES%/3)...
timeout /t 3 /nobreak >nul
goto retry_portugues
:falha_download_portugues
echo AVISO: nao consegui baixar o pacote de idioma portugues sozinho.
echo Baixe manualmente e coloque em %TESSDATA_REAL%:
echo   %URL_PORTUGUES%
goto tem_portugues
:avisa_sem_portugues
echo AVISO: nao achei a pasta tessdata do Tesseract nos lugares padrao -
echo nao consigo confirmar nem baixar o idioma portugues sozinho.
echo Reinstale marcando o pacote de idioma Portuguese:
echo   https://github.com/UB-Mannheim/tesseract/wiki
:tem_portugues

echo Instalando dependencias Python, arquivo requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo AVISO: Falha instalando dependencia Python - confira o erro
    echo acima. Tente rodar de novo, ou manualmente:
    echo   pip install -r requirements.txt
    echo.
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
echo   1. Copie data\empresas.exemplo.csv para data\empresas.csv
echo      e preencha com as empresas de verdade.
echo   2. No dia a dia, use o atalho Interface Grafica do Operador.
echo.

set /p ABRIR_AGORA="Quer abrir a interface agora, pra conferir - S ou N: "
if /i not "%ABRIR_AGORA%"=="S" goto pular_abrir
set "DOMINIO_MODO=operador"
start "" python scripts\gui.py
:pular_abrir

pause
