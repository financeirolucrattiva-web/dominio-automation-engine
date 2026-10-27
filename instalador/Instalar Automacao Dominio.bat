@echo off
setlocal
cd /d "%~dp0"
title Instalar Automacao Dominio
echo ================================================
echo  Instalar a Automacao do Dominio (Lucro Presumido)
echo ================================================
echo.
set "DESTINO=%USERPROFILE%\dominio-automation-engine"
if not exist "projeto.zip" (
  echo ERRO: projeto.zip nao encontrado ao lado deste instalador.
  echo Copie a pasta INTEIRA "Automacao Dominio - Instalador" para este PC e rode de novo.
  pause
  exit /b 1
)

rem Python de verdade (o "python" falso da Microsoft Store abre a loja e nao roda nada).
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python 3.10 ou mais novo nao encontrado.
  echo.
  echo  1. Instale o Python de https://www.python.org/downloads/ e marque "Add Python to PATH".
  echo  2. Se o Windows abrir a Microsoft Store ao digitar "python", desligue o atalho falso:
  echo     Configuracoes ^> Aplicativos ^> Configuracoes avancadas de aplicativos
  echo     ^> Aliases de execucao de aplicativo ^> desligue "python.exe" e "python3.exe".
  echo  3. Feche esta janela e rode este instalador de novo.
  pause
  exit /b 1
)

if exist "%DESTINO%\app" (
  echo A automacao JA esta instalada em:
  echo   %DESTINO%
  echo Nada foi alterado. Para atualizar use Atualizar.bat dentro dessa pasta.
  echo Para reinstalar do zero, renomeie essa pasta e rode este instalador de novo.
  pause
  exit /b 0
)

echo Instalando em: %DESTINO%
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath '%~dp0projeto.zip' -DestinationPath '%DESTINO%' -Force"
if errorlevel 1 (
  echo ERRO ao extrair o projeto.zip.
  echo Confirme que o arquivo foi copiado por completo e que ha espaco em disco.
  pause
  exit /b 1
)
if not exist "%DESTINO%\app" (
  echo ERRO: a extracao nao criou a pasta app em "%DESTINO%".
  pause
  exit /b 1
)

where git >nul 2>nul
if not errorlevel 1 (
  pushd "%DESTINO%"
  git init -q -b main >nul 2>nul
  git remote add origin https://github.com/financeirolucrattiva-web/dominio-automation-engine >nul 2>nul
  git add -A >nul 2>nul
  git -c user.name=Instalador -c user.email=instalador@local commit -q -m "Instalacao inicial" >nul 2>nul
  popd
) else (
  echo AVISO: Git nao encontrado. A automacao funciona, mas o Atualizar.bat precisa do Git.
)
echo.
echo Instalando dependencias (Python)...
pushd "%DESTINO%"
call "Instalar.bat"
set "CODIGO=%errorlevel%"
popd
if not "%CODIGO%"=="0" (
  echo.
  echo A instalacao das dependencias NAO foi concluida. Leia o erro acima, corrija e rode este
  echo instalador de novo (ele continua de onde parou se apagar a pasta %DESTINO%).
  pause
  exit /b 1
)
echo.
echo ================================================
echo  Instalado. Leia os guias desta pasta ("1 - Instalar em outro PC.txt"):
echo  Tesseract em portugues, instalar o servidor, calibrar a tela, ligar ao docauto.
echo ================================================
pause
