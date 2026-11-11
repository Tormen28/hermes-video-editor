# Hermes Video Editor — proposal for the Nous catalog

**Language:** this file is bilingual. English first, Spanish from the heading
[Español](#español) onwards.

| | |
|---|---|
| Plugin name | `hermes-video-editor` |
| Version proposed | `0.3.4` |
| Manifest version | 2 |
| Author | Tormen (GitHub `Tormen28`) |
| License | MIT (proposed) |
| Category | Media · Productivity |
| Status | Working local build. 359 tests green. Real MP4 exported and verified. |

![Hermes Video Editor](img/editor-video.jpg)

---

## 1 · What it is

A video editor that lives **inside Hermes Desktop as a pane**. You talk to Hermes,
drag a clip in, cut it, reorder it, put text on it, grade the colour, and export an
MP4 — without leaving the conversation.

Nothing leaves the machine. The pane talks to a **local service on `127.0.0.1:8770`**
that drives **FFmpeg**; there is no cloud, no account, no upload.

## 2 · Why it belongs in the catalog

Hermes agents already make images, documents and code. Video was the one medium
where the agent had to hand the user a folder of files and wish them luck. This
closes that loop: the agent produces a deliverable video and the user can still
open it, trim it and fix it themselves.

Three things make it a good catalog citizen:

1. **No network dependency.** Local service, local FFmpeg, loopback only.
2. **A real contract.** `core/CONTRATO.md` documents every endpoint and field,
   read out of the code rather than written from memory.
3. **It is tested like software, not like a demo.** 359 automated tests, plus an
   end-to-end script that exports a real MP4 and probes it with `ffprobe`.

## 3 · What it does

| Area | Capability |
|---|---|
| Media | Import video/image/audio by path inside an allowed root; dedupe by SHA-256 |
| Timeline | Scenes with `in`/`out`, reorder, split, trim; images hold for a duration |
| Text | Per-scene captions with position and timing |
| Colour | Brightness, contrast, saturation, grayscale, vignette, blur |
| Speed | Per-scene `speed`, audio pitch-corrected with `atempo` |
| Transitions | 7 xfade styles: fade, slide left/right, wipe left/right, circle, zoom |
| Audio | Master volume, per-scene volume, fades, optional loudness normalisation |
| Music & SFX | Generates music and sound effects locally, or via a configurable HTTP provider |
| Export | MP4 H.264 + AAC, presets: 720p, 1080p, vertical, square; progress, cancel, dedupe |
| Return to chat | Finished MP4 comes back to the conversation as an attachment |

## 4 · Security posture

The service is deliberately small and deliberately locked:

- **Loopback only.** It refuses a request whose `Host` header is not
  `127.0.0.1:<port>` or `localhost:<port>` — that blocks DNS rebinding.
- **Origin allowlist.** `Origin` is checked when present; `null` and `file://` are
  accepted only because the pane runs from `file://`, and that is documented as a
  known local-CSRF trade-off rather than hidden.
- **Shared token.** The installer writes `X-VE-Token` into the plugin and a
  `service.token` file readable only by the user. Without it: `401`.
- **Path jail.** Media must resolve inside the configured `mediaRoot`; anything
  outside is a 400, not a silent read.
- **No secrets in the document.** The project JSON never stores credentials.

## 5 · What is deliberately NOT in this version

Being explicit about the boundary is part of the proposal:

- No cloud rendering, no accounts, no collaboration.
- No multi-camera, no keyframes, no colour grading curves (planned, not promised).
- No 4K in the default presets (it renders, it is just not offered).
- No telemetry. The plugin phones home to nothing.

## 6 · Install

```bash
cd video-editor
py -3.12 instalar.py          # installs the pane, writes the token, starts the service
core/iniciar-servicio.cmd     # start it later (keeps the token)
```

Open the pane with `Ctrl+Shift+E`, or from the command palette:
`videoEditor.toggle`.

**Requirement:** FFmpeg on `PATH`, or `VIDEO_EDITOR_TOOLS` pointing at a folder
that contains it. Tested with FFmpeg 9.0.1.

## 7 · Verification, stated plainly

| Claim | Evidence |
|---|---|
| Backend works | 359 tests green (`core/tests`) |
| Export works | E2E script: generate → scene → music → SFX → export → `ffprobe` reports H.264/AAC 1280×720 |
| Colour changes the picture | Brightness −0.5 → mean luma 23.8 → 0.0; +0.6 → 199.7 |
| Grayscale works | RGB 13/25/39 → 21.8/21.8/21.8 |
| Speed works | 3.0 s → 6.0 s at 0.5× |
| Known gap | The pane has never been driven end-to-end by a human with a mouse; the API path is what is verified |

That last row matters. The honest description is **“engine verified, UI not yet
walked through by a user”**, and a catalog listing should say so.

---

# Español

| | |
|---|---|
| Nombre del plugin | `hermes-video-editor` |
| Versión propuesta | `0.3.4` |
| Autor | Tormen (GitHub `Tormen28`) |
| Licencia | MIT (propuesta) |
| Categoría | Medios · Productividad |
| Estado | Compilación local funcionando. 359 pruebas en verde. MP4 real exportado y verificado. |

![Hermes Video Editor](img/editor-video.jpg)

## 1 · Qué es

Un editor de vídeo que vive **dentro de Hermes Desktop como panel**. Le hablas a
Hermes, arrastras un clip, lo cortas, cambias el orden, le pones texto, ajustas el
color y exportas un MP4 — sin salir de la conversación.

Nada sale de la máquina. El panel habla con un **servicio local en `127.0.0.1:8770`**
que maneja **FFmpeg**; no hay nube, ni cuenta, ni subida.

## 2 · Por qué merece estar en el catálogo

Los agentes de Hermes ya hacen imágenes, documentos y código. El vídeo era el único
medio donde el agente tenía que entregar una carpeta de archivos y desear suerte.
Esto cierra el círculo: el agente produce un vídeo entregable y el usuario todavía
puede abrirlo, recortarlo y corregirlo por su cuenta.

Tres cosas lo convierten en un buen ciudadano del catálogo:

1. **Sin dependencia de red.** Servicio local, FFmpeg local, solo loopback.
2. **Un contrato de verdad.** `core/CONTRATO.md` documenta cada endpoint y cada
   campo, leídos del código y no escritos de memoria.
3. **Probado como software, no como demo.** 359 pruebas automáticas, más un script
   de extremo a extremo que exporta un MP4 real y lo verifica con `ffprobe`.

## 3 · Qué hace

| Área | Capacidad |
|---|---|
| Medios | Importa vídeo/imagen/audio por ruta dentro de una raíz permitida; deduplica por SHA-256 |
| Línea de tiempo | Escenas con `in`/`out`, reordenar, partir, recortar; las imágenes duran lo que se pida |
| Texto | Rótulos por escena, con posición y tiempos |
| Color | Brillo, contraste, saturación, blanco y negro, viñeta, desenfoque |
| Velocidad | `speed` por escena, con el audio corregido de tono mediante `atempo` |
| Transiciones | 7 estilos xfade: fundido, deslizar izq./der., barrido izq./der., círculo, zoom |
| Audio | Volumen general, volumen por escena, entradas y salidas suaves, normalización opcional |
| Música y efectos | Genera música y efectos en local, o mediante un proveedor HTTP configurable |
| Exportación | MP4 H.264 + AAC, presets: 720p, 1080p, vertical, cuadrado; progreso, cancelar, deduplicar |
| Vuelta al chat | El MP4 terminado vuelve a la conversación como archivo adjunto |

## 4 · Postura de seguridad

El servicio es pequeño y está cerrado a propósito:

- **Solo loopback.** Rechaza cualquier petición cuyo `Host` no sea `127.0.0.1:<puerto>`
  o `localhost:<puerto>`: eso frena el *DNS rebinding*.
- **Lista de orígenes.** Se comprueba el `Origin` cuando viene; se aceptan `null` y
  `file://` solo porque el panel corre desde `file://`, y eso queda documentado como
  un riesgo CSRF local conocido, no escondido.
- **Token compartido.** El instalador escribe `X-VE-Token` dentro del plugin y un
  archivo `service.token` legible solo por el usuario. Sin él: `401`.
- **Cárcel de rutas.** Los medios tienen que resolverse dentro del `mediaRoot`
  configurado; cualquier cosa de fuera es un 400, no una lectura silenciosa.
- **Sin secretos en el documento.** El JSON del proyecto nunca guarda credenciales.

## 5 · Lo que a propósito NO trae esta versión

Decir el límite también forma parte de la propuesta:

- Sin render en la nube, sin cuentas, sin colaboración.
- Sin multicámara, sin keyframes, sin curvas de color (planeado, no prometido).
- Sin 4K en los presets por defecto (se puede renderizar, simplemente no se ofrece).
- Sin telemetría. El plugin no llama a casa.

## 6 · Instalación

```bash
cd video-editor
py -3.12 instalar.py          # instala el panel, escribe el token y arranca el servicio
core/iniciar-servicio.cmd     # arrancarlo más tarde (conserva el token)
```

Abre el panel con `Ctrl+Shift+E`, o desde la paleta de comandos:
`videoEditor.toggle`.

**Requisito:** FFmpeg en el `PATH`, o `VIDEO_EDITOR_TOOLS` apuntando a una carpeta
que lo contenga. Probado con FFmpeg 9.0.1.

## 7 · Verificación, dicha sin adornos

| Afirmación | Evidencia |
|---|---|
| El motor funciona | 359 pruebas en verde (`core/tests`) |
| La exportación funciona | Script E2E: generar → escena → música → efectos → exportar → `ffprobe` informa H.264/AAC 1280×720 |
| El color cambia la imagen | Brillo −0,5 → luminancia media 23,8 → 0,0; +0,6 → 199,7 |
| El blanco y negro funciona | RGB 13/25/39 → 21,8/21,8/21,8 |
| La velocidad funciona | 3,0 s → 6,0 s a 0,5× |
| Hueco conocido | El panel nunca se ha recorrido de punta a punta con ratón; lo verificado es la ruta del API |

Esa última fila importa. La descripción honesta es **«motor verificado, interfaz
todavía no recorrida por un usuario»**, y una ficha de catálogo debería decirlo.
