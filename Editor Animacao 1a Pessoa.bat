@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Prepare o ambiente Python 3.14 conforme o README.md.
    pause
    exit /b 1
)
echo Editor de animacao de 1a pessoa: o navegador vai abrir sozinho.
echo Deixe esta janela aberta enquanto edita. Feche-a (ou Ctrl+C) para encerrar.
".venv\Scripts\python.exe" scripts\editor_fp\server.py %*
if errorlevel 1 pause
