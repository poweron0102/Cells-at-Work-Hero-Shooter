@echo off
setlocal
cd /d "%~dp0"

rem Prepara o ambiente .venv com Python 3.14 64-bit.
rem O pybullet vem pre-compilado da pasta wheels\, entao nao e preciso compilar nada.

set "PY="
py -3.14 -c "import struct,sys; sys.exit(struct.calcsize('P') != 8)" >nul 2>&1 && set "PY=py -3.14"
if not defined PY (
    python -c "import struct,sys; sys.exit(not (sys.version_info[:2] == (3, 14) and struct.calcsize('P') == 8))" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo Python 3.14 64-bit nao encontrado.
    echo Instale pelo site https://www.python.org/downloads/ e rode este arquivo de novo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Criando o ambiente .venv...
    %PY% -m venv .venv
    if errorlevel 1 goto falhou
)

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install --find-links wheels -r requirements.txt
if errorlevel 1 goto falhou

echo.
echo Pronto! Abra Jogar.bat para jogar.
pause
exit /b 0

:falhou
echo.
echo A instalacao falhou. Veja as mensagens acima.
pause
exit /b 1
