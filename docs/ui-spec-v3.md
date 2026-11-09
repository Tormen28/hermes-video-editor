# UI Spec v3 · Editor de vídeo (pane de Hermes)

Estado: **vigente** · 2026-11-08 · Harmonia
Alcance: la maqueta `docs/mockup-v3.html` (11 estados, 1440×900) es la referencia visual **y métrica** de este documento. Todo lo que aquí se mide está medido en el navegador sobre esa maqueta, no estimado.
Sustituye a `docs/ui-spec-rev2.md` en medidas, tipografía, inventario de componentes y contrato de datos. Rev2 sigue siendo válido en el análisis de producto (§5 permisos, §12 decisiones).

---

## 0 · Reglas de la v3

1. **Un solo dueño del dato**: el documento del proyecto vive en el servicio (`GET /projects/<id>` → `project`). El pane no guarda copia propia ni inventa campos. `ui` es adaptador de pintado, no fuente de verdad (`core/CONTRATO.md` §4).
2. **Nada se enseña que no exista**: si el dato no está en el contrato, el control se pinta **deshabilitado con la etiqueta «requiere backend»** (`gratis` = 0). Ejemplos vivos: tamaño y familia del texto.
3. **Placeholder declarado**: las miniaturas y la onda de la maqueta son **de ejemplo**. Llevan la marca «sin fotograma» y una nota al pie. Ver §7.
4. **Timecodes**: todo valor de tiempo de la secuencia o del medio se escribe `HH:MM:SS:FF` a 30 fps. Prohibidos `0:03`, `03.12`, `3,2 s` en cualquier superficie. Las **estimaciones** y tiempos relativos («quedan ~7 s», «hace 6 min», «Guardado hace 12 s») van en lenguaje natural a propósito y no son timecodes.
5. **Nada por debajo de 12 px** salvo dos excepciones declaradas (§2.3).

---

## 1 · Rejilla 1440×900

Marco fijo `1440 × 900` con `overflow:hidden`. El pane real ocupa el 100 % del área del plugin; estas medidas son las del tamaño de referencia y las que se degradan (§1.4).

### 1.1 Columnas y filas

