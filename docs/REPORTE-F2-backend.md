# REPORTE · Fase 2 (MVP) — backend del plugin editor

- **Origen:** Harmonia (diseño/UI) ejecutando el bloque autorizado «backend primero».
- **Destino:** Tormen (Padre) · revisión de QA: Dike · siguiente implementador de UI: Harmonia.
- **Fecha:** 2026-11-08, America/Caracas (UTC-4). **Tarea:** PLAN-CONSOLIDADO, fase 2.4–2.6 (servicio de jobs, worker, recuperación).
- **Estado:** servicio backend **funcional y probado**; pane visual (fase 2.2–2.3) **pendiente**, sin bloqueo técnico.

## 1. Qué existe ahora

| Módulo | Líneas | Qué resuelve | Tests |
|---|---|---|---|
| `core/paths.py` | 161 | aislamiento de rutas (traversal, absolutas, dispositivos, junctions) | 18 |
| `core/project.py` | 967 | documento canónico, migración, hash, revisión optimista, adaptador UI | 61 |
| `core/service/journal.py` | 523 | SQLite propio: proyectos, cola, eventos, reaper | 35 |
| `core/service/worker.py` | 1 331 | allowlist de flags, Job Objects, compilación del grafo, render, promoción atómica, log redactado | 82 |
| `core/service/app.py` | 803 | **HTTP loopback + runner de 1 job** (contrato `ui-spec §6.3`) | 36 |
| `core/scripts/e2e_evidence.py` | 222 | corrida de evidencia end-to-end por HTTP | — |

**Suite completa: 232 tests, OK, 2 skipped** (junctions no permitidas / Job Objects fuera de Windows). Corregido el 2026-11-08: la columna anterior contaba **líneas** de los archivos de test, no casos; verificado con `python -m unittest discover -s tests`. Comando reproducible:

```bash
cd core/tests && python -m unittest test_paths test_project test_journal test_worker test_service
```

## 2. Contrato HTTP implementado (`ui-spec §6.3`)

| Método | Ruta | Notas |
|---|---|---|
| GET | `/health` | engine, ffmpeg+versión, cola, recuperados |
| GET | `/grants` | carpeta concedida (raíz de medios) |
| GET | `/projects?session=&cwd=` | lista filtrada |
| POST | `/projects` | crea (revisión 0) |
| GET | `/projects/<id>` | documento + revisión + medios con `exists`/`previewUrl` |
| PUT | `/projects/<id>` | `{revision, project}` → **409 con `current_revision`** |
| POST | `/projects/<id>/media` | `{path}` relativo o absoluto dentro de la concesión; registra asset y crea escena |
| GET | `/media/<pid>/<asset>` | **Range/206** sobre el original |
| POST | `/projects/<id>/export` | `{preset, captions}` → `202 {jobId, deduped}` |
| GET | `/jobs/<id>` · `/jobs` | estado, etapa, progreso, ETA, `outputUrl` |
| POST | `/jobs/<id>/cancel` | cancelación cooperativa (≤10 s, medida 0.52 s en el spike) |
| GET | `/jobs/<id>/output` | **Range/206** del MP4 final |
| GET | `/events?since=&timeout=` | long-poll; `timeout=0` = sondeo inmediato |
| POST | `/admin/stop` | sólo local (tests/operación) |

Dos decisiones de diseño que no estaban en la spec y conviene validar:

1. **Idempotencia con reintento:** exportar dos veces la misma revisión devuelve el mismo `jobId` (`deduped: true`) **mientras el job esté en cola, corriendo o haya salido bien**. Si falló, se permite reintentar (clave de deduplicación con sufijo). Sin esto, un fallo dejaba el proyecto sin forma de re-exportar.
2. **Guardas de origen/host:** el servicio no tiene auth de red; se rechaza `Host` que no sea loopback y `Origin` que no sea `file://`/`null`/localhost. Un sitio web abierto en el navegador no puede encolar renders.

## 3. Defectos reales encontrados y corregidos

