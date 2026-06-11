@echo off
title OBS MCP Bridge — Instalador
color 0B
echo.
echo  ==========================================
echo   OBS MCP Bridge — Instalacao rapida
echo  ==========================================
echo.

REM Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado.
    echo.
    echo  Baixe e instale em: https://www.python.org/downloads/
    echo  Marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

echo  [OK] Python encontrado.
echo.
echo  Instalando dependencias...
echo.

pip install obsws-python mcp pystray Pillow --quiet --upgrade
if errorlevel 1 (
    echo.
    echo  [ERRO] Falha ao instalar dependencias.
    echo  Tente rodar como Administrador.
    pause
    exit /b 1
)

echo.
echo  [OK] Dependencias instaladas!
echo.
echo  Iniciando OBS MCP Bridge...
echo.

REM Inicia o app em background
start "" pythonw "%~dp0app\obs_tray.py"

echo  [OK] OBS MCP Bridge iniciado na bandeja do sistema!
echo.
echo  Procure o icone "O" na barra de tarefas (canto inferior direito).
echo.
timeout /t 3 >nul
exit /b 0