```
┌─────────────────────────────────────────────── topbar 40 ───────────────────────────────────────────────┐
│ biblioteca 220 │              visor 920              │             inspector 300                        │
│                │  header 36 / escena 1fr / transport 56│  tabs 40                                         │
│                │                                      │  panel (scroll)                                  │
├────────────────┴──────────────────────────────────────┴──────────────────────────────────────────────────┤
│        línea de tiempo 280  (ancho 1140)              │  (el inspector llega hasta abajo)                │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Zona | Medida exacta | Notas |
|---|---|---|
| Pane | 1440 × 900 | borde 1 px, radio 0, sombra `--shadow` |
| Barra superior | alto **40** | padding `0 8px 0 12px`, gap 8 |
| Biblioteca | ancho **220** | `--surf-1`, borde derecho 1 px |
| Visor | **920 × 580** | 1440 − 220 − 300 = 920; 900 − 40 − 280 = 580 |
| Inspector | ancho **300** | borde izquierdo 1 px |
| Línea de tiempo | alto **280**, ancho **1140** | 920 + 220; ocupa las columnas 1 y 2 |
| Rejilla | `220px minmax(0,1fr) 300px` × `40px minmax(0,1fr) 280px` | áreas `top / lib view insp / time time insp` |

### 1.2 Medidas internas por zona

**Biblioteca (220)**
| Pieza | Alto | Detalle |
|---|---|---|
| Cabecera «MEDIOS n» | 36 | padding `0 8px 0 12px`; dos botones-icono de 32 |
| Buscador | 32 | márgenes `8px 10px 6px` |
| Filtros | **26 × 2 filas + 4 gap = 56** | rejilla `1fr 1fr`, gap 4, padding `0 10px 8px` |
| Zona de importación | ~50 | borde discontinuo, padding `9px 10px` |
| Rejilla de medios | 2 columnas, gap 8 | miniatura 96 × 54 (16:9), pie 12 px |
| Nota de miniaturas + pie | 22 + 28 | `libnote` + `libft` |

**Visor (920 × 580)**
| Pieza | Medida |
|---|---|
| Cabecera de escena | 36 |
| Escenario | 1fr; marco 16:9 con `max-height` = 100 % (≈ 432 px de alto útil) |
| Transporte | 56; botones 32, scrub de 1 px de alto visual sobre caja de toque 32 |

**Inspector (300)**
| Pieza | Medida |
|---|---|
| Pestañas | 40 (`label` de 40, borde inferior 2 px en activa) |
| Grupos | padding 12, gap 9, separador 1 px |
| Campo | etiqueta 12 + input **32** |
| Pie de exportar | botón 36 |

**Línea de tiempo (1140 × 280)**
| Pieza | Medida |
|---|---|
| Barra de herramientas | 40 |
| Regla | 22 (esquina 116 + regla) |
| Cuerpo de pistas | 1fr |
| Cabecera de pista | **116** de ancho (antes 100: «Subtítulos» se cortaba) |
| Filas de pista | **78 · 54 · 46** (V1 · A1 · T1) |
| Barra de clip | **24** (antes 22) |
| Pie | 40 |
| Escala | **62 px/s** a zoom 100 %; `In 00:00:01:04` en x=70, `Out 00:00:14:02` en x=872, playhead x=211 |

### 1.3 Controles
- Botón estándar: alto **32**; `sm` 28; `icon` 32 × 32. En pista, icono **22** dentro de fila de 32 (excepción declarada).
- Chips: alto **24** (filtros 26). Campos: alto **32**, radio 4.
- Radios: `--r` 4 px (controles), `--rlg` 7 px (modales).

### 1.4 Degradación
| Ancho | Cambio |
|---|---|
| ≥ 1280 | rejilla completa |
| 1024–1279 | inspector 264, biblioteca 180; se ocultan `hide-md` (chips de formato, «2 clips seleccionados») |
| < 960 | la maqueta escala con `zoom` en vez de crear scroll horizontal; en el pane real: biblioteca 180 + inspector 264 mínimo y `hide-sm` (pie de timeline reducido) |
| < 720 | no soportado en v1: el pane muestra `ErrorState` «La ventana es demasiado estrecha» |

---

## 2 · Jerarquía tipográfica

### 2.1 Escala (3 pasos, sin excepciones ocultas)

| Paso | Tamaño / interlínea | Peso | Color | Uso |
|---|---|---|---|---|
| **T1 · título** | 15 / 1.3 | 650 | `--foreground` | título de modal, `EmptyState`, nombre de proyecto |
| **T2 · cuerpo** | 13 / 1.45 | 400–600 | `--foreground` | texto de trabajo: nombres de medio, campos, pestañas, botones, filas |
| **T3 · secundario** | **12 / 1.4** | 400–600 | `--ink-3` (76 %) o `--ink-2` (82 %) | metadatos, duraciones, cabeceras de pista, ayudas, contadores |
| micro | 11 / 1.35 | 500–650 | `--ink-3` | **solo** dentro de miniatura de 96 px y en la marca «sin fotograma» |
| cifras | — | — | — | todo número con `font-variant-numeric: tabular-nums` (timecodes, bytes, porcentajes) |

Reglas:
- **El secundario sube de 11 a 12 px** en toda la interfaz (biblioteca, inspector, pistas, regla, pie, modales). No hay texto de más de 30 caracteres a 11 px.
- Gris secundario: `--ink-3` = 76 % de `--foreground` (antes 66 %). Es un escalón de contraste más, no un cambio de paleta.
- Máximo 2 pesos por superficie (400/500/600/650). No se usa 700 salvo en el badge de pista y la marca «Falta».
- Todo texto en mayúsculas lleva `letter-spacing` 0.06–0.08 em y nunca baja de 12 px.

### 2.2 Contrastes medidos (WCAG 2.1, calculados sobre los tokens del mockup)

Tema oscuro (`--foreground` #E6E7EA, `--card` #141517):

| Token | card | surf-1 | surf-2 | surf-3 | surf-4 |
|---|---|---|---|---|---|
| `--ink-1` (100 %) | 14.78:1 | 13.79:1 | 12.72:1 | 11.30:1 | 9.64:1 |
| `--ink-2` (82 %) | 10.15:1 | 9.57:1 | 9.02:1 | 8.10:1 | 7.05:1 |
| `--ink-3` (76 %) | **8.90:1** | 8.41:1 | 7.93:1 | 7.20:1 | 6.34:1 |
| `--ink-3` (66 %, retirado) | 6.98:1 | 6.68:1 | 6.31:1 | 5.81:1 | 5.19:1 |

Tema claro (`--foreground` #1A1B1F, `--card` #FBFBFC): `--ink-2` **9.52:1**, `--ink-3` 76 % **7.67:1** (antes 5.47:1), `--ink-3` 66 % 5.47:1.

Mínimo garantizado en toda la app: **6.34:1** (peor caso: `--ink-3` sobre `surf-4`), muy por encima de AA 4.5:1 para texto normal y de 3:1 para elementos no textuales. Ningún texto queda por debajo de 6:1.

### 2.3 Excepciones declaradas (las dos únicas)
1. **Marca «sin fotograma»** y **etiqueta de duración dentro de miniatura**: 11 px, porque la miniatura mide 96 px y a 12 px la etiqueta `HH:MM:SS:FF` (11 caracteres) no cabe con su padding.
2. **Escala de los medidores L/R** del transporte: 11 px en una caja de 34 px de alto.

Cualquier otro 11 px es un defecto de implementación.

---

## 3 · Inventario control → componente del SDK

SDK real: `@hermes/plugin-sdk` (`apps/desktop/src/sdk/index.ts`; lista publicada en `desktop-plugin-sdk.md` → «SDK exports at a glance»). **No** existen `Slider`, `Progress`, `TabsContent` ni `DialogClose`: las cuatro sustituciones de abajo son definitivas, no un pendiente.

### 3.1 Controles de la v3

| Control en pantalla | Componente real | Notas de implementación |
|---|---|---|
| Botones de barra, inspector, modales | `Button` (`variant` default/outline/ghost/primary, `size` sm/icon) | `icon` = 32×32; en pista 22 (override de clase, no de API) |
| Nombre de proyecto + desplegable | `DropdownMenu` + `Button variant="ghost"` | el disparador es el `chipbtn` (32 de alto) |
| Chips de estado (Rev 7, Vista previa, In/Out, contadores) | `Badge variant="muted" / "outline"` | `tabular-nums`; el contador va en un `<b>` a la derecha |
| Guardado «Guardando… / Guardado hace 12 s» | `StatusDot` + texto 12 | `relativeTime()` del SDK, no `toLocaleTimeString` |
| Buscador de medios | `SearchField` | atajo `/` para enfocar; `Esc` limpia |
| Filtros Todos/Vídeo/Audio/Imagen | `SegmentedControl` (2×2 con `Button variant="ghost"`) | los 4 contadores siempre visibles; si no caben, se parte en dos filas (§1.2) |
| Pestañas del inspector | `Tabs` (lista y disparadores) | ver 3.2 para el cuerpo |
| Campos de texto y timecode | `Input` | `class="mono"` con `tnum`; máscara `HH:MM:SS:FF` |
| Texto en pantalla | `Textarea` | el borrador vive en el contenedor, no en el control |
| Transición (desplegable) | `Select` | opciones = presets del motor |
| 16:9 / 9:16, Arriba/Centro/Abajo | `SegmentedControl` | `aria-label` explícito por grupo |
| Interruptores (ver pista, márgenes seguros) | `Switch` | `aria-checked` lo pone Radix; no duplicar |
| Scrub del visor y zoom | **`input[type="range"]`** (no `Slider`) | `accent-color: var(--ui-accent)`, alto de caja 32, `aria-label` obligatorio, `aria-valuetext` en `HH:MM:SS:FF` («00:00:03:12 de 00:00:16:06»); `step = 1/30`; `aria-valuenow` lo pone el navegador, **no** se escribe a mano |
| Barra de progreso de exportación / importación | **`div[role="progressbar"]`** (no `Progress`) | `aria-valuemin/max/now` + `aria-valuetext="Etapa 2 de 4, 38 %"`; el anuncio va en un `role="status"` hermano, no en la barra (nada de locutar cada frame) |
| Cuerpo de pestaña (Escena/Texto/Audio/Export) | **render condicional** (no `TabsContent`) | `{tab==='esc' && <PanelEscena/>}`; el visible lleva `role="tabpanel"`, `id` y `aria-labelledby` a mano; el resto `hidden` si se montan |
| Cerrar modal | **`onOpenChange(false)`** (no `DialogClose`) | la «X» es `Button variant="ghost" size="icon"` con `aria-label="Cerrar"`; `Esc` lo gestiona Radix, **no** añadir handler; el foco vuelve al disparador solo |
| Mostrar atajos | `Kbd` + `KbdGroup` | `<KbdGroup><Kbd>Ctrl</Kbd><Kbd>Mayús</Kbd><Kbd>E</Kbd></KbdGroup>` con `aria-label="Ctrl más Mayús más E"` |
| Avisos de «requiere backend» | `Badge variant="outline"` | texto «requiere backend», `title` con el motivo |
| Vacíos | `EmptyState` (`title`/`description`) | el icono y los botones van **como hermanos** dentro del contenedor centrado |
| Errores del servicio | `ErrorState` + `Button` «Reintentar» / «Ver registro» | cabecera con `Badge variant="destructive"` «Sin conexión» |
| Estado de exportación (cola, etapas) | `LogView` para el registro; `Skeleton`/`GlyphSpinner` para espera | `DecodeText` solo si se pide `loop` explícito |
| Modales de exportar / conflicto / proyectos / ajustes / ayuda | `Dialog` (+ `DialogHeader/Title/Description/Footer`) | ancho 560 (760 en «Ayuda» y «Proyectos») |
| Borrado de proyecto / quitar medio | `ConfirmDialog` | acción destructiva a la derecha, foco inicial en «Cancelar» |
| Menú `⋯` de la barra | `DropdownMenu` | una sola entrada por acción; sin submenús de más de un nivel |
| Toasts (guardado, importación, error) | `host.notify` / `host.notifyError` | nunca un toast propio |
| Registro de errores | `LogView` | redactado por el servicio |

### 3.2 Prohibiciones
- No `Slider`, no `Progress`, no `TabsContent`, no `DialogClose`, no `KbdCombo`.
- No estilos en línea con colores literales: solo variables `--ui-*` del tema (`--ui-text-secondary`, `--ui-accent`, `--ui-stroke-secondary`…).
- No `position:fixed` para overlays: el pane es `contain:layout paint` y el overlay es `absolute` dentro (la maqueta ya lo hace así).

---

## 4 · Contrato de datos

### 4.1 Servicio
- Base **`http://127.0.0.1:8770`** (`core/CONTRATO.md` §1, versión **0.3.0**). El 8765 es del spike y de `plugin/README.md`: **está obsoleto**, el puerto vigente es 8770.
- Solo loopback; `Host` obligatorio (`403` sin él), `Origin: null` aceptado para el pane `file://`. Sin autenticación de red → no exponer a LAN.
- Arranque desacoplado (`start_service.py --port 8770`, `DETACHED_PROCESS`); el pane **no** arranca el servicio: si `/health` falla dos veces seguidas, estado **down** (`down`).
- Errores: `{"error": "…"}`; `409` siempre con `current_revision`.

