# ui-spec **rev2** · Editor de vídeo (pane de Hermes Desktop)

- **Origen:** Harmonia (diseño/UI) · **Destino:** Tormen (Padre) → Athena/Hephaestus para implementar.
- **Fecha:** 2026-11-08, America/Caracas (UTC-4). **Tarea:** segunda pasada del spec tras F2 (backend real, maqueta medida).
- **Estado:** especificación **implementable**. Sustituye 6 secciones de `ui-spec.md` con material ya verificado; el resto del documento rev1 sigue vigente.
- **Regla de esta revisión:** solo entra lo que tiene evidencia (código leído, probe medido, captura). Lo que no, va a §14 como abierto, nunca como hecho.

---

## 0. Cómo leer esta revisión (y cuál es la fuente del estilo)

### 0.1 Qué sustituye y qué no

| Sección de `ui-spec.md` (rev1) | Estado en rev2 |
|---|---|
| §4 Inventario de componentes | vigente; **se añade §4.1** (sustituciones de componentes que el SDK no exporta) |
| **§5.2 Importación** | **sustituida** por §5.2 de este documento |
| **§5.3 Escenario (preview)** | **sustituida** por §5.3 de este documento |
| §5.1, §5.4–§5.9 | vigentes sin cambios |
| §6.1, §6.2, §6.4 | vigentes sin cambios |
| **§6.3 Endpoints (`ctx.rest`)** | **sustituida** por §6.3 de este documento (rutas loopback reales) |
| **§7 Estados** | **sustituida** por §7 de este documento |
| §8 Textos | vigente; §5.2/§5.3/§7 de rev2 añaden claves nuevas (`import.*`, `preview.*`, `error.*`) |
| **§9 Atajos** | **sustituida** por §9 de este documento |
| §10 Accesibilidad, §11 Pruebas, §13 Handoff | vigentes; §11 se amplía con las pruebas de importación de §14.3 |
| **§12 Decisiones** | **sustituida** por §12 de este documento |

Nada de rev1 se borra: `ui-spec.md` queda como histórico. **Este archivo manda** en las secciones marcadas.

### 0.2 Fuente única del estilo: `docs/mockup.html`

La maqueta es **autocontenida**: el CSS vive en su bloque `<style>` (líneas 7–464, **456 líneas efectivas**) y no hay `<link>` a ninguna hoja externa, ni CDN, ni JS. Eso es deliberado: abre igual por `::preview`, por `file://` y desde el visor de la app, sin dependencias que puedan no resolverse.

`docs/_mockup-style.css` era una **extracción literal** de ese bloque. Se comprobó que ambos eran idénticos byte a byte tras normalizar CRLF→LF (25 572 caracteres) y se retiró como fuente: hoy el archivo solo contiene el aviso, sin CSS. **Dos copias idénticas son dos verdades** y la primera edición en el lado equivocado se habría perdido.

- Fuente editable: `docs/mockup.html`.
- `docs/_mockup-style.css`: retirado, no editar, no usar en build.
- Comprobación de deriva (debe imprimir `456` y el hash):

```bash
cd video-editor/docs
python -c "import re,hashlib;h=open('mockup.html',encoding='utf-8').read();b=re.search(r'<style>(.*?)</style>',h,re.S).group(1).replace('\r\n','\n').strip();print(b.count(chr(10))+1, hashlib.sha256(b.encode()).hexdigest())"
# 456 26764c1dbbe5b1b7d5e4cf8573b45b98f60bf35f512908c7137d3b38ac8f9157
```

Si algún día hace falta la hoja suelta (build, lint de CSS), **se genera desde mockup.html**; nunca se edita a mano y nunca se copia de vuelta.

### 0.3 Lo que la maqueta ya demuestra (y lo que no)

- 6 estados conmutables por radios reales (alcanzables por teclado): **A sin proyecto · B sin medios · C cargando · D error · E edición · F exportando**.
- 900×560 px CSS, con `zoom` por debajo de 960 px en vez de scroll horizontal.
- Cero colores literales fuera de los cinco tokens del prelude; rellenos derivados con `color-mix()`.
- Capturas medidas en 4 skins (nous claro/oscuro, classic oscuro y variantes de estado) en `docs/qa/rev2-*.png`; **0 fallos AA** en la medición de rev2.
- El texto terciario real de la app (`--muted-foreground`, 54 %) mide **3.55:1** en claro y no sirve para 9–11 px; la maqueta usa derivados `--ink-2` (80 % → **7.8:1**) y `--ink-3` (68 % → **5.7:1**). En el plugin eso equivale a no usar `--ui-text-tertiary` por debajo de 14 px.
- **No** demuestra: estados G–J (§7) ni el flujo de importación con carpeta real; esas capturas faltan y están en §14.

---

## 4.1 Sustituciones de componentes que el SDK no exporta

`@hermes/plugin-sdk` no exporta `Slider`, `Progress`, `TabsContent`, `DialogClose` ni `KbdCombo` (rev1 §4, verificado). Estas son las sustituciones **cerradas**; no son un pendiente.

