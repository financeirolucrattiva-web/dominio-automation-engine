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
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%~dp0projeto.zip' -DestinationPath '%DESTINO%' -Force"
if errorlevel 1 (
  echo ERRO ao extrair o projeto.
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
  echo AVISO: Git nao encontrado. A automacao funciona, mas Atualizar.bat precisa do Git.
)
echo.
echo Instalando dependencias (Python)...
pushd "%DESTINO%"
call "Instalar.bat"
popd
echo.
echo ================================================
echo  Instalado. Leia o LEIAME.txt desta pasta para os proximos passos:
echo  Tesseract em portugues, calibrar a tela, Configurar Acesso Rede.
echo ================================================
pause