### 4.2 Endpoints que usa la UI (todos verificados en el contrato)

| Uso en pantalla | Petición |
|---|---|
| Latido / estado del servicio | `GET /health` → `{ok, service, engine, ffmpeg, presets, queue, startedAt}` |
| Carpeta concedida | `GET /grants` → `{mediaRoot}` |
| Lista de proyectos (**filtrar**) | `GET /projects?query=` → `{projects:[{projectId,title,revision,scenes,assets,updatedAt,sessionId,cwd}], mediaRoot, query}` — filtro por título, sin distinguir mayúsculas ni acentos |
| Abrir proyecto | `GET /projects/<id>` → `{projectId, revision, docHash, updatedAt, project, ui, media:[{id,path,kind,bytes,sha256,exists,previewUrl}]}` |
| Guardar | `PUT /projects/<id>` `{revision, draft}` → `200` o **`409 {current_revision}`** |
| Crear | `POST /projects` `{title?, session_id?, cwd?}` |
| **Duplicar** | `POST /projects/<id>/duplicate` → `201`, nuevo id, revisión 0, título «(copia)» |
| **Borrar proyecto** | `DELETE /projects/<id>?confirm=1` → `{deleted, projectId, jobsDeleted, filesPurged[]}`; `409` si hay export en curso |
| Importar medio | `POST /projects/<id>/media` `{path}` → `201` con el asset y la escena creados |
| **Quitar medio** | `DELETE /projects/<id>/media/<assetId>?revision=` → payload nuevo + `removedAsset` + `removedScenes[]`; `409` con revisión vieja |
| Reproducir en el visor | `GET /media/<projectId>/<assetId>` con `Range`/206 (el original, no hay proxy) |
| **Miniatura** | `GET /thumbnails/<projectId>/<assetId>?t=<seg>` → JPEG 320×, `max-age=300` |
| **Onda** | `GET /waveform/<projectId>/<assetId>` → `{buckets:200, duration, peaks:[0..1]}` |
| Exportar | `POST /projects/<id>/export` `{preset:"mp4-720p30", captions?}` → `202 {jobId, deduped}` |
| Progreso | `GET /jobs/<jobId>` → `{state, stage, progress, eta_s, artifacts, outputName}`; `POST /jobs/<jobId>/cancel` |
| **Exports** | `GET /exports?project=<id>&limit=20` → `{count, jobs:[{jobId,preset,state,stage,progress,outputName,outputUrl,outputBytes,createdAt,finishedAt}]}` |
| Descargar / abrir salida | `GET /jobs/<jobId>/output` (Range/206) |
| Eventos | `GET /events?since=<seq>` (long-poll; `timeout=0` no bloquea) |