| Necesidad | No existe | Sustituto exacto | Reglas de implementación | Coste |
|---|---|---|---|---|
| Scrub y volumen | `Slider` | `<input type="range">` nativo | `accent-color: var(--ui-accent)`; `height: 32px` de caja de toque; `aria-label` obligatorio; `aria-valuetext` en tiempo legible (`00:03,4 de 00:16,2`) o porcentaje (`80 %`); el `value` numérico se mantiene y el `aria-valuenow` lo pone el navegador (no se sobreescribe a mano en `range`: duplicarlo confunde). Paso fino `1/30 s`; flechas y Home/End gratis. | 0 |
| Progreso de exportación | `Progress` | `<div role="progressbar">` propio | `aria-valuemin="0" aria-valuemax="100" aria-valuenow={pct} aria-valuetext="Etapa 2 de 4, 38 %" aria-label="Progreso de la exportación"`. Altura 3–4 px, relleno `--ui-accent`. **No** poner `aria-live` en la barra: el anuncio va en un `role="status"` hermano con el texto de etapa, para no locutar un porcentaje por frame. | 0 |
| Cuerpo de pestañas | `TabsContent` | render condicional | `{tab === 'props' && <Props/>}`. El panel visible lleva `role="tabpanel"`, `id` y `aria-labelledby` del `TabsTrigger` a mano (con `hidden` en el resto si se prefiere montarlos). **Trampa:** un campo no controlado dentro de un panel que se desmonta pierde el texto → el borrador del caption vive en el estado del contenedor, no en el `Textarea`. | 0 |
| Cerrar diálogo | `DialogClose` | `onOpenChange(false)` | El botón de la barra inferior es un `Button variant="outline"` que llama a `onOpenChange(false)`; la «X» es `Button variant="ghost" size="icon-sm"` con `aria-label="Cerrar"`. `Esc` lo gestiona Radix: **no** añadir handler propio. Al cerrar, el foco vuelve al disparador (lo hace Radix; no robar el foco a mano). | 0 |
| Mostrar un atajo | `KbdCombo` | `Kbd` + separador | `<span aria-label="Ctrl más Z"><Kbd>Ctrl</Kbd><span aria-hidden="true"> + </span><Kbd>Z</Kbd></span>`. En Mac se pinta `⌘` con el mismo helper de plataforma de rev1 §9. Nunca `KbdCombo`. | 0 |
| Vacíos / errores | `EmptyState` con icono y acción | hermanos | `EmptyState` solo acepta `title`/`description`: el icono y los botones van **como hermanos debajo**, dentro del mismo contenedor centrado (así está en la maqueta, `.es__icon` + `.es__actions`). | 0 |

Nada de esto requiere cambios en el SDK. Si el SDK llegara a exportar `Slider`/`Progress`, se sustituyen sin tocar el diseño (mismas medidas y mismo texto accesible).

---

## 5.2 Importación

### 5.2.1 El modelo real: **dos permisos distintos**

Esto es lo que rev1 no tenía y es la causa número uno de fricción si se ignora:

1. **Permiso de la app (`ctx.files`)** — la app concede al plugin leer **una carpeta** elegida por el usuario con su propio picker. El plugin la recibe como handle opaco (`folder.id`) y solo puede navegar **por ruta relativa** dentro de ella. Se recuerda entre arranques, aparece en **Capacidades → Plugins → Acceso a carpetas** y el usuario puede revocarla ahí.
2. **Permiso del servicio (`mediaRoot`)** — el servicio Python tiene **su** carpeta de medios, la que devuelve `GET /grants` (`{mediaRoot}`), y **solo acepta rutas dentro de ella** (`verify_media_file` rechaza traversal, absolutas fuera, symlinks y junctions). No sabe nada de los grants de la app.

**En el MVP los dos permisos tienen que apuntar a la misma carpeta.** El pane no copia, no mueve ni reescribe rutas para "arreglarlo": compara `folder.path` con `mediaRoot` y, si no coinciden, lo dice y pide elegir otra. La alternativa (un endpoint para conceder medios al servicio) es backend nuevo → §12 D5.

```
usuario elige carpeta ──► ctx.files (app)        ──► podemos listar y leer
                        └► GET /grants mediaRoot  ──► el servicio puede importar
                        ambas deben ser la misma ruta
```

### 5.2.2 API real de `ctx.files` (leída del SDK, no supuesta)

Todas las llamadas **devuelven un resultado, ninguna lanza**. Ante un build sin la puerta, `{ ok:false, error:'unavailable' }`.

| Miembro | Firma / resultado | Uso en el editor |
|---|---|---|
| `dataFolder` | `'data'` | Carpeta privada del plugin, sin prompt. Solo caché/índice propio. |
| `requestFolder()` | `{ok, folder:{id,name,path}}`; `folder` viene **`null`** si el usuario cancela | Abre el picker de la app. `error:'protected'` si la carpeta contiene datos de Hermes. |
| `folders()` | `Promise<PluginFolder[]>` | Reutilizar una concesión previa **sin volver a preguntar**. Vacío si no hay puerta. |
| `release(id)` | `Promise<boolean>` | Devolver la carpeta (también se revoca en Ajustes). |
| `list(id, rel?)` | `{ok, entries:[{name, path, isDirectory}], truncated}` | Navegación del diálogo. `path` es relativo a la carpeta y se devuelve tal cual al servicio. Máx. **10 000** entradas; `truncated` avisa. |
| `stat(id, rel)` | `{ok, exists, isDirectory?, size?, mtimeMs?}` | Tamaño y tipo antes de importar (para el listado y para bloquear > lo razonable). |
| `readText(id, rel)` | `{ok, text, size, mtimeMs}` | **No se usa** para medios. |
| `readDataUrl(id, rel)` | `{ok, url:'data:…;base64,…'}` | Solo **miniaturas de imagen** ≤ **16 MiB**. Nunca clips. |
| `writeText(id, rel, text, {exclusive})` | `{ok, path, size, mtimeMs}` | Solo `writeText('data', …)` para historial/índice propio si excede `ctx.storage`. **Nunca** sobre medios del usuario. |
| `rename`, `trash` | — | **No se usan.** El editor no renombra ni envía a la papelera los originales. |

### 5.2.3 Errores y su copy exacto

