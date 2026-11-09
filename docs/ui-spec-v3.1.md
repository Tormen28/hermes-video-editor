# UI Spec v3.1 · Editor de vídeo en el dock derecho (variante compacta)

Estado: **propuesta para aprobación de Tormen** · 2026-11-08 · Harmonia
Alcance: el pane `editor-video` ya registrado como **dock derecho** del workspace (`placement:'right'`, `dock:{pane:'workspace',pos:'right'}`, `width:'64%'`). Este documento **no sobrescribe** `docs/ui-spec-v3.md`: corrige y añade seis materias (reparto, chip de modelo, element picker, regla de overlays, atajos y aceptación U1–U4) que la v3 no podía resolver cuando asumía 1440 px para el editor solo. Donde la v3 y esta v3.1 discrepen en medidas, manda la v3.1. En todo lo demás (tokens, contrato de datos, timecodes, mínimo de 12 px, los 11 estados) **sigue vigente la v3**.

Referencia visual y métrica: `docs/mockup-v31.html` (nuevo, autocontenido, mismos tokens que la v3) y `docs/qa/v31-dock-dark.png` (1440×900), `docs/qa/v31-chip-tip.png` (popover del chip), `docs/qa/v31-1024x700.png` (degradación). Todas las cifras de este documento están **medidas en el navegador sobre esa maqueta**, no estimadas.

---

## 0 · Las cuatro frases de Tormen, convertidas en reglas

| Lo que pidió (textual, 8-nov) | Regla de esta v3.1 |
|---|---|
| «chat a la izquierda, no tiene que ocupar mucho espacio» | El chat es el 36 % del ancho (518 px a 1440) y **no se toca**: el plugin no pinta nada dentro del chat. |
| «el editor a la derecha» | El editor ocupa el 64 % (922 px a 1440) como dock derecho, con borde izquierdo de 1 px y **todo su contenido contenido** en ese rectángulo. |
| «orden y crear/cambiar cosas rápido» | Biblioteca e inspector **dejan de ser columnas** y pasan a drawers de 326 px con botón propio; el visor y la línea de tiempo ganan el ancho completo. Sustituir un medio son **dos gestos** (S → Intro). |
| «botón para cambiar de modelo» | **Chip de modelo** en la topbar del editor: lee `host.state.model` y **lleva al selector del chat**. El editor no cambia el modelo: no puede, por diseño del SDK. |
| «faltan sustitutos, elementos que flotan» | **Element picker** anclado al clip seleccionado y **overlays flotantes pero contenidos** dentro del pane (regla §4). |

---

## 1 · Reparto 36 / 64 y degradación

### 1.1 Rejilla a 1440×900 (medida)

```
┌───────────────────────────┬──────────────────────────────────────────────────────────┐
│ CHAT DE HERMES  518       │ EDITOR  922                                              │
│ header 48                 │ topbar 40  (proyecto · rev · guardado · chip modelo · ⧉) │
│ transcripción 1fr         │ visor: header 36 / escenario 1fr (893×502) / transporte 56│
│ compositor 96 + pie 24    │──────────────────────────────────────────────────────────│
│                           │ línea de tiempo 260 (toolbar 40 · regla 22 · pistas 166 · │
│                           │                     pie 32)                              │
└───────────────────────────┴──────────────────────────────────────────────────────────┘
```

| Zona | Medida exacta | Nota |
|---|---|---|
| Shell | 1440 × 900, `overflow:hidden` | `contain:layout paint`; nada escapa |
| Chat | **518** × 900 | 36 % de 1440; borde derecho 1 px |
| Editor | **922** × 900 | 64 %; borde izquierdo 1 px |
| Topbar editor | 921 × **40** | padding `0 6px 0 10px`, gap 6 |
| Visor | 921 × **600** | header 36 + escenario 502,3 + transporte 56 |
| Escenario | **893 × 502,3** | 16:9, radio 6; el alto lo manda el ancho |
| Línea de tiempo | 921 × **260** | toolbar 40 · regla 22 · pistas 166 · pie 32 |
| Cabecera de pista | **116** de ancho | igual que la v3 |
| Filas de pista | **70 · 48 · 40** (V1 · A1 · T1) | la v3 usaba 78 · 54 · 46 |
| Escala | **46 px/s** | antes 62: el ancho útil es 805, no 1140 |

