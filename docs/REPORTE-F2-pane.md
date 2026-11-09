# Fase 2 · pane v0.2 — verificación real en navegador

Fecha: 2026-11-08 (America/Caracas)
Artefacto: `plugin/plugin.js` (2.175 líneas) instalado en
`%LOCALAPPDATA%\hermes\desktop-plugins\editor-video\plugin.js` (hash idéntico, `.bak` conservado).
Servicio: `core/service/app.py` 0.2.0 · FFmpeg n9.0.1.

## Cómo se verificó (y por qué así)

El pane no se puede "probar" leyendo el código: `node --check` sólo demuestra que parsea.
Se montó en un navegador real (Chromium del harness) contra el **servicio real** en
`127.0.0.1:8765`, con fixtures sintéticos generados por FFmpeg y un `ctx` simulado.

Banco de pruebas: `plugin/harness/`

| Archivo | Papel |
| --- | --- |
| `index.html` | import map + montaje del pane y `ctx` falso (storage, files, session) |
| `react-shim.js` | reexporta hooks del UMD de React 18 (igual que la app) |
| `jsx-shim.js` | `jsx/jsxs` sobre `createElement` con children aplanados |
| `sdk-shim.js` | `@hermes/plugin-sdk` mínimo |
| `vendor/` | React 18.3.1 UMD (local, sin CDN en tiempo de prueba) |
| `setup_fixtures.py` | clips 720p + PNG, `/projects` real, subtítulos, transición, servicio en marcha |
| `media.json` | listado que consume el `ctx.files` simulado |

Servir con `python -m http.server 8800 --directory plugin` y abrir
`/harness/index.html?open=<projectId>&media=1&session=sess_harness`.
El servicio necesita `--allow-origin http://127.0.0.1:8800` (ver abajo).

## Resultado medido

| Prueba | Resultado |
| --- | --- |
| Montaje sin excepciones | `window.__VE_ERRORS__ == []` en todos los estados |
| Proyecto real con 3 escenas | carga, `<video>` `readyState 4`, `duration 3`, rev 4 |
| Layout a 784×511 | sin overflow, sin elementos fuera |
| Layout a **380×820** (panel lateral) | `scrollWidth == clientWidth == 380`, 0 elementos fuera |
| Marco de vídeo | AR medido 1,780 ≈ 16:9, centrado, sin bandas |
| Contraste WCAG AA | **0 fallos** (calculado componiendo alfa hasta fondo opaco) |
| Exportación con clics reales | Preparando → Renderizando → Escribiendo MP4 → Listo · 2,4 MB |
| MP4 resultante (ffprobe) | 1280×720, h264, 30/1, 255 frames, AAC, 8,500000 s, 2.507.795 B |
| Edición + autoguardado | texto nuevo persistido, revisión 4 → **5** vía `GET /projects` |
| Estado sin servicio (`svc=:9`) | «No se pudo cargar el proyecto · no responde en 127.0.0.1:9» + Reintentar |
| Tema claro | `bg #fff`, `fg #1b1b1f`, sin errores |
| Suite del backend | **235 tests OK, 2 skipped, 36,2 s** |

## Defectos encontrados y corregidos

1. **CORS inexistente** (bloqueante, no era del harness): el navegador bloqueaba todo
   `fetch` cross-origin. El renderer del plugin vive en otro origen, así que el servicio
   *necesitaba* CORS de verdad. Añadido: preflight `OPTIONS`, `Access-Control-Allow-Origin`
   sólo para orígenes de la allowlist, `Expose-Headers` para Range, y `--allow-origin` para
   el banco de pruebas.
2. **Reflejo de origen no validado** (seguridad): el primer intento reflejaba el `Origin`
   en el 403. Un test lo cazó. Ahora `_send_cors` revalida con `_origin_allowed` y **nunca**
   emite cabecera para un origen ajeno.
3. **El override de servicio sólo afectaba a las URLs de media**: `request()` ignoraba
   `__VE_SERVICE__`, así que el estado "sin servicio" cargaba el proyecto igualmente.
   Unificado en `serviceBase(ctx)`.
4. **`offline` se pisaba con `noProject`**: al fallar la carga, el fallback final escribía
   `noProject`. Ahora `loadProjects` devuelve `null` y el arranque se detiene.
5. **Grid sin columna explícita**: `.ve-root` era `grid` sin `grid-template-columns`, así que
   la columna se dimensionaba al max-content del contenido (391 px en un panel de 380).
   Fix: `grid-template-columns: minmax(0,1fr)`.
6. **Marco de vídeo deformado**: `height:100%` en CSS anulaba `aspect-ratio`. Ahora el
   tamaño se calcula con `ResizeObserver` sobre el lienzo (`fitStyle`), con AR exacto.
7. **Cabecera desbordada en compacto** (llegaba a 526 px): en `≤520 px` se ocultan título,
   separador, badges y estado de guardado; el botón Guardar pasa a icono.
8. **Datos inventados en la UI** (auditoría): se quitó la onda decorativa, la etiqueta
   «A1 · Voz» y las miniaturas con degradado; ahora la pista muestra el **volumen real**
   de la escena y las miniaturas son neutras.
9. **Botones anidados** en la lista de escenas (HTML inválido): fila convertida en
   `div.ve-scene-row` con tres botones hermanos y `aria-label` por escena.
10. **`job.log` inexistente** en el menú: sustituido por «Estado del servicio» con datos
    reales del job (`state`, `stage`, `progress`, `error`, `outputPath`, `outputBytes`).

## Decisiones que quedan abiertas (para Tormen)

- **Alto del panel**: a 380 px es usable pero comprimido. El manifest declara
  `width: '900px'`; si el pane vivirá siempre estrecho, conviene subir la altura de la
  pista de audio y valorar un modo «solo escena» sin rail.
