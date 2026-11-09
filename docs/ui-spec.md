# Editor de vídeo · Especificación de UI del pane (Hermes Desktop)

**Autor:** Harmonia (diseño UI/UX) · **Fecha:** 2026-11-08
**Destino:** Hephaestus (implementación del plugin) · revisión de Dike
**Estado:** especificación de diseño lista para implementar. **No** es código de plugin ni autorización de publicación.
**Fuentes verificadas:** `PLAN-CONSOLIDADO.md` (MVP + aceptación U1–U4), `00-fase0/01-superficie-ui-hermes.md`, `hermes-agent/website/docs/developer-guide/desktop-plugin-sdk.md` y el código real del UI kit (`apps/desktop/src/components/ui/*`, `sdk/index.ts`, `contrib/plugin-files.ts`).

Artefacto visual: [`mockup.html`](./mockup.html) — 6 estados del pane a 900×560, autocontenido, sin CDN, con los tokens del tema.
Abrir: `::preview{file="C:/Users/EgtYP/AppData/Local/hermes/fleet-workspace/video-editor/docs/mockup.html"}` (o el panel de vista previa de la app).

---

## 0. Resumen de la decisión de diseño

El editor es **un pane más de la app**, no una app embebida: hereda tema, tipografía, atajos del sistema, foco y espaciado. Nada de "ventana dentro de la ventana". El editor ocupa `placement: 'main'` porque una línea de tiempo necesita ancho; el rail derecho del editor es **interno** al pane (no el sidebar de la app), para no competir con la barra lateral de Hermes.

Cuatro principios rectores, en orden:

1. **El estado real manda.** Ningún porcentaje, miniatura ni duración se simula: si el backend no lo sabe, la UI lo dice ("Calculando…", "Sin ETA") en vez de animar una barra plausible.
2. **Nada de terminal, HTML, JSON ni código** para el usuario final (criterio U1–U4 del plan).
3. **Toda acción tiene dos caminos:** puntero (arrastrar, botón) y teclado (atajos + botones ▲▼). Nunca solo arrastrar.
4. **Una sola fuente de verdad por dato:** `host.state` para contexto de sesión, `ctx.rest` para el proyecto, `ctx.storage` solo para preferencias de vista.

---

## 1. Superficie: cómo se registra

```js
ctx.register({
  id: 'pane',
  area: 'panes',
  title: t('pane.title'),           // "Editor de vídeo" — ver §9 (i18n)
  data: {
    placement: 'main',              // main | right | bottom
    tabTitle: () => LocalizedTabTitle, // título que sigue el idioma activo
    width: '900px'
  },
  render: () => jsx(EditorPane, {})
})
```

- **`placement: 'main'`**: el editor necesita ≥820 px útiles; en `right` (340 px) solo cabría el rail. Si `main` no está disponible en la versión del app, degradar a `right` **con aviso visible** ("Abre el editor en el área principal para editar la línea de tiempo") y modo solo-propiedades. No fingir un editor usable en 340 px.
- **Tamaño:** el pane debe funcionar de **620×420** (mínimo) a pantalla completa. La maqueta fija 900×560 como referencia de revisión.
- **Ancho recordado:** `ctx.storage.set('pane.width', w)` al arrastrar el divisor (preferencia de vista, no del proyecto).
- **Ciclo de vida:** todo listener va por `ctx.addEventListener` / `ctx.setTimeout` / `ctx.onDispose`; el `<video>` se pausa y se libera el `src` al desmontar (nada de `window.*` desnudo).
- **Estado del editor** vive en átomos (`atom`/`computed`) del módulo del plugin, no en `localStorage`.

---

## 2. Layout y medidas

```
┌──────────────────────────────────────────────────────────────────────────────┐ 900
│ HEADER 44   ▶ Editor de vídeo · Rev 7   │ Proyecto: Lanzamiento Q4 ▾ │ Sesión 4f2a · video-editor │  ↺ ↻ [Guardar] ⋯
├───────────────────────────────────────────────────┬──────────────────────────┤
│ ESCENARIO (preview)                     flex 1    │ RAIL 292                 │
│  · marco 16:9 centrado, caption overlay           │  Escenas (4)             │
│                                                   │  · 01 Intro      3,2 s ▲▼│
│                                                   │  · 02 Demo       5,6 s ▲▼│ (seleccionada)
│                                                   │  · 03 Testimonio 4,4 s ▲▼│
├───────────────────────────────────────────────────┤  · 04 Cierre     3,0 s ▲▼│
│ TRANSPORTE 34  ⏮ ▶ ⏭  00:03,4/00:16,2 ▬▬▬●▬▬ ✂ ⟲ │  ──────────────────────  │
├───────────────────────────────────────────────────┤  Propiedades · Escena 2  │
│ LÍNEA DE TIEMPO 118                               │  Texto en pantalla  [..] │
│  regla 18 │ V1 clips 56 │ A1 audio 22             │  Volumen  ▬▬▬▬▬ 80 %    │
│                                                   │  Orientación [H][V]      │
│                                                   │  Transición  Fundido ▾   │
│                                                   │  Entrada/Salida 00:00,0  │
├───────────────────────────────────────────────────┴──────────────────────────┤
│ FOOTER 44  [+ Importar medios]   ● Sin trabajos en cola   Ver chat  [Exportar 720p·30] │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Zona | Alto | Comportamiento al redimensionar |
|---|---|---|
| Header | 44 fijo | A 760 px: el chip de sesión pasa a icono + `Tip`. A 620 px: el título se acorta a "Editor". |
| Escenario | `flex:1`, mín. 180 | El marco 16:9 se centra con `aspect-ratio`; si el alto no da, se letterboxea sobre `--card` (nunca se recorta el vídeo). |
| Transporte | 34 fijo | El scrub es elástico; los timecodes nunca se ocultan. |
| Línea de tiempo | 118 (colapsable a 56) | Scroll horizontal propio; ancho de clip proporcional a duración. |
| Rail | 292 fijo | Bajo 860 px de ancho total del pane: el rail pasa a **sheet inferior** de 220 px con las propiedades (ver §5.7). |
| Footer | 44 fijo | "Ver chat" se oculta antes de "Exportar"; "Exportar" nunca se oculta. |

Rejilla: `display:grid; grid-template-columns: 1fr 292px; grid-template-rows: 44px 1fr 44px`, separadores de 1 px con `var(--ui-stroke-secondary)`. Densidad: `--pad:10px`, `--gap:8px`, radio 3 px (igual que `Button`/`control`), nunca `border-radius` de píldora.

---

## 3. Tokens y tema

**Regla dura:** cero colores literales. Ni en el plugin ni en la maqueta.

| Uso en el plugin | Variable SDK | Token del prelude `::preview` (maqueta) |
|---|---|---|
| Texto principal, cifras, títulos | `--ui-text-primary` | `--foreground` |
| Texto secundario, metadatos | `--ui-text-tertiary` | `--muted-foreground` |
| Acento (selección, playhead, primario) | `--ui-accent` | `--accent` |
| Hairlines, bordes de control | `--ui-stroke-secondary` / `--ui-stroke-tertiary` | `--border` |
| Superficie del pane | `--ui-bg-editor` (fondo del pane, no tocar) | `--card` |
| Rellenos suaves | `--ui-bg-quaternary`, `--ui-bg-tertiary`, `--chrome-action-hover` | `color-mix(in oklab, var(--foreground) 6%, transparent)` |

- El mapeo del prelude es el real del app: `--foreground→--ui-text-primary`, `--muted-foreground→--ui-text-tertiary`, `--accent→--ui-accent`, `--border→--ui-stroke-tertiary`, `--card→--ui-bg-editor`. Por eso la maqueta es representativa del pane real y **no** un tema inventado.
- En la maqueta los rellenos derivan con `color-mix()` de esos cinco tokens (no se introduce ni un hex). En el plugin se usan los `--ui-*` reales.
- El fondo del pane **no** se pinta: el pane ya está sobre el fondo del editor. Solo se pintan superficies internas (tarjetas de escena, marco del preview) con `--ui-bg-*`.
- Modo claro y oscuro salen gratis si se respeta lo anterior. Cualquier `#rrggbb` en el diff es un defecto de revisión.