| `error` | Cuándo | Copy (es-ES) | Acción ofrecida |
|---|---|---|---|
| `unavailable` | build sin puerta de archivos | «Esta versión de Hermes no permite elegir carpetas desde un plugin.» + línea con la ruta de medios | «Ver ruta de medios» (muestra `mediaRoot` para copiar allí los archivos fuera del pane) |
| `protected` | carpeta con datos de Hermes (`~/.hermes`, perfiles, `config.yaml`, `.env`, auth), o `~/.ssh`, `/proc` | «Esa carpeta contiene datos de Hermes y no se puede usar como medios.» | «Elegir otra carpeta» |
| `not-granted` | permiso revocado o carpeta de otro plugin | «Hermes ya no tiene permiso sobre esa carpeta.» | «Volver a elegirla» |
| `folder-missing` | la carpeta ya no está | «La carpeta ya no está en su sitio.» | «Elegir otra carpeta» |
| `folder-changed` | movida o reemplazada | «La carpeta se movió o se reemplazó. Vuelve a elegirla.» | «Volver a elegirla» |
| `sensitive-file` | `.env`, claves SSH y similares, aun dentro de una carpeta concedida | ««{nombre}» no se puede usar como medio.» | — (se omite del listado) |
| `outside-folder` / `invalid-path` | ruta con `..`, absoluta, letra de unidad o enlace que sale de la carpeta | «Esa ruta queda fuera de la carpeta concedida.» | — (defecto si aparece: el `path` lo devuelve `list`) |
| `too-large` | lectura por encima del límite | ««{nombre}» supera el límite de {n} MiB.» | — |
| `binary` | lectura de texto sobre binario | no aplica (no se lee texto de medios) | — |
| `io-error` | fallo del sistema de archivos | «No se pudo leer la carpeta.» | «Reintentar» |

El SDK define además `exists`, `is-directory`, `not-a-directory` y `not-a-file`. **No aplican** a este flujo: no se escribe, y `isDirectory` de `list()`/`stat()` filtra antes de intentar leer un directorio. Si aparecieran, es un defecto nuestro, no del usuario: al `LogView` y mensaje genérico.

Nunca se muestra `error` crudo al usuario; el código va al `LogView`.

### 5.2.4 Límites que condicionan el diseño

| Límite | Valor | Consecuencia en la UI |
|---|---|---|
| Texto (lectura/escritura) | **4 MiB**, rechazo, nunca truncado | irrelevante para medios |
| `data:` URL | **16 MiB** | solo miniaturas; un PNG de 20 MiB cae al icono de tipo |
| Entradas por `list()` | **10 000** | si `truncated`: «Se muestran los primeros 10 000 elementos. Abre una subcarpeta.» — **no** se inventa un total (la API no lo da) |
| Cuerpo JSON del servicio | **4 MiB** (`MAX_BODY_BYTES`) | no se suben archivos por HTTP: se pasan rutas |
| Carpetas de Hermes | inalcanzables por diseño | `protected` siempre; el fixture de pruebas vive fuera: `C:/Users/EgtYP/Videos/hermes-spike-fixtures` |

### 5.2.5 Flujo completo (I1–I6)

| # | Paso | Llamada real | UI |
|---|---|---|---|
| I1 | Comprobar servicio | `GET /health` → `{ok, mediaRoot, presets, queue…}` | si falla → estado **D**; el botón «Importar medios» queda deshabilitado con `Tip` «El servicio del editor no responde». |
| I2 | Saber qué carpeta puede leer el servicio | `GET /grants` → `{mediaRoot}` | el diálogo muestra **siempre** la ruta de medios en una línea (`header.mediaRoot`), en `--ink-3` 10 px. |
| I3 | Reutilizar concesión | `ctx.files.folders()` y comparar `path` con `mediaRoot` | si coinciden: se salta el picker. Si no hay ninguna: paso I4. |
| I4 | Pedir carpeta | `ctx.files.requestFolder()` | `folder === null` → cierra sin ruido. `protected`/`unavailable` → §5.2.3. |
| I5 | Comparar y navegar | `list(id, rel)` + `stat(id, rel)` | si `folder.path` ≠ `mediaRoot` (ni está dentro): aviso en el diálogo «El servicio solo lee {mediaRoot}. Elige esa carpeta.» + «Elegir otra». **No** se reescribe la ruta. Navegación por subcarpetas con `isDirectory`; filtro por extensión (§5.2.6). |
| I6 | Importar selección | por archivo, **de uno en uno**: `POST /projects/<id>/media` `{path}` | fila por archivo con estado «Importando… / Añadido / Error»; el 201 devuelve el pane completo del proyecto, así que **no** hace falta un `GET` extra. |

Respuesta de `POST /projects/<id>/media` (201): el mismo payload que `GET /projects/<id>` (§6.3), con el `media[]` ya actualizado y `previewUrl` por asset. Errores: `400` con `{error}` si el archivo no tiene vídeo ni audio («no contiene vídeo ni audio») o si la ruta se sale de `mediaRoot`; `404` si el proyecto no existe.

Dos detalles del endpoint que el pane **debe** aprovechar (leídos en `add_media`, no supuestos):

- **El asset se identifica por ruta.** Reimportar el mismo `path` no duplica el asset: conserva su `id` y solo refresca `sha256`/`bytes`. Es lo que hace posible «Volver a vincular» del estado **H** sin romper las escenas que lo usan.
- **`{path, scene:false}`** registra el medio **sin** crear escena. Se usa al revincular (H) y al reemplazar el clip de una escena existente; el valor por defecto es `scene:true`.

**Concurrencia:** un archivo a la vez. El servicio renderiza un job a la vez y `add_media` hace `probe` + `sha256`; en paralelo se castiga el disco sin ganar nada.

### 5.2.6 Qué **no** hace el editor (y por qué)

