# CONTRATO · Servicio del editor de vídeo (loopback)

Versión: **0.3.0**. Verificado por el Padre el 2026-11-08 con `scripts/e2e_http_check.py` (ver §8);
la superficie v3 (biblioteca, medios, miniaturas, waveform, historial) se verificó contra el
servicio vivo en 8770 (ver §9).
Este documento manda sobre la prosa de cualquier informe: los endpoints y campos se leyeron del código (`service/app.py`).

## 1. Transporte

- Base: `http://127.0.0.1:<puerto>` (por defecto **8770** con `start_service.py`; el spike usaba 8765).
- Solo loopback. El servidor **exige** `Host` (`127.0.0.1:<puerto>`/`localhost:<puerto>`; sin `Host` → 403) y valida `Origin` cuando viene (anti DNS-rebinding/CSRF). `Origin: null` se acepta para el pane `file://`; ver §7 como riesgo pendiente de decisión.
- Sin autenticación de red: no exponer el puerto a LAN.
- JSON UTF-8 en peticiones y respuestas (`Content-Type: application/json`).
- Errores: `{"error": "<texto>", ...}`. `409` incluye `current_revision`.

## 2. Arranque

```bash
cd C:/Users/EgtYP/AppData/Local/hermes/fleet-workspace/video-editor/core
python start_service.py --data-root C:/.../core/data --media-root C:/.../medios --port 8770
```

- `start_service.py` arranca **desacoplado** (DETACHED_PROCESS): sobrevive al cierre del proceso que lo lanzó. Log: `core/logs/service.stdout.log`.
- `--stop` pide `/admin/stop` (si admin está habilitado; `--no-admin` lo desactiva).
- El servicio carga `VIDEO_EDITOR_TOOLS` o `C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin`.

## 3. Endpoints

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| GET | `/health` | — | `{ok, service, engine, ffmpeg, ffmpegVersion, dataRoot, mediaRoot, queue, recovered, presets, startedAt}` |
| GET | `/grants` | — | `{mediaRoot}` — carpeta con la que se concedió el acceso |
| GET | `/projects?session=&cwd=&query=` | — | `{projects:[{projectId,title,revision,scenes,assets,updatedAt,sessionId,cwd}], mediaRoot, query}` — `query` filtra por título, sin distinguir mayúsculas ni acentos |
| POST | `/projects` | `{title?, session_id?, cwd?}` | `201` con el payload de proyecto (revisión 0) |
| GET | `/projects/<projectId>` | — | `{projectId, revision, docHash, updatedAt, project:<documento>, ui:<adaptador UI>, media:[{id,path,kind,bytes,sha256,exists,previewUrl}]}` |
| PUT | `/projects/<projectId>` | `{revision, draft}` (o `project`) | `200` payload nuevo; **`409 {current_revision}`** si la revisión no es la vigente; `400 {errors:[...]}` si el documento no valida |
| DELETE | `/projects/<projectId>?confirm=1` | `{confirm:true}` opcional | `200 {deleted, projectId, jobsDeleted, filesPurged[]}`; `400` sin confirmación; `404` desconocido; `409` si hay un export en curso. Borra proyecto, jobs, eventos y ficheros derivados |
| POST | `/projects/<projectId>/duplicate` | — | `201` con el payload del proyecto nuevo: otro `projectId`, revisión 0, título «(copia)», assets y escenas copiados con ids nuevos |
| POST | `/projects/<projectId>/media` | `{path}` (relativo a `mediaRoot` o absoluto dentro de ella) | `201` payload con el asset y la escena creados; `400` ruta fuera de la raíz / formato no permitido / archivo inválido |
| DELETE | `/projects/<projectId>/media/<assetId>?revision=` | `{revision?}` opcional | `200` payload nuevo + `removedAsset` + `removedScenes[]`; `404` asset desconocido; **`409 {current_revision}`** con revisión vieja |
| GET | `/media/<projectId>/<assetId>` | — | bytes del original con **`Range`/206** (para el `<video>` del pane) |
| GET | `/thumbnails/<projectId>/<assetId>?t=<seg>` | — | JPEG `320×-2` del fotograma `t` (def. `0`), `Content-Type: image/jpeg`, `Cache-Control: public, max-age=300`; caché en `<data>/cache/thumbs/<sha256>_<t>.jpg` |
| GET | `/waveform/<projectId>/<assetId>` | — | `{projectId, assetId, sha256, buckets:200, duration, peaks:[0..1]×200}`; caché en `<data>/cache/wave/<sha256>.json` |
| GET | `/exports?project=<id>&limit=20` | — | `{projectId, count, jobs:[{jobId, projectId, revision, preset, state, stage, progress, error, outputName, outputUrl, outputBytes, createdAt, finishedAt}]}` ordenados del más reciente al más viejo; `404` si el proyecto no existe |
| POST | `/projects/<projectId>/export` | `{preset?, captions?}` · `preset` único: `mp4-720p30` | `202 {jobId, deduped}`; `deduped:true` = mismo documento, se devuelve el job vigente |
| GET | `/jobs` | — | `{jobs:[...]}` (los más recientes, `limit` opcional) |
| GET | `/jobs/<jobId>` | — | `{jobId, state, stage, progress, message, error, workerPid, artifacts, outputName, revision, preset, engineTag, dedupeKey, createdAt, startedAt, finishedAt, eta_s}` |
| POST | `/jobs/<jobId>/cancel` | — | job actualizado; `cancelRequested:true`; si estaba `queued` pasa a `cancelled` |
| GET | `/jobs/<jobId>/output` | — | MP4 con **`Range`/206**; `409` si aún no hay salida |
| GET | `/events?since=<seq>&timeout=<s>` | — | `{events:[...], lastSeq}` (long-poll; `timeout=0` no bloquea) |
| POST | `/admin/stop` | — | `{stopping:true}` si admin habilitado; `403` si no |

