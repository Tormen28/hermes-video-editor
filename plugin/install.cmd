@echo off
setlocal EnableExtensions
rem ---------------------------------------------------------------------------
rem  Editor de video - instalador del pane para Hermes Desktop
rem  Uso: install.cmd [carpeta-destino]
rem
rem  Sin argumentos copia plugin.js a:
rem    %LOCALAPPDATA%\hermes\desktop-plugins\video-editor\plugin.js
rem  El argumento opcional existe para probar el instalador en una carpeta de
rem  staging sin tocar la instalacion real.
rem ---------------------------------------------------------------------------

set "SRC=%~dp0..\desktop\plugin.js"
set "DEST_DIR=%~1"
if not defined DEST_DIR (
  if not defined LOCALAPPDATA (
    echo.
    echo  [ERROR] La variable LOCALAPPDATA no esta definida y no se indico
    echo          una carpeta destino. Ejecuta install.cmd desde tu sesion
    echo          normal de Windows o pasa una ruta:
    echo          install.cmd "D:\ruta\video-editor"
    echo.
    if not defined VE_NO_PAUSE pause
    exit /b 1
  )
  set "DEST_DIR=%LOCALAPPDATA%\hermes\desktop-plugins\video-editor"
)

echo.
echo  Editor de video - instalacion del pane
echo  --------------------------------------
echo  Origen : "%SRC%"
echo  Destino: "%DEST_DIR%\plugin.js"
echo.

if not exist "%SRC%" (
  echo  [ERROR] No se encontro plugin.js junto a este instalador.
  echo          Se esperaba en: "%SRC%"
  echo          Copia la carpeta "plugin" completa ^(plugin.js + install.cmd^)
  echo          y vuelve a ejecutar install.cmd.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

if not exist "%DEST_DIR%\" (
  mkdir "%DEST_DIR%" >nul 2>&1
  if errorlevel 1 (
    echo  [ERROR] No se pudo crear la carpeta destino:
    echo          "%DEST_DIR%"
    echo          Comprueba permisos de escritura y vuelve a intentarlo.
    echo.
    if not defined VE_NO_PAUSE pause
    exit /b 1
  )
  echo  [OK] Carpeta creada: "%DEST_DIR%"
) else (
  echo  [OK] La carpeta destino ya existia.
)

if exist "%DEST_DIR%\plugin.js" (
  fc /b "%SRC%" "%DEST_DIR%\plugin.js" >nul 2>&1
  if not errorlevel 1 (
    echo  [OK] plugin.js ya estaba instalado y es identico. No se cambio nada.
    echo.
    echo  Siguiente paso: reinicia Hermes Desktop ^(o recarga los plugins^)
    echo  para que el pane "Editor de video" aparezca.
    echo.
    if not defined VE_NO_PAUSE pause
    exit /b 0
  )

  echo  [INFO] Hay una version anterior distinta; se guarda una copia en plugin.js.bak
  copy /y "%DEST_DIR%\plugin.js" "%DEST_DIR%\plugin.js.bak" >nul 2>&1
  if errorlevel 1 (
    echo  [ERROR] No se pudo crear la copia de seguridad plugin.js.bak.
    echo          No se sobrescribio nada. Revisa permisos de la carpeta.
    echo.
    if not defined VE_NO_PAUSE pause
    exit /b 1
  )
)

copy /y "%SRC%" "%DEST_DIR%\plugin.js" >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] No se pudo copiar plugin.js a:
  echo          "%DEST_DIR%\plugin.js"
  echo          Comprueba que la carpeta no sea de solo lectura.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

fc /b "%SRC%" "%DEST_DIR%\plugin.js" >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] La copia no coincide con el origen. Instalacion NO valida.
  echo          Vuelve a ejecutar install.cmd con permisos de tu usuario.
  echo.
  if not defined VE_NO_PAUSE pause
  exit /b 1
)

for %%F in ("%DEST_DIR%\plugin.js") do set "SIZE=%%~zF"
echo  [OK] plugin.js instalado ^(%SIZE% bytes^).
echo.
echo  Siguiente paso: reinicia Hermes Desktop ^(o recarga los plugins^)
echo  para que el pane "Editor de video" aparezca.
echo  Desinstalar: cierra la app y borra la carpeta
echo               "%DEST_DIR%"
echo.
if not defined VE_NO_PAUSE pause
exit /b 0
