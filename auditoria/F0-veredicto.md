# VIDEO-EDITOR · Fase 0 · Veredicto de auditoría (Dike)

**Veredicto: OBSERVADO** — no bloqueante para el motor, bloqueante para declarar «extensión UI verificada» tal como está escrita.

- Fecha: 2026-11-08, hora local Caracas.
- Auditor: Dike (QA). Rol: verificar, no autorizar. La decisión es de Tormen.
- Material auditado (no modificado): `00-fase0/00-inventario-medido.md`, `00-fase0/01-superficie-ui-hermes.md`, `00-fase0/02-deltas-y-decisiones.md`, contra `PLAN-CONSOLIDADO.md` (gates 0 y 0R, líneas 110-116 y 174-179).
- Método: re-ejecución independiente de cada comando citado; comparación cifra por cifra; inspección del artefacto real (SDK, plugins, backend, bundle de la app). Nada se aprobó por self-report.
- Límites declarados: no ejecuté un pane nuevo ni reinicié el gateway (prohibido por contrato); por tanto **la carga en runtime de los 4 plugins de UI no está probada por mí** y lo digo abajo como faltante, no como aprobado.

---

## 1. Reproducción cifra por cifra

Todo lo de esta tabla lo ejecuté en esta sesión. `OK` = reproduce; `DRIFT` = la cifra cambió respecto al documento; `FALSO` = la afirmación no se sostiene con la evidencia citada.

### 1.1 Hardware

| Afirmación (00-inventario) | Comando ejecutado | Salida observada | Estado |
|---|---|---|---|
| Windows 11 Pro Build 26200 | `Get-CimInstance Win32_OperatingSystem` | `Caption: Microsoft Windows 11 Pro` · `BuildNumber: 26200` · `Version: 10.0.26200` | OK |
| Ryzen 5 3600 · 6 cores / 12 hilos | `Get-CimInstance Win32_Processor` | `AMD Ryzen 5 3600 6-Core Processor` · `NumberOfCores: 6` · `NumberOfLogicalProcessors: 12` | OK |
| RAM total 23.9 GB | `Win32_ComputerSystem.TotalPhysicalMemory / 1GB` | `23,93` GB | OK |
| 12.9 GB libres al medir | `Win32_OperatingSystem.FreePhysicalMemory / 1MB` | `10,86` GB | DRIFT (ver H-5) |
| GT 1030 · 2 GB VRAM · driver 32.0.15.8108 | `Get-CimInstance Win32_VideoController` | `NVIDIA GeForce GT 1030` · `VRAM_GB: 2` · `DriverVersion: 32.0.15.8108` · `DriverDate: 14/8/2025` | OK |
| Disco 223 GB total · 193 usados · 31 libres (87%) | `df -h /c` y `Win32_LogicalDisk` | `C: 223G 189G 35G 85% /c` · `SizeGB 222,6` · `FreeGB 34,5` · `PctFree 15,5` | DRIFT (ver H-6) |

### 1.2 Software

| Afirmación | Comando | Salida observada | Estado |
|---|---|---|---|
| Hermes v0.23.0 (2026.9.24) stable · local 2bd378ed1b8d · git | `hermes --version` | `Hermes Agent v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d` / `Install method: git` / `Python: 3.11.15` / `Up to date` | OK |
| Node v24.15.0 | `node -v` | `v24.15.0` | OK |
| npm 12.0.2 | `npm -v` | `12.0.2` | OK |
| Python 3.11.15 | `python --version` | `Python 3.11.15` (y además `python3` → `3.14.9`, sin conflicto con lo afirmado) | OK |
| Git 2.53.0.windows.3 | `git --version` | `git version 2.53.0.windows.3` | OK |
| Rust NO instalado | `cargo --version` · `rustc --version` | `command not found` (ambos) | OK |
| FFmpeg n9.0.1 | `ffmpeg -version` | `ffmpeg version n9.0.1-11-ge47273f4d9-20260831` | OK |
| ffprobe n9.0.1 | `ffprobe -version` | `ffprobe version n9.0.1-11-ge47273f4d9-20260831` | OK |
| Build con `--enable-gpl --enable-libx264 --enable-libfreetype --enable-libass --enable-libmp3lame --enable-libopus --enable-libvpx` | `ffmpeg -buildconf` | las 7 banderas presentes, más `--enable-version3` | OK (matiz: ver H-8) |
| Licencia «GPL» | `ffmpeg -L` | `GNU General Public License … either version 3 of the License, or (at your option) any later version` | PARCIAL (ver H-8) |

