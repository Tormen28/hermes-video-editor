# Fase 2A — Texto con estilo, filtros y logo (verificada)

Fecha: 2026-11-08. Implementación por Hephaestus (subagente), **verificada por el Padre**.

## Qué entró

- **Texto con estilo** (`scene.text[]`): `size` 12–120 (def 42), `color` #RRGGBB, `border` 0–10, `borderColor`, `shadow` 0–10, `animation {in,out}` con `none|fade|slide-up|slide-down`. Defaults rellenados en `normalize()`, así los documentos viejos siguen validando.
- **Filtros por escena** (`scene.filters`): `brightness` −1..1, `contrast` 0..2, `saturation` 0..3, `grayscale`, `vignette`, `blur` 0..20 → cadena `eq,hue,vignette,boxblur` antes de `scale/pad`. Sin filtros el grafo es **idéntico** al anterior.
- **Logo** (`project.logo`): `{assetId de imagen, position (9 anclas), opacity 0..1, scale 0.05..0.5}` → `overlay` después del texto, con `colorchannelmixer=aa`.
- **InputPlan**: los índices de entrada (escenas, música, logo) ya no se asumen; un solo lugar los numera.
- **Tests**: `core/tests/test_phase2a.py` (45 casos, incluye 2 renders reales con música+texto animado+filtro+logo).

## Verificación del Padre (no self-report)

- `python -m py_compile project.py service/worker.py service/app.py` → **OK**.
- `python -m unittest discover -s tests` desde `core/` → **312 tests OK (skipped=2)**.
- `python -m unittest test_phase2a.BrandedExportTest -v` desde `core/tests/` → **2 tests OK, 1.59 s** (render real; el fallo al invocarlo desde `core/` es del import `_support`, no del producto).

## Pendiente declarado

- `CONTRATO.md` de 2A no se actualizó en esa pasada; se documenta junto con transiciones (fase 2B, en curso).
- El proyecto **no tiene repositorio git**: los cambios están en el árbol de trabajo sin versionar. Es una brecha de rollback real (no bloquea el render, sí la trazabilidad).
- Riesgo menor: `shadow` sin `border` puede no pintarse en algunas versiones de ffmpeg; `boxblur` recorta el radio a `min(w,h)//2`.
