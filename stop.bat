@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Stop Snapgent Local Bridge
cd /d "%~dp0"

echo.
echo ====================================================================
echo   Snapgent Connector - Menghentikan Local Bridge (Windows)
echo ====================================================================
echo.

set "STOPPED=0"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :17613 ^| findstr LISTENING 2^>nul') do (
    set "OLDPID=%%a"
    echo [*] Menghentikan proses bridge PID !OLDPID! di port 17613...
    taskkill /F /T /PID !OLDPID! >nul 2>nul
    set "STOPPED=1"
)

taskkill /F /IM bridge.exe >nul 2>nul
if %errorlevel% equ 0 set "STOPPED=1"

if "!STOPPED!"=="1" (
    echo.
    echo [✓] Snapgent Bridge berhasil dihentikan.
) else (
    echo [-] Snapgent Bridge tidak sedang berjalan di port 17613.
)
echo.
timeout /t 2 /nobreak >nul