Ruta real del binario (dato que el inventario no registra y es relevante para empaquetado/licencia):
`C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg` — es decir, **viene con Hermes**, no es una instalación independiente del usuario.

### 1.3 Capacidades del motor (`ffmpeg -filters` / `-encoders`)

| Afirmación | Salida literal | Estado |
|---|---|---|
| `trim` | `.. trim  V->V  Pick one continuous section from the input, drop the rest.` | OK |
| `concat` | `.. concat  N->N  Concatenate audio and video streams.` | OK |
| `xfade` | `.S xfade  VV->V  Cross fade one video with another video.` | OK |
| `scale` | `.. scale  V->V` | OK |
| `crop` | `.. crop  V->V` | OK |
| `overlay` | `TS overlay  VV->V` | OK |
| `drawtext` (libfreetype) | `T. drawtext  V->V  … using libfreetype library.` | OK |
| `subtitles` / `ass` (libass) | `.. subtitles  V->V  … libass` · `.. ass  V->V  … libass` | OK |
| `afade` | `T. afade  A->A` | OK |
| `acrossfade` | `.. acrossfade  N->A` | OK |
| `fade` | `TS fade  V->V  Fade in/out input video.` (verificado aparte con `^\s*[.TSC]+\s+fade\s`) | OK |
| `libx264` `aac` `libmp3lame` `libopus` | `V....D libx264` · `A....D aac` · `A....D libmp3lame` · `A....D libopus` | OK |
| `h264_nvenc` / `hevc_nvenc` «aparecen compilados» | `V....D h264_nvenc  NVIDIA NVENC H.264 encoder` · `V....D hevc_nvenc` | OK |
| «la GT 1030 no tiene unidad NVENC» (causa) | Ver prueba directa abajo | **FALSO como causa medida** (ver H-4) |

Prueba directa de NVENC (no destructiva, salida a `-f null`):

```
$ ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=320x240:rate=30:duration=1 \
    -c:v h264_nvenc -f null -
[h264_nvenc] Cannot load nvEncodeAPI64.dll
[h264_nvenc] The minimum required Nvidia driver for nvenc is 610.00 or newer
[vost#0:0/h264_nvenc] Error while opening encoder …
```

Conclusión operativa **confirmada**: NVENC no sirve en esta máquina → `libx264` por CPU. Pero el motivo que da el documento no es el que arroja la medición.

### 1.4 Plugins de Hermes y superficie UI