---

## 4. Inventario de componentes

| Necesidad | Componente SDK (exportado, verificado) | Nota de uso |
|---|---|---|
| Acciones | `Button` | `variant`: `default` (Guardar/Exportar), `outline` (Importar), `ghost`/`text` (Ver chat), `destructive` (Cancelar exportación), `icon-sm`/`icon-xs` para iconos. |
| Campos de una línea | `Input` | `size="sm"`, `prefix`/`suffix` para unidades (`%`, `s`). |
| Texto de caption | `Textarea` | 2–4 filas, contador de caracteres. |
| Desplegables | `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem` | Transición, preajuste de exportación, proyecto. |
| Elección excluyente corta | `SegmentedControl` | Orientación horizontal/vertical; `sizing="content"`. |
| Interruptores | `Switch` | "Incluir subtítulos en el MP4". |
| Casilla | `Checkbox` | "Abrir el MP4 al terminar". |
| Pestañas | `Tabs`, `TabsList`, `TabsTrigger` | Solo si el rail crece (>360 px). **No existe `TabsContent` exportado**: el cuerpo se renderiza por estado. |
| Diálogo | `Dialog*` (`Content/Header/Title/Description/Footer`) | Exportación en curso, conflicto de revisión. **No existe `DialogClose`**: cerrar con `onOpenChange`. |
| Confirmación destructiva | `ConfirmDialog` | Cancelar exportación, borrar escena. |
| Menú contextual / desbordamiento | `DropdownMenu*`, `ContextMenu*` | Acciones de clip: duplicar, partir, eliminar, silenciar. |
| Globo de ayuda | `Tip` | Etiqueta de iconos y explicación de "Transición". |
| Estado / etiquetas | `Badge` (`default`, `muted`, `success`, `warn`, `destructive`, `outline`) | Revisión, estado de trabajo, "sin guardar". |
| Estado puntual | `StatusDot` (`good`, `muted`, `warn`, `bad`) | Autosave, cola. |
| Atajos | `Kbd`, `KbdGroup` | `KbdGroup keys={['Ctrl','Z']}`. |
| Buscar | `SearchField` | Buscar escena por texto (proyectos >12 escenas). |
| Lista con scroll | `ScrollArea` | Rail y línea de tiempo. |
| Separadores | `Separator` | Entre secciones del rail. |
| Carga | `Skeleton`, `GlyphSpinner`, `Loader` | Esqueletos de clip y de rail; spinners en el botón de exportar. |
| Vacíos / errores | `EmptyState` (solo `title`/`description`), `ErrorState` (`title`/`description`/`children`) | **`EmptyState` no acepta icono ni acción**: la acción se pone como hermano debajo. |
| Diagnóstico | `LogView` | Panel de registro del trabajo (colapsado). |
| Iconos | `icons.*` (lucide) o `Codicon` | Nunca emoji como icono de acción. |

**No usar** (no están en el SDK aunque existan en el app): `Slider`, `Progress`, `TabsContent`, `DialogClose`, `KbdCombo`, `RowButton` fuera del SDK, `SandboxedFrame` para el preview propio (el preview es un `<video>` del mismo origen, no contenido externo).

---

## 5. Controles, uno por uno

Formato: **control → componente** · comportamiento · datos · accesibilidad.

### 5.1 Cabecera (44 px)

