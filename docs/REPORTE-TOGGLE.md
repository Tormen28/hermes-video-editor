# REPORTE · Cerrar / reabrir el pane `editor-video`

- **Autor:** Hephaestus (subagente) · **Fecha:** 2026-11-08, America/Caracas.
- **Archivo tocado:** `C:/Users/EgtYP/AppData/Local/hermes/desktop-plugins/editor-video/plugin.js`
  (copia fuente sincronizada: `fleet-workspace/video-editor/plugin/plugin.js`, mismo md5).
- **Estado:** código implementado y sintaxis validada. **Verificación visual en la app: PENDIENTE**
  (ver «Pendiente»; no hay captura porque no se llegó a recargar el plugin en esta sesión).

## Qué se implementó

1. **Cierre real por disposer.** `register(ctx)` guarda el disposer de `ctx.register({ area: 'panes' })`
   en `paneDisposer`; `unmountPane()` lo ejecuta y lo anula. Cerrar ya no mata el plugin.
2. **Botón en la cabecera del pane:** `✕ Cerrar editor` (icono + texto; icono solo en ancho
   compacto), `title="Cerrar (Ctrl+Shift+E)"`, `aria-label` equivalente. Llama a `onClose`,
   que es el `setOpen(false)` del registro.
3. **Reapertura por tres vías**, todas sobre el mismo `toggle()`:
   - barra de título (`TITLEBAR_AREAS.right`) — botón «Vídeo» con `aria-pressed` = abierto;
   - ⌘K (`PALETTE_AREA`) — «Abrir/Cerrar editor de vídeo», con `action: 'videoEditor.toggle'`
     para que la fila muestre el atajo vivo;
   - atajo `KEYBINDS_AREA` — `mod+shift+e` (Ctrl+Shift+E en Windows: `combo.ts` normaliza
     `ctrl`→`mod` fuera de macOS), categoría `view`, rebindable.
4. **Estado persistido** en `ctx.storage['ui.open']` (booleano). Al montar, `readOpen()` decide:
   `false` ⇒ no se registra el pane y quedan solo titlebar/paleta/atajo.
5. **Limpieza al cerrar/desmontar:** `releaseVideos()` pausa, quita `src` y `load()` de cada
   `<video>` dentro de `[data-ve-pane]`, antes del teardown; el cleanup del efecto de montaje
   anula `autoRef` (autoguardado 4 s) y `pollRef` (polling de export 400 ms) y vuelve a llamar a
   `releaseVideos`; `ctx.onDispose` cubre descarga/recarga del plugin.
6. **Documentado en `plugin/README.md`** (sección «Cerrar y reabrir el pane») que la X nativa
   desactiva el plugin y que debe usarse este botón.

## Comportamiento real del SDK vs. documentación

- `ctx.register()` **sí** devuelve disposer (doc §PluginContext). Verificado por lectura del doc;
  el uso es el estándar.
- **`TITLEBAR_AREAS.right` NO pinta `data`.** En este build el slot hace
  `items.map(c => c.render && <ContribRender render={c.render}/>)`
  (`apps/desktop/src/contrib/react/slot.tsx:10-24`) y los `TitlebarTool` de verdad se leen de
  `titleBar.tools.left|right` (`app/contrib/panes.tsx:189`), área que alimentan los setters del
  core. Es decir: una contribución **solo con `data: TitlebarTool` en `TITLEBAR_AREAS.right`
  no dibuja nada**. Fallback aplicado: la misma contribución en `TITLEBAR_AREAS.right` pero con
  `render` de un botón propio (`TitlebarToggle`) que imita el chrome (`aria-pressed`,
  `title`, tokens `--ui-*`) y recibe el estado por suscripción, así el `active` queda vivo sin
  re-registrar. Si un build futuro empieza a pintar `data`, no hay duplicado porque no se
  registra `data` en esa área.
- Efecto lateral conocido: cualquier contribución en `titleBar.left/right` pone
  `pageOwnsTitlebar = true` (`titlebar-controls.tsx:206`), lo que cambia el chrome en rutas
  overlay. Es el mismo comportamiento que tendría el `data` documentado.

## Verificación hecha

- `node --check` sobre copia `.mjs`: **rc 0** (Node v24.15.0).
- Lectura cruzada del código del host para confirmar semántica de `register`/`Slot`/keybinds
  (rutas citadas arriba).

## Pendiente (no ocultar)

1. **Carga en la app y capturas.** No se llegó a recargar el plugin en la ventana de Hermes en
   esta sesión, así que **no hay `docs/qa/pane-toggle.png`**. Pasos exactos:
   1. Ajustes ▸ Capacidades ▸ Plugins → desactivar/activar `video-editor` (o reiniciar la app).
   2. Comprobar el botón «Vídeo» en la barra de título → clic ⇒ el pane desaparece, la pestaña
      se retira y `ui.open=false` queda en storage.
   3. Ctrl+Shift+E (o ⌘K → «Abrir/Cerrar editor de vídeo») ⇒ el pane vuelve y se reabre el
      último proyecto (`lastProjectId`).
   4. Captura de ambos estados → `docs/qa/pane-toggle.png`.
2. **Foco al reabrir:** el pane se re-monta en su zona (`placement: 'main'`) y debería quedar
   como pestaña activa; no se fuerza ninguna acción de layout porque `view.toggleRightSidebar`
   podría colapsar la zona equivocada. Si al reabrir la zona está colapsada, el usuario debe
   mostrarla; verificar en la prueba visual.
3. Sin tocar `config.yaml`, gateway, `~/.hermes/plugins`, `spike/` ni docs de diseño. Sin
   instalaciones ni grabación de pantalla.
