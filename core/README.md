# Núcleo del editor de vídeo (backend loopback)

Servicio local que sostiene el plugin editor dentro de Hermes: documento de proyecto versionado,
cola de un solo job con journal SQLite, worker FFmpeg endurecido y API HTTP en loopback para el pane.

- Contrato de API: [`CONTRATO.md`](./CONTRATO.md)
- Decisión de motor: [`../docs/ADR-001-motor-ffmpeg.md`](../docs/ADR-001-motor-ffmpeg.md)
- Evidencia del spike previo: [`../spike/REPORTE.md`](../spike/REPORTE.md)

## Requisitos

- Windows con el FFmpeg que trae Hermes (`tools/ffmpeg-9.0.1-win32-x64/bin`) o `VIDEO_EDITOR_TOOLS`.
- Python 3.11+ estándar. **Sin dependencias externas** (stdlib + ctypes).

## Correr

```bash
cd core
python start_service.py --data-root C:/.../core/data --media-root C:/.../medios --port 8770
curl -s http://127.0.0.1:8770/health
```

`start_service.py` arranca **desacoplado** (DETACHED_PROCESS + nuevo grupo): el servicio sobrevive
al cierre del proceso que lo lanzó. Log en `logs/service.stdout.log`.

Parar: `python start_service.py --port 8770 --stop` (si admin está habilitado).

## Pruebas

```bash
cd core
python -m unittest discover -s tests -v      # suite completa (359 tests, 2 skipped en esta máquina)
python scripts/smoke_render.py               # render corto + staging vacío + frame
python scripts/e2e_evidence.py               # corrida de evidencia
```

E2E por HTTP contra un servicio vivo:

```bash
python scripts/e2e_http_check.py --base http://127.0.0.1:8770 \
  --media clipA.mp4 clipB.mp4 vfr_mix.mp4 \
  --out logs/e2e-http-output.mp4
# reporte JSON: logs/e2e-http-report.json
```

## Estructura

| Ruta | Qué hace |
|---|---|
| `paths.py` | reglas de rutas (traversal, absolutas, junctions, extensiones) |
| `project.py` | documento canónico, validación, migración, hash, revisión optimista, adaptador UI |
| `schema/` | JSON Schema + ejemplo del documento |
| `service/journal.py` | SQLite propio: proyectos, cola, eventos, reaper, dedupe |
| `service/worker.py` | allowlist de flags, Job Objects, compilación del grafo, render, promoción atómica |
| `service/app.py` | HTTP loopback + runner de 1 job |
| `scripts/` | smoke, evidencia, E2E HTTP |
| `tests/` | unittest (stdlib) |

## Operación

- Un solo render a la vez; el hilo HTTP nunca ejecuta ffmpeg.
- La cola vive en `data/service.sqlite3`; sobrevive caídas. Al arrancar, los jobs `running` pasan a `interrupted`.
- Dedupe por hash del documento: exportar dos veces sin cambiar nada devuelve el mismo job.
- Los MP4 se escriben en `data/jobs/<jobId>/` con staging + rename atómico.

## Límites conocidos

- Único preset: `mp4-720p30`. 1080p/4K fuera del MVP.
- Un job concurrente.
- El pane real (UI) es otra pieza: este README cubre solo el backend.
- La ruta `--data-root` debe pasarse en formato nativo `C:/...` (un `/c/...` de MSYS se interpreta como `C:\c\...`).
