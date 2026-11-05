@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Snapgent Local Bridge
cd /d "%~dp0"

if not exist "%~dp0logs" mkdir "%~dp0logs" >nul 2>nul
set "LOGFILE=%~dp0logs\start.log"

echo.
echo ====================================================================
echo   Snapgent Connector - Local Bridge Windows
echo   Menghubungkan AI Chat (ChatGPT, DeepSeek, Claude) ke VS Code / Tools
echo ====================================================================
echo.

REM --- 1. Bersihkan Port 17613 jika ada bridge lama di Windows ---
set "OLDPID="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :17613 ^| findstr LISTENING 2^>nul') do (
    set "OLDPID=%%a"
)
if defined OLDPID (
    echo [INFO] Menghentikan bridge lama PID !OLDPID! di port 17613...
    taskkill /F /T /PID !OLDPID! >nul 2>nul
    timeout /t 1 /nobreak >nul
)

REM --- 2. Pastikan file config.json ada (tanpa perlu Roblox Studio) ---
if not exist "%~dp0config.json" (
    echo {"mcpServers": {}} > "%~dp0config.json"
)

REM --- 3. Deteksi atau Siapkan Python ---
set "PY_EXE="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
    goto :PYTHON_READY
)

echo [1/3] Memeriksa instalasi Python di komputer ini...

REM Cek Python launcher 'py'
py -3 -c "import sys; sys.exit(0)" >nul 2>nul
if !errorlevel! equ 0 (
    set "BASE_PY=py -3"
    goto :CREATE_VENV
)

REM Cek 'python' standar (bukan alias Microsoft Store yang kosong)
python -c "import sys; sys.exit(0)" >nul 2>nul
if !errorlevel! equ 0 (
    set "BASE_PY=python"
    goto :CREATE_VENV
)

REM Cek folder instalasi umum Python di Windows
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "BASE_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :CREATE_VENV
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :CREATE_VENV
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "BASE_PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto :CREATE_VENV
)
if exist "%ProgramFiles%\Python312\python.exe" (
    set "BASE_PY=%ProgramFiles%\Python312\python.exe"
    goto :CREATE_VENV
)
if exist "%ProgramFiles%\Python311\python.exe" (
    set "BASE_PY=%ProgramFiles%\Python311\python.exe"
    goto :CREATE_VENV
)

REM --- Jika Python belum ada sama sekali, install otomatis ---
echo.
echo [!] Python belum terpasang di komputer ini.
echo [+] Mengunduh dan memasang Python otomatis...
echo.

winget --version >nul 2>nul
if !errorlevel! equ 0 (
    winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements --silent
) else (
    echo [*] Mengunduh installer resmi Python dari python.org...
    powershell.exe -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile \"$env:TEMP\python-setup.exe\"; Start-Process \"$env:TEMP\python-setup.exe\" -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1' -Wait"
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "BASE_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :CREATE_VENV
)

python -c "import sys; sys.exit(0)" >nul 2>nul
if !errorlevel! equ 0 (
    set "BASE_PY=python"
    goto :CREATE_VENV
)

echo.
echo [ERROR] Gagal mendeteksi Python. Silakan pasang Python 3.10+ manual dari python.org
echo Pastikan centang opsi 'Add python.exe to PATH' saat instalasi.
echo.
pause
exit /b 1

:CREATE_VENV
echo [2/3] Menyiapkan environment lokal .venv...
!BASE_PY! -m venv "%~dp0.venv"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Gagal membuat virtual environment .venv.
    pause
    exit /b 1
)
set "PY_EXE=%~dp0.venv\Scripts\python.exe"

:PYTHON_READY
REM --- 4. Pastikan library websockets terinstal ---
"!PY_EXE!" -c "import websockets" >nul 2>nul
if !errorlevel! neq 0 (
    echo [3/3] Menginstal dependensi websockets...
    "!PY_EXE!" -m pip install websockets --quiet
    if !errorlevel! neq 0 (
        echo [ERROR] Gagal menginstal websockets via pip.
        pause
        exit /b 1
    )
)

echo.
echo ====================================================================
echo   [OK] Bridge Siap!
echo   Target : VS Code MCP / Workspace dan Agent Tools
echo   Alamat : ws://127.0.0.1:17613
echo   Biarkan jendela ini tetap terbuka saat menggunakan ekstensi.
echo ====================================================================
echo.

"!PY_EXE!" "%~dp0bridge.py"
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [INFO] Bridge berhenti dengan kode %EXIT_CODE%.
    echo Tekan tombol apa saja untuk menutup jendela.
    pause >nul
)
exit /b %EXIT_CODE%