| Afirmación | Comando | Salida observada | Estado |
|---|---|---|---|
| `~/.hermes/plugins/` 16 entradas con esa lista | `ls -1 .../hermes/plugins \| wc -l` y `ls -1` | `16` y los 16 nombres exactos: advanced-delegation, blender, bot-agente, bot-chat-agent, bsk-studio, candado-kanban, github-copilot, hermes-handoff, hermes-jev, homeassistant, meshy, model-providers, padre-flow, pixel-forge, pruner-pilot, tormen-skill | OK |
| `plugins.enabled` = esos 10 | `sed -n '566,584p' .../hermes/config.yaml` | exactamente los 10 citados (advanced-delegation, blender, bot-chat-agent, bsk-studio, github-copilot, hermes-handoff, hermes-jev, meshy, pixel-forge, tormen-skill) | OK |
| 4 desktop-plugins existen | `ls -1 .../desktop-plugins` | `bot-agente` `bot-chat-agent` `meshy` `padre-flow` | OK |
| «los 4 cargan en la app» | ver H-2 | sin evidencia en logs ni en estado de la app | **NO VERIFICABLE** |
| SDK existe, 132.763 bytes, 3-nov-2026 | `stat -c '%s %y' .../website/docs/developer-guide/desktop-plugin-sdk.md` | `132763 bytes  2026-11-03 20:58:25` · 2529 líneas | OK |
| `padre-flow/plugin.js` 13 KB, 2-nov-2026 | `ls -la` | `13353` bytes, `nov. 2 21:46` | OK |
| importa `@hermes/plugin-sdk` | `grep -n` | línea 1: `import { atom, host, useValue } from '@hermes/plugin-sdk'` | OK |
| «llama `host.request(...)` para leer el Kanban» | `grep -c "host.request" padre-flow/plugin.js` | **`0`** | **FALSO** (ver H-1) |
| Mecanismo real de datos de padre-flow | `grep -n "ctx.rest\|ctx.socket"` | `284: ctx.rest(\`/active?board=${BOARD}\`)` · `323: ctx.rest(\`/cards?board=${BOARD}\`)` · `412: ctx.socket(\`/events?board=${BOARD}\`)` | OK (otro mecanismo) |
| Los 4 `plugin.js` son ESM válidos | `node --check` sobre copia `.mjs` | `rc=0` en los 4 | OK |
| Backend `plugin_api.py` con `manifest.json` | `cat plugins/padre-flow/dashboard/manifest.json` | `{"name":"padre-flow", …, "api":"plugin_api.py"}` + `plugin_api.py` de 182 líneas | OK — el patrón que el editor necesita **está demostrado en disco** |
| Hot reload + «Reload desktop plugins» | `grep -iE "hot.?reload\|reload desktop"` en el SDK | líneas 21, 145-147, 2138, 2189, 2509 | OK |
| `host.request` es API real del SDK | `grep -c "host.request"` en el SDK | `13` (línea 50: «the gateway JSON-RPC door»; 1449: `host.request<T>(method, params?)`) | OK |
| `ctx.storage` / `ctx.os.notify` / `revealPath` / `openExternal` / `writeClipboard` | `grep -c` en el SDK | 12 / 3 / 2 / 3 / 3 | OK |
| `ROUTES_AREA` / `SIDEBAR_NAV_AREA` / `TOOL_MEDIA_RENDERER_AREA` / `SandboxedFrame` | `grep -c` en el SDK | 4 / 6 / 3 / 4 | OK |
| i18n con `usePluginI18n` | `grep -c "usePluginI18n"` en el SDK | **`0`**; el hook documentado es `useI18n` (línea 2113) | **FALSO el nombre** (ver H-3) |
| Componente `Slider` del UI kit | `grep -c "Slider"` en el SDK | `0` (el propio doc lo marca con «(via Segmented?)») | Aceptable: ya está marcado como duda |
| Loader de plugins de disco presente en la app instalada | `grep -o "desktop-plugins"` en `app.asar.unpacked/dist/assets/main-*.js` | 3 coincidencias + cadena `Reload desktop plugins` | OK (código enviado, no prueba de ejecución) |

---

## 2. Hallazgos

Severidad: **A** = afecta a la conclusión del gate; **B** = error de evidencia corregible; **C** = precisión/estilo.

### H-1 · [B] La evidencia citada de `padre-flow` es incorrecta: no usa `host.request`
- Archivo: `00-fase0/01-superficie-ui-hermes.md:10` — «`padre-flow/plugin.js` (13 KB, 2-nov-2026) importa `@hermes/plugin-sdk`, registra UI y llama `host.request(...)` para leer el Kanban».
- Comando: `grep -c "host.request" .../desktop-plugins/padre-flow/plugin.js` → `0`.
- Realidad: usa `ctx.rest` (líneas 284 y 323) y `ctx.socket` (línea 412) contra su `plugin_api.py`.
- Impacto: la frase se presenta como prueba del patrón que necesita el editor. El patrón real (`ctx.rest` → `/api/plugins/<id>` servido por `plugin_api.py`) es **igual de válido y más específico** para el editor, pero el documento describe otro mecanismo.
- Causa probable: confusión entre `host.request` (JSON-RPC al gateway) y `ctx.rest` (REST al backend del plugin), ambos documentados en el SDK.
- Recomendación: corregir la línea 10 citando `ctx.rest`/`ctx.socket` con número de línea; el resto del documento no cambia.

