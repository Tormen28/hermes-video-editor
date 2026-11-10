---
name: editor-video
description: "Crear, ver y editar vídeos en el Editor de vídeo de Hermes (pane local): importar o generar medios, montar escenas, y editar POR TIEMPO desde el chat («en el 3:13 cambia el texto, baja la música…») sobre el mismo proyecto que el usuario tiene abierto; exportar MP4 y verificarlo. Incluye el flujo Cinematic (guion → película) y la versión Plus opcional."
version: 1.0.0
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [video, editor, timeline, mp4, ffmpeg, cinematic, voiceover]
    related_skills: [cinematic-film]
---

# Editor de vídeo (chat + pane = un solo proyecto)

El editor es un pane dentro de Hermes más un servicio local (`http://127.0.0.1:8770`, solo tu máquina).
**El pane y tú editáis el mismo proyecto.** Lo que haces por chat aparece en el pane abierto en ~4 s;
lo que el usuario toca a mano se respeta (las operaciones se aplican sobre la revisión actual).

Sin claves ni cuentas: crear, importar, voz local (si hay), imágenes locales, editar, exportar.
Lo de pago es opcional → sección «Versión Plus».

## 0. Preparación (siempre primero)

```
python <repo>/core/scripts/ve_timeline.py ensure        # arranca el servicio si no responde (lanzador desacoplado)
python <repo>/core/scripts/ve_timeline.py projects      # proyectos existentes
```

- `<repo>` = carpeta `video-editor` del plugin (p. ej. `…\hermes\fleet-workspace\video-editor`).
- El **token** lo leen solos los scripts de `%LOCALAPPDATA%\hermes\video-editor\service.token`. **Nunca lo imprimas, lo pegues en el chat ni lo pongas en URLs/logs.**
- Si da 401/403: el usuario debe ejecutar `activar-editor.cmd` y apagar/encender el plugin. No lo desactives ni uses `--no-token`.
- No reinicies Hermes ni el gateway por esto.

## 1. Flujo base: crear → medios → montar → exportar

1. **Proyecto:** `POST /projects {"title": "…"}` (devuelve `projectId`) — o abre uno existente.
2. **Medios:** los archivos deben estar dentro de la carpeta de medios concedida (`GET /grants` → `mediaRoot`). Importa con `POST /projects/<id>/media {"path":"clips/a.mp4"}` (cada vídeo/imagen crea una escena; un audio queda como medio, sin escena).
3. **Generar (opcional, local, sin claves):** `python core/scripts/ve_generate.py --project <id> --kind image|music|voice --prompt "…" [--use scene|music|sfx|voice] [--at <segundos>]`
   - `image`: `--style cinematic` (por defecto; también noir|warm|neon|studio|forest) y `--aspect 16:9|9:16|1:1`; sin texto quemado salvo `--caption`.
   - `music`: `--mood calm|epic|tension|bright`.
   - `voice`: voz de Windows (SAPI, sin red); `--use voice --at 2` la deja colocada en el segundo 2.
   - `--provider edge|web|http` son opt-in y sacan el texto/prompt de la máquina: pregunta antes.
4. **Montar por tiempo** (sección 2). Mira siempre el resultado con `show` antes y después.
5. **Exportar:** `ve_timeline.py export <proyecto>` (720p30 por defecto; sale `output.mp4`).
6. **Verificar** (no digas «listo» sin esto): `ffprobe` del MP4 → códec h264/aac, resolución, duración esperada, y un fotograma (`ffmpeg -ss 8 -i out.mp4 -frames:v 1 f.png`) donde esperas el texto. El usuario también puede verlo dentro del editor tras exportar.

## 2. Editar por tiempo («en el 3:13 …»)

Tiempos válidos: `83.5`, `1:23.5`, `01:23.500` = segundos del **vídeo final** (el mismo reloj del pane).

1. **Mira dónde estás:**
   `ve_timeline.py show <proyecto>` → escenas con `inicio → fin`, textos con su ventana, sonidos (♪), música, volúmenes.
   `ve_timeline.py at <proyecto> 3:13` → qué escena/texto/sonido hay en ese instante.
2. **Edita** con atajos o con operaciones:
   - `ve_timeline.py text <proyecto> 3:13 "Nuevo texto"` (reemplaza el texto en pantalla en ese instante; si no hay, crea uno desde ahí)
   - `ve_timeline.py volume <proyecto> 3:13 40` · `mute <proyecto> 3:13`
   - `ve_timeline.py edit <proyecto> --ops '[…]'` — varias a la vez, **todo o nada**:

```json
[
  {"op":"set_text","time":"3:13","content":"Nuevo título","position":"top"},
  {"op":"split","time":"3:13"},
  {"op":"trim","scene":2,"duration":4},
  {"op":"move_scene","time":"3:13","to_index":1},
  {"op":"set_volume","target":"music","volume":25},
  {"op":"add_audio","assetId":"md_xxxx","at":"3:13","volume":90},
  {"op":"move_audio","id":"ae_xxxx","at":"3:20"},
  {"op":"insert_media","path":"clips/extra.mp4","at":"1:00"}
]
```

   Lista completa de operaciones y campos: `docs/CHAT-Y-EDITOR.md`.
3. **Confirma** leyendo lo que devuelve (`✓ …` y la nueva duración) y vuelve a hacer `show`/`at`.
4. Dile al usuario qué cambiaste con los tiempos exactos; su pane se actualiza solo (si estaba escribiendo, se actualiza al terminar o se combina al guardar).

Reglas:
- Una petición de varios cambios = **una sola** llamada `edit` con todas las operaciones.
- Cambiar duración/orden mueve todo lo posterior: recalcula con `show` antes de la siguiente orden por tiempo.
- Un error devuelve `operación N: motivo` y no cambia nada: corrige y repite, no insistas a ciegas.
- No pises trabajo manual: si el usuario dijo «deja la escena 2 como está», no la toques.
- No borres proyectos ni medios sin confirmación explícita.

## 3. Flujo Cinematic (guion → película) — sin tocarlo

El Cinematic sigue siendo su propio flujo y **no cambia**: se hace como siempre con la skill `cinematic-film`
(guion `script.json` → tabla de beats → aprobar → voz → render). El editor se usa **después** para retoques:

1. Termina el Cinematic y pon el MP4 final (y, si quieres, la narración `audio/narration.m4a`) dentro de la carpeta de medios concedida.
2. Importa: `POST /projects/<id>/media {"path":"cinematic/pelicula.mp4"}` (o `insert_media`).
3. Retoca por tiempo (títulos extra, recortes, bajar música, añadir un sonido) y exporta de nuevo.
4. Si el usuario quiere cambiar el **guion** o los beats, vuelve al flujo Cinematic y re-renderiza; el editor no regenera la película.

Recomendaciones de montaje:
- Vídeos cortos (≤ 60 s): una idea por escena, 3–6 s por escena, texto de ≤ 8 palabras, transición `fade-0.5` sutil.
- Voz en off sobre vídeo: voz al 100 %, música `volume` 20–30 con `ducking:true`.
- Vertical (9:16) para redes: orientación `v` y texto en `position:"center"` o `top`.

## 4. Manual en el pane (para decírselo al usuario)

Reloj `mm:ss.ms` y «ir a…» para saltar; arrastrar/recortar escenas; texto y estilo por escena; silenciar o bajar el volumen por escena;
sección «Sonidos y voz» para colocar audios en el tiempo; música con fades; vista previa; exportar y ver el MP4 en el mismo diálogo.
Tras editar a mano, pídele **Guardar** (o espera al autoguardado de 4 s) antes de que tú hagas una edición larga.

## 5. Versión Plus (opcional · solo documentada)

Nada de esto es necesario ni bloquea la base.
- **Voz profesional con ElevenLabs** (el usuario lo llama «LevelX»): hueco HTTP `VE_PROVIDER_VOICE_URL` / `VE_PROVIDER_VOICE_KEY` (pasarela local que llama a `…/v1/text-to-speech/<voice_id>` con `xi-api-key`).
- **Imágenes con la API de imágenes de OpenAI:** `VE_PROVIDER_IMAGE_URL` / `VE_PROVIDER_IMAGE_KEY` (pasarela que llama a `/v1/images/generations` y devuelve `{"base64":…}`).
- Otros proveedores: igual, mientras devuelvan bytes o `base64/url/path`.
- Orquestación: solo si el usuario **ya configuró** las claves (`/health` con token muestra `voiceModes.http`). Si no, usa lo local y no lo menciones como carencia. El texto/prompt sale de la máquina: avísalo y pide su OK la primera vez.
- Detalle y contrato de la pasarela: `docs/PLUS.md`.

## Errores típicos

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `Failed to fetch` / no responde | servicio parado | `ve_timeline.py ensure` |
| 401 / 403 | falta/incorrecto el token, o plugin sin actualizar | `activar-editor.cmd`; apagar/encender el plugin |
| `no hay escena en 05:00` | tiempo fuera de la duración | `show` y usa un tiempo ≤ duración |
| `409` en el pane | cambios en dos sitios a la vez | el pane combina solo; si pide elegir, «Recargar» y repite el cambio |
| Exporta pero sin voz | el audio no está colocado | `add_audio` en su `at`, o `ve_generate.py … --use voice --at …` |