**Contraste medido** (texto sobre su fondo real, resuelto con canvas): chip 9,70:1 · chip de modelo 13,94:1 · timecode de clip 8,50:1 · sub de pista 8,50:1 · «en uso» del picker 7,52:1 · subtítulo del picker 8,13:1 · popover 9,27:1 · placeholder del compositor 8,50:1. **Ningún texto baja de 4,5:1**; el mínimo real de la maqueta es 7,52:1.

### 1.2 Qué se colapsa y con qué botón

| Panel | v3 | v3.1 | Disparador |
|---|---|---|---|
| Biblioteca | columna fija 220 | **drawer izquierdo de 326**, dentro del pane, `z:50` | botón «Biblioteca» (icono capas) en la topbar · atajo **B** |
| Inspector | columna fija 300 | **drawer derecho de 326**, dentro del pane, `z:50` | botón «Inspector» (icono panel) · atajo **I** |
| Reemplazar medio | botón en inspector | igual, pero abre el **picker filtrado por tipo** (§3.3) | botón «Reemplazar» · atajo **S** |

Reglas de los drawers:

1. **Nunca dos a la vez.** Abrir uno cierra el otro (un solo overlay de panel).
2. **El scrim cubre solo el editor**, de `top:40px` a abajo: el chat sigue legible y usable. Un scrim sobre el chat sería mentir sobre quién manda en esa mitad.
3. **Cierre**: el botón ✕ de su cabecera, `Esc`, o volver a pulsar el mismo botón de la topbar (estado `aria-pressed`).
4. **No roban el foco del visor**: al abrirse, el foco va al primer control del drawer; al cerrarse vuelve al botón que lo abrió.
5. **No cambian el ancho del editor**: flotan encima. El visor no se re-maqueta al abrirlos (evita el «salto» de layout que Tormen llama desorden).

### 1.3 Degradación (medida en la maqueta)

| Ancho de ventana | Chat 36 % | Editor 64 % | Línea de tiempo | Escala | Escenario | Topbar |
|---|---|---|---|---|---|---|
| **1440 × 900** | 518 | **922** | 260 | 46 px/s | 893 × 502 | completa |
| **1024 × 700** | 369 | **655** | 220 | 32 px/s | 634 × 357 | sin marca «Editor», proyecto 118, guardado solo punto |
| **900 × 700** | 324 | **576** | 200 | 28 px/s | 555 × 312 | ídem + chips de formato ocultos |

Umbrales por **container query sobre el editor** (`container-type:inline-size`), no sobre la ventana: el plugin no sabe el ancho de la ventana, sabe el suyo.

| Ancho del editor | Cambios |
|---|---|
| ≤ 780 | se oculta la marca «Editor»; proyecto a 132; «Guardado · 12 s» → solo el punto; tooltips de la barra de timeline a icono; se oculta la última etiqueta de la regla y la nota «onda de ejemplo» |
| ≤ 700 | visor header 32 y transporte 48 (para que el 16:9 siga cabiendo); picker pasa a `left:8 right:8` y rejilla de 2 columnas; se ocultan «Vista previa» y el total del timecode |

**El 16:9 nunca se deforma**: el escenario toma el ancho disponible y el alto sale de la proporción; si no cabe, se reduce el chrome del visor (§1.3), no el marco.

### 1.4 Qué NO se degrada

