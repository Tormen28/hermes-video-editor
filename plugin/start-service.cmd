@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ---------------------------------------------------------------------------
rem  Editor de video - servicio local (loopback)
rem  Uso: start-service.cmd [puerto]
rem
rem  Sin argumentos usa el puerto 8765, que es el que espera el pane.
rem  El argumento opcional existe para pruebas o para mover el servicio.
rem
rem  Datos : %LOCALAPPDATA%\hermes\video-editor\data
rem  Medios: %LOCALAPPDATA%\hermes\video-editor\media
rem ---------------------------------------------------------------------------

title Editor de video - servicio local

set "PORT=%~1"
if not defined PORT set "PORT=8765"

rem --- validar que el puerto sea un numero -----------------------------------
for /f "delims=0123456789" %%X in ("%PORT%") do (
  echo.
  echo  [ERROR] Puerto invalido: "%PORT%"
  echo          Usa un numero entero entre 1 y 65535. Ejemplo:
  echo          start-service.cmd 8765
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)
rem  Quitar ceros iniciales antes de convertir: set /a los lee como octal.
set "PORT_CLEAN=%PORT%"
for /f "tokens=* delims=0" %%N in ("%PORT_CLEAN%") do set "PORT_CLEAN=%%N"
if not defined PORT_CLEAN set "PORT_CLEAN=0"
set /a "PORT_NUM=%PORT_CLEAN%+0" >nul 2>&1
if not defined PORT_NUM (
  echo.
  echo  [ERROR] Puerto invalido: %PORT%. Debe estar entre 1 y 65535.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)
if %PORT_NUM% LSS 1 (
  echo.
  echo  [ERROR] Puerto fuera de rango: %PORT%. Debe estar entre 1 y 65535.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)
if %PORT_NUM% GTR 65535 (
  echo.
  echo  [ERROR] Puerto fuera de rango: %PORT%. Debe estar entre 1 y 65535.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)
rem  Normalizar el puerto (quitando ceros iniciales) para netstat, URL y Python.
set "PORT=%PORT_NUM%"