Estados de job: `queued → running → succeeded | failed | cancelled | interrupted`. Etapas: `probing | rendering | done | failed`.

### 4.3 Documento (lo que se pinta)
`project = {projectId, revision, engineTag, fps (racional), width, height, title, sessionId, cwd, assets[], scenes[], createdAt, updatedAt}`
`scene = {id, source:{path, sha256?, kind}, in, out, transition?, text[], audio?}`
- El tiempo de escena sale de `in`/`out` en frames → se pinta `HH:MM:SS:FF` con `fps` del documento (30/1). No se recalcula con 29.97 «redondeado».
- `media[].exists === false` → escena **Falta** (borde discontinuo + «Volver a vincular») y «Exportar» deshabilitado antes de intentarlo.
- Dedupe: `POST export` con el mismo documento + preset devuelve `{deduped:true}`; la UI lo dice («Ya existe un export de esta revisión»), no lanza un segundo job.

### 4.4 `host.state` (lo que el pane lee del host, no del servicio)

| Clave | Para qué |
|---|---|
| `host.state.sessionId` / `host.state.cwd` | crear proyecto con la sesión y carpeta correctas |
| `host.state.theme` (`useTheme()`) | `data-theme="dark" \| "light"`; el pane hereda, no conmuta por su cuenta |
| `host.state.paneWidth` (medido con `ResizeObserver`) | degradación §1.4 |
| `ctx.storage` | claves propias (§8.1): `layout.*`, `preview.guides`, `lastProjectId` |
| `ctx.files.requestFolder()` | carpeta de medios (debe **coincidir** con `mediaRoot` de `/grants`; si no, se dice y se pide otra carpeta) |