### H-2 · [A] «Los 4 cargan en la app» / «ya está probada aquí» no está medido
- Archivos: `00-inventario-medido.md:45` («los 4 cargan en la app (evidencia de que la superficie UI funciona en esta máquina)»), `01-superficie-ui-hermes.md:53` («CUMPLE por evidencia documental + 4 plugins en producción local»), `02-deltas-y-decisiones.md:12` («Demostrada … ya está probada aquí»).
- Lo que sí comprobé: los 4 directorios existen, los 4 `plugin.js` compilan (`node --check rc=0`), la app instalada contiene el loader (`desktop-plugins` ×3 en el bundle) y el comando `Reload desktop plugins`; `padre-flow` tiene backend real (`plugin_api.py`, 182 líneas, `manifest.json` con `"api"`).
- Lo que **no** pude comprobar: que los 4 panes se monten en runtime. Búsquedas hechas:
  - `grep -ci "plugin" logs/desktop.log` → `8` coincidencias, ninguna de carga; los únicos tags presentes son `[gateway-route]` (152), `[bot-roster]` (21), `[bot-meta]` (16). El loader no escribe en ese log.
  - `grep -r "padre-flow" AppData/Roaming/Hermes` → **sin coincidencias**; `bot-agente` sí aparece en `Local Storage/leveldb`, `meshy` en `Cache`.
  - `logs/desktop.log` sí muestra `GET /api/plugins/kanban/board` desde el renderer con errores (`Gateway ticket bootstrap failed`, `Gateway starting (deadline)`), lo que prueba actividad de *alguna* ruta de plugin, no que cargue `padre-flow`.
- Dato adicional relevante: `padre-flow` y `bot-agente` están en `plugins.disabled` del config por defecto (líneas 579 y 582). El pane de UI puede montarse igual (el plugin de disco no depende de `plugins.enabled`), pero **su `ctx.rest` a `/api/plugins/padre-flow` no puede servirse** mientras esté deshabilitado. Eso el propio documento lo reconoce en `01:32`, pero no lo conecta con la afirmación «los 4 cargan y funcionan».
- Impacto: el gate 0 del plan exige «**extensión UI real verificada**» (PLAN línea 177). Documentación + archivos en disco + código válido es evidencia fuerte de que la superficie **existe y está soportada**, no de que **funciona en esta máquina** hoy.
- Recomendación: rebajar la afirmación a lo medido («SDK documentado y en uso; 4 plugins de disco con código válido; carga en runtime pendiente de pane nuevo») o aportar captura de Capabilities → Plugins / log del loader. El propio `01:54` ya dice que el pane nuevo queda para F1: la contradicción interna se resuelve suavizando `00:45`, `01:53` y `02:12`.

### H-3 · [B] Identificador de API inventado: `usePluginI18n`
- Archivo: `01-superficie-ui-hermes.md:24` — «`ctx.i18n.register({ es, en })` + `usePluginI18n`».
- Comando: `grep -c "usePluginI18n" desktop-plugin-sdk.md` → `0`. El hook real es `useI18n` (SDK línea 2113); `ctx.i18n.register` sí existe (línea 2016) y `ctx.i18n.t` también (línea 524).
- Impacto: en un documento que se declara «contrato operativo», un identificador que no existe costaría tiempo en F1.
- Recomendación: sustituir por `useI18n` o marcar «por confirmar en el spike».

### H-4 · [B] Atribución de causa en NVENC no medida (conclusión correcta)
- Archivo: `00-inventario-medido.md:17` — «la GT 1030 no tiene unidad NVENC; el render real será libx264 por CPU».
- La evidencia citada (`ffmpeg -encoders`) sólo prueba que los encoders están **compilados**; no dice nada del hardware.
- Mi medición: `h264_nvenc` **falla al abrir** con `Cannot load nvEncodeAPI64.dll` y `The minimum required Nvidia driver for nvenc is 610.00 or newer`. El driver instalado es `32.0.15.8108`.
- Impacto: la conclusión operativa (`libx264`) queda **confirmada por prueba directa**; lo que no está probado es el motivo (silicio sin NVENC vs. driver por debajo del mínimo del build FFmpeg 9). El documento mezcla una inferencia con una medición.
- Recomendación: escribir «NVENC no utilizable en esta máquina (falla al abrir; el build exige driver ≥610.00 y el instalado es 32.0.15.8108) → libx264». Es un dato mejor y verificable.

### H-5 · [C] RAM libre: cifra sujeta a deriva y sin hora
- Doc: `12.9 GB libres`; medido ahora: `10,86 GB`. Total (23,93 GB) sí coincide.
- Corrección: anotar la hora exacta de la medición o quitar la cifra de «libres», que no es estable. La conclusión del delta («memoria no es el cuello de botella») se sostiene con 10,86 GB libres.