- El **chip de modelo** sigue visible y con el nombre completo hasta 576 px de editor (172 px de ancho máximo, medido 108 px de texto + 34 de iconos). Por debajo de 576 no hay soporte declarado: el pane mínimo es **560 px** y ahí el chip pasa a icono + `title`, con el nombre en el `aria-label`.
- Los **timecodes** `HH:MM:SS:FF` no se abrevian nunca; si no caben, se oculta el total, no los dígitos.
- El **mínimo de 12 px** de la v3 se mantiene; las dos excepciones siguen siendo las de la v3 §2.3.

---

## 2 · Chip de modelo (solo lectura, lleva al chat)

### 2.1 Por qué es así

El SDK de plugins **rechaza** acciones de modelo: *«model/provider changes … are not app actions a plugin can run»*. Un botón que pretendiera cambiar el modelo sería un botón que miente. Pero el plugin **sí puede leer** `host.state.model` (ReadableAtom<string>), y Tormen quiere un botón de modelo en el editor. La solución honesta: **mostrarlo y llevar al sitio donde sí se cambia**.

### 2.2 Anatomía

```
[ ✦  deepseek-v4.1-flash  🔒 ]
  │        │             └─ candado 12 px, --ink-3: «no editable aquí»
  │        └─ host.state.model, 12 px, tabular, elipsis si no cabe
  └─ icono de modelo 14 px, --accent
```

- Alto **28**, radio **7**, borde `--border`, fondo `--surf-1`; hover `--accent-1` + borde `--accent-2`.
- Colocado en la topbar **a la derecha**, antes del separador de los tres botones de panel: es contexto de la sesión, no una acción del proyecto. No se mezcla con Guardar ni con Rev.
- `aria-label` = «Modelo del chat: {modelo}. Solo lectura. Pulsa para ir al selector del chat».
- `title` = el nombre completo (para elipsis).

### 2.3 Comportamiento al pulsar

1. Se llama a **`host.composer.focus()`** (una vez; sin `send`).
2. Se abre un **popover contenido**, anclado bajo el chip, `z:55`, ancho **306**, con:
   - título «El modelo se cambia en el chat»;
   - texto «El editor solo lee el modelo de la sesión. Los plugins no pueden cambiarlo por diseño: usa el selector del chat, arriba del compositor.»;
   - línea de salida: «El foco ya está en el compositor. Escribe o pulsa **Esc** para volver.»
3. El popover **se cierra** con `Esc`, con clic fuera (dentro del editor) o al abrir cualquier otro overlay. **No** se cierra solo por tiempo: si el usuario está leyendo, se queda.
4. El foco **no se queda en el chip**: el usuario ya está escribiendo en el chat. El popover es informativo, no interactivo (sin botones que prometan cambiar nada).

> Prohibido: pintar un desplegable de modelos dentro del editor, un `select` simulado o un toast que diga «modelo cambiado». Eso es simular estado, y el frontend refleja estado real o no lo pinta.

### 2.4 Estados del chip

| Estado | Cuándo | Qué se ve | Accesible |
|---|---|---|---|
| **Con modelo** | `host.state.model` es string no vacío | `✦ deepseek-v4.1-flash 🔒` | label completo |
| **Sin sesión** | no hay sesión activa / atom `''` | `✦ Sin sesión 🔒`, sin hover de acción | «Sin sesión de chat. Abre una conversación para elegir modelo» |
| **Modelo desconocido** | el atom emite un id que no está en el catálogo local | el id **tal cual**, en `--ink-2`, sin intentar «traducirlo» | label = el id literal |
| **Nombre largo** | > 172 px | elipsis al final, `title` completo | label completo |
| **Chat no disponible** | `host.composer` ausente (ventana sin chat) | chip normal, al pulsar **no** hay foco y el popover dice «Abre el chat para cambiar el modelo» | igual |

Regla transversal: el chip **nunca** muestra un valor por defecto inventado mientras llega el atom. Si el atom es `null`/`undefined`, se pinta el estado «Sin sesión», no el último modelo visto.

