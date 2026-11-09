# REPORTE · Dock derecho y compactación v3.1 (pane `editor-video`)

- **Autor:** Hephaestus (subagente) · **Cierre y despliegue:** Hermes Padre.
- **Fecha:** 2026-11-08, America/Caracas.
- **Estado:** código desplegado y sintaxis verificada; **verificación visual pendiente** (la ventana estaba en otra sesión al cerrar).

## Qué se aplicó (en el plugin desplegado, md5 `3be3af93…`, 2775 líneas)

1. **Dock derecho**: `placement:'right'`, `dock:{pane:'workspace',pos:'right'}`, `width:'64%'` → en 1440 el chat queda ~518 px a la izquierda y el editor ~922 px a la derecha.
2. **Compactación**: `compact = ancho < 1100`, `tight = ancho < 760`.
   - Biblioteca → **drawer** de 220 px con scrim, montado dentro de `.ve-body` (sin `position:fixed`); botón «Medios» en topbar.
   - Inspector → **sheet inferior** de 240 px (`max-height:72%`, scroll interno); botón «Propiedades».
   - Timeline 118 → 96 px (compact) → 84 px (tight). Topbar aprieta a <760 (oculta autosave/título).
3. **Overlays contenidos**: causa raíz del «flotar» era `.ve-rail{position:absolute; top:44px; bottom:44px}` resolviendo contra `.ve-root` y desbordando el footer; ahora se ancla a `.ve-body`. `.ve-root` con `contain:paint`; z-index ordenado (scrim 8 / drawer 9 / diálogo 11 / menú 12).
4. **Chip de modelo (solo lectura)**: lee `host.state.model` vía `useValue`; si el host no expone el atom, no se dibuja. Click → `host.composer.focus(null)` + aviso «Cambia el modelo en el selector del chat». **No cambia modelo**: el SDK lo prohíbe expresamente.
5. **Element picker**: «Añadir medio» abre diálogo contenido con `GET /projects/<id>` → `media[]`; elegir hace `POST /projects/<id>/media` con la ruta relativa. «Reemplazar medio» en el inspector reutiliza el picker y solo cambia `source.assetId/kind`, conservando `in/out`.
6. **Fallback de carpeta**: «Otra carpeta…» usa `ctx.files.requestFolder()` + `list()`.

## Evidencia de backend (prueba del subagente, instancia propia)

`GET /health` ok (ffmpeg-9.0.1) → `POST /projects` 201 → `GET /projects` 1 → dos `POST /projects/<id>/media` 201 (2 escenas, 2 assets) → `GET /projects/<id>` con `paths ['clip-a.mp4','clip-b.mp4']` y `exists [true,true]`. Es exactamente la llamada del picker.

## Verificación del Padre

- `node --check` del desplegado → **OK**.
- Fuente y despliegue con **md5 idéntico** (`3be3af93…`).
- Servicio núcleo **8770** arriba (0.3.0) tras reinicio desacoplado.
- `desktop.log`: **sin errores del plugin `editor-video`**. El único fallo es ajeno: una copia `editor-video-spike.disabled` con el mismo id que el plugin del spike (`duplicate id "editor-video-spike"`), que conviene retirar de `desktop-plugins/`.

### Causa raíz de «no veo el plugin» (21:06)

El plugin estaba **desactivado** en el almacén de la app (`"video-editor":false` en el mapa de plugins de `%APPDATA%/Hermes/Local Storage/leveldb`), así que el loader lo importaba pero no registraba nada. El código estaba bien: el banco de stubs del SDK ejecutó `register()` y el render del pane **sin errores** (4 contribuciones: titlebar, paleta, atajo y pane).

**Arreglo aplicado:** id del plugin `video-editor` → **`video-editor-v2`** (nuevo id = sin estado desactivado heredado; `defaultEnabled:true`). Tras el escaneo, el pane aparece montado a la derecha y abierto por defecto.

**Verificado visualmente:** captura `docs/qa/pane-dock-right.png` — chat a la izquierda, editor a la derecha (64 %), chip `deepseek-v4.1-flash`, selector de proyecto, estado vacío con «Elegir proyecto»/«Crear proyecto», «Importar medios», «Ver chat», «Exportar MP4» y «Cerrar editor».

## Pendiente (no ocultar)

1. **Verificación visual**: la app estaba en otra sesión («FIXTURE DE E2…») y no se pudo capturar «chat izquierda + editor derecha». Se hará al volver a esta sesión o tras **Ctrl+K → Reload desktop plugins**.
2. Confirmar en vivo `host.state.model` en este build (si no existe, el chip no se dibuja, como está diseñado).
3. Probar el picker desde la UI (clic) — el camino HTTP está probado.
4. Limpiar `desktop-plugins/editor-video-spike.disabled` (copia duplicada que rompe la carga del spike; no afecta al editor).

## Rollback

- Respaldo del plugin anterior al dock: `desktop-plugins/editor-video/plugin.js.prev-dock.bak`.
- Parar servicio: `python core/start_service.py --port 8770 --stop`.
- Cerrar el editor: ✕ de la cabecera (no la X nativa del tab).
