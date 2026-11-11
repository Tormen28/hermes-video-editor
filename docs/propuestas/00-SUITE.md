# The Panteón suite — three plugins for the Nous catalog

**Bilingual:** English first, Spanish from [Español](#español).

Submitted by **Tormen** (GitHub `Tormen28`) · all three MIT · all three local-only.

| Plugin | What it gives an agent | State |
|---|---|---|
| **`hermes-bot-chat-agent`** | A conversation it can be trusted with: short replies, a safety wall, real delegation | `0.3.0-dev` on a branch; `main` is `0.2.0` |
| **`argos`** | Hands on a live Godot editor: build, run, screenshot, fix | `1.1.0`, repo clean |
| **`hermes-video-editor`** | A pane that edits and exports real video with FFmpeg | `0.3.4`, engine verified |

Each has its own proposal file with its own honest limitations:

- [`HERMES-BOTS.md`](HERMES-BOTS.md)
- [`ARGOS.md`](ARGOS.md)
- [`EDITOR-VIDEO.md`](EDITOR-VIDEO.md)

---

## The argument for taking all three

Individually they are three good tools. Together they describe a **complete loop
that a local agent can run on its own machine**:

```
Bot Chat  →  decides and delegates
   ↓
ARGOS     →  builds the game, sees it running, fixes it
   ↓
Editor    →  cuts the trailer from what actually shipped
```

That is the thing no cloud agent can do: **see its own output and correct it,
without an upload, an account, or a per-minute bill.**

## What is common to all three

- **Loopback only.** No plugin opens a port to the internet or calls home.
- **No telemetry.** None of the three phones anywhere.
- **Honest docs.** Each proposal states what is verified and what is not. We would
  rather be listed as “verified engine, UI not yet walked through” than be found
  out later.
- **Bilingual.** English and Spanish in every README, because that is the language
  these were built in and for.

## What we are NOT claiming

- Not that they are finished. ARGOS has never built a whole scene unaccompanied;
  the video editor's pane has not been driven end to end by a human; Bot Chat's
  `0.3.0` is not merged.
- Not that they work on every platform. Built and tested on Windows 11.
- Not that they replace the cloud tools. They replace the part of the workflow that
  never needed the cloud: the file on your own desk.

## Decision needed from Tormen before sending

1. **Whose name goes on it** — personal (`Tormen28`) or a project name.
2. **One submission or three** — the suite argues better together; a catalog may
   require them separately.
3. **Bots version** — propose `0.2.0` (safe, no delegation) or merge `0.3.0` first.
4. **Licence confirmation** — MIT for all three.

---

# Español

Suite del Panteón: tres plugins para el catálogo de Nous.

Presentado por **Tormen** (GitHub `Tormen28`) · los tres MIT · los tres solo en local.

| Plugin | Qué le da al agente | Estado |
|---|---|---|
| **`hermes-bot-chat-agent`** | Una conversación de fiar: respuestas cortas, un muro de seguridad, delegación real | `0.3.0-dev` en rama; `main` es `0.2.0` |
| **`argos`** | Manos sobre un editor de Godot vivo: construir, ejecutar, capturar, corregir | `1.1.0`, repo limpio |
| **`hermes-video-editor`** | Un panel que edita y exporta vídeo real con FFmpeg | `0.3.4`, motor verificado |

Cada uno tiene su propio archivo de propuesta, con sus propios límites dichos sin
adornos:

- [`HERMES-BOTS.md`](HERMES-BOTS.md)
- [`ARGOS.md`](ARGOS.md)
- [`EDITOR-VIDEO.md`](EDITOR-VIDEO.md)

## El argumento para aceptar los tres

Por separado son tres buenas herramientas. Juntos describen un **circuito completo
que un agente local puede recorrer en su propia máquina**:

```
Bot Chat  →  decide y delega
   ↓
ARGOS     →  construye el juego, lo ve corriendo, lo corrige
   ↓
Editor    →  corta el tráiler de lo que de verdad salió
```

Eso es lo que ningún agente en la nube puede hacer: **ver su propio resultado y
corregirlo, sin subir nada, sin cuenta y sin factura por minuto.**

## Lo que los tres comparten

- **Solo loopback.** Ningún plugin abre un puerto hacia internet ni llama a casa.
- **Sin telemetría.** Ninguno de los tres manda datos a ningún sitio.
- **Documentación honesta.** Cada propuesta dice qué está verificado y qué no.
  Preferimos aparecer como «motor verificado, interfaz aún no recorrida» a que nos
  descubran después.
- **Bilingüe.** Inglés y español en todos los README, porque es el idioma en el que
  se construyeron y para el que se construyeron.

## Lo que NO estamos afirmando

- No que estén terminados. ARGOS nunca construyó una escena entera sin
  acompañamiento; el panel del editor de vídeo no se ha recorrido de punta a punta
  con ratón; la `0.3.0` de Bot Chat no está fusionada.
- No que funcionen en toda plataforma. Construidos y probados en Windows 11.
- No que sustituyan a las herramientas en la nube. Sustituyen la parte del flujo que
  nunca necesitó la nube: el archivo que está en tu escritorio.

## Decisión que hace falta de Tormen antes de enviar

1. **A nombre de quién va** — personal (`Tormen28`) o un nombre de proyecto.
2. **Un envío o tres** — la suite argumenta mejor junta; puede que el catálogo las
   exija por separado.
3. **Versión de Bots** — proponer `0.2.0` (segura, sin delegación) o fusionar la
   `0.3.0` primero.
4. **Confirmación de licencia** — MIT para los tres.
