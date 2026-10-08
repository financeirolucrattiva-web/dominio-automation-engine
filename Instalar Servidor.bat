@echo off
cd /d "%~dp0"
python -m pip install -r requirements-servidor.txt
if errorlevel 1 goto falhou
python -c "import json; from pathlib import Path; p=Path('data'); p.mkdir(exist_ok=True); (p/'servidor_instalado.json').write_text(json.dumps({'versao': 1}), encoding='utf-8')"
if errorlevel 1 goto falhou
echo.
echo Componentes do servidor instalados. Configure o acesso abaixo.
python scripts\configurar_servidor.py
if errorlevel 1 goto falhou
pause
exit /b 0
:falhou
echo.
echo Instalacao nao concluida. Confira o erro antes de abrir o servidor.
pause
exit /b 1
