@echo off
chcp 65001 >nul
title Pasang Ekstensi Snapgent ke Browser
cd /d "%~dp0"

echo.
echo ====================================================================
echo   🧩 PANDUAN CEPAT MEMASANG EKSTENSI SNAPGENT DI CHROME / EDGE
echo ====================================================================
echo.
echo   Langkah 1: Browser Anda akan terbuka ke halaman Ekstensi.
echo              (Jika tidak otomatis terbuka, buka chrome://extensions atau edge://extensions)
echo.
echo   Langkah 2: Nyalakan saklar "Developer mode" (Mode Pengembang) di kanan atas.
echo.
echo   Langkah 3: Klik tombol "Load unpacked" (Muat yang belum dibongkar) di kiri atas.
echo.
echo   Langkah 4: Pilih folder "snapgent-extension" yang otomatis terbuka di Explorer.
echo.
echo ====================================================================
echo.

REM 1. Buka folder snapgent-extension di Windows File Explorer
explorer.exe "%~dp0snapgent-extension"

REM 2. Coba buka browser Edge atau Chrome ke halaman extensions
start msedge.exe edge://extensions 2>nul || start chrome.exe chrome://extensions 2>nul

echo Folder ekstensi dan halaman browser sudah dibuka.
echo Setelah ekstensi terpasang, klik ganda file "start.bat" untuk menjalankan bridge!
echo.
pause

