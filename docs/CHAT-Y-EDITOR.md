# Chat y editor: un solo documento

El pane (a mano) y Hermes (por chat) editan **el mismo proyecto**. Hermes puede decir
«en el 3:13 cambia el texto, baja la música y mueve esa escena» y el editor abierto lo muestra en ~4 s,
sin perder lo que tú habías tocado.

## Cómo no se pisan

- Cada guardado lleva `revision`. Hermes **no** manda el documento entero: manda *operaciones*
  (`POST /projects/<id>/edit`) que el servicio aplica sobre la revisión **actual**, de forma atómica
  (si tú guardaste justo antes, las reaplica encima; hasta 5 reintentos). Nunca 409 por culpa de Hermes.
- El pane, si no estás escribiendo, recoge la revisión nueva solo («Proyecto actualizado desde el chat»).
- Si tú tenías cambios sin guardar cuando llegó el chat, al guardar el pane **combina** los dos lados
  (por escena/sonido/medio; en el mismo campo gana lo tuyo) en vez de pedirte elegir.

## API (token obligatorio: cabecera `X-VE-Token`)

| Método y ruta | Qué hace |
|---|---|
| `GET /projects/<id>/timeline` | Línea de tiempo completa con tiempos absolutos (`start`, `end`, `startTc`), textos con `from`/`to`, sonidos con `at`, música, volumen general, medios. |
| `GET /projects/<id>/at?t=3:13` | Qué hay en ese instante: escena, textos activos, sonidos que suenan. |
| `POST /projects/<id>/edit` | `{"ops":[...]}` (máx. 100). Aplica todo o nada. Devuelve `applied` (resumen en palabras) y el `timeline` nuevo. `strict:true` + `revision` pide 409 si hay una más nueva. |

Tiempos: `83.5`, `1:23.5` o `01:23.500` (segundos del vídeo final, transiciones ya descontadas, igual que el reloj del pane).

### Operaciones

Una escena se indica con `scene` (id, número 1-based o nombre) **o** con `time` (la escena que está en pantalla en ese instante).

| `op` | Campos | Efecto |
|---|---|---|
| `set_text` | `time`/`scene`, `content`, `from`,`to`, `position`,`size`,`color`,`border`,`borderColor`,`shadow`,`animation`, `add`, `index` | Por `time`: sustituye el texto que está en pantalla en ese instante; si no hay, crea uno desde ahí. `content:""` lo quita. |
| `trim` | `scene`/`time`, `in`,`out` (s de la fuente) o `duration` (s en pantalla) | Recorta; los textos se ajustan o se quitan avisando. |
| `split` | `time` | Parte la escena en dos en ese instante. |
| `delete_scene` | `scene`/`time` | Borra la escena. |
| `move_scene` | `scene`/`time`, `to_index` (1-based) o `to_time` | Reordena. |
| `set_transition` | `scene`/`time`, `value` (`none`, `fade-0.5`, …) | Transición de entrada. |
| `set_speed` | `scene`/`time`, `speed` 0.5–2 | Velocidad. |
| `set_volume` | `target`: `scene` (por defecto)/`music`/`master`/`event`; `volume` 0–100 o `mute:true`; `id` si es `event` | Volumen o silencio. |
| `add_audio` | `assetId` (audio del proyecto), `at`, `volume`, `fadeIn`, `fadeOut` | Coloca un sonido/voz en el tiempo. |
| `move_audio` / `set_audio` | `id` (o `time`), `at`, `volume`, `mute`, `assetId` | Mueve o ajusta ese sonido. |
| `remove_audio` | `id` | Lo quita. |
| `set_music` / `remove_music` | `assetId`, `volume`, `fadeIn`, `fadeOut`, `loop`, `ducking` | Música de fondo. |
| `insert_media` | `path` (dentro de la carpeta de medios), `at`/`to_index`, `duration`, `volume` | Importa un archivo y lo coloca (un audio queda como sonido en `at`). |
| `set_title` | `title` | Título del proyecto. |

Error en cualquier operación ⇒ `400` con `operación N: motivo` y **no se cambia nada**.

## CLI para Hermes

`core/scripts/ve_timeline.py` envuelve lo anterior y lee el token del archivo del usuario (no lo imprime):

```
python core/scripts/ve_timeline.py ensure
python core/scripts/ve_timeline.py show   <proyecto>
python core/scripts/ve_timeline.py at     <proyecto> 3:13
python core/scripts/ve_timeline.py text   <proyecto> 3:13 "Nuevo texto"
python core/scripts/ve_timeline.py volume <proyecto> 3:13 40
python core/scripts/ve_timeline.py edit   <proyecto> --ops '[{"op":"move_scene","time":"3:13","to_index":1}]'
python core/scripts/ve_timeline.py export <proyecto>
```