| # | Control | Componente | Comportamiento |
|---|---|---|---|
| H1 | Título del pane | texto + `Codicon('film')` en placa tintada de acento | Fijo "Editor de vídeo". |
| H2 | Revisión | `Badge variant="outline" size="xs"` | "Rev 7" si hay proyecto; "Sin guardar" (`variant="warn"`) mientras haya cambios pendientes. `Tip`: "Revisión del documento del proyecto". |
| H3 | Selector de proyecto | `DropdownMenu*` con botón `variant="outline" size="sm"` | Lista los proyectos del contexto autorizado de la sesión + "Crear proyecto…". Cambiar de proyecto con cambios pendientes → `ConfirmDialog` ("Guardar y abrir" / "Descartar"). |
| H4 | Contexto de sesión | chip no interactivo + `Tip` | `Sesión 4f2a · video-editor`: `host.state.activeSessionId` abreviado a 4 caracteres + `basename(host.state.cwd)` (`'(sin carpeta)'` si `cwd === ''`). `Tip` muestra el `cwd` completo. Si `activeSessionId === null`: "Sesión nueva · <cwd>". **Nunca** se envía el proyecto entero por estar en una sesión: la vinculación es explícita (H3) y se muestra. |
| H5 | Autosave | `StatusDot` + texto 11 px, en `aria-live="polite"` | `good` + "Guardado hace 12 s" · `warn` + "Guardando…" · `bad` + "No se pudo guardar" (con `Button variant="text"` "Reintentar"). Tiempo relativo con `relativeTime()` del SDK. |
| H6 | Deshacer / Rehacer | `Button variant="ghost" size="icon-sm"` ×2 | Habilitados según la pila. `aria-label` + `Tip` con el atajo. |
| H7 | Guardar | `Button variant="default" size="sm"` | Deshabilitado si no hay cambios; "Guardando…" mientras; nunca dos guardados en paralelo. |
| H8 | Más acciones | `Button variant="ghost" size="icon-sm"` + `DropdownMenu` | "Abrir carpeta del proyecto" (`ctx.os.revealPath`), "Copiar ruta", "Ver registro del trabajo", "Volver al chat". |

Atajos de cabecera: `Ctrl+S` guardar · `Ctrl+Z` / `Ctrl+Shift+Z` · `Ctrl+O` abrir proyecto.

### 5.2 Importación

| # | Control | Componente | Comportamiento |
|---|---|---|---|
| I1 | Botón importar | `Button variant="outline" size="sm"` + icono | Abre el flujo de importación (§5.2.1). Etiqueta "Importar medios". |
| I2 | Zona de arrastre | contenedor con `border: 1px dashed var(--ui-stroke-secondary)` | Activa `dragover` **solo** dentro del pane; overlay de 2 px de acento + texto "Suelta para importar". Acepta `image/png`, `image/jpeg`, `video/mp4`, `video/quicktime`, `audio/mpeg`, `audio/wav`. Rechaza el resto con `Badge variant="destructive"` "Formato no admitido: .gif". `Drop` del SO en Electron: `e.preventDefault()` obligatorio. |
| I3 | Progreso de subida | barra 4 px + texto | Por archivo: "Subiendo demo.mp4 · 42 %". Un archivo a la vez; el resto queda "En cola". |

#### 5.2.1 Flujo de archivos (incógnita del spike, resuelta con API soportada)

El pane **no** puede asumir que `<input type="file">` le dé una ruta usable. Camino soportado, en este orden:

1. **Arrastrar y soltar** sobre el pane: `DataTransfer.files[i]` → `await file.arrayBuffer()` → `ctx.rest('/projects/<id>/media', { method:'POST', upload:{ filename, contentType: file.type, bytes } })`. `upload.bytes` es `ArrayBuffer` (firma real de `PluginRestOptions`), así que no hace falta ruta local.
2. **Botón "Importar medios"** → `ctx.files.requestFolder()` (picker del propio app, con consentimiento y lista de concesiones). Devuelve `{ folder }` o `null` al cancelar; luego `ctx.files.list(folder.id)` → `Dialog` con la lista de medios (nombre, tamaño, tipo), selección múltiple y "Importar seleccionados". El backend recibe el `path` relativo y lee el archivo, o se sube vía `upload` si el archivo es pequeño.
3. Si `ctx.files` devuelve `{ ok:false, error:'protected' }` (carpeta con datos de Hermes): mensaje "Esa carpeta contiene datos de Hermes y no se puede usar como medios." Nada de forzar.

Nunca se envía "el proyecto entero": cada archivo se autoriza explícitamente (criterio U1).

### 5.3 Escenario (preview)

| # | Control | Componente | Comportamiento |
|---|---|---|---|
| P1 | Marco de vídeo | `<video>` nativo dentro de un contenedor `aspect-ratio` | Fuente: `GET /api/plugins/video-editor/media/<id>/preview` (proxy 540p del backend). `muted` por defecto en el primer arranque (política de autoplay), con botón de volumen. `poster` = primer fotograma si el backend lo sirve. |
| P2 | Caption overlay | capa absoluta, `bottom: 8%`, ancho máx. 82 % | Refleja el texto de la escena seleccionada en el tiempo actual. Fondo `color-mix(in oklab, var(--ui-bg-editor) 72%, transparent)` + texto `--ui-text-primary` 13 px. Es **preview**, no editable aquí (se edita en el rail). |
| P3 | Etiqueta de calidad | `Badge variant="muted" size="xs"` | "Preview 540p" — para que nadie confunda preview con export. |
| P4 | Guías | `Switch` en el menú `⋯` | "Mostrar guías de zona segura". Persistido en `ctx.storage`. |
| P5 | Sin medios | `EmptyState` dentro del marco | "Aquí verás tu vídeo" / "Importa un clip para empezar." |
| P6 | Cargando el preview | `Skeleton` + `GlyphSpinner` | "Preparando la vista previa…". Nunca un `poster` falso. |

El `<video>` no decodifica el archivo original si el backend sirve proxy: así el scrub es fluido y el original queda intacto (plan: originales protegidos).

### 5.4 Transporte y scrub (34 px)

| # | Control | Componente | Comportamiento |
|---|---|---|---|
| T1 | Ir al inicio / anterior / play / siguiente / fin | `Button variant="ghost" size="icon-sm"` (5) | Play ⇄ Pausa con icono y `aria-label` que cambia ("Reproducir"/"Pausar"). Anterior/siguiente = escena previa/siguiente. |
| T2 | Timecode | texto monoespaciado 11 px, `tabular-nums` | `00:03,4 / 00:16,2` (coma decimal es-ES). `Tip`: "Posición / duración total". |
| T3 | Scrub | **`<input type="range">` nativo** estilizado | Pasos finos de 1/30 s; `aria-label="Posición de reproducción"`, `aria-valuetext="00:03,4 de 00:16,2"`. Durante el arrastre: `pointerdown` pausa, `pointerup` reanuda si estaba reproduciendo. |
| T4 | Partir en el cursor | `Button variant="ghost" size="icon-sm"` + icono tijera | Divide la escena en la posición actual (mín. 0,3 s por lado). Si no se puede: `Tip` "Coloca el cursor a más de 0,3 s del borde". |
| T5 | Recortar al cursor | dos botones `icon-sm` | "Fijar entrada en el cursor", "Fijar salida en el cursor". |
| T6 | Volumen maestro | icono + `<input type="range">` 72 px | 0–100 %, paso 5, con `aria-valuetext="80 %"`. Persistido por proyecto. |