### H-6 · [C] Disco: cifras y porcentaje ambiguo
- Doc: `223 GB total · 193 usados · 31 libres (87%)`; medido ahora: `222,6 GB · 34,5 libres · 15,5% libre` (`df`: `223G 189G 35G 85%`).
- Total coincide; libres difieren en ~3,5 GB. Además «87%» no dice si es usado o libre (usado sería ~85%). La conclusión del delta («disco justo, limpiar derivados por job») se mantiene.

### H-7 · [C] `⌘K` es atajo de macOS; el host es Windows
- `01:11` cita «⌘K → Reload desktop plugins», copiado del SDK. En Windows el atajo del app será `Ctrl+K`. No afecta al gate; conviene decirlo para no confundir en F1.

### H-8 · [C] Licencia: es GPLv3, no «GPL» genérico
- Doc `00:39`: «Licencia del build: **GPL** (`--enable-gpl`, x264)».
- `ffmpeg -buildconf` incluye además `--enable-version3`, y `ffmpeg -L` dice «GNU General Public License … **version 3** … or any later version». Es GPLv3-or-later.
- Relevancia para apollo: empaquetar el binario arrastra GPLv3 (no GPLv2), que es más exigente. Llamarlo por ruta externa no redistribuye, como dice el documento. Nota extra: el binario vive en `hermes/tools/…`, es decir ya viene con Hermes; si el plugin lo invoca desde ahí, la obligación es de Hermes, no del plugin.

### H-9 · [C] El spike F1 ya arrancó antes de que el gate 0 tenga veredicto
- `find video-editor -printf` muestra: `00-fase0/*.md` 14:03, `PLAN-CONSOLIDADO.md` 14:05, y ya `spike/probe_gateway.py` 14:10, `spike/probe_ports.py` 14:11, `spike/fixtures/*` 14:12, `spike/logs/t1.err` 14:13, `spike/out/.staging/t1/out.mp4` 2.772.029 bytes 14:13.
- No es violación de alcance (todo dentro de `video-editor/`) y no lo audito aquí, pero el orden importa: el plan dice que F1 entra con «Gate 0 + permiso de experimento» (PLAN línea 113). Observación de proceso para Hermes.

---

## 3. Overclaims (resumen)

| # | Dónde | Qué se afirma | Qué se midió | Veredicto |
|---|---|---|---|---|
| O-1 | `01:10` | `padre-flow` llama `host.request` | 0 ocurrencias; usa `ctx.rest`/`ctx.socket` | Falso |
| O-2 | `00:45`, `01:53`, `02:12` | «los 4 cargan en la app» / «en producción local» / «ya está probada aquí» | archivos + compilación + loader en el bundle; runtime sin evidencia | No verificado |
| O-3 | `01:24` | `usePluginI18n` | no existe; es `useI18n` | Falso |
| O-4 | `00:17` | «la GT 1030 no tiene unidad NVENC» (como hecho) | la prueba citada no mide hardware; la mía falla por driver | Causa no medida (conclusión correcta) |
| O-5 | `00:39` | licencia «GPL» | GPLv3-or-later (`--enable-version3`) | Impreciso |

**No** son overclaim, y lo digo explícitamente porque era el riesgo principal: que FFmpeg cubre el MVP (filtros y encoders verificados uno a uno), que la RAM es 23,9 GB (no 8), que Chrome no está instalado, que Node/npm/Python/Git están en las versiones dichas, que el SDK existe con ese tamaño exacto y documenta `host.request`/`ctx.rest`/`ctx.storage`/las áreas de UI/`plugin_api.py`/hot reload, y que `padre-flow` demuestra el patrón `manifest.json {api: plugin_api.py}` + `ctx.rest`.

---

## 4. Faltantes para el gate 0 (según su propia definición, PLAN línea 177)

El gate 0 pide: contrato de plugin · entorno · medios · contexto autorizado · permisos definidos · extensión UI real verificada.