### 4.5 Brechas declaradas (no las tapa la maqueta)
1. **Miniaturas y onda**: el contrato 0.3.0 ya las sirve, pero el pane pinta marcos neutros y no las pide. La maqueta dibuja degradados **de ejemplo**, marcados «sin fotograma». Conectarlas es trabajo del pane. Coste UI: 0 endpoints nuevos.
2. **Arrastrar y soltar**: **desactivado**. La zona de la biblioteca no dice «arrastra» sino «Importar medios · arrastrar está desactivado»; los clips no se arrastran (`cursor:pointer`), el orden se cambia con «Subir/Bajar». Reactivarlo exige endpoint de subida (rev2 §12 D7).
3. **Tamaño y familia de texto**: no están en el esquema → controles deshabilitados con «requiere backend».
4. **Vista previa**: se sirve el original con Range; la etiqueta dice «Vista previa», nunca «540p».
5. **Deuda documental detectada**: `core/CONTRATO.md` cita «§9 (superficie v3)» en su cabecera, pero el archivo termina en §8 y no hay §9. `plugin/README.md` sigue diciendo 8765. Ambos los corrige quien sea dueño de `core/` y `plugin/` — no este documento.

---

## 5 · Los 11 estados

Un estado = una entrada del selector `?state=`, un panel visible y un copy cerrado. Ninguno se inventa en cliente: cada uno se dispara con una condición real.