- **No sube bytes.** El servicio no tiene endpoint de subida y `MAX_BODY_BYTES` son 4 MiB; además los originales no se copian (se referencian por ruta relativa dentro de `mediaRoot`).
- **No arrastra y suelta como camino de importación.** En Electron moderno el drop entrega `File` sin `path` utilizable, y sin endpoint de subida no hay forma de convertir ese `File` en un medio. La zona de arrastre **existe visualmente pero deshabilitada**, con copy honesto (§7 estado B). Reactivarla exige endpoint + medición de subida → §12 D7.
- **No lee clips con `readDataUrl`.** 16 MiB no dan para vídeo; un clip de 8,9 MB entraría y uno de 90 s no. El preview va por HTTP con Range (§5.3).
- **No toca los originales:** ni `writeText`, ni `rename`, ni `trash` sobre medios del usuario. El único uso de escritura es `dataFolder` para caché propio.
- **No importa carpetas de Hermes** ni intenta rodear `protected`. `raw/` del vault queda fuera de alcance por regla del workspace.

Extensiones aceptadas (las que el servicio sabe tipar y probar): `.mp4 .m4v .mov .mkv .webm .avi .png .jpg .jpeg .webp .bmp .m4a .mp3 .wav`. Cualquier otra se muestra atenuada con `Tip` «Formato no admitido».

---

## 5.3 Escenario (preview) — **ya verificado, deja de ser bloqueante**

### 5.3.1 Evidencia medida

Probes guardados por el pane del spike en la app real (tabla `plugin_probes`, 7 filas):

| Probe | Resultado |
|---|---|
| `range_probe` | `status 206`, `contentRange "bytes 0-65535/8884986"`, `acceptRanges "bytes"`, `contentType "video/mp4"` |
| `preview_metadata` | `duration 8`, `videoWidth 1280`, `videoHeight 720`, `readyState 4`, `networkState 1`, `mode "url"` |
| `preview_canplay` | `readyState 4`, `duration 8`, `mode "url"` |

Conclusión: el renderer (`origin file://`) **puede** cargar el MP4 por HTTP loopback en un `<video>`; la **CSP no bloquea media**. El `<video>` reproduce con URL directa y el servicio responde `206` con `Content-Range`. Rev1 lo marcaba como incógnita que bloqueaba P1/P6: **queda desbloqueado**.

Alcance de la prueba: se hizo en un pane montado en esta app (spike F1), no en `plugin.js`. Volver a pasarla dentro del plugin es parte de V4/V6, no un riesgo nuevo.

### 5.3.2 Controles

| # | Control | Implementación | Comportamiento |
|---|---|---|---|
| P1 | Marco de vídeo | `<video>` nativo en contenedor `aspect-ratio: 16/9` (o `9/16` en vertical) | `src = base + media[].previewUrl` (`/media/<pid>/<assetId>`). `preload="metadata"`, `playsInline`, sin `autoplay`, `muted` inicial según `ctx.storage`. Controles propios (§5.4): el `<video>` no muestra `controls`. |
| P2 | Caption overlay | capa absoluta `bottom: 8%`, ancho máx. 82 % | Refleja el texto de la escena en el tiempo actual. Fondo `color-mix(in oklab, var(--ui-bg-editor) 72%, transparent)`, texto `--ui-text-primary` 13 px. Es preview, no editable. |
| P3 | Etiqueta de calidad | `Badge variant="muted"` | **«Vista previa»**, no «Preview 540p»: el servicio sirve el **original** con Range (no hay proxy). Prometer 540p sería mentir en la etiqueta. |
| P4 | Guías de zona segura | `Switch` en el menú `⋯` | Persistido en `ctx.storage` (`preview.guides`). Dos rectángulos al 90 % / 80 % con `outline: 1px dashed`. |
| P5 | Sin medios | `EmptyState` dentro del marco | «Aquí verás tu vídeo» / «Importa un clip para empezar.» + botón hermano «Importar medios». |
| P6 | Cargando | `Skeleton` 16:9 + texto de etapa | «Preparando la vista previa…». **Nunca un póster falso**: sin `poster` inventado; si no hay primer frame, fondo del marco. |
| P7 | Fallo de reproducción | `ErrorState` dentro del marco | «No se pudo reproducir la vista previa» / «El clip está en su sitio; el servicio no respondió a tiempo.» + «Reintentar». El botón de exportar **no** se bloquea por esto (el render usa el archivo, no el `<video>`). |

### 5.3.3 Detalles que fallan si se ignoran

- **`Cache-Control: no-store`** en todas las respuestas: cada `seek` vuelve a pedir rangos. Es correcto (contenido cambiante) pero implica que el scrub no debe disparar un `src` nuevo por cada movimiento: se cambia `currentTime`, nunca `src`.
- **`src` estable:** un `src` nuevo por render reinicia el buffer y provoca parpadeo. La clave de React del `<video>` no debe incluir la revisión; solo el `assetId`.
- **`Range` y `206`** los pone el servidor; el `<video>` ya los usa. No hace falta `fetch` manual para reproducir.
- **Autoplay:** el navegador exige `muted` para arrancar solo. El botón de play es explícito; no se autoplay nunca (también por `prefers-reduced-motion`).
- **`currentTime` y 1/30 s:** el scrub es `step=0.0333`; el tiempo mostrado se formatea con coma decimal es-ES y `tabular-nums` para que no baile.
- **El preview decodifica el original.** Un clip 4K puede tironear. El MVP lo acepta (material de entrega 720p) y el proxy 540p sigue siendo opcional futuro (§12 D6). **No medido con material real** → §14.

### 5.3.4 Fallback si algún día cambia la CSP

Hoy no se usa. Se documenta para que nadie improvise:

