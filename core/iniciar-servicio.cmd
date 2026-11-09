@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "CONFIG=%LOCALAPPDATA%\hermes\video-editor\config.json"
if exist "%CONFIG%" (
  python start_service.py --config "%CONFIG%"
) else (
  echo Config no encontrada; usando valores locales.
  python start_service.py --data-root "%~dp0data" --media-root "%USERPROFILE%\Videos\hermes-video" --port 8770
)
pause