**Slider:** el app tiene un `Slider` interno, pero **no está exportado por `@hermes/plugin-sdk`**. Por eso scrub y volumen usan `<input type="range">` nativo con `accent-color: var(--ui-accent)` y altura de toque ≥32 px. Es control HTML permitido, accesible de fábrica (flechas, Home/End) y tematizado. Si el SDK exporta `Slider` en el futuro, se sustituye sin cambiar el diseño.

### 5.5 Escenas (rail, sección superior)

| # | Control | Componente | Comportamiento |
|---|---|---|---|
| S1 | Cabecera | texto 11 px mayúsculas + `Badge variant="muted"` con el número | "ESCENAS · 4". |
| S2 | Buscar escena | `SearchField` | Visible con >12 escenas; filtra por nombre y texto de caption. |
| S3 | Fila de escena | botón de fila (`<button>`) 36 px: nº mono, miniatura 40×23, nombre, duración | Clic selecciona y hace seek al inicio de la escena. `aria-current="true"` en la seleccionada. |
| S4 | Subir / bajar | `Button variant="ghost" size="icon-xs"` (32 px de caja) ×2 | Reordena **y anuncia** por `aria-live`: "Escena 2 movida a la posición 1". Deshabilitados en los extremos. |
| S5 | Arrastrar para reordenar | drag nativo en la fila y en el clip | Región de inserción de 2 px de acento entre filas; `Esc` cancela el arrastre. El reordenar por botones es el camino equivalente obligatorio (WCAG 2.5.7). |
| S6 | Menú de escena | `DropdownMenu` (clic derecho = `ContextMenu`) | Duplicar, Partir aquí, Silenciar, Eliminar. |
| S7 | Añadir escena | `Button variant="outline" size="sm"` a ancho completo | Crea una escena con el último medio seleccionado; si no hay, abre el flujo de importación. |
| S8 | Eliminar escena | `ConfirmDialog destructive` | Solo si es la última o tiene caption: "¿Eliminar «Demo producto»? Se puede deshacer con Ctrl+Z." |

### 5.6 Línea de tiempo (118 px)

| # | Control | Componente | Comportamiento |
|---|---|---|---|
| L1 | Regla | canvas/DOM con marcas cada 1 s y etiquetas cada 5 s | Unidades en segundos; a zoom bajo, etiquetas cada 10 s. |
| L2 | Clip | contenedor `role="listitem"` con nombre + duración + miniaturas | Ancho = `duración / total`. Borde 1 px `--ui-stroke-secondary`; seleccionado: 2 px `--ui-accent` + relleno `color-mix(accent 10%)`. |
| L3 | Playhead | línea 1 px de acento + triángulo superior | `pointer-events:none`; posición = `currentTime / total`. |
| L4 | Manijas de recorte | 3 px en los bordes del clip seleccionado, cursor `ew-resize` | Arrastrar ajusta entrada/salida con límite de 0,3 s; el valor se muestra en el rail y en un `Tip` flotante "00:01,8". |
| L5 | Pista de audio | franja 22 px con forma de onda | "A1 · Voz". Si no hay audio: "Sin audio" en `--ui-text-tertiary`. |
| L6 | Zoom | `SegmentedControl` ["Ajustar", "1×", "2×"] o `−/+` | "Ajustar" por defecto. |
| L7 | Scroll | `ScrollArea` horizontal | Rueda = scroll horizontal con `Shift`; nunca zoom accidental por rueda. |
| L8 | Cursor | clic en cualquier punto del track | Mueve el cursor y hace seek; `aria-label="Línea de tiempo, 16,2 segundos"`. |

El track completo es foco-able (`tabindex="0"`); flechas mueven el cursor 1 fotograma, `Shift+flecha` 1 s. Nada se hace **solo** con arrastre.

### 5.7 Propiedades (rail, sección inferior)

| # | Control | Componente | Comportamiento y datos |
|---|---|---|---|
| R1 | Cabecera | texto + `Badge variant="outline"` | "PROPIEDADES · Escena 2". |
| R2 | Texto en pantalla | `Textarea` `size="sm"` (2–4 filas) + contador | Valor del caption de la escena. Máx. 90 caracteres; contador "52/90" en `--ui-text-tertiary` y `aria-describedby`. Acentos y `ñ` se guardan tal cual (UTF-8, sin normalizar). `Enter` inserta salto de línea; el salto **no** se exporta (el backend lo aplana con espacio). Debounce 400 ms → autosave. |
| R3 | Volumen de la escena | `<input type="range">` + `Input size="sm"` numérico con `suffix="%"` | 0–100, paso 5. Escribir en el número mueve el rango y viceversa. `Switch` "Silenciar escena" al lado. |
| R4 | Orientación | `SegmentedControl` `[{id:'h',label:'Horizontal'},{id:'v',label:'Vertical'}]` | Cambia relación de aspecto del preview (16:9 ⇄ 9:16) y el `crop/fit` del export. Texto de ayuda bajo el control: "Vertical recorta los bordes laterales." |
| R5 | Transición | `Select` con 3 opciones | "Sin transición", "Fundido · 0,3 s", "Fundido · 0,5 s". Limitada a propósito (MVP). Deshabilitado en la primera escena con `Tip` "La primera escena no tiene transición de entrada". |
| R6 | Entrada / Salida | dos `Input size="sm"` con `prefix` reloj, formato `mm:ss,d` | Editable; valida salida > entrada + 0,3 s. Error inline `aria-invalid` + texto "La salida debe ser al menos 0,3 s después de la entrada." Nunca se corrige en silencio. |
| R7 | Duración de la escena | texto calculado | "5,6 s" en `--ui-text-tertiary`, no editable directamente. |
| R8 | Restablecer | `Button variant="text" size="xs"` | Vuelve a los valores del clip original; entra en la pila de undo. |
| R9 | Sin selección | `EmptyState` | "Elige una escena" / "Selecciona una escena de la lista o de la línea de tiempo para editar su texto, volumen y encuadre." |

