# Editor de vídeo · pane local para Hermes Desktop

Pane de edición de vídeo por escenas que corre **entero en esta máquina**. La
interfaz vive dentro de Hermes Desktop (`plugin.js`) y habla por loopback con un
servicio Python propio (`core/service/app.py`) que renderiza con el FFmpeg ya
instalado. No hay nube, no hay cuentas y no se sube nada.

- **Qué produce:** un MP4 H.264 + AAC, 30 fps, 720p horizontal (1280×720) o
  vertical (720×1280).
- **Cómo trabaja:** importas medios, ordenas escenas, ajustas duración, encuadre,
  volumen, transiciones y subtítulos; el servicio renderiza un trabajo cada vez.
- **Dónde guarda:** proyectos y cola en `%LOCALAPPDATA%\hermes\video-editor\data`;
  la carpeta de medios concedida se registra aparte y los originales no se tocan.

## Archivos de esta carpeta

| Archivo | Para qué |
|---|---|
| `plugin.js` | El pane. Es lo único que se copia a la carpeta de plugins de la app. |
| `install.cmd` | Instalador de doble clic: copia `plugin.js` a `desktop-plugins\video-editor`. |
| `start-service.cmd` | Arranca el servicio local en el puerto 8765. |
| `README.md` | Este documento. |

El servicio y el motor están en el repositorio, un nivel arriba:
`..\core\service\app.py`. `start-service.cmd` los busca ahí, así que debe
ejecutarse desde esta carpeta `plugin` (no desde una copia suelta del `.cmd`).

## Requisitos (ya instalados en esta máquina)

| Requisito | Estado | Ruta / versión |
|---|---|---|
| Windows 10/11 + Hermes Desktop con soporte de plugins | Presente | La app carga carpetas de `%LOCALAPPDATA%\hermes\desktop-plugins\` |
| Python 3.10 o superior en el `PATH` | Presente | Primer `where python`: `C:\Users\EgtYP\AppData\Local\hermes\installs\add27c619e6ab1e0\environments\f610a3578286433a9c126f78871316e4\venv\Scripts\python.exe` → **Python 3.14.9** |
| Python alternativo (también instalado) | Presente | `C:\Users\EgtYP\AppData\Local\Programs\Python\Python312\python.exe` (3.12) |
| FFmpeg + ffprobe | Presente | `C:\Users\EgtYP\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin` → **ffmpeg n9.0.1** |

El servicio solo usa la biblioteca estándar de Python: no hay `pip install`, ni
entorno virtual que crear, ni dependencias de Node para ejecutarlo. El pane usa
el SDK y React que ya trae Hermes Desktop.

## Arrancar el servicio

1. Doble clic en `plugin\start-service.cmd` (o desde una consola:
   `cd` a esta carpeta y `start-service.cmd`).
2. El script:
   - encuentra Python con `where python` y comprueba que sea ≥ 3.10;
   - comprueba `ffmpeg.exe` y `ffprobe.exe` en la ruta de arriba;
   - comprueba con `netstat -ano` que el puerto **8765** esté libre y, si está
     ocupado, **no arranca un segundo proceso**: muestra el PID y termina;
   - crea si faltan `%LOCALAPPDATA%\hermes\video-editor\data` y `...\media`;
   - lanza el servicio en primer plano.
3. Cuando veas una línea JSON como esta, el servicio está listo:

   ```json
   {"service": "0.2.0", "url": "http://127.0.0.1:8765", "dataRoot": "...", "mediaRoot": "...", "restartedJobs": []}
   ```

4. Para detenerlo: **Ctrl+C** en esa ventana. Si Windows pregunta si terminar el
   trabajo por lotes, responde `S`.

Comprobación rápida desde otra consola:

```bat
curl http://127.0.0.1:8765/health
```

Debe responder JSON con `"ok": true`, la versión de FFmpeg y el estado de la cola.
El servicio escucha **solo en 127.0.0.1** y rechaza peticiones con `Host` u
`Origin` que no sean locales.

### Puerto alternativo

```bat
start-service.cmd 8799
```

Sirve para pruebas o para convivir con otro proceso en 8765. El pane apunta a
8765 por defecto; hoy no hay ajuste visual de URL, así que para uso normal deja
el puerto 8765.

### Carpetas alternativas (avanzado)

Los valores por defecto son los de arriba. Si necesitas aislar una prueba, puedes
definir antes de arrancar:

```bat
set VE_DATA_ROOT=%TEMP%\ve-data
set VE_MEDIA_ROOT=%TEMP%\ve-media
set VIDEO_EDITOR_TOOLS=C:\ruta\a\ffmpeg\bin
start-service.cmd 8799
```

Sin esas variables, las rutas son siempre las documentadas.

### Banco de pruebas del pane (harness)

```bat
python plugin\harness\setup_fixtures.py --port 8765 --harness-origin http://127.0.0.1:8800
```

Genera clips sintéticos 720p y un PNG con FFmpeg, escribe `harness\media.json` (el listado
que consume el `ctx.files` simulado), arranca `core\service\app.py` y crea el proyecto
«Lanzamiento Q4 (harness)» con tres medios. Imprime un JSON con `service`, `projectId`,
`media`, `data` y `servicePid`.

- La carpeta de trabajo es `%TEMP%\ve-harness` **siempre en ruta absoluta** (en cmd.exe y
  PowerShell no existe `TMPDIR`; una raíz relativa hacía que el servicio respondiera 400 al
  importar medios). Se puede mover con `set VE_HARNESS_DIR=D:\pruebas`.
- En Windows el servicio se lanza `DETACHED_PROCESS`, así que sobrevive al cierre de la
  consola. Para pararlo: `curl -X POST http://127.0.0.1:8765/admin/stop -H "Host: 127.0.0.1:8765"`.
