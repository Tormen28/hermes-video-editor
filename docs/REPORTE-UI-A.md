# Work Report · UI-A — transiciones, música y presets de export

- **Origen:** Hermes Padre (Task Spec UI-A) · **Destino:** Padre → `dike` para verificación
- **Autor:** Hephaestus · **Fecha:** 2026-11-08
- **Alcance:** `video-editor/plugin/plugin.js` (fuente) y `desktop-plugins/editor-video/plugin.js` (copia desplegada)

## Qué cambió

### 1. Transiciones (catálogo completo + duración)
- `TRANSITIONS` pasa a `TRANSITION_STYLES` con los 7 estilos reales de
  `core/project.TRANSITION_STYLES`, con etiquetas es-ES: Fundido, Deslizar izq.,
  Deslizar der., Barrido izq., Barrido der., Círculo, Zoom. `TRANSITIONS` sigue
  existiendo como `[Sin transición, ...estilos]` para el select.
- El documento guarda `estilo-duracion` (`slideleft-0.5`), no el estilo suelto.
  Helpers nuevos `parseTransition()` / `transitionValue()` / `transitionLabel()`;
  cualquier valor raro o legado (`fade-0.3`) se lee sin romper el select.
- Junto al select hay un `input[type=range]` 0,1–2,0 s (paso 0,1) con el valor en
  `0,5 s` (coma es-ES). La escena 0 no puede llevar transición: select y slider
  deshabilitados con nota explícita.
- Catálogo: si `/health` publica `transitions`, manda esa lista; si no contesta,
  se usa el catálogo local. Un estilo que el documento ya use y el catálogo no
  liste se agrega al select en vez de perderse.

### 2. Música de fondo (nivel proyecto, en el rail)
- Sección «Música» entre Propiedades y el footer, con `ve-rail__sec` + `Badge`
  de estado (`Fondo` / `—`).
- Sin assets `kind:'audio'`: aviso «Importa un audio para usarlo como música.» y
  botón «Importar medios». Con assets: select de pista (opción «Sin música»),
  volumen 0–100 (paso 5), fundido de entrada/salida 0–10 s, toggles «Repetir en
  bucle» y «Bajar bajo la voz (ducking)», toggle «Normalizar audio del proyecto»
  (`audio.normalize`) y «Quitar música».
- Mutaciones con el patrón existente (`mutate(...)` sobre clon + autosave/`save()`
  en `onBlur`); `Quitar música` hace `delete draft.music`, así que sin música no
  queda la clave. Se escriben exactamente los campos que valida el backend:
  `{assetId, volume, fadeIn, fadeOut, loop, ducking}`.
- Valores con los que nace `doc.music` (decisión declarada): `volume 50`,
  `fadeIn/fadeOut 0`, `loop true`, `ducking true`. Nada más se inventa.

### 3. Presets de export
- `EXPORT_PRESETS` con los cuatro: `mp4-720p30`, `mp4-1080p30` (etiquetado
  «requiere medición»), `mp4-720p30-vertical`, `mp4-720p30-square`.
- El diálogo de export gana el select; `startExport({ preset })` manda el elegido
  en el POST. Los presets que `/health` **no** publica se muestran
  deshabilitados (y el botón Exportar se deshabilita con aviso) en vez de
  mandarse y recibir un 400. Si `/health` publica presets que el catálogo local
  no conoce, se agregan igual.

### 4. Trampa del contrato (encontrada y resuelta)
`core/project.validate()` rechaza un fundido **más largo que la escena o que la
escena anterior** («fade is longer than the scene» / «transition is longer than
the previous scene»). Por eso:
- El slider tiene como techo `min(2,0 s, duración escena, duración anterior)`
  (`maxFadeFor`), y muestra «máximo N s aquí».
- `fitTransition()` reajusta (o pone `none`) la transición al mover in/out o al
  partir una escena, para que el PUT nunca reciba un documento inválido.
- Al partir, la cola entra con `transition: 'none'`: un corte no inserta cruce
  (antes heredaba el del clip original).

## Cómo se probó (salida real)

| Comprobación | Comando | Resultado |
|---|---|---|
| Sintaxis fuente | `node --check plugin.js` | `NODE_CHECK_OK` |
| Sintaxis desplegado | `node --check desktop-plugins/editor-video/plugin.js` | `NODE_CHECK_DEPLOYED_OK` |
| Fuente y copia idénticas | `md5sum` ambas | `c8f1c2c26e7ad207a2173268a84aa454` en las dos |
| `register()` no lanza (stubs) | `node runner.mjs` en `cache/scratch/ve-smoke` | `register OK, contribuciones: 4` + `render OK: panes pane` |
| Helpers de transición (código real extraído del archivo) | `node transitions-probe.mjs` | `slideleft-0.5`, `zoomin-2`, `fade-0.1`, clamp 5→`fade-2`; `parseTransition('fade-0.3')→{fade,0.3}` |
| Lo que escribe el pane pasa `project.validate()` | `python3 contract-probe-2.py` | `RESULTADO: VALID` con `['none','slideleft-0.5','zoomin-2']`, música con ducking y `audio.normalize` |
| Contrapruebas (la validación es real) | idem | estilo inventado + volumen 140 → 2 errores; `fade-2` en escena de 0,8 s → «fade is longer than the scene» |
| Sin música | idem | `tras Quitar musica: VALID` |
| Sin `position:fixed` en el CSS del pane | `grep -c` | `0` |
| `QA_PROBE` | `grep -n` | ausente (ya estaba apagado; no se reintrodujo) |

## Qué **no** se probó / límites
- **No se reinició el servicio ni el gateway** (fuera de alcance). El pane nuevo
  se verá al recargar el desktop; no se hizo smoke visual en la app abierta.
- El banco `ve-smoke` renderiza el pane en fase `boot` (sin documento), así que
  la sección de música **no** se ha ejercitado con un `doc` real en pantalla:
  su contrato se verificó contra `project.validate()`, no visualmente.
- El repo de `video-editor/` **no es un repositorio git** (`fatal: not a git
  repository`): no hubo rama ni commit; la sincronización fuente→desplegado se
  hizo por copia y se verifica por md5.
- El backend actual solo acepta `mp4-720p30` (`ALLOWED_PRESETS`), así que los
  otros tres presets aparecen deshabilitados hasta que 0.3.3 los publique en
  `/health`. No se tocó el backend.
- Extracción de audio real, ducking audible y `xfade` en el render final no se
  ejecutaron aquí (requieren ffmpeg + export): verificado solo el contrato del
  documento.

## Archivos
- `video-editor/plugin/plugin.js` — 2775 → 3197 líneas (fuente)
- `desktop-plugins/editor-video/plugin.js` — copia desplegada, md5 idéntico
- Sondas: `cache/scratch/ve-smoke/{runner.mjs, transitions-probe.mjs, contract-probe-2.py}`
