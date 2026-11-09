# REPORTE · Pane real `editor-video` (desktop plugin)

- **Autor:** Hephaestus (subagente, deleg_e28cec04) · **Cierre:** Hermes Padre (QA_PROBE apagado, reporte y captura).
- **Fecha:** 2026-11-08, America/Caracas.
- **Estado:** pane montado y camino renderer→servicio verificado; faltan los clics de usuario (abrir proyecto, previsualizar, exportar, cancelar) y el grant de `ctx.files`.

## Entregable

`C:/Users/EgtYP/AppData/Local/hermes/desktop-plugins/editor-video/plugin.js` — **930 líneas**, ESM sin JSX, imports permitidos. `node --check` → **rc 0** (Node v24.15.0).

Cubre:
1. Conexión con URL base editable persistida en `ctx.storage` + botón «Probar /health».
2. Lista `GET /projects` + «Crear proyecto» (`POST /projects`).
3. Proyecto abierto: `project.scenes`, `media[]` y `<video>` del `previewUrl`.
4. Añadir medio por ruta relativa/absoluta + `ctx.files.requestFolder()`/`list()` con fallback manual.
5. Exportar (`POST /projects/<id>/export` 202) → polling `GET /jobs/<id>` con `role=progressbar`, etapa, ETA y «Cancelar»; al terminar `<video src=/jobs/<id>/output>` + «Abrir carpeta».
6. Estados vacío/cargando/error, textos es-ES.

`QA_PROBE` (sonda automática que creaba proyecto y export en cada recarga) quedó **en `false`** por el Padre.

## Evidencia verificada (archivos y log, no self-report)

- `C:/Users/EgtYP/AppData/Roaming/Hermes/plugin-files/data/editor-video/diag-qa.json` (18:47:43): `origin: file://`, `base http://127.0.0.1:8770`; health 200 (47 ms) → create 201 (rev 0) → media 201 (rev 1, `md_738723c6`, 1 escena) → export 202 (`j8e011fe7ec`, deduped false) → job `succeeded` (stage done, 100 %) → output **206** (`bytes 0-1023/3725875`). `ok: true`.
- `core/logs/service.stdout.log`: `POST /projects 201`, `POST /projects/prj_4dc45b89ea638106/media 201`, `POST .../export 202`, `GET /jobs/j8e011fe7ec/output 206` (18:47:43–44). El renderer `file://` habla con el servicio sin bloqueo CORS.
- Captura del pane montado en la app: `docs/qa/pane-real.png` (849.678 B).

## Pendiente (no ocultar)

1. **Clics de usuario**: abrir proyecto, previsualizar, exportar y cancelar desde la UI. Los botones existen y el camino equivalente está probado vía renderer (`diag-qa.json`); falta la pulsación real.
2. **`ctx.files.requestFolder()`**: no ejercitado — requiere el diálogo nativo del usuario (P2). Carpeta de prueba: `C:\Users\EgtYP\Videos\hermes-spike-fixtures`.
3. **Preflight OPTIONS** explícito no probado; los POST JSON pasaron sin preflight fallido.

## Cómo probarlo tras el reinicio

1. Abrir el pane **«Editor de vídeo»** (barra derecha) → «Probar /health» → debe dar 200.
2. «Crear proyecto» → se lista con revisión 0.
3. Añadir medio `clipA.mp4` (ruta relativa) o «Elegir carpeta» → grant de la carpeta de fixtures.
4. «Exportar» → barra de progreso con etapa/ETA → al terminar, `<video>` del MP4 y «Abrir carpeta».
5. «Cancelar» en un export nuevo (hay que cambiar el proyecto para que no lo dedupee).

## Restricciones respetadas

Sin cambios en `config.yaml`, gateway, `~/.hermes/plugins` ni `spike/`. Sin instalaciones. Sin grabación de pantalla. El servicio 8770 sigue vivo (desacoplado) y no se reinició el gateway.