- Con `--reuse` no arranca nada: usa el servicio que ya esté escuchando en ese puerto.

## Instalar el pane

1. Cierra Hermes Desktop si está abierto (o prepárate para recargar plugins).
2. Doble clic en `plugin\install.cmd`.
3. El script copia `plugin.js` a:

   ```text
   %LOCALAPPDATA%\hermes\desktop-plugins\video-editor\plugin.js
   ```

   Crea la carpeta si no existe, verifica la copia byte a byte y es idempotente:
   si el archivo ya es idéntico, no cambia nada y lo dice. Si había una versión
   distinta, guarda la anterior como `plugin.js.bak` antes de sobrescribir.
4. Abre Hermes Desktop. El pane aparece como **Editor de vídeo**. No hace falta
   manifiesto: la app carga la carpeta que contiene `plugin.js` (el mismo patrón
   del plugin de spike).

Para probar el instalador sin tocar la instalación real:

```bat
install.cmd "C:\ruta\de\staging\video-editor"
```

El primer argumento opcional es la carpeta destino.

## Desinstalar

Todo es reversible y no toca perfiles de Hermes ni la base de datos de la app:

1. Cierra Hermes Desktop.
2. Borra la carpeta:

   ```text
   %LOCALAPPDATA%\hermes\desktop-plugins\video-editor
   ```

3. Opcional: borra también los datos y exports locales:

   ```text
   %LOCALAPPDATA%\hermes\video-editor
   ```

   Eso elimina proyectos, cola y MP4 exportados. No borra tus vídeos originales.

Si solo quieres volver a la versión anterior del pane, renombra `plugin.js.bak`
a `plugin.js` dentro de la carpeta instalada.

## Límites honestos del MVP

- **Export 720p/30, con 1080p como techo del motor.** El único preset expuesto
  y probado es `mp4-720p30`: 1280×720 horizontal o 720×1280 vertical, 30 fps,
  H.264 (libx264, CPU) + AAC. El motor admite documentos de hasta 1920×1080 y
  fuentes de hasta 1080p (que se escalan/recortan al lienzo), pero la interfaz
  **no expone una salida 1080p** y esa salida no se ha medido en este MVP. El
  vertical 720×1280 **sí está soportado** (el encuadre recorta los bordes
  laterales).
- **Preview por escena, no del timeline completo.** Cada escena reproduce su
  archivo original por HTTP con `Range` (206). No hay proxy 540p ni una
  previsualización renderizada del timeline entero: el texto de la escena se
  dibuja superpuesto en el preview, pero las transiciones y la concatenación
  solo se ven en el MP4 exportado. El scrub es del clip seleccionado, no de un
  stream continuo de todas las escenas.
- **Pausa de export no soportada.** No hay botón de pausar. Si necesitas parar,
  se cancela el trabajo (cancelación cooperativa, ≤10 s medidos en 0,52 s en el
  spike) y se relanza desde el principio; el MP4 parcial se descarta. No se
  reanuda un render a medias.