- **`/admin/stop`**: ahora `main()` sale cuando `Service.stop()` activa el evento, pero
  cerrar el proceso desde el pane no es una acción de UI; la parada sigue siendo Ctrl+C
  o cerrar el lanzador.
- **Fixtures de prueba** (`%TEMP%\ve-harness`, puerto 8765 y 8800) son desechables:
  borrarlos no afecta al producto.

## Chat vivo (v0.3)

El pane dejó de ser una isla: sabe en qué chat está y devuelve ahí el resultado.

| Pieza | Contrato real usado | Qué hace |
| --- | --- | --- |
| Sesión del chat | `host.state.focusedStoredSessionId` (atom, `useValue`) | el header muestra `Chat <id>` con punto verde/gris y «trabajando» si `host.state.busy` |
| Carpeta del chat | `host.state.cwd` | se guarda en el proyecto al crearlo |
| Agregar al chat | `host.composer.insertText(sid, texto, {mode:'block'})` + `focus(sid)` | inserta resumen + ruta del MP4 en el compositor del chat activo |
| Copiar ruta | `ctx.os.writeClipboard(texto)` | portapapeles real |
| Volver al chat | `host.navigate('/chat')` | ya existía |

**Hallazgo de contrato:** el SDK **no expone `ctx.session`**. El pane leía de ahí, así que
en la app real la sesión habría sido siempre `null` y el badge habría mentido. Ahora se lee
de `host.state` con `useValue`, y queda el fallback a `ctx.session` sólo para el harness viejo.

### Verificado con clics reales (no simulado)

| Prueba | Resultado |
| --- | --- |
| Chip con sesión viva | `Chat harness` · aria-label «Chat harness. Ir al chat» |
| Estado «trabajando» (`busy`) | punto ámbar + etiqueta, aria-label «…, trabajando ahora» |
| Agregar al chat tras exportar | compositor recibe `sess_harness_chat`, `mode:block`, texto con **00:08,5 · 1280×720 · 2.4 MB · ruta real · prj_59bc… · revisión 5** |
| Foco al insertar | `host.composer.focus('sess_harness_chat')` invocado |
| Copiar ruta | `__VE_CLIPBOARD__` con la ruta real del MP4 |
| Sin compositor (`nocomposer=1`) | «Esta versión de Hermes no expone el compositor del chat; copia la ruta y pégala.» y **no** inserta nada |
| Geometría a 380×820 | `scrollWidth == clientWidth == 380`, 0 elementos fuera; el chip se reduce a su punto |

### Verificado también dentro de Hermes Desktop

El plugin se cargó en la app real (⌘/Ctrl+K → *Reload desktop plugins*) y el pane se abrió con
**Ctrl+Shift+E**. Evidencia en la captura `computer_use_31a6147af4f840e29a9caf869a6286c6.png`:

| Elemento | Lo que se ve |
| --- | --- |
| Header | `EDITOR DE VIDEO Rev 4` · **`Chat local-24 trabajando`** (chip de sesión viva) · `Guardado hace 1 h` |
| Stage | Escena 1/6, timecode, marco 16:9 con el clip real |
| Rail | Escenas 01/02/03 + Propiedades de la escena |
| Timeline | V1/A1, «Sin trabajos en cola», «Ver chat», «Exportar 720p · 30» |
| Status | `hermes` · `Backend listo` · `0.23.0` |

El chip tomó el id de la sesión real (`local-24…`) y el estado `trabajando` del turno en curso:
eso prueba que `host.state` + `useValue` funcionan en producción, no sólo en el shim.

**Nota de convivencia:** el pane viejo (`editor-video-spike`, el de «spike F1-b») competía por
el slot y tapaba al nuevo. Se movió a
`%LOCALAPPDATA%\hermes\desktop-plugins-off\editor-video-spike` (reversible: devolver la carpeta
a `desktop-plugins/`). No se borró nada.

## Qué falta para que Hermes cree vídeo de verdad (fase 3, no implementado)

La demo actual es un editor determinista (cortes, texto, transiciones, export). Para que
Hermes **cree** vídeo con IA hace falta una capa nueva, y ninguna de estas piezas se debe
prometer antes de tenerla:

1. **Generación de clips**: proveedor de vídeo (texto/imagen → vídeo), cola de trabajos con
   coste por clip y caché por prompt+semilla. El `Job` actual ya sirve de molde, pero esos
   trabajos son **externos y de pago**: requieren aprobación explícita de Tormen por lote.
2. **Voz y música**: TTS (ya hay `text_to_speech` en el runtime) + pistas con licencia
   comercial verificada. Sin licencia clara no entra al producto.
3. **Guion → timeline**: el chat propone un guion estructurado (escenas, duración, texto) y
   el editor lo materializa como `Project`; el usuario revisa antes de gastar créditos.
4. **Assets del chat**: hoy el media root se concede a mano. En fase 3, el chat debería
   poder proponer «usa este clip» con una ruta ya concedida, nunca abrir el disco.
5. **Publicación**: sigue siendo puerta humana. Nada se sube ni se entrega desde el pane.

**Decisión necesaria:** qué proveedor de generación (y su coste/licencia) antes de escribir
una línea de la fase 3. Mientras tanto, el editor determinista es la demo honesta.

## Reproducir

```bash
python plugin/harness/setup_fixtures.py --port 8765 --harness-origin http://127.0.0.1:8800
python -m http.server 8800 --bind 127.0.0.1 --directory plugin
# abrir http://127.0.0.1:8800/harness/index.html?open=<projectId>&media=1&session=sess_harness
cd core/tests && python -m unittest test_paths test_project test_journal test_worker test_service
```
