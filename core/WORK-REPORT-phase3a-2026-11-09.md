# Fase 3A — SFX y generación desde el chat (cerrada y verificada)

Fecha: 2026-11-09. Implementación por Hephaestus (parcial, sin probar); **el Padre completó ruta, health, correcciones, tests, CLI y verificación**.

## Qué entró

- **`audioEvents[]`** (máx 50): `{id, assetId (audio), at, volume, fadeIn?, fadeOut?}`. Mezcla con `adelay` después de las escenas y antes de la música; sin eventos el grafo es idéntico.
- **Generación**: `POST /projects/<id>/generate` → **202** `{jobId}`; job en hilo aparte (`generate`), cancelable, progreso; registra asset en `media/generated/<projectId>/` con `rights.status="generated"` y notas `provider+prompt+fecha`.
- **Proveedor local** (sin red): imagen PNG 1280×720 con el prompt dibujado; música WAV 48 kHz sintética de `duration`.
- **Proveedor HTTP genérico**: `VE_PROVIDER_IMAGE_URL` / `VE_PROVIDER_MUSIC_URL` (+`_KEY`); acepta binario o `{path|url|base64}`; sin URL → 400, sin fallback silencioso.
- **`/health`**: publica `providers` y `providerModes` (local siempre; http según config).
- **CLI de chat** `core/scripts/ve_generate.py`: genera, espera y aplica (`--use scene|music|logo|sfx --at`), salida JSON.
- **Servicio 0.3.4** vivo en 8770.

## Verificación del Padre (evidencia real)

- `py_compile` OK en `project.py`, `worker.py`, `app.py`, `journal.py`, `generate.py`.
- **359 tests OK (skipped=2)**.
- `tests/test_phase3a.py` (11 casos): validación de eventos, índices de entrada, `adelay`/`[asfx]`, grafo sin eventos intacto.
- E2E real (`scripts/e2e_phase3a_check.py`, `docs/qa/phase3a-e2e.json`): genera **imagen** y **música** locales → ambas `succeeded`; inserta imagen como escena, fija música, añade SFX en t=1 → export **succeeded**, MP4 **1280×720**, **11 s**, **AAC** → `PASS`.
- Bugs encontrados y corregidos: orden de `is_within` (dos sitios), `duration` exigida a imágenes, y el e2e que hacía PUT con revisión vieja tras insertar la escena.

## CLI probado contra el servicio vivo

```
ve_generate.py --project prj_1173… --kind image --prompt "intro azul con texto" --use scene
  → asset md_5094039a, revisión 2
ve_generate.py --project prj_1173… --kind music --prompt "cama suave épica" --duration 6 --use music
  → md_10435776, revisión 4
ve_generate.py --project prj_1173… --kind music --prompt "whoosh corto" --duration 1 --use sfx --at 1.0
  → md_bd7f588c, revisión 6
```
Documento final: 1 escena, 3 assets, `music` con ducking, `audioEvents[0].at=1.0`.

## UI

- **Sin panel Generar** (decisión de Tormen): el chat manda.
- Se añadió **auto-refresco** al pane: cada 4 s, si el servicio tiene revisión nueva y el usuario no está escribiendo, recarga y avisa «Proyecto actualizado desde el chat». Desplegado con md5 idéntico y smoke 30/30.

## Pendiente

- Proveedores reales (imagen/música) esperan URL + clave de Tormen.
- 1080p sigue experimental.
- El proyecto no tiene repo git.