| # | Estado | Disparador | Qué se ve | Copy es-ES (literal) |
|---|---|---|---|---|
| 1 | **edit** | proyecto cargado, revisión vigente | rejilla completa; inspector en «Escena» | «Guardado hace 12 s» · «4 clips · 00:00:16:06» |
| 2 | **export** | `POST /export` → `202` | modal 560 sobre el editor, etapas y progreso | «Exportando 720p» / «Etapa 2 de 4 · 38 %» / «233 / 486 fotogramas» / «quedan ~7 s» |
| 3 | **conflict** | `PUT` → `409` | modal con la revisión real | «Hay cambios más nuevos» / «La revisión 8 se guardó en otro lugar (hoy 14:32). Tu copia es la 7.» · «Recargar y perder mis cambios» · «Guardar como copia» · «Cancelar» |
| 4 | **relink** | `media[].exists === false` | banner invertido + escena rayada | «Falta el archivo de la escena 02» / «El proyecto sigue completo; solo se perdió la ruta a clipB.mp4» · «Volver a vincular» |
| 5 | **projects** | clic en el nombre del proyecto, `Ctrl+O` | modal 760 con lista, buscador y acciones | «Tus proyectos» / «Borrar» / «Duplicar» / «Nuevo proyecto» / vacío: «No hay proyectos con «x».» |
| 6 | **settings** | menú `⋯` → Ajustes | modal con preferencias persistidas | «Ajustes del editor» / «Márgenes seguros» / «Reducir movimiento» |
| 7 | **help** | `?` o menú `⋯` → Ayuda | modal 760, tabla de atajos | «Atajos y límites» / «Todo lo que hace el editor, sin arrastrar nada» |
| 8 | **empty** | sin proyecto (`projectId` nulo) | biblioteca «Primeros pasos», visor con `EmptyState`, pistas vacías | «Elige una carpeta con tus clips» / «El editor lee los archivos de la carpeta de medios; no los copia.» · «Importar medios» · «Arrastrar está desactivado en esta versión.» |
| 9 | **import** | `POST /media` en curso | cabecera «Importando 2/3», filas con `progressbar`, un omitido | «Importando 2 de 3» / «Analizando con ffprobe…» / «En cola» / «1 omitido · logo-copia.svg ya estaba (mismo sha256)» |
| 10 | **down** | `/health` falla 2 veces o `5xx` | `ErrorState` en el visor, banner «Sin conexión», todo en solo lectura | «El servicio del editor no responde en 127.0.0.1:8770.» / «Tus medios no se han modificado.» · «Reintentar» · «Ver registro» |
| 11 | **closed** | el usuario cierra el editor | Hermes con la barra de título y el icono del editor apagado | «Editor cerrado» / «Abrir el editor de vídeo» / «Ctrl + Mayús + E · también en ⌘K» |

Reglas de copy: imperativo y en segunda persona («Elige», «Vuelve»), sin promesas de rendimiento, sin «pronto», sin emoji. Los números siempre con su unidad y en `tabular-nums`.

---

## 6 · Atajos

| Atajo | Acción | Ámbito |
|---|---|---|
| `Espacio` | Reproducir / pausar | visor |
| `←` / `→` | Fotograma anterior / siguiente (`Mayús` = 1 s) | editor |
| `Inicio` / `Fin` | Principio / final de la secuencia | editor |
| `I` / `O` | Marcar `In` / `Out` | editor |
| `S` | Partir en el cursor | editor |
| `V` / `C` | Selección / cuchilla | editor |
| `N` | Snap (imán) | editor |
| `Supr` | Borrar escena seleccionada (`ConfirmDialog`) | editor |
| `Ctrl+D` | Duplicar escena | editor |
| `Ctrl+Z` / `Ctrl+Y` | Deshacer / rehacer | editor |
| `Ctrl+S` | Guardar (`PUT` con la revisión vigente) | editor |
| `Ctrl+O` | Abrir proyectos | global del pane |
| `Mayús+Z` | Ajustar la línea de tiempo a la ventana | timeline |
| `/` | Enfocar el buscador de medios | biblioteca |
| `Esc` | Cerrar modal / limpiar búsqueda / soltar selección | global |
| `⌘K` → «Abrir editor de vídeo» | Reabrir el pane | Hermes |
| `Ctrl+Mayús+E` | Reabrir el pane (global, declarado en `KEYBINDS_AREA`) | Hermes |

