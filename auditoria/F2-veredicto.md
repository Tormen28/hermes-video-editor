# F2 · Auditoría del núcleo backend y evidencia del editor — VEREDICTO

- **Autora:** Dike (QA), 2026-11-08.
- **Estado del archivo:** reconstruido por **Hermes Padre** a partir del resumen final de Dike, porque el subagente agotó su presupuesto de iteraciones antes de escribir el archivo. Trazas crudas: `profiles/dike/cache/scratch/{f2_adv.out,f2_adv2.out,f2adv2/svc-*.log,mut/}`.
- **Regla:** este veredicto se emite sobre evidencia reproducida; el Padre re-ejecutó los puntos disputados y lo anota en §6.

## 1. Veredicto global

**OBSERVADO** — el núcleo es sólido y el gate 2 no pasa todavía por defectos reales y por overclaims del informe.

## 2. Núcleo — OBSERVADO

Reproducido: `cd core && python -m unittest discover -s tests` → **Ran 232 tests, OK (skipped=2)**, 36.1 s (paths 18, project 61, journal 35, worker 82, service 36).

Adversariales contra servicio vivo en puerto libre con raíces propias:
- traversal `../`, `..\`, `sub/../..`, absolutas fuera de raíz → **400** con motivo;
- junction real (`mklink /J`, rc=0) → **400 «escapes its root»**; control positivo 201;
- `.exe`/`.bat`/`.mp4.exe` → 400; archivo 2 GiB+1 → 400 antes de leer; 0 B → 400;
- dedupe: 5 exportaciones concurrentes → **1 jobId** (4 `deduped:true`); reintento tras éxito → mismo jobId;
- 2 PUT con la misma revisión → 200 + **409** con `current_revision`;
- cancelación 0.12 s sin huérfanos ni `out/`;
- matar ffmpeg a mitad → `failed`, `out/` inexistente; matar el servicio con job en curso → ffmpeg muerto en 0.5 s (Job Object), reinicio → `interrupted`.

Defectos declarados por Dike (estado actual en §6):
(a) `/admin/stop` respondía `{stopping:true}` sin terminar el proceso;
(b) staging parcial de un job fallido no se limpiaba (3.9 MB en su instancia);
(c) `limit.assign()` ignoraba el retorno; `limits_enforced` reflejaba crear el Job Object, no asignarlo;
(d) sin cabecera `Host` → 200 (solo se validaba si existía);
(e) CSRF: `Origin: null` (iframe sandbox) → POST 201 y `/admin/stop` 200; `Origin: http://evil` → 403;
(f) `terminate_pid_tree`/`pid_is_alive` no se usan en recuperación; sin fallback si la asignación al Job Object falla.

## 3. Informe F2 — OBSERVADO por overclaims numéricos

- La columna «Tests» (125/424/325/961/497) son **líneas de los archivos de test**, no tests; los reales son 18/61/35/82/36; la suma declarada (2 332) contradice el total.
- «230 tests» vs **232** medidos; `project.py` 964 vs 967 líneas.
- Endpoints §2: los 15 existen y coinciden con `_route` (app.py:604-690).
- §4 verificado contra `evidence/e2e-20261108-175047/e2e-report.json`: 201/201/200/202, etapas `queued→done`, 9 eventos, pared 1.03 s, 3 579 183 B, 8.0 s, h264+aac 1280×720, Range 206/4096, log 2 444 B sin ruta de home.
- Journal: `PRAGMA user_version` + `MIGRATIONS`; promoción con un solo `os.replace` en el mismo volumen.

## 4. Plan de pruebas — APROBADO con reservas

A-01/A-02/A-04/A-05/A-07/A-10/A-11 pasan con evidencia; **A-12 falla por `Origin: null`**; el control negativo (mutación en copia) demuestra que desactivar la contención de raíz y el límite de tamaño mata un test cada uno.

## 5. F1-b / ADR-001 — observaciones

- Reproducido: Range 206 (`bytes 0-65535/8884986`), proxy CFR 30/1 · 288 frames · 9.6 s, 300 frames/10.000 s/2 468 023 B, `xfade fade+slideleft` y `acrossfade` en el comando guardado.
- Dike declaró «`spike/out/jbf18c68465.mp4` NO EXISTE»; **el Padre verificó que sí existe** (2 468 023 B, 10.0 s) — §6.
- PSNR «41.202» no reproducible desde el entregable (sin comando); su medición independiente da 40.86/40.58/43.27 dB → el mapeo es correcto.
- `final.json` guarda el comando truncado a 1 200 caracteres.
- `plugin_probes` filas 8–14 muestran `render_submitted → render_succeeded` desde el pane: **P5 no estaba pendiente** (subdeclaración).
- ADR-001: coincide con lo medido; matiz: la recuperación depende del **Job Object** (kill-on-close), el fallback `taskkill` no se usa.

## 6. Re-verificación del Padre (2026-11-08, 18:45) y arreglos aplicados

| Hallazgo | Resultado medido | Acción |
|---|---|---|
| (a) `/admin/stop` no termina | **NO reproducido**: instancia en 8772, `POST /admin/stop` → puerto cerrado y proceso 21684 inexistente a los 3 s. `main()` espera `service.stopped`. | Sin cambio; se deja prueba reproducible. |
| (b) staging residual | En `data-verify` los staging quedan a 0 B tras promoción/cancelación; el caso de Dike era su instancia. Aun así faltaba purga explícita en fallo. | **Arreglado**: `worker.purge_derivatives` en fallo y en estados no-`succeeded`. |
| (c) `limits_enforced` | Cierto: reflejaba creación. | **Arreglado**: `ProcessLimit.assigned` + `limits_enforced = enforced and assigned`. |
| (d) Host ausente | Cierto. | **Arreglado**: sin `Host` → **403** (probado con socket crudo: `HTTP/1.0 403`). |
| (e) `Origin: null` CSRF | Cierto por diseño (el pane es `file://` y envía `Origin: null`). | **Pendiente de decisión de Tormen**: política (nonce/cabecera) o aceptar por escrito el riesgo local. El Host fix mitiga rebinding; no el iframe sandbox. |
| (f) fallback Job Object | Parcial: `_stop` ya cae a `taskkill` si `limit.terminate()` falla, pero `assigned` no se registraba. | **Arreglado** con (c). |
| `jbf18c68465.mp4` «no existe» | **Falso**: existe, 2 468 023 B, 10.0 s. | Sin cambio; evidencia intacta. |
| P5 «pendiente» | **Falso**: probes 8–14 muestran render desde el pane. | Corregido en `spike/REPORTE.md`. |
| Cifras del informe F2 | Cierto (líneas ≠ tests). | Corregidas en `docs/REPORTE-F2-backend.md`. |

## 7. Condiciones para el gate 2 (MVP)

1. ~~`/admin/stop` debe terminar~~ → verificado que termina.
2. ~~Limpiar staging en fallo/cancelación~~ → aplicado.
3. **Decisión de Tormen** sobre `Origin: null` (nonce/cabecera) o aceptación escrita del riesgo CSRF local.
4. ~~Cifras del informe F2~~ → corregidas.
5. Evidencia F1-b: el MP4 existe; anclar el PSNR a un comando reproducible (pendiente menor).
6. `limits_enforced` real → aplicado.
7. Declarar en ADR que la recuperación depende del Job Object → pendiente de nota de una línea.

Gate 2 = cerrado cuando (3) y (5)/(7) estén resueltos; el resto del núcleo ya está verificado y con tests verdes.