**Por qué no `Tabs` en el rail (decisión):** a 292 px, ocultar la lista de escenas tras una pestaña obliga a saltar entre "ver" y "editar" en cada cambio. El rail apilado muestra el modelo de una vez. `Tabs` queda especificado para el caso ancho (>360 px de rail o pane a pantalla completa), con el mismo contenido en dos paneles y `value`/`onValueChange` propios (el cuerpo se renderiza condicionalmente porque el SDK no exporta `TabsContent`).

**Sheet inferior (<860 px de ancho de pane):** propiedades en un panel de 220 px con tirador, manteniendo el preview visible. No se reordena el modelo, solo la presentación.

### 5.8 Exportación

| # | Control | Componente | Comportamiento |
|---|---|---|---|
| E1 | Exportar | `Button variant="default" size="sm"` + icono | "Exportar 720p · 30". Deshabilitado si: no hay escenas, hay subida en curso, o falta un medio (`Badge variant="warn"` "Falta 1 medio" con enlace "Volver a vincular"). |
| E2 | Diálogo de exportación | `Dialog` + `DialogHeader/Title/Description/Footer` | Título "Exportar vídeo". Resumen: "16,2 s · 720p · 30 fps · MP4 (H.264 + AAC)" + `Switch` "Incluir subtítulos" + `Checkbox` "Abrir el MP4 al terminar". Botones "Cancelar" y "Exportar". |
| E3 | Progreso por etapa | lista de 4 etapas + barra 4 px + `aria-live="polite"` | Etapas reales: **Preparando** → **Renderizando** → **Mezclando audio** → **Escribiendo MP4**. Cada etapa: pendiente (punto `muted`), activa (`GlyphSpinner` + % real del backend), hecha (`Codicon('check')` en acento). El porcentaje **solo** se pinta si el backend lo da; si no: "Trabajando…" sin cifra. Sin ETA inventada: se muestra `eta_s` si existe, si no "Calculando tiempo…" y luego nada. |
| E4 | Cancelar | `Button variant="outline"` | "Cancelar exportación" → `ConfirmDialog` "¿Cancelar la exportación? Se descarta el MP4 parcial." Acción del backend `POST /jobs/<id>/cancel`; la UI muestra "Cancelando…" hasta el estado terminal real (no cierra el diálogo antes). |
| E5 | Terminado | mismo diálogo, estado final | "Listo · video-2026-11-08-720p.mp4" + tamaño; botones "Reproducir" (`ctx.os.openExternal('file://…')` o `revealPath`), "Volver al chat". |
| E6 | Fallo | `ErrorState` dentro del diálogo | "La exportación falló" / mensaje del backend + "Reintentar" (nuevo job, sin duplicar) y "Ver registro" (`LogView`). |
| E7 | Volver al chat | `Button variant="text"` en footer y en el estado final | `host.navigate('/chat')`; si el pane está en `main`, vuelve al chat conservando la sesión. No se envía nada a ningún servicio externo (U4: "sin publicación externa"). |
| E8 | Cola | `StatusDot` + texto en footer | `muted` "Sin trabajos en cola" · activo "Exportando 38 %" · `warn` "Trabajo en pausa" · `bad` "Exportación falló". Un solo job visible; si hubiera más, "1 en cola". |

**Pausa:** el plan la condiciona a que el motor la soporte en punto seguro. La UI **no** expone "Pausar" en el MVP; si el backend la habilita, aparece junto a Cancelar con el texto "Pausar al terminar la etapa". No se dibuja un botón deshabilitado permanente.

### 5.9 Footer (44 px)

| # | Control | Componente |
|---|---|---|
| F1 | Importar medios | `Button variant="outline" size="sm"` |
| F2 | Estado de cola | `StatusDot` + texto 11 px (`aria-live="polite"`) |
| F3 | Ayuda | `Button variant="ghost" size="icon-sm"` con `Tip`: "Arrastra archivos al panel o pulsa Importar medios. PNG, JPG, MP4, MOV, MP3 y WAV." |
| F4 | Volver al chat | `Button variant="text"` |
| F5 | Exportar | `Button variant="default" size="sm"` |

---

## 6. Datos y contratos

### 6.1 Contexto (lectura, reactivo)

| Dato | Origen | Uso |
|---|---|---|
| `activeSessionId` | `host.state.activeSessionId` (átomo, `null` en borrador) | Chip de sesión; clave de los proyectos de la sesión; `session_id` al crear proyecto. |
| `cwd` | `host.state.cwd` (`''` si está desacoplado) | Raíz sugerida para `ctx.files`; chip de contexto. |
| `profile` | `host.state.profile` | Se pasa al backend para no mezclar perfiles. |
| `viewport` | `host.state.viewport` | Decide rail vs sheet inferior (no `window.innerWidth`). |
| Ancho del pane | `ResizeObserver` sobre el contenedor | Modo compacto; **obligatorio** para cualquier canvas de la línea de tiempo. |

Se leen con `useValue` **en la hoja que los pinta**; en handlers, `$atom.get()` (nunca el valor de un cierre).

### 6.2 Modelo de documento (propuesta para Athena/Hephaestus)

```jsonc
{
  "project_id": "prj_01",
  "session_id": "sess_4f2a",
  "cwd": "C:/Users/EgtYP/proyectos/lanzamiento-q4",
  "title": "Lanzamiento Q4",
  "revision": 7,
  "orientation": "h",                 // h | v
  "audio": { "master_volume": 80 },
  "scenes": [
    {
      "id": "sc_01",
      "media_id": "md_01",
      "name": "Intro",
      "in": 0.0, "out": 3.2,          // segundos, > 0.3 de margen
      "caption": "Exporta en 720p y vuelve al chat con el MP4 listo.",
      "volume": 80,
      "muted": false,
      "transition": "none"            // none | fade-0.3 | fade-0.5
    }
  ],
  "updated_at": "2026-11-08T18:42:10-04:00"
}
```

