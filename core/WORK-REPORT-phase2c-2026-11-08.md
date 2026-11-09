# Fase 2C — Presets, Ken Burns y velocidad (cerrada y verificada)

Fecha: 2026-11-08. Implementación por Hephaestus; el subagente agotó iteraciones **sin correr la suite**, así que el Padre completó schema, tests, contrato y verificación.

## Qué entró

- **Presets** (`service/worker.py`, `service/app.py`): `mp4-720p30` (1280×720), `mp4-1080p30` (1920×1080, **experimental**), `mp4-720p30-vertical` (720×1280), `mp4-720p30-square` (720×720). El preset manda el tamaño final: `scale=…:force_original_aspect_ratio=increase,crop=W:H` cuando el lienzo no coincide; ruta histórica con `pad` intacta. `/health` publica `presets`, `presetSizes` y `experimentalPresets`.
- **Ken Burns** (`project.ken_burns`, `worker._ken_burns_filter`): `scene.kenBurns {zoom 1.0–1.5, pan none|left|right|up|down}`; solo imágenes, rechazo explícito en vídeo (`"only applies to image scenes"`).
- **Velocidad**: `scene.speed 0.5–2.0`; `scene_duration = span / speed` y el timeline/transiciones usan la duración ajustada (`setpts`/`atempo`).
- **Schema**: `speed`, `kenBurns` y `filters` documentados en `schema/project.schema.json`.
- **Contrato**: secciones de presets, Ken Burns y velocidad en `CONTRATO.md`.
- **Versión**: servicio **0.3.3** (vivo en 8770).

## Verificación del Padre (evidencia real)

- `python -m py_compile project.py service/worker.py service/app.py` → OK.
- `python -m unittest discover -s tests` → **348 tests OK (skipped=2)**.
- `tests/test_phase2c.py` (11 casos): catálogo y 400 de preset desconocido, `_fit_filters` (pad nativo vs crop), validación Ken Burns (imagen/vídeo/zoom/pan), matemática de duración con `speed`.
- Corrección de contrato: `test_worker` esperaba 320×240; con presets el tamaño lo manda `mp4-720p30` → se actualizó a 1280×720 con comentario.
- E2E real (`core/scripts/e2e_phase2c_check.py`): clip 8 s a **speed 2.0** (4 s) + imagen 3 s con **Ken Burns** + transición `slideleft-0.5` → salida **6.5 s** exacta, **720×1280**, h264+aac. JSON en `docs/qa/phase2c-e2e.json` → `verdict: PASS`.
- Servicio vivo reiniciado a **0.3.3**: `/health` devuelve 4 presets y **7 transiciones**.

## Límites declarados

- 1080p sigue **experimental**: falta medir tiempo/RSS en esta máquina antes de ofrecerlo como opción normal.
- El proyecto sigue **sin repo git**: cambios sin versionar.