---

## 3 · Element picker · sustituir e insertar medio

### 3.1 Las dos puertas

| Puerta | Qué hace | Diferencia |
|---|---|---|
| **Sustituir** (S, botón «Sustituir medio», botón «Reemplazar» del inspector) | reemplaza **el medio de una escena existente** | conserva `in`, `out` y el texto de la escena |
| **Insertar** (Mayús+S, botón «Insertar») | añade un medio **después de la escena seleccionada** | crea una escena nueva; no conserva nada porque no hay nada que conservar |

El picker es **el mismo componente**; cambian el título («Sustituir medio» / «Insertar medio»), el subtítulo y lo que pasa al aplicar.

### 3.2 Geometría y contención (medida)

| Medida | 1440 | 1024 |
|---|---|---|
| Ancho | **468** | 638 (left 8 / right 8) |
| Alto | **411** (contenido) | **454 (máximo) → scroll interno** |
| Posición | `left:158`, `bottom: tl+14` = 274 | `left:8 right:8`, mismo `bottom` |
| Rejilla | 3 columnas, miniatura 16:9 (~140×79) | 2 columnas |
| Anclaje | caret de 9 px sobre el **centro del clip seleccionado** (x 392 del editor) | sin caret (ancho completo) |

El picker **nunca** crece más allá de `100% − tl − 26px`: si el contenido no cabe, **scrollea el cuerpo del picker**, no la página (§4). Medido a 1024: 454 px de alto y `scrollTop` interno disponible.

### 3.3 Flujo de «sustituir»

```
[clip seleccionado]
   │  S / «Sustituir medio» / inspector → «Reemplazar»
   ▼
PICKER (foco en la rejilla, filtro = tipo del medio actual)
   ├─ ↑↓←→ mover · Intro / doble clic / «Sustituir» → aplicar
   ├─ Esc → cerrar y devolver el foco al disparador
   ├─ / → buscar (filtra en vivo por nombre, sin red)
   ├─ Tab / Mayús+Tab → chips de filtro
   └─ clic simple → selecciona (no aplica)
   ▼
APLICAR
   ├─ medio más largo  → conserva in/out: mismo `start`, `duration` recalculada
   ├─ medio más corto  → el `out` se recorta al final del medio (nunca se estira en bucle)
   ├─ mismo tipo       → conserva el texto de la escena (T1 no se toca)
   └─ audio sobre escena de vídeo → se rechaza: el filtro ya lo impide
   ▼
[TIMELINE] clip actualizado + undo de un paso («Sustituir medio»)
```

**Qué se conserva, dicho antes de elegir**: el subtítulo del picker lo escribe explícito — «Escena 02 · clipB.mp4 · conserva in 00:00:03:06 → out 00:00:08:24». Si el medio elegido es más corto, el subtítulo cambia a «se recortará a 00:00:03:00 al aplicar» **antes** de aplicar. No se avisa después.

**El medio en uso** aparece en la rejilla, deshabilitado, con la etiqueta «en uso en esta escena». Se muestra para que el usuario entienda por qué no puede elegirlo; no se oculta.

### 3.4 Estados de cada celda

| Estado | Tratamiento |
|---|---|
| Reposo | miniatura con borde `--line-soft`, nombre 12 px, peso 12 px en `--ink-3` |
| **Hover** | fondo `--surf-3` + borde `--line-soft` (sin mover nada: cero `transform`) |
| **Seleccionado** | borde `--accent`, fondo `--accent-1`, `box-shadow 0 0 0 1px accent`, check de 18 px arriba a la derecha |
| **Foco de teclado** | anillo `--accent` de 2 px (`:focus-visible`), independiente del seleccionado |
| **Deshabilitado** | opacidad 0,5, `cursor:not-allowed`, sin hover, `aria-disabled="true"` |
| **Sin miniatura** | icono de tipo centrado sobre degradado neutro; **nunca** un fotograma inventado |
| **Cargando miniaturas** | esqueleto del mismo tamaño (no cambia el layout al llegar) |