| Requisito | Estado según lo auditado |
|---|---|
| Contrato de plugin | **Cubierto** por `01` (tabla capacidad↔necesidad), con las correcciones H-1/H-3. |
| Entorno | **Cubierto y reproducido** por `00`. |
| Medios | **Definido por decisión, no medido**: sólo fixtures sintéticos (decisión 2). Aceptable, está declarado. |
| Contexto autorizado | **Cubierto**: `host.state.activeSessionId/cwd/profile` (SDK líneas 41-43). |
| Permisos definidos | **Parcial / insuficiente**: hay autorizaciones puntuales (spike, medios, ventana de recarga, disco, motor), pero no una matriz de permisos del sistema: qué procesos puede lanzar el worker, qué rutas puede leer/escribir, en qué puerto loopback escucha, retención y purga de derivados, tamaño máximo de entrada, y qué pasa con el kill-tree. El plan lo exige explícitamente. |
| Extensión UI real verificada | **Documentada y soportada; no verificada en runtime** (H-2). |

Faltan además dos cosas que el plan da por hechas y el material no cierra:
- No hay **línea base p95 del gateway** antes del render (el propio `00:50` lo difiere al spike: aceptable si el gate no lo exige).
- **0R** sigue abierto: el conteo 178/174/4 no está verificado por nadie en este material (`00:51` lo delega a rafael). Coherente con PLAN línea 110 (0R bloquea integración, no demos), pero no puede presentarse como resuelto.

---

## 5. Alcance: qué se tocó y qué no

- Documentos auditados: **intactos** (no escribí en `00-fase0/` ni en el plan). Sólo lectura.
- `hermes/config.yaml`: mtime **2026-11-06 20:58** → no tocado hoy.
- `hermes/desktop-plugins/`: mtimes **2, 3, 5 de noviembre** → no tocados hoy.
- `hermes/skills/`, `hermes/plugins/`: hay cambios de hoy, pero son de otra línea de trabajo (despliegue `tormen-skill`/BSK/JEV, `bsk-studio/corpus.roots`, `hermes-jev/jevkit`), no del editor; no hay ningún artefacto de VIDEO-EDITOR fuera de `fleet-workspace/video-editor/`.
- Vault: `wiki/log.md` modificado hoy 13:33, contenido sobre despliegue de `tormen-skill`/BSK/JEV — **no** de VIDEO-EDITOR. `raw/` sin escrituras detectadas de esta tarea.
- `fleet-workspace/video-editor/`: todo el trabajo (3 documentos, plan, spike). Nada fuera de esa carpeta atribuible al Padre por VIDEO-EDITOR.
- Gateway: no lo reinicié; no creé panes; no escribí en `desktop-plugins/`. Por eso H-2 queda como faltante y no como prueba en contra.

---

## 6. Condición para pasar el gate 0

El gate 0 pasa cuando se cumple **todo** esto y se puede re-auditar en una sola pasada:

1. **C1** — `01:10`: reemplazar «llama `host.request(...)`» por «llama `ctx.rest('/active')` y `ctx.socket('/events')` (líneas 284, 323, 412)», o citar el archivo/línea correcta. Verificable con `grep -c "host.request" padre-flow/plugin.js` = 0 y `grep -n "ctx.rest"` ≠ vacío.
2. **C2** — `00:45`, `01:53`, `02:12`: o se aporta evidencia de runtime (captura de Capabilities → Plugins con los 4, o línea del loader), o se rebaja el texto a «en disco y con código válido; carga en runtime pendiente». Verificable leyendo las tres líneas.
3. **C3** — `01:24`: `usePluginI18n` → `useI18n` (SDK línea 2113) o marcar como no verificado.
4. **C4** — `00:17`: causa de NVENC según medición (falla al abrir; driver mínimo 610.00 vs 32.0.15.8108), no según inferencia de silicio.
5. **C5** — `00:13` y `00:11`: refrescar disco y RAM con hora de medición, y decir si el 87% era usado o libre.
6. **C6** — `00:39`: «GPLv3-or-later (`--enable-gpl --enable-version3`)» y nota de que el binario vive en `hermes/tools/`.
7. **C7** — añadir a `02-deltas-y-decisiones.md` la **matriz de permisos** que el gate exige: procesos que el worker puede lanzar, rutas de lectura/escritura, puerto loopback y rango, retención/purga de derivados, tamaño máximo de entrada, política de kill-tree.
8. **C8** — declarar en `01` el estado real del gate: «CUMPLE CONDICIONADO — extensión documentada y soportada; verificación en runtime se cierra con el pane de F1», en vez de «CUMPLE por evidencia documental».

Con C1-C8 el veredicto pasa a **APROBADO (con observaciones C5-C7 no bloqueantes si C7 se acota como decisión de Tormen)**. Sin C2 y C7 no puede declararse el gate cerrado, porque son literalmente dos requisitos del propio gate.

