# SPIKE F1 · Reporte consolidado (evidencia verificada)

Fecha: 2026-11-08, 14:45 Caracas.
**Autoría de este reporte:** Hermes Padre, consolidado desde los artefactos que dejó Hephaestus en esta carpeta (él agotó su límite de iteraciones sin escribir el reporte). Todo lo afirmado abajo fue verificado por el Padre con comandos; lo no verificado está marcado.

## Qué se construyó y dónde

| Artefacto | Ruta | Estado |
|---|---|---|
| Servicio de jobs (HTTP loopback) | `spike/service.py` | Funciona: `/health`, POST `/jobs`, GET `/jobs/{id}`, progreso, cancelación, journal SQLite (`jobs.sqlite3`), staging + rename atómico |
| Cliente de pruebas | `spike/client.py` | Usado por `test_demo.py` / `test_cancel.py` |
| Fixtures sintéticos | `spike/fixtures/` (`make_fixtures.sh`, `SHA256SUMS.txt`) | 2 clips 720p30 8 s (testsrc2 / smptebars) + logo PNG con texto |
| Pane de UI | `desktop-plugins/editor-video-spike/plugin.js` (instalado) | Montado en la app; `fetch` al servicio OK |
| Pruebas | `spike/test_demo.py`, `spike/test_cancel.py`, `spike/logs/*` | Ejecutadas con salidas JSON |

## Evidencia de runtime del pane (lo que el gate 0 exigía)

- `netstat -ano`: **`Hermes.exe` PID 12832** con dos conexiones `ESTABLISHED` contra `127.0.0.1:8765` (puertos 56895 y 64561).
- `spike/logs/service.access.log`: `GET /probe → 200` y `POST /probe → 200` a las **14:19:56–14:19:57**, y `GET /probe → 200` a las 14:20:17. Las probes las emite el JS del pane.
- **Conclusión:** un pane NUEVO se monta en la app y puede hablar con un servicio local por `fetch`. La incógnita CSP/CORS queda cerrada a favor.

## Render real (MP4 producido)

Verificado con `ffprobe` sobre `spike/out/j16f22b2a29.mp4`:

- `h264`, **1280×720**, `30/1` fps, **15.0 s**, **2.772.029 bytes**, audio `aac` mono.
- Codificación por CPU (`libx264`): NVENC no es utilizable en esta máquina (falla al abrir; driver 32.0.15.8108 < mínimo 610.00 del build).
- Job `j16f22b2a29`: estado `succeeded`, `exit_code 0`, `progress 100`, **wall 1.36 s** (fixture simple, preset rápido; no representa material real).

## Cancelación (prueba destructiva controlada)

`spike/logs/test_cancel.json`:

- Job `j865eca6992` con `ffmpeg` PID 13860 en curso; `progress_at_cancel` 8.2 %.
- `cancel_latency_s`: **0.52 s**; `final_state`: **cancelled**; `exit_code 1`.
- Verificación posterior del Padre: `tasklist | grep -i ffmpeg` → **NINGUNO** (cero huérfanos). El output parcial no se promovió (staging no llegó a `out/`).

## Latencia del gateway durante el render

`spike/logs/test_demo.json` (sondeo HTTP al gateway vivo):

| Fase | n | p50 | p95 | máx |
|---|---|---|---|---|
| Antes | 60 | 1.65 ms | 4.60 ms | 8.7 ms |
| Durante | 32 | 2.59 ms | **6.49 ms** | 17.8 ms |
| Después | 60 | 1.64 ms | 1.94 ms | 2.4 ms |

Lectura honesta: +41 % relativo en p95 (de 4.6 a 6.5 ms; +1.9 ms absolutos). Son valores sub-10 ms y la fase «después» queda más baja que «antes», lo que indica deriva/ruido. **No es concluyente**: el método de baseline debe repetirse con ventanas más largas y varias corridas antes de aceptar el umbral del 20 % del plan.

## Lo que el spike NO probó (pendiente, no ocultar)

1. **VFR**: los fixtures son CFR 30/30 (testsrc2/smptebars). No hay clip VFR real probado; el plan lo exige en F1.3.
2. **Selección de archivos locales** desde el pane (dialog/attachment provider): sin probar.
3. **Preview `<video>` embebido** en el pane con URL Range: el servicio sirve el MP4, pero no se verificó el reproductor dentro del pane.
4. **`plugin_api.py`** (backend dentro del gateway): no probado — requiere que el plugin esté en `plugins.enabled` y recarga del gateway, prohibida sin ventana aprobada.
5. **Títulos/captions con acentos en el render final**: el logo usa `drawtext` con «SPIKE F1»; no se verificó á/é/í/ó/ú/ü/ñ en el MP4.
6. **Transiciones xfade**: el pipeline de demo no incluyó xfade en el corte entre escenas (el plan lo pide; verificar en F1.3).