Ninguno de estos lo detectaba la suite previa; los tres aparecieron al ejecutar de verdad:

1. **`-filter_complex_script` no existe en este FFmpeg** (`n9.0.1-11-ge47273f4d9-20260831`). Todos los renders fallaban. Ahora el grafo va inline con verificación byte a byte contra el grafo compilado + techo de 20 000 caracteres. Documentado en ADR-001 (addenda).
2. **Escapado de rutas en filtros.** El formateador anterior (`C\:/…` sin comillas) nunca se había ejercitado. Matriz de 6 variantes medida: sólo `'C\:/…'` (comillas **y** backslash en los dos puntos) renderiza. Cubierto por test unitario y por render real con acentos.
3. **Fuga de handles en `run_tool`:** los pipes de stdout/stderr no se cerraban (un `ResourceWarning` por job). Cerrados tras unir los hilos lectores.

Extra: el log de ffmpeg que QA marcó por filtrar la ruta del usuario **ya no la contiene** — se redacta al escribirlo (`<home>`/`<user>`) y se conserva por job como evidencia de fallo.

## 4. Evidencia end-to-end (medida, no estimada)

Corrida `evidence/e2e-20261108-175047/`, 3 clips sintéticos 1280×720, 2 subtítulos con acentos y una transición `fade-0.3`:

| Dato | Valor |
|---|---|
| Estados por HTTP | `201` crear · `201` medio ×3 · `200` guardar · `202` export |
| Etapas empujadas | `queued → probing → rendering (5 → 90.9) → done` |
| Eventos en cola | 9 |
| Pared del render | **1.03 s** (8.0 s de vídeo) |
| Salida | H.264 + AAC, 1280×720, 8.000 s, **3 579 183 B** |
| Streaming | `Range` → **206**, 4 096 B servidos |
| Log del job | 2 444 B · `mentions_home: false` · `mentions_caption: false` |
| Verificación visual | subtítulo inferior completo con `ñ`, tildes y `¿…?`; segunda escena con rótulo superior y fondo **no** fundido a negro |

Frames para revisión: `evidence/e2e-20261108-175047/frame-t0.6.png`, `frame-t3.2.png`, `frame-t5.0.png`.

## 5. Hipótesis (separadas de los hechos)

- *H1:* el pane v0.2 puede implementarse contra este contrato **sin** tocar el backend; el mockup rev2 ya define estados y copy. Probable, no probado hasta montarlo.
- *H2:* 1080p cabrá igual, pero **no se ha medido**; el MVP sigue en 720p/30 por decisión escrita.
- *H3:* el render de un proyecto de 40 escenas podría acercarse al techo de 20 000 caracteres del grafo (≈ 500 caracteres/escena con subtítulo). Hay que medirlo antes de prometer proyectos largos.

## 6. Bloqueos

- Ninguno técnico en el backend.
- **No verificado:** instalar/recargar plugin del gateway (requiere ventana de reinicio) → Gate R sigue abierto, como estaba.
- **Pendiente de Tormen:** los 2 clics P2/P5 del spike y el umbral de latencia (propuesta: presupuesto absoluto p95 ≤ 15 ms en vez del 20 % relativo).

## 7. Rollback

Todo vive en `video-editor/core/`; no toca el gateway, ni perfiles, ni bases de datos ajenas. Revertir = dejar de arrancar `core/service/app.py` y usar `spike/service.py`. El journal y los documentos de proyecto son archivos propios (`data/service.sqlite3`, `data/jobs/<id>/snapshot.json`), nunca la DB de Hermes.

## 8. Siguiente bloque (no iniciado)

1. **Pane v0.2** desde `docs/ui-spec.md §5–§9` + mockup rev2, cableado a este contrato (estados A–F, atajos, WCAG 2.2 AA).
2. Proxy 540p opcional para preview (hoy sirve el original con Range, que es correcto y ya responde 206).
3. Pausa real: hoy es cancel/restart honesto; el motor no ofrece pausa fiable y así se declara.