---

## 7. Decisiones necesarias (Tormen)

1. **Semántica del gate 0**: ¿«extensión UI real verificada» se satisface con SDK documentado + plugins en disco + loader presente en la app, o exige un pane montado en runtime? El material se lee de las dos formas. Si vale lo primero, C2 se resuelve con redacción; si vale lo segundo, el gate **no** está cerrado y se cierra en F1.
2. **Orden F1 vs gate 0**: el spike ya empezó (14:10-14:13) antes de este veredicto. ¿Se acepta que F1 corra en paralelo o se congela hasta corregir C1-C8?
3. **Matriz de permisos (C7)**: ¿la define el Padre y la apruebas tú, o la fija el spike como resultado? Hoy no existe en el material y el gate la pide.
4. **ADR-001 (motor FFmpeg directo)**: sigue como propuesta. Mi auditoría confirma la premisa técnica (filtros, encoders, CPU, sin Chrome); la aceptación es tuya, no mía.
5. **Correcciones C1-C8**: ¿se devuelven al Padre para una pasada corta (recomendado, ~15 min de edición) o se aceptan como erratas y se anotan en el acta?
6. **0R**: confirmar que sigue en read-only y fuera de la ruta crítica del editor, como dice `02:13`.

---

## Anexo · Comandos ejecutados (reproducibles)

```bash
# hardware
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_OperatingSystem | Select-Object Caption,BuildNumber | Format-List'
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | Format-List'
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_ComputerSystem | Select-Object @{n="GB";e={[math]::Round($_.TotalPhysicalMemory/1GB,2)}} | Format-List'
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion | Format-List'
df -h /c
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_LogicalDisk | Where-Object DeviceID -eq "C:" | Select-Object Size,FreeSpace | Format-List'

# software
node -v; npm -v; python --version; git --version; cargo --version; ffmpeg -version | head -5; ffprobe -version | head -2; hermes --version

# motor
ffmpeg -hide_banner -filters | grep -E '^\s*[.TSC]+\s+(trim|concat|xfade|scale|crop|overlay|drawtext|subtitles|ass|afade|acrossfade|fade)\s'
ffmpeg -hide_banner -encoders | grep -E '(libx264|aac|libmp3lame|libopus|h264_nvenc|hevc_nvenc)'
ffmpeg -hide_banner -f lavfi -i testsrc2=size=320x240:rate=30:duration=1 -c:v h264_nvenc -f null -   # falla: driver
ffmpeg -hide_banner -buildconf | grep -E 'enable-gpl|enable-version3|libx264|libass'
ffmpeg -hide_banner -L | head -8

# plugins / SDK
ls -1 "$LOCALAPPDATA/hermes/plugins" | wc -l
sed -n '566,584p' "$LOCALAPPDATA/hermes/config.yaml"
stat -c '%s bytes %y' "$LOCALAPPDATA/hermes/hermes-agent/website/docs/developer-guide/desktop-plugin-sdk.md"
grep -c "usePluginI18n" "$LOCALAPPDATA/hermes/hermes-agent/website/docs/developer-guide/desktop-plugin-sdk.md"
grep -n "host.request\|ctx.rest\|ctx.socket" "$LOCALAPPDATA/hermes/desktop-plugins/padre-flow/plugin.js"
grep -c "host.request" "$LOCALAPPDATA/hermes/desktop-plugins/padre-flow/plugin.js"
cat "$LOCALAPPDATA/hermes/plugins/padre-flow/dashboard/manifest.json"
node --check <copia de cada plugin.js renombrada a .mjs>
grep -ci "plugin" "$LOCALAPPDATA/hermes/logs/desktop.log"

# alcance
find "$LOCALAPPDATA/hermes/fleet-workspace/video-editor" -type f -printf '%TY-%Tm-%Td %TH:%TM %8s %p\n' | sort
find "$LOCALAPPDATA/hermes" -maxdepth 3 -type f -newermt "2026-11-08 00:00" | grep -vE '/(logs|cache|sessions)/'
```

---

*Dike · 2026-11-08 · auditoría read-only. No modifiqué los documentos auditados, no reinicié el gateway, no escribí en `desktop-plugins/`, skills, config ni vault. Este veredicto alimenta la decisión de Hermes/Tormen; no la sustituye.*