### 6.3 Endpoints (`ctx.rest`, namespace del plugin)

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/projects?session=<id>&cwd=<path>` | Lista para H3. |
| `POST` | `/projects` | Crear (`{session_id, cwd, title}`). |
| `GET` | `/projects/<id>` | Documento + `revision` + medios. |
| `PUT` | `/projects/<id>` | Guardar `{revision, draft}`; **409** con `{current_revision}` si hay conflicto. |
| `POST` | `/projects/<id>/media` | Importar (`upload: {filename, contentType, bytes}`) o `{folder_id, path}`. |
| `GET` | `/media/<id>/preview` | Proxy 540p para `<video>` (rango). |
| `POST` | `/projects/<id>/export` | `{preset:'mp4-720p30', captions:true}` → `{job_id}`. |
| `GET` | `/jobs/<id>` | `{state, stage, pct?, eta_s?, output_path?}`. |
| `POST` | `/jobs/<id>/cancel` | Cancelación cooperativa. |
| `GET` | `/events` (`ctx.socket`) | Empuje de progreso; **con fallback de sondeo cada 3 s** (`ctx.socket` es no-op en remotos OAuth). |

Reglas: autosave 4 s tras el último cambio de texto, y siempre al perder el foco del campo; guardado optimista **no** (se muestra "Guardando…" y se confirma con la `revision` devuelta). Un 409 abre el diálogo de conflicto: "Hay una revisión más nueva (Rev 8)" con "Recargar y perder mis cambios" (`destructive`, `secondaryAction` "Guardar como copia") — nunca se sobrescribe en silencio (U3).

### 6.4 Preferencias de vista (`ctx.storage`)

`pane.width`, `preview.guides`, `transport.muted`, `lastProjectId`, `export.openWhenDone`. Nada de estado del documento en storage.

---

## 7. Estados (y su copy exacto)

| Estado | Disparador | Qué se pinta |
|---|---|---|
| **A · Sin proyecto** | no hay `lastProjectId` válido | Header con "Sin proyecto" + `EmptyState` "Todavía no hay proyecto abierto" / "Elige un proyecto de esta sesión o crea uno nuevo para montar tu vídeo." + botones "Elegir proyecto" (outline) y "Crear proyecto" (default). Escenario vacío, rail vacío, footer con "Importar" deshabilitado y `Tip` "Abre un proyecto primero". |
| **B · Proyecto sin medios** | `scenes.length === 0` | Escenario con dropzone (borde discontinuo, 180 px) "Arrastra clips, audio o capturas aquí" + `Button` "Importar medios"; rail con `EmptyState` "Sin escenas" / "Añade un clip para crear la primera escena."; footer "Exportar" deshabilitado con `Tip` "Añade al menos una escena". |
| **C · Cargando** | carga inicial o cambio de proyecto | `Skeleton` del escenario 16:9, 3 filas de escena, 2 campos del rail; `GlyphSpinner` + "Cargando proyecto…" en `aria-live="polite"`. Timecodes como `--:--`. Nunca datos de ejemplo mientras carga. |
| **D · Error de carga** | `ctx.rest` falla o 5xx | `ErrorState` "No se pudo cargar el proyecto" / "El servicio del editor no respondió. Tus medios no se han modificado." + `Button` "Reintentar" + `Button variant="outline"` "Ver registro" (`LogView`) + `Button variant="text"` "Volver al chat". Header conserva el proyecto con `Badge variant="destructive"` "Sin conexión". |
| **E · Edición** | proyecto cargado | Layout completo de §2. |
| **F · Exportando** | job activo | Diálogo §5.8 con etapas reales; detrás, el pane atenuado y no interactivo (`aria-busy="true"`), pero **la reproducción sigue funcionando** si el usuario cierra el diálogo. |
| **G · Conflicto de revisión** | `PUT` → 409 | `Dialog` "Hay cambios más nuevos" / "La revisión 8 se guardó en otro lugar. Tu copia es la 7." + "Recargar (perder mis cambios)" destructivo, "Guardar como copia" (`secondaryAction`), "Cancelar". |
| **H · Medio faltante** | `media.missing === true` | `Badge variant="warn"` "Falta demo.mp4" en la fila de escena + `Button variant="text"` "Volver a vincular" (abre `ctx.files` y reasigna). El export queda bloqueado hasta resolverlo. |

---

## 8. Textos (es-ES, listos para copiar)

| Clave | Texto |
|---|---|
| `pane.title` | Editor de vídeo |
| `header.project.none` | Sin proyecto |
| `header.session` | Sesión {id} · {cwd} |
| `header.autosave.saved` | Guardado hace {tiempo} |
| `header.autosave.saving` | Guardando… |
| `header.autosave.failed` | No se pudo guardar |
| `header.retry` | Reintentar |
| `action.save` | Guardar |
| `action.undo` | Deshacer |
| `action.redo` | Rehacer |
| `action.import` | Importar medios |
| `action.export` | Exportar 720p · 30 |
| `action.backToChat` | Volver al chat |
| `action.cancel` | Cancelar |
| `transport.play` / `pause` | Reproducir / Pausar |
| `transport.prevScene` / `nextScene` | Escena anterior / Escena siguiente |
| `transport.split` | Partir en el cursor |
| `timeline.caption` | Línea de tiempo, {n} segundos |
| `scenes.header` | Escenas |
| `scenes.add` | Añadir escena |
| `scenes.moveUp` / `moveDown` | Subir escena / Bajar escena |
| `scenes.moved` | Escena {n} movida a la posición {m} |
| `scenes.delete.confirm` | ¿Eliminar «{nombre}»? Se puede deshacer con Ctrl+Z. |
| `props.header` | Propiedades |
| `props.caption.label` | Texto en pantalla |
| `props.caption.hint` | Se muestra al inicio de la escena. |
| `props.volume` | Volumen |
| `props.mute` | Silenciar escena |
| `props.orientation` | Orientación |
| `props.orientation.h` / `.v` | Horizontal / Vertical |
| `props.orientation.hint` | Vertical recorta los bordes laterales. |
| `props.transition` | Transición |
| `props.transition.none` | Sin transición |
| `props.transition.fade03` | Fundido · 0,3 s |
| `props.transition.fade05` | Fundido · 0,5 s |
| `props.in` / `props.out` | Entrada / Salida |
| `props.trim.invalid` | La salida debe ser al menos 0,3 s después de la entrada. |
| `props.reset` | Restablecer escena |
| `props.empty.title` | Elige una escena |
| `props.empty.body` | Selecciona una escena de la lista o de la línea de tiempo para editar su texto, volumen y encuadre. |
| `empty.noProject.title` | Todavía no hay proyecto abierto |
| `empty.noProject.body` | Elige un proyecto de esta sesión o crea uno nuevo para montar tu vídeo. |
| `empty.noMedia.title` | Sin escenas |
| `empty.noMedia.body` | Añade un clip para crear la primera escena. |
| `dropzone.idle` | Arrastra clips, audio o capturas aquí |
| `dropzone.active` | Suelta para importar |
| `dropzone.unsupported` | Formato no admitido: {ext} |
| `dropzone.protected` | Esa carpeta contiene datos de Hermes y no se puede usar como medios. |
| `loading.project` | Cargando proyecto… |
| `loading.preview` | Preparando la vista previa… |
| `error.load.title` | No se pudo cargar el proyecto |
| `error.load.body` | El servicio del editor no respondió. Tus medios no se han modificado. |
| `error.export.title` | La exportación falló |
| `error.export.retry` | Reintentar exportación |
| `error.viewLog` | Ver registro |
| `export.dialog.title` | Exportar vídeo |
| `export.summary` | {duración} s · 720p · 30 fps · MP4 (H.264 + AAC) |
| `export.captions` | Incluir subtítulos |
| `export.openWhenDone` | Abrir el MP4 al terminar |
| `export.stage.prepare` | Preparando |
| `export.stage.render` | Renderizando |
| `export.stage.mux` | Mezclando audio |
| `export.stage.write` | Escribiendo MP4 |
| `export.cancel` | Cancelar exportación |
| `export.cancel.confirm` | ¿Cancelar la exportación? Se descarta el MP4 parcial. |
| `export.done` | Listo · {archivo} |
| `export.eta.pending` | Calculando tiempo… |
| `export.play` | Reproducir |
| `conflict.title` | Hay cambios más nuevos |
| `conflict.body` | La revisión {nueva} se guardó en otro lugar. Tu copia es la {mía}. |
| `conflict.reload` | Recargar y perder mis cambios |
| `conflict.saveCopy` | Guardar como copia |
| `queue.idle` | Sin trabajos en cola |
| `queue.running` | Exportando {pct} % |
| `queue.failed` | La exportación falló |
| `missing.badge` | Falta {archivo} |
| `missing.relink` | Volver a vincular |

Registro i18n: `ctx.i18n.register({ es: {...}, en: {...} })` con `es` como idioma primario del proyecto; `usePluginI18n('video-editor')` en componentes y `translateNow` para el `title` del pane (se lee al registrar). Nunca concatenar género: usar frases completas.

---

## 9. Atajos

Alcance **del pane** (no global): listener en el contenedor raíz, activo solo si el pane o un hijo tiene el foco. Guard: si `event.target` es `input`, `textarea`, `select` o `[contenteditable]`, **solo** pasan `Ctrl/⌘` combos; nunca `Espacio`.

| Tecla | Acción |
|---|---|
| `Espacio` | Reproducir / pausar |
| `←` / `→` | −/+ 1 fotograma (1/30 s) |
| `Shift+←` / `Shift+→` | −/+ 1 s |
| `Inicio` / `Fin` | Ir al inicio / al final |
| `I` / `O` | Fijar entrada / salida en el cursor |
| `S` | Partir en el cursor |
| `Alt+↑` / `Alt+↓` | Subir / bajar la escena seleccionada |
| `Supr` | Eliminar la escena seleccionada (con confirmación) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Deshacer / rehacer |
| `Ctrl+S` | Guardar |
| `Ctrl+E` | Abrir el diálogo de exportación |
| `Esc` | Cerrar diálogo / quitar selección |

En mac se muestra `⌘` en el `KbdGroup` (detección de plataforma en un helper; el código usa `metaKey || ctrlKey`).
`Esc` dentro de un diálogo lo gestiona Radix; no duplicar el handler.
No se registra nada en `KEYBINDS_AREA`: robar `Espacio` a la app sería un defecto.

---

## 10. Accesibilidad (objetivo WCAG 2.2 AA)

**Contraste**
- Texto normal (12–13 px): `--ui-text-primary` sobre `--ui-bg-editor`/`--ui-bg-quaternary` ≥ 4.5:1; `--ui-text-tertiary` solo para metadatos ≥ 4.5:1 comprobado, nunca para texto crítico en 11 px sin verificar.
- Bordes de control interactivo: `--ui-stroke-secondary` (si no llega a 3:1, subir a `--ui-text-tertiary` al 40 %).
- **Prueba automatizada obligatoria:** `contrastRatio()` del SDK sobre los pares reales en tema claro y oscuro, en un test del plugin. Un par por debajo de 4.5 falla el build. Sin esto, "AA" es una afirmación sin evidencia.

**Foco y teclado**
- Foco visible en todo control (anillo del app en `Button`/`Input`; en elementos propios: `outline: 2px solid var(--ui-accent); outline-offset: 2px`).
- Orden de tabulación: header → escenario/transporte → línea de tiempo → rail → footer. Sin `tabindex` positivos.
- Foco atrapado en `Dialog` (Radix) y devuelto al disparador al cerrar.
- Todo el flujo U1–U4 se completa con teclado: reordenar (`Alt+↑/↓`), recortar (campos + `I`/`O`), partir (`S`), cambiar texto (tab + escribir), exportar (`Ctrl+E`, tab, `Enter`).

**Tamaño de objetivo**
- Mínimo 32×32 px en punteros finos (todo `icon-sm` = 32 px; botones de texto `size="sm"` = 32 px de alto). En punteros gruesos o pane estrecho, `size="touch"` (44 px) en el transporte.
- Separación ≥4 px entre acciones contiguas; las manijas de recorte tienen zona de agarre de 8 px aunque se pinten de 3 px.

**Semántica**
- Iconos con `aria-label` propio (`Button` sin texto ⇒ `aria-label` obligatorio) + `Tip` como ayuda, nunca como etiqueta única.
- `aria-live="polite"` en: autosave, progreso de exportación, reordenación de escenas, error de validación de tiempo. Un solo `role="status"` por región para no solapar locuciones.
- Línea de tiempo: `role="list"` de escenas; el nombre accesible de cada clip incluye número, nombre y duración ("Escena 2, Demo producto, 5,6 segundos"). El scrub es `input[type=range]` con `aria-valuetext` en tiempo legible.
- `aria-busy="true"` en el pane durante la carga y en la región de exportación mientras corre el job.
- `lang="es"` en el contenedor del pane (evita que un lector pronuncie "Exportar" en inglés).

**Movimiento**
- Transiciones ≤120 ms, solo color/opacidad. `prefers-reduced-motion: reduce` → sin transiciones ni pulsos (el `GlyphSpinner` se sustituye por texto de etapa).
- Nada de movimiento automático en bucle en la UI (el playhead solo se mueve cuando hay reproducción real).

---

## 11. Pruebas visuales y de aceptación

| # | Prueba | Cómo se comprueba | Evidencia |
|---|---|---|---|
| V1 | Maqueta abre con `::preview` | Mensaje con `::preview{file="…/docs/mockup.html"}`, o panel de vista previa | Captura de los 6 estados |
| V2 | Tokens | Inspeccionar el pane en tema claro y oscuro; buscar `#`/`rgb(` en el CSS del plugin (0 resultados) | 2 capturas + `grep` |
| V3 | Responsive | 900×560, 760×520, 620×420, pane a pantalla completa; y rail→sheet al estrechar | 4 capturas |
| V4 | Estados | forzar A–H (sin red, sin medios, job fallido, 409, proxy caído) | 1 captura por estado |
| V5 | Contraste | test con `contrastRatio()` claro/oscuro en CI | salida del test |
| V6 | Teclado | recorrido U2 completo sin ratón (reordenar, recortar, partir, texto, exportar) | grabación corta |
| V7 | Carga | verificar que no hay porcentajes ni duraciones de ejemplo durante la carga | captura del estado C |
| V8 | Undo | una edición de cada tipo y `Ctrl+Z` recupera el valor anterior (U2) | checklist firmado |

