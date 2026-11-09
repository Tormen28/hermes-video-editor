# Work Report — Backend v3 (biblioteca, medios, miniaturas, waveform, exports)

- **Origen:** Hermes Padre → **Destino:** Hermes Padre / `dike`
- **Fecha:** 2026-11-08
- **Objetivo:** añadir al servicio (`core/service/app.py`, `project.py`, `journal.py`) las 5 capacidades que la UI v3 necesita, sin romper las 232 pruebas previas.
- **Estado:** entrega completa (1–5), tests verdes, verificado contra servicio vivo.

## Qué cambió

1. **Biblioteca de proyectos**
   - `DELETE /projects/<id>?confirm=1` (o body `{confirm:true}`): borra proyecto, jobs, eventos y ficheros derivados; `400` sin confirmación, `404` desconocido, `409` si hay export en curso.
   - `POST /projects/<id>/duplicate`: nuevo `projectId`, revisión 0, título «(copia)», assets/escenas con ids nuevos.
   - `GET /projects?query=`: filtro por título, insensible a mayúsculas y acentos.
2. **Gestión de medios**: `DELETE /projects/<id>/media/<assetId>?revision=` — quita el asset y las escenas que lo referencian, guarda revisión nueva (optimista: `409 {current_revision}`), `404` si el asset no existe.
3. **Miniaturas**: `GET /thumbnails/<projectId>/<assetId>?t=<seg>` — JPEG 320px de ancho con ffmpeg (`-ss t -frames:v 1 -vf scale=320:-2`), `Content-Type: image/jpeg`, caché `<data>/cache/thumbs/<sha256>_<t>.jpg` con regeneración si falta.
4. **Waveform**: `GET /waveform/<projectId>/<assetId>` — ffmpeg decodifica a PCM s16le mono 8 kHz por stdout; RMS/max por bucket en Python puro; `{peaks:[…200], buckets:200, duration}`, caché `<data>/cache/wave/<sha256>.json`.
5. **Historial de exports**: `GET /exports?project=<id>&limit=20` — jobs del proyecto ordenados desc con estado, bytes, error y `outputUrl`.

Reglas respetadas: solo stdlib, loopback, Host/Origin preservados, errores JSON, revisiones optimistas en cada mutación, purga de caché al borrar proyecto, sin tocar config/gateway/plugins.

## Cómo se probó

- `python -m unittest discover -s tests` → **Ran 259 tests in 51.045s — OK (skipped=2)**.
- Tests nuevos en `core/tests/test_service_library.py` (+ soporte en `_support.py`): borrar proyecto (jobs y caché desaparecen), duplicar (ids y assets), quitar medio (escenas afectadas + 404), thumbnail (200, content-type, cache hit), waveform (200 buckets y duration), exports (filtrado y `404`).
- Verificación contra servicio vivo con data-root `core/data-verify` (jobs/out/cache reales) y `curl` sobre cada endpoint nuevo.

## Qué NO se probó / limitaciones

- Thumbnails y waveform requieren `ffmpeg` en PATH; si falta, el endpoint devuelve error JSON (no hay fallback sintético).
- Waveform es mono 8 kHz: suficiente para dibujar, no para análisis de audio fino.
- No se probó concurrencia de dos borrados simultáneos del mismo proyecto.
- Sin push, merge ni despliegue: la rama y el servicio vivo quedan para revisión de `dike`.

## Evidencia

- `core/CONTRATO.md` (tabla de endpoints v3, líneas 33–44), `core/README.md` actualizado.
- `core/tests/test_service_library.py`, `core/data-verify/` (jobs/out/cache de la verificación viva).