### Estados de job

`queued → running → succeeded | failed | cancelled | interrupted`

- `interrupted`: el servicio cayó con el job en curso; al arrancar marca los que quedaron `running`
  (`reap_interrupted`) y el Job Object de Windows mata el ffmpeg huérfano.
- `stage`: `probing | rendering | done | failed` (progreso en `progress` 0–100).

## 4. Documento de proyecto

- Fuente de verdad: `project` en `GET /projects/<id>` (el `ui` es un adaptador para pintar, no para guardar).
- Campos clave: `projectId`, `revision`, `engineTag`, `fps` racional, `width`, `height`, `title`, `sessionId`, `cwd`, `assets[]`, `scenes[]`, `createdAt`, `updatedAt`.
- `scenes[]`: `{id, source:{path, sha256?, kind}, in, out, transition?, text[], audio?}`.
- Escritura solo por `PUT` con `revision` vigente (control optimista). Nunca reescribir la revisión de otro.
- Export usa un **snapshot inmutable** del documento; preview y export parten del mismo documento.
- **Texto con estilo**: cada item puede traer `size` (12–120), `color` (#RRGGBB), `border`/`borderColor` (0–10), `shadow` (0–10) y `animation {in,out}` con `none|fade|slide-up|slide-down`. Sin esos campos se usan defaults y el grafo antiguo no cambia.
- **Filtros por escena**: `filters {brightness −1..1, contrast 0..2, saturation 0..3, grayscale, vignette, blur 0..20}`; se aplican antes de `scale/pad`.
- **Logo**: `logo {assetId de imagen, position (9 anclas), opacity 0..1, scale 0.05..0.5}`; se compone después del texto.
- **Eventos de sonido**: `audioEvents[]` (máx 50) `{id, assetId (audio), at (s), volume 0-100, fadeIn?, fadeOut?}`; se mezclan tras la cama de escenas y antes de la música, con `adelay`; sin eventos el grafo no cambia.
- **Generación**: `POST /projects/<id>/generate` `{kind: image|music, prompt 1-500, provider: local|http, duration 1-120 (música), options?}` → **202** con `{jobId}`; el job corre fuera del hilo HTTP y al terminar registra el asset en `generated/<projectId>/` con `rights.status="generated"` y notas de proveedor+prompt. `provider:"http"` exige `VE_PROVIDER_IMAGE_URL`/`VE_PROVIDER_MUSIC_URL` (+`_KEY`); si no está configurado → **400**, nunca fallback a un servicio de pago.
- **CLI de chat**: `python scripts/ve_generate.py --project <id> --kind image --prompt "…" --use scene` (también `--use music|logo|sfx --at <s>`); genera, espera el job y aplica al proyecto en un paso. `/health` publica `providers` y `providerModes`.
- **Presets de export**: `mp4-720p30` (1280×720), `mp4-1080p30` (1920×1080, experimental), `mp4-720p30-vertical` (720×1280), `mp4-720p30-square` (720×720). El preset manda el tamaño final: `scale + crop` centrado si el lienzo no coincide; el proyecto define el lienzo de origen.
- **Ken Burns**: `scene.kenBurns {zoom 1.0–1.5, pan none|left|right|up|down}` solo para escenas de imagen; en vídeo se rechaza con error claro.
- **Velocidad**: `scene.speed 0.5–2.0`; la duración efectiva es `span / speed` y el timeline/transiciones la usan automáticamente (`setpts`/`atempo`).
- **Transiciones**: `scene.transition` acepta `none` o `(fade|slideleft|slideright|wipeleft|wiperight|circleopen|zoomin)-<segundos 0.1–2.0>`. La transición es la **entrada** de la escena; la escena 0 nunca solapa; la duración final = suma de escenas − solapes. Es **solo visual**: el audio sigue concatenado sin `acrossfade`.
- `music?`: `{assetId, volume 0-100, fadeIn?, fadeOut?, loop?, in?, out?, ducking?}` — pista de fondo mezclada con el audio de escenas (`amix`), recortada a la duración total, con `afade` de entrada/salida. `ducking:true` baja la música con `sidechaincompress`.
- `audio.normalize:true` aplica `loudnorm=I=-16:TP=-1.5:LRA=11` al audio final.
- Assets de audio (`kind:"audio"`; extensiones `.mp3 .wav .m4a .aac .ogg .oga .flac .opus`) no crean escena salvo `{"scene": true}` en `POST /media`.

## 5. Medios y límites

- `mediaRoot` es la única raíz legible. Se rechazan rutas absolutas fuera de ella, `..`, junctions que escapan y extensiones no permitidas.
- Extensiones de vídeo/audio/imagen de la allowlist del worker; se valida con `ffprobe` antes de encolar.
- Límites: tamaño de entrada por job y duración total (ver `project.MAX_*`); 720p30 como único preset del MVP.
- Un job concurrente. El worker nunca corre dentro del hilo HTTP.

## 6. Dedupe, idempotencia y conflicto

- `export` calcula un `dedupeKey` con el hash del documento + preset + captions. Si ya existe un job vigente con esa clave, devuelve `{deduped:true, jobId}` en lugar de crear otro.
- Para forzar un job nuevo hay que cambiar el documento (nueva `revision`).
- `PUT` con revisión vieja → `409` con `current_revision` para que la UI abra el diálogo de conflicto.

## 7. Seguridad operativa

- Host/Origin validados; sin CORS abierto a orígenes externos.
- El worker lanza solo `ffmpeg.exe`/`ffprobe.exe` por ruta absoluta, con allowlist de flags y sin `shell=True`; entorno filtrado (sin secretos).
- Job Objects: límites de memoria y kill-tree del proceso ffmpeg.
- Promoción atómica: el MP4 se valida en staging y se renombra; nunca se publica una salida parcial.
- En fallo o cancelación se purgan derivados del job (`staging/`, textos, `tmp/`); el log redactado se conserva.
- `limits_enforced` es `true` solo si el Job Object se creó **y** el proceso se asignó a él; si no, el cancel cae a `taskkill /T /F`.

## 8. Verificación reproducible (Padre, 2026-11-08)

```
python scripts/e2e_http_check.py --base http://127.0.0.1:8770 --media clipA.mp4 clipB.mp4 vfr_mix.mp4
→ ok: True | failures: []
   proyecto 201 (rev 3, 3 escenas) · stale PUT 409 (current 3)
   export 202 no-deduped → job succeeded → MP4 h264 1280×720 30/1, 25.566667 s, 8.310.551 bytes
   touch rev 4 → export 202 → cancel 200 → job cancelled (progress 1.0), ffmpeg huérfanos: NINGUNO
```

Reporte JSON completo: `core/logs/e2e-http-report.json`.