Criterio de "listo para revisión": V1–V8 en verde y las Decisiones de §12 resueltas o aceptadas por escrito.

---

## 12. Decisiones necesarias (para Tormen / Athena / Hephaestus)

1. **Slider no exportado.** El app tiene `Slider` interno pero el SDK solo exporta la lista de §4. Se usa `<input type="range">` nativo con `accent-color: var(--ui-accent)`. *Coste:* 0. *Alternativa:* añadir `Slider` al SDK (decisión de Hermes, no de este plugin).
2. **`Progress` no exportado.** Barra propia de 4 px con `role="progressbar"`/`aria-valuenow`. *Coste:* 0.
3. **Selección de archivos.** Propuesta: drag&drop con `upload` + `ctx.files.requestFolder()` (picker del app). Falta que el spike F1 confirme que el drop de Electron entrega `File` con `arrayBuffer()` utilizable y que `upload` acepta archivos >100 MB. Si falla: importar por carpeta concedida y ruta.
4. **Preview dentro del pane.** Depende de que el renderer pueda cargar `/api/plugins/video-editor/media/<id>/preview` en un `<video>` (CSP/red, incógnita 2 del spike). Si no: `ctx.files.readDataUrl` solo sirve ≤16 MiB → no vale para clips; habría que servir por el gateway y abrir el preview en el navegador integrado. **Bloquea P1/P6.**
5. **`placement: 'main'`.** Requiere que el área `main` exista y admita panes en la versión instalada. Si no, degradación explícita (§1).
6. **Split como esencial.** El plan lo condiciona al ensayo. La UI lo incluye; si se retira, desaparecen T4, `S` y la acción del menú sin afectar al resto.
7. **Pausa de exportación.** No se expone hasta que el motor la garantice en punto seguro.
8. **Transiciones.** Tres opciones fijas. Ampliarlas exige consenso con el motor (un solo renderer, sin dos motores).
9. **Ancho del rail.** 292 px fijos con sheet inferior bajo 860 px; si el diseño de producto quiere rail redimensionable, entra en la misma preferencia `pane.width` (fuera del MVP).
10. **Idioma.** `es` primario y `en` mínimo en el registro i18n. Textos de backend (mensajes de FFmpeg) se muestran crudos en `LogView`, nunca como copy de usuario.