### 3.5 Estados del picker (además del normal)

| Estado | Cuándo | Qué se pinta |
|---|---|---|
| Vacío | la biblioteca no tiene medios de ese tipo | «No hay vídeos en este proyecto» + botón «Añadir medio» (abre la importación de la v3) |
| Sin resultados | la búsqueda no casa | «Ningún medio coincide con “…”» + «Limpiar búsqueda»; el filtro sigue visible |
| Cargando | pidiendo `media[]` | 6 esqueletos + barra fina de 2 px en el borde superior del picker |
| Error | el servicio no responde | «No se pudo leer la biblioteca» + «Reintentar»; el resto del editor sigue operable |
| Sin escena seleccionada | se pulsa S sin selección | el picker **no** se abre; el botón queda deshabilitado con `title` «Selecciona una escena» |

### 3.6 Teclado y foco

- Al abrir: foco en la celda **seleccionada** o, si no hay, en la primera habilitada; `aria-activedescendant` sobre la rejilla (`role=listbox` / `role=option`).
- **Trampa de foco** dentro del picker: `Tab` cicla rejilla → chips → búsqueda → pie → rejilla. No se escapa al resto del editor mientras esté abierto.
- `Esc` cierra y **devuelve el foco al disparador** (clip o botón). Sin excepción.
- `Intro` aplica lo mismo que el botón primario del pie («Sustituir» / «Insertar»); `Espacio` **no** aplica (para no chocar con el transporte del editor).
- El pie del picker tiene **siempre** un botón primario explícito, deshabilitado mientras no haya una celda seleccionable. Es la salida para quien usa ratón y no descubre el doble clic, y el punto de retorno del foco al aplicar.

---

## 4 · Regla de overlays: flotan, pero dentro del pane

Esta es la regla que evita el defecto que Tormen ve en otras apps: cosas que se salen del panel.

1. **Cero `position:fixed` en el plugin.** Ni diálogos, ni menús, ni toasts, ni tooltips. Si algo necesita cubrir la app, es que el diseño está mal.
2. **Todo overlay es `absolute` dentro de `.ed`** (que ya es `position:relative; overflow:hidden; contain:layout paint`). El dock recorta; el overlay nunca pinta fuera de sus 922 × 900.
3. **Escala de z-index, cerrada:**

| z | Capa |
|---|---|
| 3 | playhead |
| 45 | scrim del editor (nunca sobre el chat) |
| 50 | drawer (biblioteca / inspector) |
| 55 | popover (chip de modelo, tooltips de icono) |
| 60 | picker y diálogos modales del editor |

4. **Un modal a la vez.** Abrir picker cierra drawer; abrir drawer cierra picker. El popover del chip es el único que puede convivir con nada más porque no es modal.
5. **Alto acotado + scroll interno**: `max-height:calc(100% − tl − 26px)`; el cuerpo scrollea, la ventana no. En la maqueta, a 1024 el picker mide 454 px y scrollea por dentro.
6. **El scrim no cubre el chat.** El chat es de Hermes, no del plugin; atenuarlo sería secuestrar una superficie ajena.
7. **Nada de anotaciones flotantes de producto.** Las notas azules de la maqueta v3 son **documentación**, no UI. En el producto no hay cajas con explicaciones superpuestas al contenido: las explicaciones viven en el popover del chip, en el subtítulo del picker o en «Ayuda».
8. **Los tooltips** son `absolute` con `max-width:240px` y se recortan contra el borde del pane: si no caben a la derecha, se anclan a la izquierda del control. Nunca se salen del dock.
9. **Menús contextuales** (⋯): mismo criterio. Si el último ítem no cabe, el menú cambia de lado o scrollea; no se desborda.

---

## 5 · Atajos nuevos