## Servicio vivo y limpieza

- `python.exe` PID **23428** sigue escuchando en `127.0.0.1:8765` (necesario para que el pane montado no falle). Para detenerlo: `taskkill /PID 23428 /F`.
- Derivados: `spike/out/.staging/` conserva restos de pruebas; `spike/jobs.sqlite3*` es el journal. Limpiar staging al cerrar el spike, conservando `out/j16f22b2a29.mp4` como evidencia.
- Nada de esto toca `config.yaml` ni `~/.hermes/plugins/`.

## Actualización 14:55 (reportes completos de los subagentes + verificación del Padre)

- **Pane**: el payload capturado por el servicio (reporte de Hephaestus) dice `stage=pane_mounted`, `origin=file://`, UA `Hermes/0.0.0 Chrome/152.0.7977.167 Electron/44.9.3`; el `access.log` confirma los `POST /probe 200`. El body no quedó persistido en disco.
- **Captura del pane**: `C:/Users/EgtYP/AppData/Local/hermes/profiles/hephaestus/cache/images/computer_use_dbc42a1b57ac43d4b2e16659518b4df6.png`.
- **CSP/CORS**: `fetch` desde el renderer (origin `file://`) a `http://127.0.0.1:8765/health` → **HTTP 200 en 165 ms**. `plugin_api.py` **no es necesario** para el MVP; servicio en loopback basta.
- **Dedupe**: dos `POST /jobs` con `dedupe_key='kanban-42'` → mismo id. Confirmado en `jobs.sqlite3`: job `jf2aefa6cc4` con `dedupe_key=kanban-42`.
- **Crash + reaper**: servicio matado con job en curso → `ffmpeg` PID 19724 huérfano; al relanzar, el reaper lo mata y marca el job `je1e5a3054f` como **interrupted** (8.2 %). `tasklist` final sin ffmpeg. Confirmado en SQLite.
- **Recursos del render**: pared 1.359 s; CPU ffmpeg 8.828 s (≈10.3× tiempo real); RSS pico muestreado 435.8 MB (ffmpeg `maxrss` 498.3 MiB). Cadena real: scale + drawtext + overlay + xfade + acrossfade.
- **Pendiente real tras esta actualización**: pulsar «Render demo» dentro del pane (captura de progreso en la UI), VFR real, preview `<video>` embebido y acentos/xfade en el render final.

## F1-b · Cierre de huecos (verificado por el Padre, 15:05)

Verificación fresca ejecutada por el Padre sobre los artefactos; no se aceptó el self-report del subagente.

### P1 · Preview `<video>` en el pane — CERRADO

El pane montado en la app reprodujo el MP4 servido por HTTP con Range. Evidencia en `plugin_probes` (SQLite, 7 filas):

- `range_probe`: `status 206`, `contentRange "bytes 0-65535/8884986"`, `acceptRanges "bytes"`, `contentType "video/mp4"`.
- `preview_metadata`: `duration 8`, `videoWidth 1280`, `videoHeight 720`, `readyState 4`, `networkState 1`, `mode "url"`, `src http://127.0.0.1:8765/media/clipA.mp4`.
- `preview_canplay`: `readyState 4`, `duration 8`, `mode "url"`.

**CSP no bloquea media** en el renderer (origin `file://`): el `<video>` con URL directa reproduce. El fallback fetch+blob está implementado pero no se ejercitó (limitación declarada). Captura: `C:/Users/EgtYP/AppData/Local/hermes/profiles/hephaestus/cache/images/computer_use_92863f7261ef4104983760bb00c5c190.png` (pane con vídeo en 0:03/0:08).

### P3 · VFR real — HECHO

- Fixture `spike/fixtures/vfr_mix.mp4`: concat copy de 30 fps + 24 fps. `ffprobe`: `r_frame_rate 30/1`, `avg_frame_rate 5040/143`, 336 frames, 9.533 s; deltas de pts 0.0301 / 0.0333 s (irregulares). JSON: `spike/logs/f1b/vfr.json`.
- Cortes: `-ss` con `-c copy` → 3.021 s (atado a keyframe); re-encode → 3.000 s / 89 frames (preciso).
- Proxy CFR: `fps=30,setpts=N/30/TB,-fps_mode cfr` → avg 30/1 = r 30/1, 288 frames, 9.6 s; mapeo verificado por PSNR (`average 41.202`, `spike/logs/f1b/psnr_mapping.txt`).