```js
// solo si <video src> falla por CSP (media-src) o por un proxy que rompa Range
const res = await fetch(url)                 // descarga completa: sin Range
const blob = await res.blob()
const objectUrl = URL.createObjectURL(blob)
video.src = objectUrl
// al desmontar / cambiar de asset: URL.revokeObjectURL(objectUrl)
```

Condiciones para activarlo: (a) el `<video>` falla con `error.code === MEDIA_ERR_SRC_NOT_SUPPORTED` **y** el `fetch` del mismo URL responde 200; (b) el archivo es pequeño (referencia: < 200 MB; por encima se muestra «No se puede previsualizar aquí» y se ofrece exportar). Coste: memoria del tamaño del clip y pérdida del streaming. El fallback está implementado en el spike pero **no se ejercitó** (limitación declarada allí); en el plugin debe existir el código y una prueba que lo fuerce con un `src` inválido.

---

## 6.3 Contrato real del servicio core (loopback)

Base: `http://127.0.0.1:8765` (`SERVICE_VERSION = "0.2.0"`), constante `DEFAULT_SERVICE` en `plugin.js`. Sin TLS, **sin autenticación de red** → defensa por guardas (§6.3.3).

**`plugin_api.py` no se usa en el MVP.** No hay `manifest.api`, no hay `ctx.rest`, no hay `ctx.socket` y por tanto **no hace falta la ventana de recarga del gateway**. Ese patrón queda como opción de empaquetado futuro; si algún día se usa, el contrato de esta sección no cambia (solo el prefijo).

### 6.3.1 Rutas

| Método | Ruta | Cuerpo / query | Respuesta |
|---|---|---|---|
| `GET` | `/health` | — | `{ok, service, engine, ffmpeg, ffmpegVersion, dataRoot, mediaRoot, queue, recovered, presets, startedAt}` |
| `GET` | `/grants` | — | `{mediaRoot}` — **la única carpeta que el servicio puede leer** |
| `GET` | `/projects` | `?session=&cwd=` | `{projects:[{projectId,title,revision,scenes,updatedAt,sessionId,cwd}], mediaRoot}` |
| `POST` | `/projects` | `{title?, session_id?, cwd?}` | **201** payload completo (§6.3.2), `revision 0` |
| `GET` | `/projects/<id>` | — | payload completo (§6.3.2) |
| `PUT` | `/projects/<id>` | `{revision, project}` o `{revision, draft}` | **200** payload completo · **409** `{error, current_revision}` |
| `POST` | `/projects/<id>/media` | `{path}` (relativa a `mediaRoot`, o absoluta **dentro** de ella) | **201** payload completo con `media[]` actualizado y escena creada · **400** `{error}` |
| `GET` | `/media/<pid>/<assetId>` | `Range: bytes=…` | **200/206**, `Content-Type` por extensión, `Accept-Ranges: bytes`, `Content-Range`, `Cache-Control: no-store` |
| `POST` | `/projects/<id>/export` | `{preset, captions}` | **202** `{jobId, deduped, state}` · **400** `{error, errors:[…]}` si el proyecto no está listo |
| `GET` | `/jobs/<id>` | — | job + `outputUrl` (solo si `state === 'succeeded'`, si no `null`) + `outputPath` |
| `GET` | `/jobs` | `?limit=` | `{jobs:[…]}` (1–200) |
| `POST` | `/jobs/<id>/cancel` | — | job actualizado; `cancelRequested: true`. Si estaba `queued` pasa a `cancelled` en el acto; si corría, se pide cancelación cooperativa (≤10 s; medido 0,52 s) |
| `GET` | `/jobs/<id>/output` | `Range` | **200/206** del MP4 final, `video/mp4` · **409** «el trabajo todavía no tiene salida» · **410** si el archivo se borró del disco |
| `GET` | `/events` | `?since=<seq>&timeout=<s>` | `{events:[…], lastSeq}`; `timeout=0` = sondeo inmediato, sin bloqueo |
| `POST` | `/admin/stop` | — | **200** `{stopping:true}` o **403** si la administración está deshabilitada (solo operación/tests) |

`presets` en `/health` hoy es `["mp4-720p30"]`: **un solo preset**. La UI no debe ofrecer una lista que el servidor no tenga.

**Fuente canónica y deltas.** `core/CONTRATO.md` (apareció durante esta pasada, 18:30) es el contrato máquina-legible del servicio y coincide con esta tabla. Dos diferencias, comprobadas contra `app.py` y por eso corregidas aquí: el **202 de export también devuelve `state`** (CONTRATO.md solo lista `{jobId, deduped}`) y `/jobs/<id>/output` responde **409** si el job aún no ha terminado y **410** si la salida se borró. Si ambos documentos vuelven a divergir, manda `core/service/app.py`; se corrige aquí y se avisa a Athena.

### 6.3.2 Payload de proyecto (lo que consume el pane)

```json
{
  "projectId": "prj_9f3c…",
  "revision": 7,
  "docHash": "…",
  "updatedAt": "2026-11-08T22:10:04Z",
  "project": { "…documento canónico…": "…" },
  "ui": { "…adaptador de UI…": "…" },
  "media": [
    { "id": "a1b2c3", "path": "clips/demo.mp4", "kind": "video",
      "bytes": 8884986, "sha256": "…", "exists": true,
      "previewUrl": "/media/prj_9f3c…/a1b2c3" }
  ]
}
```

- La UI pinta desde `ui` (forma de edición); `project` no se toca en el pane.
- `media[].exists === false` → estado **H**; el export se bloquea (`validate_for_export`).
- `previewUrl` es **relativo**: siempre se prefija con la base. No construir la URL a mano con el nombre del archivo.

### 6.3.3 Guardas, errores y ciclo