Los de la v3 (espacio, J/K/L, ←/→, `Mayús+Z` ajustar, `Ctrl+Z`/`Ctrl+Mayús+Z`) se mantienen. **Nuevos** en esta variante:

| Atajo | Acción | Dónde |
|---|---|---|
| **B** | abre/cierra biblioteca (drawer) | editor |
| **I** | abre/cierra inspector (drawer) | editor |
| **S** | «Sustituir medio» de la escena seleccionada | editor |
| **Mayús+S** | «Insertar medio» después de la selección | editor |
| **Mayús+M** | lleva el foco al selector de modelo del chat (equivale a pulsar el chip, sin el popover) | editor |
| **↑ ↓ ← →** | mover por la rejilla del picker | picker |
| **Intro** | aplicar el medio seleccionado | picker |
| **/** | buscar en la biblioteca del picker | picker |
| **Tab / Mayús+Tab** | chips de filtro ↔ rejilla ↔ búsqueda | picker |
| **Esc** | cerrar overlay y devolver el foco al disparador | picker, drawers, popover |

Conflictos revisados: `S` no choca con el transporte (espacio) ni con split (la v3 no define split); `B`/`I` no chocan con nada existente; `Mayús+M` evita el mute de audio, que en la v3 no está asignado pero es el candidato natural para `M`.

---

## 6 · Criterios de aceptación U1–U4 (variante docked)

Cada criterio se prueba **midiendo**, no mirando. Todos son binarios.

### U1 · Reparto y degradación

| # | Se cumple si | Cómo se prueba |
|---|---|---|
| U1.1 | A 1440 el chat mide 518 ±1 y el editor 922 ±1 | `getBoundingClientRect()` de ambas raíces |
| U1.2 | A 1024 el editor mide 655 ±1 y a 900 mide 576 ±1, con el chat al 36 % | idem |
| U1.3 | El pane no tiene scroll horizontal ni vertical (`scrollWidth === clientWidth`) en los tres anchos | JS en el contenedor del plugin |
| U1.4 | El escenario mantiene 16:9 ±0,5 % en los tres anchos | cociente de medidas |
| U1.5 | La secuencia completa (16,2 s) cabe con la escala por defecto: 46 / 32 / 28 px/s | último clip `right` < ancho del editor |
| U1.6 | Abrir biblioteca o inspector **no** cambia el ancho del visor ni del timeline (0 px de salto) | medir antes/después |

### U2 · Chip de modelo

| # | Se cumple si | Cómo se prueba |
|---|---|---|
| U2.1 | Muestra **exactamente** el valor de `host.state.model`, sin normalizar ni abreviar el id | comparar `textContent` con el atom |
| U2.2 | No existe ningún control que emita cambio de modelo: ni `select`, ni menú, ni acción de plugin | revisar el DOM del chip y las acciones registradas |
| U2.3 | Al pulsar, el foco está en el compositor del chat (document.activeElement dentro del compositor) | `document.activeElement` tras el clic |
| U2.4 | El popover aparece **dentro** del rect del editor y se cierra con `Esc` y con clic fuera | rects + teclado |
| U2.5 | Estados «Sin sesión» y «modelo desconocido» pintan texto propio, nunca el último modelo visto ni un valor por defecto | forzar el atom a `''` y a un id inventado |
| U2.6 | `aria-label` contiene el nombre completo aunque la vista esté truncada | AX tree |

### U3 · Element picker

| # | Se cumple si | Cómo se prueba |
|---|---|---|
| U3.1 | Se abre en ≤ 200 ms desde S o desde «Reemplazar», **dentro** del rect del editor, anclado al clip seleccionado | rects + marca de tiempo |
| U3.2 | Sustituir conserva `start` e `in/out` cuando el medio nuevo es igual o más largo | comparar la escena antes/después |
| U3.3 | Si el medio es más corto, el `out` se recorta y el subtítulo lo avisa **antes** de aplicar | estado del picker |
| U3.4 | El texto (T1) de la escena no cambia al sustituir | diff del proyecto |
| U3.5 | El medio en uso aparece deshabilitado con «en uso en esta escena» | DOM |
| U3.6 | Todo el flujo es posible sin ratón: abrir, filtrar, mover, aplicar, cerrar | solo teclado |
| U3.7 | `Esc` cierra y devuelve el foco al disparador | `document.activeElement` |
| U3.8 | Con contenido que no cabe, scrollea el **cuerpo del picker**, no el pane | `scrollHeight` de cada uno |
| U3.9 | Estados vacío / sin resultados / cargando / error existen y no rompen el resto del editor | forzarlos |
| U3.10 | El pie tiene botón primario con el verbo correcto («Sustituir» / «Insertar»), deshabilitado sin selección, y hace lo mismo que `Intro` | DOM + teclado |

### U4 · Overlays contenidos

| # | Se cumple si | Cómo se prueba |
|---|---|---|
| U4.1 | `document.querySelectorAll('*')` filtrado por `position:fixed` devuelve **0** dentro del plugin | JS |
| U4.2 | Con cada overlay abierto, ningún descendiente del pane tiene rect fuera del rect del editor (±1 px) | recorrido de rects |
| U4.3 | Nunca hay dos modales abiertos; abrir uno cierra el otro | estado del DOM |
| U4.4 | El scrim no cubre el chat (su rect empieza en x = ancho del chat) | rect |
| U4.5 | Todo texto visible ≥ 4,5:1; ningún texto < 12 px salvo las dos excepciones de la v3 | medición de contraste y `font-size` |
| U4.6 | `Esc` cierra cualquier overlay sin dejar el foco en `body` | `activeElement` |

---

## 7 · Evidencia y qué queda abierto

**Medido en la maqueta** (1440 y 1024): reparto 518/922 y 369/655; escenario 893×502,3 y 634×356,6; picker 468×411 y 638×454 con `inside:true` en ambos; 0 desbordes de texto a 1440; contraste mínimo 7,52:1; `scrollWidth === clientWidth` en el documento en los tres anchos.

**Capturas**: `docs/qa/v31-dock-dark.png` (picker abierto, chip visible), `docs/qa/v31-chip-tip.png` (popover del chip + compositor enfocado), `docs/qa/v31-1024x700.png` (degradación con picker scrolleable).

**No probado / fuera de alcance de esta entrega** (declarado, no oculto):
- La maqueta **no** consume el atom real ni el SDK: `host.state.model` y `host.composer.focus()` están especificados, no ejercitados en el pane.
- El picker no habla con el servicio: no hay `POST /projects/<id>/scenes/<id>/media` en el contrato leído; **la sustitución necesita endpoint o reutilizar `PATCH` de escena** (ver decisiones).
- Sin probar lector de pantalla real (solo estructura AX prevista) ni zoom de navegador al 200 %.

### Decisiones necesarias (para Tormen)

1. **¿El 36/64 es fijo o arrastrable?** La v3.1 lo fija. Si el usuario puede arrastrar el divisor, hace falta recordar el ancho por sesión y un mínimo de 480 por lado; hoy no está pedido.
2. **¿Sustituir es un `PATCH` de escena o un endpoint propio?** El contrato actual no tiene «reemplazar medio»; hay que decidir si se reutiliza el `PATCH` de escena (más simple, conserva in/out en el cliente) o se añade `POST …/scenes/<id>/replace` (más explícito, permite validar duración en servidor).
3. **¿El picker permite importar un medio nuevo sin salir?** La v3.1 lo deja en un botón «Añadir medio» que abre el flujo de importación existente; meter la importación dentro del picker es más rápido pero alarga el componente.
4. **Por debajo de 560 px de editor** no hay diseño: se declara no soportado y el dock no debería permitirlo.