- **Un render a la vez.** La cola es persistente en SQLite: sobrevive a reinicios
  y los trabajos que estaban en curso se marcan `interrupted` al arrancar, no se
  reanudan solos.
- **Proyectos largos sin medir.** El grafo de FFmpeg viaja inline y tiene un techo
  duro de 20 000 caracteres; con muchas escenas y subtítulos podría acercarse al
  límite (hipótesis a ~40 escenas, no medida). Para proyectos largos, exporta por
  partes.
- **Sin red ni autenticación.** El diseño es loopback puro; no está pensado para
  exponerse en LAN ni para varios usuarios.
- **Sin firma ni autoactualización.** El instalador es un `.cmd` legible; no hay
  updater. Actualizar = volver a ejecutar `install.cmd`.

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `[ERROR] No se encontro Python en el PATH` | Python no está en `PATH` o la consola es antigua | Instala Python 3.10+, marca “Add python.exe to PATH”, abre una consola nueva y comprueba `where python` |
| `[ERROR] El puerto 8765 ya esta ocupado` | Otra instancia del servicio u otro proceso | Cierra la ventana anterior con Ctrl+C o mata el PID que muestra el script (`tasklist /FI "PID eq <PID>"`) |
| `[ERROR] No se encontro ffmpeg.exe` | FFmpeg movido o ruta distinta | Define `VIDEO_EDITOR_TOOLS` con la carpeta que contiene `ffmpeg.exe` y `ffprobe.exe` |
| El pane dice “sin conexión” | Servicio apagado o en otro puerto | Arranca `start-service.cmd` y abre `http://127.0.0.1:8765/health` |
| `/health` responde `"service": "editor-video-spike"` | Queda un servicio antiguo del spike ocupando 8765 | Cierra esa ventana o mata su PID; después arranca `start-service.cmd` |
| El pane no aparece tras instalar | La app no recargó plugins | Reinicia Hermes Desktop; confirma que existe `desktop-plugins\video-editor\plugin.js` |
| El export falla al empezar | Medio movido o borrado | Vuelve a vincular el medio en el pane; revisa el log del job en `data\jobs\<id>\` |
| `tools directory not found` | `--tools-root` apunta a una carpeta inexistente | Usa la ruta de FFmpeg documentada o corrige `VIDEO_EDITOR_TOOLS` |

## Estado de esta entrega

Preparado y probado en esta máquina el 2026-11-08, **sin instalar el pane en la
app ni recargar Hermes Desktop**.

- `install.cmd` contra staging en `TMPDIR`: primera pasada copió 89 374 bytes;
  segunda pasada dijo “idéntico, no se cambió nada”; al alterar el destino creó
  `plugin.js.bak` y restauró el original. También probado con espacios en la
  ruta destino.
- `install.cmd` sin `plugin.js` al lado: error claro con la ruta esperada y
  salida 1; no creó la carpeta destino.
- `start-service.cmd 8799`: creó `data` y `media`, `/health` respondió
  `"ok": true`, servicio 0.2.0 y FFmpeg n9.0.1.
- `start-service.cmd 8799` con el puerto ya ocupado: mostró el PID, salió 1 y no
  arrancó un segundo proceso.
- Durante la prueba, 8765 estaba ocupado por el servicio antiguo del spike; el
  script lo detectó y se negó a arrancar, como corresponde.
- Sin Python en `PATH` y con `VIDEO_EDITOR_TOOLS` inválido: mensajes de error
  útiles y salida 1 en ambos casos.



## Cerrar y reabrir el pane (imprescindible)

La **X nativa de la pestaña no sirve para cerrar el editor**: cerrar el único pane de un
plugin lo desactiva entero y desaparecen también el botón de barra de título, el comando
de paleta y el atajo. Para cerrar y volver a abrir usa estos tres caminos, que sí
respetan el estado:

- botón **«✕ Cerrar editor»** en la cabecera del pane (tooltip: «Cerrar (Ctrl+Shift+E)»);
- **Ctrl+Shift+E** (canónico `mod+shift+e`, rebindable en Ajustes ▸ Atajos);
- botón **«Vídeo»** de la barra de título o la fila **«Abrir/Cerrar editor de vídeo»** del ⌘K.

El estado vive en `ctx.storage['ui.open']`: con `false` el plugin arranca sin pane y deja
solo barra de título, comando y atajo. Al cerrar se pausan y sueltan los `<video>` y se
limpian los temporizadores de autoguardado y de polling del export.
