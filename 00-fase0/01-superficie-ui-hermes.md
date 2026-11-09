# VIDEO-EDITOR · Fase 0 · Superficie de extensión UI de Hermes — VERIFICADA

Fecha: 2026-11-08. Pregunta que el plan dejaba abierta (P1 «WebUI sin extensión»): **¿existe una API/UI de extensión real para meter un editor dentro de Hermes?** **Revisión 2 (14:35)**: correcciones C1–C8 de Dike aplicadas.

## Veredicto: SÍ EXISTE, está documentada, ya se usa en esta PC **y funciona en runtime**

Evidencia primaria (archivos y comandos, no afirmaciones):

1. **SDK de plugins de escritorio instalado con el runtime**: `C:\Users\EgtYP\AppData\Local\hermes\hermes-agent\website\docs\developer-guide\desktop-plugin-sdk.md` (132.763 bytes, 3-nov-2026). Documenta el contrato completo.
2. **Cuatro plugins de UI instalados**: `~/.hermes/desktop-plugins/{bot-agente, bot-chat-agent, meshy, padre-flow}` (código válido, `node --check` rc=0). `padre-flow/plugin.js` usa **`ctx.rest('/active')` y `ctx.socket('/events')`** (líneas 284, 323, 412) contra su propio `plugin_api.py` (manifest `{api: plugin_api.py}`) — el patrón exacto que el editor necesita.
3. **App de escritorio = superficie objetivo**: Hermes v0.23.0 con app Electron; plugins en caliente desde esa carpeta. En **Windows** el atajo de recarga es `Ctrl+K` (el SDK cita ⌘K de macOS).
4. **Runtime probado con un pane NUEVO (spike F1)**: `editor-video-spike` quedó montado en la app; `Hermes.exe` (PID 12832) mantiene **dos conexiones ESTABLISHED** a `127.0.0.1:8765` y `spike/logs/service.access.log` registra `GET /probe → 200` y `POST /probe → 200` (14:19–14:20). El pane hizo `fetch` directo al servicio: **incógnita CSP/CORS resuelta a favor**.

## Qué permite el SDK (resumen operativo para el editor)

| Necesidad del editor | Capacidad del SDK |
|---|---|
| Panel/pestaña propia dentro de la app | `ctx.register({ area: 'panes', render, data: { placement: 'main'|'right'|'bottom', dock, width, height } })` |
| Página completa + acceso desde sidebar | `ROUTES_AREA` + `SIDEBAR_NAV_AREA` |
| Botones, inputs, selects, tabs, diálogos | UI kit nativo: `Button`, `Input`, `Textarea`, `Select*`, `Switch`, `Checkbox`, `SegmentedControl`, `Tabs*`, `Dialog*`, `Badge`, `ScrollArea`, `EmptyState`, `ErrorState`, `Skeleton`, `LogView`… (no hay `Slider` en el kit: usar control nativo/numérico o Segmented) |
| Contexto de sesión/proyecto compartido | `host.state.activeSessionId / cwd / profile` (átomos reactivos) + `host.request(...)` al gateway |
| Persistencia local del plugin | `ctx.storage.get/set/remove` |
| Backend propio (cola de jobs, FFmpeg) | Paquete con `manifest.json { name, api: "plugin_api.py" }` → rutas `/api/plugins/<id>` vía `ctx.rest` / `ctx.socket` |
| Notificaciones y abrir archivos | `ctx.os.notify`, `ctx.os.revealPath`, `ctx.os.openExternal`, `ctx.os.writeClipboard` |
| i18n | `ctx.i18n.register({ es, en })` + hook **`useI18n`** (corregido: `usePluginI18n` no existe, SDK línea 2113) |
| Render multimedia en el chat | `TOOL_MEDIA_RENDERER_AREA` renderiza archivos `MEDIA:` de las tools del plugin |
| Iframe aislado (preview) | `SandboxedFrame` del UI kit |

## Incógnitas que el spike debe cerrar (no asumir)

1. **Acceso de red del pane**: ✔ **CERRADO por el spike**. `fetch('http://127.0.0.1:8765')` funciona desde el pane (probes 200 + conexiones de `Hermes.exe`).
2. **Selección de archivos**: ruta soportada identificada por Harmonia en el SDK real: `ctx.files.requestFolder()` / `ctx.files.list` + drag&drop con `ctx.rest(..., {upload:{bytes}})`; falta probarla en el pane.
3. **`plugin_api.py`**: **no necesario para el MVP**. El `fetch` directo del renderer (origin `file://`, `Origin: null`) responde 200 → el servicio en loopback basta y **no hay ventana de recarga pendiente**. `plugin_api.py` queda como opción de empaquetado (exige `plugins.enabled` + recarga) si algún día se quiere el backend dentro del gateway.
4. **Preview de vídeo dentro del pane**: `<video>` con URL de rango servida por el backend; probar con MP4 generado.
5. **Layout**: tamaño mínimo/máximo del pane y comportamiento con la app redimensionada.

## Arquitectura que la evidencia habilita (propuesta, sujeta a ADR-001)

```
Hermes desktop (app)
├─ plugin "video-editor" (plugin.js)        ← pane UI nativo, tema de la app
│    ├─ host.state (sesión, cwd, perfil)     ← contexto compartido explícito
│    └─ ctx.rest /api/plugins/video-editor   ← REST al backend del plugin
├─ plugin_api.py  (gateway)                  ← enqueue jobs, estado, cancelación
└─ worker FFmpeg (proceso separado, detached) ← cola SQLite, un job, límites, kill-tree
```

- La UI vive **dentro** de Hermes (requisito del plan) sin app aparte.
- La cola vive **fuera** del gateway (requisito del plan): `plugin_api.py` solo encola; el worker corre como proceso propio con journal SQLite y sobrevive caídas.
- El motor es **FFmpeg del sistema** (medido en 00-inventario): cubre el MVP sin Node/Chrome ni licencias de render.

## Gate 0 (extensión UI): estado

- **CUMPLE (runtime probado)**: SDK documentado + plugins en disco + **pane nuevo montado y `fetch` funcionando en la app** (evidencia en 00-inventario §Plugins y en `spike/logs/`).
- Pendiente para cerrar F1: selección de archivos, preview `<video>` en el pane y —si se usa— import de `plugin_api.py` con ventana de recarga.
- Si algo falla: se documenta bloqueo parcial y se propone variante (ventana de recarga aprobada o servicio local), **sin app separada**.
