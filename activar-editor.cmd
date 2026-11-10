@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Activar el editor de video (token + servicio nuevo) ===
echo Conserva tus proyectos y medios actuales de esta carpeta (core\data, core\media).
echo No toca Hermes. Si hay una exportacion en curso, NO reinicia el servicio.
echo.
python instalar.py --data-root "%~dp0core\data" --media-root "%~dp0core\media" --restart %*
echo.
echo Siguiente paso: en Hermes, Capacidades - Plugins, apaga y enciende "Editor de video".
pause