- **Host:** solo `127.0.0.1:<puerto>`, `localhost:<puerto>`, `[::1]:<puerto>`. Si no → **403** `host no permitido`.
- **Origin:** vacío, `null`, `file://` o los mismos loopback. Cualquier otro → **403** `origen no permitido`. Esto es lo que impide que una web abierta en el navegador encole renders.
- **Envoltura de error:** `{error: "<mensaje>", …extra}`. `409` añade `current_revision`; `400` de export añade `errors` (lista de lo que falta). `413` si el cuerpo supera 4 MiB. `404` ruta/proyecto/job desconocido.
- **Idempotencia de export:** la misma revisión + preset + captions devuelve el **mismo** `jobId` con `deduped: true` mientras el job esté en cola, corriendo o haya salido bien. Si falló, se permite reintentar. La UI debe decir «Ya hay una exportación de esta revisión» y **abrir el job existente**, no crear otro.
- **Progreso:** `state` (`queued`→`running`→`succeeded`/`failed`/`cancelled`), `stage` (`queued`→`probing`→`rendering`→`done`), `progress` 0–100, `eta_s`, `message`. Se consume con `GET /events?since=<lastSeq>&timeout=20` (long-poll) y, si el long-poll falla o el `ctx` está en remoto, **sondeo cada 3 s** con `timeout=0`. Nunca se calcula un porcentaje en el cliente: se pinta el que llega.
- **Cancelación** cooperativa: se pide y se espera; la UI muestra «Cancelando…» hasta que el `state` cambia. No se mata el proceso desde el pane.
- **Un job a la vez:** `queue` en `/health` lo dice. Con la cola llena, exportar encola; el diálogo muestra la posición.

### 6.3.4 Mapa control → llamada

| Control del pane | Llamada |
|---|---|
| Arranque | `GET /health` + `GET /grants` |
| Lista de proyectos (H3/A) | `GET /projects?session=<id>&cwd=<path>` |
| Crear proyecto | `POST /projects` |
| Abrir proyecto | `GET /projects/<id>` |
| Autosave / Guardar | `PUT /projects/<id>` con la `revision` en mano |
| Importar medio | `POST /projects/<id>/media` `{path}` |
| `<video>` del preview | `GET /media/<pid>/<assetId>` (lo hace el navegador, con Range) |
| Exportar | `POST /projects/<id>/export` |
| Progreso / ETA | `GET /events` (o `GET /jobs/<id>`) |
| Cancelar | `POST /jobs/<id>/cancel` |
| Abrir el MP4 | `GET /jobs/<id>/output` (o el `outputPath` en el explorador) |

---

## 7. Estados (disparador real, no supuesto)

| Estado | Disparador verificable | Qué se pinta | Copy |
|---|---|---|---|
| **A · Sin proyecto** | `GET /projects` devuelve `[]`, o `lastProjectId` ya no existe (`404`) | Header «Sin proyecto»; `EmptyState` centrado; escenario vacío; footer con «Importar» y «Exportar» deshabilitados + `Tip` «Abre un proyecto primero». | «Todavía no hay proyecto abierto» / «Elige un proyecto de esta sesión o crea uno nuevo para montar tu vídeo.» |
| **B · Proyecto sin medios** | payload con `media.length === 0` (o `scenes.length === 0`) | Zona de importación de 190 px (borde discontinuo) **sin** promesa de arrastre; rail con `EmptyState`. | «Elige una carpeta con tus clips» / «El editor lee los archivos de la carpeta de medios; no los copia.» + botón «Importar medios». Nota al pie: «Arrastrar está desactivado en esta versión.» |
| **C · Cargando** | `GET /health` + `GET /projects/<id>` en vuelo | `Skeleton` del escenario 16:9, 3 filas de escena, 2 campos; `aria-busy="true"` en el pane. | «Cargando proyecto…», timecodes `--:--`. **Cero datos de ejemplo.** |
| **D · Servicio no disponible** | `fetch` a `/health` lanza (`ECONNREFUSED`/timeout 2 s) o `5xx` | `ErrorState` con dos acciones; header con `Badge variant="destructive"` «Sin conexión»; el resto del pane no interactivo. | «El servicio del editor no responde en 127.0.0.1:8765.» / «Tus medios no se han modificado.» + «Reintentar» + «Ver registro» |
| **E · Edición** | payload válido y `media.length > 0` | Layout completo (rev1 §2). | — |
| **F · Exportando** | `POST …/export` → 202, job en `queued`/`running` | Diálogo §5.8 con etapas reales (`probing`, `rendering`), `role="progressbar"` + `role="status"` hermano; pane atenuado con `aria-busy="true"` pero **reproducible** si se cierra el diálogo. | «Preparando el render…» / «Renderizando 38 % · quedan 4 s» |
| **G · Conflicto de revisión** | `PUT` → 409 con `current_revision` | `Dialog` con la revisión real recibida (no un número inventado). | «Hay cambios más nuevos» / «La revisión {current_revision} se guardó en otro lugar. Tu copia es la {revision}.» · acciones: «Recargar y perder mis cambios» (destructivo), «Guardar como copia», «Cancelar» |
| **H · Medio faltante** | `media[].exists === false` y/o `scene.needsRelink === true` | `Badge variant="warn"` «Falta {nombre}» en la fila; «Exportar» falla en `validate_for_export` («media not relinked»), así que se deshabilita antes con `Tip`; acción «Volver a vincular» (abre §5.2 y hace `POST …/media` con `{path, scene:false}`). | «Falta {nombre}» / «El archivo se movió o se borró de la carpeta de medios.» |
| **I · Importación bloqueada** | `requestFolder`/`list` devuelve `ok:false` (§5.2.3) o `folder.path` ≠ `mediaRoot` | El diálogo de importación sigue abierto con el aviso **dentro**, no un toast que se pierde; el botón «Importar seleccionados» deshabilitado. | según tabla §5.2.3; el caso de carpeta distinta: «El servicio solo lee {mediaRoot}. Elige esa carpeta.» |
| **J · Importación parcial** | algún `POST …/media` responde 400, o `list.truncated === true` | Lista de resultados por archivo (añadido / error) con el motivo; los que sí entraron quedan en el proyecto. | «{n} de {m} archivos añadidos.» + motivo por fila; truncado: «Se muestran los primeros 10 000 elementos. Abre una subcarpeta.» |