---

## 13. Handoff a Hephaestus (orden de implementación)

1. Esqueleto del pane con `Data `de §2 + tokens, y los estados A/C/D (sin backend real, con datos inyectados por props).
2. Documento + `GET /projects/<id>` + autosave/`PUT` (B/E, badges de revisión, 409 → G).
3. Importación (drag&drop + `ctx.files`) → B desaparece.
4. Escenas: lista, ▲▼, selección, reordenar por arrastre (S1–S8) con anuncios `aria-live`.
5. Línea de tiempo + transporte + scrub + recorte + split (L1–L8, T1–T6).
6. Propiedades (R1–R9) y su validación.
7. Exportación: diálogo, etapas, cancelar, terminar, fallo (E1–E8, F).
8. Accesibilidad y pruebas V1–V8; capturas en `docs/evidencia/`.

**No** incluye: código del backend/cola (Athena), decisión de motor (Tormen), publicación (nadie sin OK).

---

### Anexo · Mapa maqueta ↔ componente real

| En `mockup.html` | En el plugin |
|---|---|
| `.btn--primary` | `Button variant="default" size="sm"` |
| `.btn--outline` | `Button variant="outline" size="sm"` |
| `.btn--ghost.btn--icon` | `Button variant="ghost" size="icon-sm"` |
| `.field` | `Input size="sm"` |
| `.textarea` | `Textarea size="sm"` |
| `.seg` | `SegmentedControl` |
| `.select` | `Select` + `SelectTrigger` |
| `.badge` | `Badge` |
| `.dot` | `StatusDot` |
| `.kbd` | `Kbd` |
| `.tabs` | `Tabs`/`TabsList`/`TabsTrigger` |
| `.dialog` / `.dialog__scrim` | `Dialog` + `DialogContent` |
| `.skeleton` | `Skeleton` |
| `.spinner` | `GlyphSpinner` |
| barra de exportación | `<div role="progressbar">` propio |
| pista de la línea de tiempo | DOM propio con `ScrollArea` |
