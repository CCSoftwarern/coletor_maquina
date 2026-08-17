@echo off
echo ========================================
echo  Build do Coletor de Maquina (.exe)
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

echo.
echo [2/4] Instalando dependências...
pip install -r requirements.txt

echo.
echo [3/4] Compilando com PyInstaller...
pyinstaller --onefile --name coletor_maquina ^
    --add-data "config.json;." ^
    --hidden-import psutil ^
    --hidden-import psutil._psutil_windows ^
    --hidden-import psutil._psutil_linux ^
    --hidden-import psutil._psutil_osx ^
    --hidden-import socket ^
    --hidden-import uuid ^
    --hidden-import platform ^
    --hidden-import json ^
    --hidden-import datetime ^
    --hidden-import pymongo ^
    --hidden-import dns ^
    --hidden-import dns.resolver ^
    main.py

echo.
echo [4/4] Verificando resultado...
if exist "dist\coletor_maquina.exe" (
    echo.
    echo ========================================
    echo  BUILD CONCLUIDO COM SUCESSO!
    echo ========================================
    echo.
    echo Executavel: dist\coletor_maquina.exe
    echo Config:     dist\config.json - copie e edite
    echo.
    echo Para testar:
    echo   cd dist
    echo   copy ..\config.json .
    echo   edite config.json com sua URI do MongoDB Atlas
    echo   coletor_maquina.exe
) else (
    echo.
    echo [ERRO] Falha ao gerar o executavel.
    exit /b 1
)

pause