### P4 · Render final con acentos + xfade — HECHO

- Job `jbf18c68465` (`kind "final"`): `succeeded`, pared 1.359 s, **2.468.023 bytes**, `ffprobe`: h264 1280×720, `avg_frame_rate 30/1`, **300 frames**, **10.000 s**, aac.
- La duración 10 s = 4+4+4 s menos dos `xfade` de 1 s → **ambos xfade aplicados**.
- Textos por `textfile` UTF-8: «Escena áéíóúüñ ÁÉÍÓÚÑ ¿¡qué pasa?»; subtítulos `.ass` con acentos; `xfade=fade` + `xfade=slideleft`; `acrossfade` de audio.
- Verificación visual sobre frame t=1.0: glifos correctos, sin cajas. Frames: `spike/logs/f1b/finaljob_t*.png`. Artefacto: `spike/out/jbf18c68465.mp4`.

### P6 · Latencia del gateway (n=200, 3 corridas) — MEDIDO, NO CONCLUYENTE

| Corrida | p95 antes | p95 durante | Δp95 |
|---|---|---|---|
| 1 | 2.25 ms | 6.41 ms | **+184.9 %** |
| 2 | 2.48 ms | 3.59 ms | +44.8 % |
| 3 | 4.03 ms | 3.61 ms | −10.4 % |

Veredicto honesto: en valores absolutos el impacto es despreciable (p95 siempre < 7 ms), pero **el umbral relativo del 20 % no se cumple de forma estable**. El método (latencia del listener HTTP, no turnos LLM) tiene ruido alto con baseline de 2–4 ms. Recomendación: sustituir el criterio relativo por un **presupuesto absoluto** (p. ej. p95 ≤ 15 ms y máx ≤ 100 ms con 1 job) o medir con carga sintética sostenida; decisión para Tormen/Gate 2.

### P2 y P5 — ÚNICOS PENDIENTES (2 clics de UI)

1. **P2 (grant de carpeta)**: en la app, pane «Editor de vídeo · spike F1» → «Elegir carpeta» → conceder `C:\Users\EgtYP\Videos\hermes-spike-fixtures` → seleccionar un clip → `POST /assets`. El permiso `ctx.files` prohíbe conceder carpetas dentro de los datos de Hermes; por eso el fixture externo vive en `Videos`.
2. **P5 (render desde el pane)**: pulsar «Render demo» o «Render final» dentro del pane y capturar el progreso (la barra `role=progressbar` ya emite probes cada 25 %).

Ninguno de los dos se puede completar sin interacción en la ventana; quedan para la sesión de verificación con Tormen tras el reinicio.

## Correcciones tras auditoría de Dike (18:45)

- **El artefacto F1-b existe**: `spike/out/jbf18c68465.mp4`, 2 468 023 B, 10.0 s (verificado por el Padre). La afirmación de la auditoría «NO EXISTE» no se reproduce.
- **P5 quedó cerrado**: `plugin_probes` filas 8–14 muestran `render_submitted → render_progress → render_succeeded` desde el pane (`jee6bc81dd7`, 1.5 s, 2 772 029 B). P2 (grant de carpeta) sigue pendiente de clic.
- PSNR: el mapeo es correcto (medición independiente 40.86/40.58/43.27 dB); falta anclar el comando exacto en el reporte (pendiente menor).

## Incidencia 18:21 · «TypeError: Failed to fetch» en el pane

- **Síntoma:** el pane montado mostró conexión fallida (2059 ms) y preview fallido.
- **Causa raíz:** el servicio del spike **no estaba corriendo**: murió junto con el árbol de procesos del subagente que lo lanzó. El pane no tiene culpa: `netstat :8765` vacío.
- **Fix:** arranque desacoplado con `spike/start_service.py` (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, log a `logs/service.stdout.log`). Verificado: `/health` 200 y `GET /media/clipA.mp4` con `Range` → **206**, 65536 bytes.
- **Lección para el núcleo:** el servicio de producción (`core/service/app.py`) necesita el mismo arranque desacoplado y una prueba de «mata al padre y sobrevive». Pasado a Hephaestus en la tarea de F2.
- **Para el usuario:** pulsar «Probar /health» en el pane; si el preview sigue en error, recargar plugins (Ctrl+K) y volver a abrir el pane.

## Reproducción

```bash
cd C:/Users/EgtYP/AppData/Local/hermes/fleet-workspace/video-editor/spike
bash make_fixtures.sh
python service.py &            # ventana 1
python test_demo.py            # escribe logs/test_demo.json
python test_cancel.py          # escribe logs/test_cancel.json
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate -of default=noprint_wrappers=1 out/j16f22b2a29.mp4
```
