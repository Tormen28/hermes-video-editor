@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Editor de video para Hermes: instalador ===
python instalar.py %*
echo.
pause