Reglas: ningún atajo de un solo carácter se registra mientras el foco está en `input`, `textarea` o `select`; los de `Ctrl`/`⌘` sí. La ayuda (§5.7) lista exactamente estos y nada más.

---

## 7 · Placeholder declarado (miniaturas y onda)

- La maqueta **no** pinta fotogramas: pinta degradados. Llevan la marca **«sin fotograma»** (11 px, borde discontinuo) y `title="Miniatura de ejemplo: el panel aún no pide /thumbnails; no es un fotograma real"`.
- Nota al pie de la biblioteca: «Miniaturas de ejemplo · el panel aún no pide `/thumbnails`».
- Pie de la línea de tiempo: «… · onda e imágenes de ejemplo».
- Etiqueta del visor: «clipB.mp4 · escena 02 · fotograma de ejemplo».
- En el pane real: mientras no se consuma `GET /thumbnails/...`, la miniatura es un marco neutro `--surf-3` con el icono de tipo. **No** se rellena con color de marca (se leería como contenido).

---

## 8 · Persistencia de layout y cierre / reapertura

### 8.1 Lo que se persiste (`ctx.storage`, no `localStorage`)

| Clave | Valor | Defecto |
|---|---|---|
| `layout.lib` | `{width:220}` | 220 (180 en ventana estrecha) |
| `layout.insp` | `{width:300}` | 300 (264 estrecha) |
| `layout.tl` | `{height:280}` | 280; rango 180–420 |
| `layout.tab` | `'esc' \| 'txt' \| 'aud' \| 'exp'` | `'esc'` |
| `layout.zoom` | `{pxPerSec:62}` | 62 |
| `preview.guides` | `boolean` | `true` |
| `lastProjectId` | `string` | último abierto |
| `reduceMotion` | `boolean` | `host.state` si existe |

Nada de esto viaja al servicio: el layout es del usuario y del equipo, no del documento. El **documento** solo cambia con `PUT`.

### 8.2 Cierre del editor (volver al chat)

Hay **tres** caminos, y los tres hacen lo mismo: guardar si hay cambios pendientes (o pedir confirmación), soltar el `<video>`, y volver al chat.

1. **✕ propio** de la barra superior (`aria-label="Cerrar el editor y volver al chat"`).
2. **Icono de la barra de título** de Hermes (el pane se pliega; el icono queda apagado).
3. **Paleta `⌘K`** → «Cerrar editor de vídeo».

Al cerrar: si `dirty`, `PUT` con la revisión vigente; si devuelve `409`, se abre el modal **conflict** *antes* de cerrar (nunca se pierde trabajo en silencio). Si `PUT` falla por red, se ofrece «Guardar como copia» / «Salir sin guardar».

### 8.3 Reapertura

- **Icono de la barra de título**, **`⌘K` → «Abrir editor de vídeo»** o **`Ctrl+Mayús+E`**.
- Al reabrir: se relee `GET /projects/<lastProjectId>`; si `404`, se abre **projects** con el buscador vacío. No se restaura nada de memoria: el estado vuelve del servicio.
- El layout sí se restaura (§8.1): mismo ancho de paneles, misma pestaña, mismo zoom.

### 8.4 Qué NO reabre el editor
- **La X nativa de la ventana de Hermes** cierra la aplicación, no el pane: no hay «restaurar sesión» propio y el plugin **no** se monta al volver. Con la app cerrada el servicio sigue vivo (proceso desacoplado) pero sin nadie que lo pinte.
- **Desactivar el plugin** (Ajustes → Plugins) lo apaga: desaparece la barra de título, `⌘K` deja de ofrecerlo y `Ctrl+Mayús+E` no hace nada. Al reactivarlo, el estado vuelve del servicio igual que en 8.3.
- Un `export` en curso **sobrevive** al cierre del editor y de la app: el job lo lleva el servicio; al reabrir, `GET /exports?project=` lo recupera y se pinta en `export`.

---

## 9 · Accesibilidad (objetivo AA)