rem --- localizar el servicio respecto a este script --------------------------
for %%I in ("%~dp0..\core\service\app.py") do set "APP=%%~fI"
if not exist "%APP%" (
  echo.
  echo  [ERROR] No se encontro el servicio del editor de video.
  echo          Se esperaba en: "%APP%"
  echo          Ejecuta start-service.cmd desde la carpeta "plugin" del
  echo          repositorio video-editor, no desde una copia suelta.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

rem --- localizar python con where python -------------------------------------
set "PY="
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PY (
    "%%P" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY=%%P"
  )
)
if not defined PY (
  echo.
  echo  [ERROR] No se encontro Python en el PATH.
  echo          Este servicio necesita Python 3.10 o superior.
  echo          1. Instala Python desde https://www.python.org/downloads/windows/
  echo             y marca "Add python.exe to PATH".
  echo          2. Abre una consola NUEVA ^(o reinicia el explorador^) y comprueba:
  echo             where python
  echo          3. Vuelve a ejecutar start-service.cmd.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [ERROR] El Python encontrado es demasiado antiguo:
  echo          "%PY%"
  echo          Se necesita Python 3.10 o superior. Version actual:
  "%PY%" --version
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

rem --- localizar ffmpeg/ffprobe ----------------------------------------------
if defined VIDEO_EDITOR_TOOLS (
  set "TOOLS_ROOT=%VIDEO_EDITOR_TOOLS%"
) else (
  set "TOOLS_ROOT=%LOCALAPPDATA%\hermes\tools\ffmpeg-9.0.1-win32-x64\bin"
)
if not exist "%TOOLS_ROOT%\ffmpeg.exe" (
  echo.
  echo  [ERROR] No se encontro ffmpeg.exe.
  echo          Se esperaba en: "%TOOLS_ROOT%\ffmpeg.exe"
  echo          Esta maquina ya tiene FFmpeg en:
  echo          "%LOCALAPPDATA%\hermes\tools\ffmpeg-9.0.1-win32-x64\bin"
  echo          Si lo moviste, define VIDEO_EDITOR_TOOLS con la carpeta que
  echo          contiene ffmpeg.exe y ffprobe.exe antes de arrancar.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)
if not exist "%TOOLS_ROOT%\ffprobe.exe" (
  echo.
  echo  [ERROR] No se encontro ffprobe.exe en "%TOOLS_ROOT%".
  echo          ffmpeg.exe y ffprobe.exe deben estar en la misma carpeta.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

rem --- comprobar si el puerto ya esta ocupado --------------------------------
rem  Se usa netstat -ano y se compara el PUERTO LOCAL exacto (no :87650).
rem  Longitud de ":PUERTO" para recortar la direccion local por la derecha.
set "PLEN=0"
set "PTMP=:%PORT%"
:plen_loop
if not defined PTMP goto :plen_done
set /a PLEN+=1
set "PTMP=!PTMP:~1!"
goto :plen_loop
:plen_done

set "BUSY="
for /f "tokens=1,2,5" %%A in ('netstat -ano ^| findstr /C:":%PORT%" ^| findstr /C:"LISTENING" 2^>nul') do (
  set "ADDR=%%B"
  if "!ADDR:~-%PLEN%!"==":%PORT%" (
    set "BUSY=1"
    echo    %%A  %%B  PID %%C
  )
)
if defined BUSY (
  echo.
  echo  [ERROR] El puerto %PORT% ya esta ocupado por otro proceso.
  echo          No se arranca un segundo servicio.
  echo          Cierra la instancia anterior ^(Ctrl+C en su ventana^) o averigua
  echo          el proceso con: tasklist /FI "PID eq <PID>"
  echo          Para usar otro puerto: start-service.cmd 8766
  echo          ^(elige uno libre; el pane apunta a 8765 por defecto^)
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

rem --- crear carpetas de datos y medios --------------------------------------
if defined VE_DATA_ROOT (
  set "DATA_ROOT=%VE_DATA_ROOT%"
) else (
  set "DATA_ROOT=%LOCALAPPDATA%\hermes\video-editor\data"
)
if defined VE_MEDIA_ROOT (
  set "MEDIA_ROOT=%VE_MEDIA_ROOT%"
) else (
  set "MEDIA_ROOT=%LOCALAPPDATA%\hermes\video-editor\media"
)

if not exist "%DATA_ROOT%\" mkdir "%DATA_ROOT%" >nul 2>&1
if not exist "%DATA_ROOT%\" (
  echo.
  echo  [ERROR] No se pudo crear la carpeta de datos:
  echo          "%DATA_ROOT%"
  echo          Comprueba permisos de escritura.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)
if not exist "%MEDIA_ROOT%\" mkdir "%MEDIA_ROOT%" >nul 2>&1
if not exist "%MEDIA_ROOT%\" (
  echo.
  echo  [ERROR] No se pudo crear la carpeta de medios:
  echo          "%MEDIA_ROOT%"
  echo          Comprueba permisos de escritura.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

echo.
echo  Editor de video - servicio local
echo  --------------------------------
echo  URL     : http://127.0.0.1:%PORT%
echo  Datos   : "%DATA_ROOT%"
echo  Medios  : "%MEDIA_ROOT%"
echo  FFmpeg  : "%TOOLS_ROOT%"
echo  Python  : "%PY%"
echo.
echo  Esperando la linea JSON de arranque. Para detener: Ctrl+C.
echo.

"%PY%" "%APP%" --data-root "%DATA_ROOT%" --media-root "%MEDIA_ROOT%" --tools-root "%TOOLS_ROOT%" --port %PORT%
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  echo  [ERROR] El servicio termino con codigo %RC%.
  echo          Revisa los mensajes de arriba. Si el puerto se ocupo justo
  echo          despues de la comprobacion, vuelve a ejecutar este script.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b %RC%
)

echo  [OK] Servicio detenido.
echo.
if not defined VE_NO_PAUSE pause
exit /b 0
