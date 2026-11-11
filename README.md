# Hermes Video Editor

![Hermes Video Editor](docs/propuestas/img/editor-video.jpg)

**English** · [Español](#español)

A video editor that lives **inside** Hermes: chat on the left, editor on the right.
Local-first. No provider is required, and nothing leaves your machine.

## Quick start

```
instalar.cmd
```

Then in Hermes: **Capacidades → Plugins → Editor de vídeo** (off/on) and
**Ctrl+K → «Editor de vídeo»**. Or just `Ctrl+Shift+E`.

## What it does

- Scenes with trim, reorder, split and speed 0.5–2×.
- Background music (volume, fades, loop, ducking, loudnorm) and per-event SFX.
- Real transitions: fade, slide, wipe, circle, zoom.
- Text with style and animation; filters; Ken Burns; logo with 9 anchors.
- Export 720p30, vertical 9:16, square 1:1; 1080p experimental.
- Optional generation (image/music/voice) with a free local provider or your own.

## Provider keys are optional, never a requirement

The editor works fully offline with the local generator. If you configure a key,
quality goes up:

| Provider | Variable | What it improves |
|---|---|---|
| **Nano Banana** (Gemini 2.5 Flash Image) | `VE_GEMINI_KEY` | Images |
| **ElevenLabs** | `VE_ELEVEN_KEY` | Voice |

Without a key the service refuses before making a single network call. There is no
silent fallback to a paid service, and no key ever appears in an error message.

## Chat + editor are one thing

- **By hand:** play with an `mm:ss.ms` clock, jump to an exact time, move/trim/reorder
  scenes, edit text, mute or lower volume per scene, place voices and sounds on the
  timeline, preview and export (the MP4 plays inside the editor).
- **By chat:** Hermes reads and edits **the same project by time** («en el 3:13
  cambia el texto…») with `core/scripts/ve_timeline.py` or the API; the pane updates
  itself and your changes are not lost. → [`docs/CHAT-Y-EDITOR.md`](docs/CHAT-Y-EDITOR.md)
- **Hermes skill:** [`hermes-skill/editor-video/SKILL.md`](hermes-skill/editor-video/SKILL.md)
  teaches the whole flow, including Cinematic.

## Start-up and security

1. `activar-editor.cmd` (or `python instalar.py`): creates the service **token**,
   embeds it in the installed plugin (with a `.bak` backup), starts the service with
   the **detached** launcher (it survives closing terminals) and, only with
   `--restart`, replaces an old service if no exports are running. Optional:
   `--autostart` starts it with your session.
2. In Hermes: Capacidades → Plugins → turn «Editor de vídeo» off and on.
3. No token, no access: the API rejects requests without `X-VE-Token` or with a
   foreign `Origin` (other web pages cannot drive your editor).

## Guides

- [`docs/propuestas/00-SUITE.md`](docs/propuestas/00-SUITE.md) — the three-plugin suite.
- [`docs/propuestas/EDITOR-VIDEO.md`](docs/propuestas/EDITOR-VIDEO.md) — proposal, bilingual.
- [`docs/README-USUARIO.md`](docs/README-USUARIO.md) — install, use, providers, problems.
- [`docs/REGLAS-DEL-PLUGIN.md`](docs/REGLAS-DEL-PLUGIN.md) — what it does and what it never will.
- [`docs/COMO-VERLO.md`](docs/COMO-VERLO.md) — walkthrough.
- [`core/CONTRATO.md`](core/CONTRATO.md) — technical contract of the service.

## Layout

- `plugin/` — the Hermes pane (`plugin.js`).
- `core/` — loopback service + FFmpeg engine + tests.
- `docs/` — guides, design, QA.
- `auditoria/` — test plans and verdicts.
- `spike/` — evidence from the initial spike (fixtures).

## Status

Service version: see [`VERSION`](VERSION). Suite:
`cd core && py -3.12 -m pytest tests -q` (408 passed, 3 skipped) plus
`node plugin/tests/merge.test.cjs` for the pane merge. End-to-end smoke against a
running service: `python core/scripts/e2e_smoke.py --help`.

License: MIT.

---

# Editor de vídeo para Hermes Desktop

![Editor de vídeo de Hermes](docs/propuestas/img/editor-video.jpg)

Un editor de vídeo **dentro** de Hermes: chat a la izquierda, editor a la derecha.
Local-first. Ningún proveedor es obligatorio y nada sale de tu máquina.

## Arranque rápido

```
instalar.cmd
```

Luego en Hermes: **Capacidades → Plugins → Editor de vídeo** (apagar/encender) y
**Ctrl+K → «Editor de vídeo»**. O directamente `Ctrl+Shift+E`.

## Qué incluye

- Escenas con recorte, orden, split y velocidad 0,5–2×.
- Música de fondo (volumen, fades, loop, ducking, loudnorm) y SFX por eventos.
- Transiciones reales: fundido, deslizar, barrido, círculo, zoom.
- Texto con estilo y animación; filtros; Ken Burns; logo con 9 anclas.
- Export 720p30, vertical 9:16, cuadrado 1:1; 1080p experimental.
- Generación opcional (imagen/música/voz) con proveedor local gratis o el tuyo.

## Las claves de proveedor son opcionales, nunca un requisito

El editor funciona entero sin red con el generador local. Si configuras una clave,
sube la calidad:

| Proveedor | Variable | Qué mejora |
|---|---|---|
| **Nano Banana** (Gemini 2.5 Flash Image) | `VE_GEMINI_KEY` | Imágenes |
| **ElevenLabs** | `VE_ELEVEN_KEY` | Voz |

Sin clave, el servicio rechaza antes de hacer una sola petición de red. No hay
respaldo silencioso a un servicio de pago, y la clave nunca aparece en un mensaje
de error.

## Chat y editor son una sola cosa

- **A mano:** reproduce con reloj `mm:ss.ms`, salta a un tiempo exacto, mueve,
  recorta y reordena escenas, edita textos, silencia o baja el volumen por escena,
  coloca voces y sonidos en la línea de tiempo, previsualiza y exporta (el MP4 se ve
  dentro del propio editor).
- **Por chat:** Hermes lee y edita **el mismo proyecto por tiempo** («en el 3:13
  cambia el texto…») con `core/scripts/ve_timeline.py` o la API; el panel se
  actualiza solo y tus cambios no se pierden. →
  [`docs/CHAT-Y-EDITOR.md`](docs/CHAT-Y-EDITOR.md)
- **Skill de Hermes:** [`hermes-skill/editor-video/SKILL.md`](hermes-skill/editor-video/SKILL.md)
  enseña todo el flujo, incluido el Cinematic.

## Arranque y seguridad

1. `activar-editor.cmd` (o `python instalar.py`): crea el **token** del servicio, lo
   incrusta en el plugin instalado (con respaldo `.bak`), arranca el servicio con el
   lanzador **desacoplado** (sobrevive al cierre de terminales) y, solo con
   `--restart`, reemplaza un servicio viejo si no hay exportaciones en curso.
   Opcional: `--autostart` lo arranca al iniciar sesión.
2. En Hermes: Capacidades → Plugins → apagar/encender «Editor de vídeo».
3. Sin token no hay acceso: la API rechaza peticiones sin `X-VE-Token` o con
   `Origin` ajeno (otras páginas web no pueden manejar tu editor).

## Guías

- [`docs/propuestas/00-SUITE.md`](docs/propuestas/00-SUITE.md) — la suite de los tres plugins.
- [`docs/propuestas/EDITOR-VIDEO.md`](docs/propuestas/EDITOR-VIDEO.md) — propuesta, bilingüe.
- [`docs/README-USUARIO.md`](docs/README-USUARIO.md) — instalación, uso, proveedores, problemas.
- [`docs/REGLAS-DEL-PLUGIN.md`](docs/REGLAS-DEL-PLUGIN.md) — qué hace y qué nunca hará.
- [`docs/COMO-VERLO.md`](docs/COMO-VERLO.md) — recorrido de prueba.
- [`core/CONTRATO.md`](core/CONTRATO.md) — contrato técnico del servicio.

## Estructura

- `plugin/` — el panel de Hermes (`plugin.js`).
- `core/` — servicio loopback + motor FFmpeg + tests.
- `docs/` — guías, diseño, QA.
- `auditoria/` — planes de prueba y veredictos.
- `spike/` — evidencia del spike inicial (fixtures).

## Estado

Versión del servicio: ver [`VERSION`](VERSION). Suite:
`cd core && py -3.12 -m pytest tests -q` (408 pasan, 3 saltadas) más
`node plugin/tests/merge.test.cjs` para la fusión del panel. Smoke de punta a punta
contra un servicio en marcha: `python core/scripts/e2e_smoke.py --help`.

Licencia: MIT.