1. **Contraste**: mínimo medido 6.34:1 (§2.2). Ni el texto secundario baja de 4.5:1. Los estados no dependen solo del color: «Falta» lleva icono + palabra; la selección lleva borde 1 px + fondo, no solo color.
2. **Foco visible**: `outline: 2px solid var(--ui-accent)` con `outline-offset` −2 en radios/tabs y +2 en botones. Nunca `outline:none` sin sustituto.
3. **Teclado**: todo alcanzable; orden = lectura (topbar → biblioteca → visor → inspector → timeline). Las pistas son `role="listbox"`/`option` con `aria-selected`; los clips llevan `tabindex="0"` y `aria-label` con nombre y duración en timecode.
4. **Regiones**: `header/nav/aside/section/footer` con `aria-label` en español («Biblioteca de medios», «Inspector», «Línea de tiempo»). El pane declara `lang="es"`.
5. **Radios nativos con `input` visible sólo para lectores**: los grupos (estado, pestaña, orientación, posición) son `<input type="radio">` reales + `label`; `role="tablist"`/`tab` con `aria-labelledby` apuntando al panel.
6. **Progreso**: `role="progressbar"` con `aria-valuetext` en texto humano; el `role="status"` hermano anuncia etapa, no porcentajes.
7. **Movimiento**: `prefers-reduced-motion` o `reduceMotion` → sin transición de `pbar` ni `shimmer`; el skeleton se queda estático.
8. **Zoom 200 %**: la rejilla no debe cortar contenido; a 200 % entra en la degradación de §1.4 y el inspector pasa a 264 con scroll propio.
9. **Timecodes legibles**: se anuncian como «cero cero cero cero tres, doce» con `aria-label` en palabras cuando el lector está activo (`aria-label` explícito en el input, no `aria-valuetext` inventado).

---

## 10 · Checklist U1–U4 → pantalla / estado

Cada U es una pregunta del usuario. Si la respuesta no está en la pantalla indicada, la pantalla falla, aunque «se vea bonita».

| U | Pregunta | Pantalla / estado donde se responde | Criterio de aceptación |
|---|---|---|---|
| **U1** | *¿Dónde estoy y qué proyecto tengo abierto?* | **topbar** (todos los estados): nombre + `Rev N` + estado de guardado | nombre, revisión y «Guardando…/Guardado hace N s» visibles sin clic; en `empty` dice «Sin proyecto»; en `down` añade «Sin conexión»; en `closed` el icono del editor está apagado |
| **U2** | *¿Qué material tengo y cuál falta?* | **biblioteca 220** + `relink` + `import` | 6 medios con tipo y duración en TC; contadores de filtro siempre visibles (los 4); un medio faltante se marca en la biblioteca **y** en su escena; la importación muestra progreso por archivo y el motivo del omitido |
| **U3** | *¿Qué estoy editando exactamente?* | **visor 920** + **inspector 300** + **timeline 280** | playhead y `tc` coinciden; `in/out` del inspector coinciden con los chips de la timeline; el clip seleccionado está marcado en las tres zonas; la duración de cada clip y el total cuadran (suma = 00:00:16:06) |
| **U4** | *¿Qué pasa cuando termino?* | **export**, **conflict**, **down**, **closed** | export con etapas, frames y ETA; conflicto con la revisión real y tres salidas; caída del servicio en solo lectura con reintento; cierre con guardado previo y reapertura que devuelve el estado desde el servicio |

Pruebas visuales mínimas por entrega (`docs/qa/`): `v3-dark.png`, `v3-light.png`, `v3-dark-closed.png`, `v3-dark-export.png` a 1440×900 exactos, más `v3-dark-empty`, `-import`, `-down`, `-conflict`, `-relink`, `-projects`, `-settings`, `-help`, `-texto` y `v3-1024x700`.

---

## 11 · Lo que la v3 demuestra y lo que no

**Demuestra**: las 11 pantallas con copy real, la rejilla exacta, dos temas, la degradación a 1024×700, y que cada control visible tiene componente en el SDK o sustituto cerrado.

**No demuestra**: miniaturas y onda reales (§4.5.1), arrastrar y soltar (§4.5.2), tamaño/familia de letra (§4.5.3), proxy de vista previa, ni la latencia real del scrub sobre un MP4 de 200 MB. Nada de eso se puede afirmar sin medirlo en el pane.