**Cobertura de la maqueta:** A–F tienen captura (`docs/qa/rev2-*.png`). **G–J no la tienen** y hay que añadirlas a la maqueta en la siguiente pasada (los estados I/J son diálogo + lista, no un pane completo; G y H sí caben como variantes de E). Registrado como pendiente en §14.2, no como hecho.

**Regla transversal:** ningún estado inventa cifras. Sin `progress`, no hay porcentaje; sin `eta_s`, no hay «quedan N s»; sin `current_revision`, no se escribe un número de revisión.

---

## 9. Atajos

Alcance **del pane**, nunca global: un listener en el contenedor raíz, activo solo si el pane o un descendiente tiene el foco. Guard: si `event.target` es `input`, `textarea`, `select` o `[contenteditable]`, solo pasan los combos con `Ctrl/⌘`; **nunca** `Espacio` ni flechas (si no, el scrub y los campos de tiempo dejan de funcionar).

| Tecla | Acción |
|---|---|
| `Espacio` | Reproducir / pausar (no dispara si el foco está en un control) |
| `←` / `→` | −/+ 1 fotograma (1/30 s) |
| `Shift+←` / `Shift+→` | −/+ 1 s |
| `Inicio` / `Fin` | Ir al inicio / al final |
| `I` / `O` | Fijar entrada / salida en el cursor |
| `S` | Partir en el cursor (mín. 0,3 s por lado; si no, no hace nada y el `Tip` explica) |
| `Alt+↑` / `Alt+↓` | Subir / bajar la escena seleccionada, con anuncio `aria-live` |
| `Supr` | Eliminar la escena seleccionada (con `ConfirmDialog`) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Deshacer / rehacer |
| `Ctrl+S` | Guardar (si no hay cambios: «Sin cambios que guardar», `role="status"`) |
| `Ctrl+E` | Abrir el diálogo de exportación (deshabilitado sin escenas) |
| `Esc` | Cerrar diálogo / quitar selección |

Reglas de implementación:

- **Cómo se muestra:** `Kbd` + separador, nunca `KbdCombo` (§4.1). En Mac se pinta `⌘` con un helper de plataforma; el código compara `metaKey || ctrlKey`.
- **`Esc` dentro de un diálogo lo gestiona Radix:** no duplicar el handler, o se cierra dos veces (una por el diálogo y otra por el pane).
- **Nada en `KEYBINDS_AREA`:** registrar `Espacio` a nivel de app le robaría la tecla al chat.
- **Un solo anuncio por acción:** el cambio de escena se anuncia por `aria-live`, no por `title` ni por foco forzado.
- **Deshacer** cubre: reordenar, recortar, partir, caption, duración, volumen, transición. No cubre: importar (es aditivo y visible) ni exportar.

---

## 12. Decisiones (estado real a 2026-11-08)

| # | Decisión | Estado | Quién |
|---|---|---|---|
| **D1** | **Motor único: FFmpeg 9.0.1** por CLI con allowlist de flags, un job a la vez, sin segundo renderer. Addenda de ADR-001: `-filter_complex_script` no existe en este build → grafo inline con verificación byte a byte y techo de 20 000 caracteres. | **Aprobada** — no se reabre | Tormen |
| **D2** | **Servicio en loopback** (`127.0.0.1:8765`), sin auth de red, con guardas de `Host`/`Origin` (`file://`, `null`, loopback). El pane habla por `fetch` directo; medido 200 desde el renderer. | **Aprobada** (decisión de arquitectura del MVP) | Tormen/Athena |
| **D3** | **`plugin_api.py` no se usa en el MVP.** Sin `manifest.api`, sin `ctx.rest`, sin `ctx.socket`, sin ventana de recarga. Queda como opción de empaquetado futuro. | **Aprobada**; Gate R solo aplica si se empaqueta | Tormen |
| **D4** | **Sustituciones de SDK** (§4.1): `input[type=range]`, `role="progressbar"` propio, render condicional en vez de `TabsContent`, `onOpenChange` en vez de `DialogClose`, `Kbd` en vez de `KbdCombo`. | **Aprobada** (coste 0, sin cambios de SDK) | Harmonia |
| **D5** | **Doble permiso**: la carpeta concedida en `ctx.files` debe ser la misma que `mediaRoot` del servicio. Si no coincide, se avisa y se pide otra; **no** se copia ni se reescribe la ruta. Alternativa futura: endpoint `POST /grants` para que el servicio acepte la carpeta elegida (requiere backend y validación propia). | **MVP: así**; alternativa **pendiente** de decisión | Tormen/Athena |
| **D6** | **Preview = original con Range**, etiqueta «Vista previa». El proxy 540p queda como mejora opcional (hoy no existe y no se promete). Fallback `fetch`+blob documentado, sin ejercitar. | **Aprobada**; proxy sin fecha | Harmonia/Tormen |
| **D7** | **Arrastrar y soltar desactivado** hasta que exista endpoint de subida; la importación va por carpeta concedida. Reactivarlo exige medir subida >100 MB y decidir si se copian archivos (hoy los originales no se copian). | **Pendiente** | Tormen |
| **D8** | **Export idempotente** (`deduped: true` reutiliza job vivo o exitoso) y **cancelación cooperativa**. La UI abre el job existente en vez de crear otro. | **Aprobada** (implementada y probada en el servicio) | Athena |
| **D9** | **Pausa de exportación: no se expone.** El motor no ofrece pausa en punto seguro; la UI dice «Cancelar» y permite reintentar. | **Aprobada** (honesta por diseño) | Tormen |
| **D10** | **Presupuesto de latencia:** el umbral relativo del 20 % no se cumple de forma estable (3 corridas: +184,9 %, +44,8 %, −10,4 % con p95 absoluto < 7 ms). Propuesta: presupuesto **absoluto p95 ≤ 15 ms** y máx ≤ 100 ms con 1 job. | **Pendiente de aprobación** | Tormen |
| **D11** | **Split como esencial** mientras la UI lo muestre; si se retira, caen `S` y la acción del menú sin tocar el resto. | **Aprobada condicional** | Tormen |
| **D12** | **1080p no se promete**: el MVP es 720p/30 (`presets: ["mp4-720p30"]`). Subir de resolución exige medir pared, CPU y RSS (§14). Proyectos de 40 escenas pueden acercarse al techo de 20 000 caracteres del grafo: medir antes de prometer. | **Pendiente de medición** | Athena |
| **D13** | **Idioma:** `es` primario y `en` mínimo en i18n. Los mensajes de FFmpeg se muestran crudos **solo** en `LogView`, nunca como copy de usuario. | **Aprobada** | Harmonia |

### 12.1 Pendientes reales (nada más)

1. **P2 y P5 del spike:** los dos clics que faltan (conceder carpeta desde el pane y lanzar un render desde el pane). Requieren ventana con Tormen; sin ellos, la importación y el render están probados por HTTP pero no por clic.
2. **Gate R:** solo si se decide empaquetar `plugin_api.py`. No bloquea el MVP.
3. **Mediciones abiertas:** preview con material real 4K (tirones), render 1080p, proyecto de 40 escenas, subida >100 MB si algún día se reactiva el drop.
4. **Maqueta:** estados G–J sin captura.

---

## 14. Verificación de esta entrega

### 14.1 Qué se leyó y se ejecutó para escribir esto

| Fuente | Qué se tomó |
|---|---|
| `core/service/app.py` (803 líneas) | rutas, códigos, payloads, guardas, `MAX_BODY_BYTES = 4 MiB`, `SERVICE_VERSION 0.2.0`, `ALLOWED_PRESETS` |
| `core/service/journal.py` | columnas del job (`state`, `stage`, `progress`, `eta_s`); `request_cancel` |
| `core/CONTRATO.md` (18:30) | contraste del contrato; 2 deltas corregidos a favor de `app.py` (§6.3) |
| `docs/REPORTE-F2-backend.md` | 230 tests OK / 2 skipped; e2e medido; dedupe; guardas |
| `spike/REPORTE.md` | probes `range_probe` 206, `preview_metadata` 1280×720, `preview_canplay`; CSP no bloquea media |
| SDK de Hermes (`apps/desktop/src/contrib/plugin-files.ts` + `website/docs/developer-guide/desktop-plugin-sdk.md`) | firmas, formas de resultado, lista de errores, límites 4 MiB / 16 MiB / 10 000, `protected`, `sensitive-file` |
| `docs/mockup.html` | 456 líneas de estilo, 6 estados, tokens, `role="progressbar"`, `input[type=range]` con `aria-valuetext` |
| `docs/qa/rev2-*.png` | 9 capturas en 4 skins |

Comprobaciones ejecutadas en esta pasada: extracción del bloque `<style>` vs `_mockup-style.css` → **idénticos** (25 572 caracteres, sha256 `26764c1d…`); el CSS quedó retirado como fuente (§0.2). No se modificó `mockup.html`, `ADR-001`, `licencias.md`, `plugin/` ni `spike/`.

### 14.2 Abierto (declarado, no escondido)

- Capturas de G, H, I, J (§7) y de la lista de importación.
- Script de medición de contraste **no versionado**: la cifra «0 fallos AA» viene de la revisión anterior; conviene dejarlo como test reproducible (`V5`).
- El preview se verificó en el pane del spike, no en `plugin.js`.

### 14.3 Pruebas que añade esta revisión

| # | Prueba | Cómo | Evidencia |
|---|---|---|---|
| V9 | Importación feliz | conceder `mediaRoot`, elegir 2 clips, importar | captura + `media[]` con 2 assets y 2 escenas |
| V10 | Carpeta protegida | intentar `~/.hermes` | copy de §5.2.3, sin crash, sin reintento automático |
| V11 | Carpeta distinta de `mediaRoot` | conceder otra carpeta | aviso «El servicio solo lee …», botón deshabilitado |
| V12 | Revocación en caliente | revocar en Capacidades y volver a importar | `not-granted` → «Volver a elegirla» |
| V13 | Preview con Range | abrir proyecto, hacer 5 seeks | 206 en la pestaña Red; sin recarga del `<video>` |
| V14 | Fallback de preview | forzar `src` inválido | `ErrorState` P7 o blob reproducido; objeto URL revocado |
| V15 | Estado D | matar el servicio con el pane abierto | «El servicio del editor no responde…», medios intactos |
| V16 | 409 | guardar con revisión vieja | diálogo G con `current_revision` real |
| V17 | Export dedupe | exportar dos veces seguidas | mismo `jobId`, `deduped: true`, un solo job en `/jobs` |

---

**Fin de rev2.** Lo que no está aquí sigue en `ui-spec.md` (rev1); lo que está aquí manda.
