# Envío a Nous — texto listo para copiar

Tres envíos por separado, como pediste. Cada uno es un correo/mensaje distinto.

---

## 1 · Argos (actualización 1.1.0 → con imagen)

**Asunto:** `argos` — README update with banner (v1.1.0)

```
Hi,

Updating the listing assets for `argos`, the Hermes ⇄ Godot 4 editor portal.

Changed in this update:
- Banner image added to docs/img/argos.jpg, shown in both the English and
  Spanish halves of the README.
- Everything else stays as in 1.1.0: 27 MCP tools, real Godot undo, scene
  tree, play/stop, screenshots.

Repo: https://github.com/Tormen28/argos
License: MIT
State: repo clean, tag 1.1.0.

What is verified: the addon installs, the 27 tools respond, scene tree, node
creation, property reads and captures work against a real Godot 4 project.
What is not: a full agent-driven session that builds a playable scene end to end
without a human clicking. Saying so is deliberate.

Thanks,
Tormen
```

---

## 2 · Hermes Bots (actualización **0.2.0**, como pediste)

**Asunto:** `hermes-bot-chat-agent` — listing update, 0.2.0

```
Hi,

Listing update for `hermes-bot-chat-agent` (Hermes Bots), on 0.2.0.

Changed in this update:
- Banner image added to docs/img/hermes-bots.jpg, shown in both README halves.

What 0.2.0 is: a calmer Bot Chat for people who want answers instead of a wall
of reasoning blocks, tool cards and diffs — plus a configurable safety guard
(secrets, deletes, destructive git, protected-branch pushes, outbound messages,
expensive models) with presets `strict`, `default` and `relaxed`. The guard only
blocks; it never approves.

Note: a 0.3.0 line exists on a branch (real delegation to teammate profiles, a
kanban lock, subagent inheritance). It is NOT part of this listing and will be
proposed separately once it is reviewed.

Repo: https://github.com/Tormen28/hermes-bot-chat-agent
License: MIT
Note on the repo: `main` is 0.2.0. The branch `cursor/bot-chat-team-ux-58e8`
carries the 0.3.0 work and should not be what gets installed.

Thanks,
Tormen
```

---

## 3 · Hermes Video Editor (**primera vez**, no existe)

**Asunto:** New plugin submission — `hermes-video-editor`

```
Hi,

Submitting a new plugin: a video editor that lives inside Hermes Desktop as a
pane and drives FFmpeg on the local machine.

The point: Hermes agents already produce images, documents and code. Video was
the one medium where the agent had to hand you a folder and wish you luck. This
closes that loop — the agent makes the video, and you can still open it, trim it
and fix it yourself.

WHAT IT DOES
- Import video/image/audio by path inside an allowed root; dedupe by SHA-256.
- Timeline: scenes with in/out, reorder, split, trim.
- Text captions per scene, with position and timing.
- Colour: brightness, contrast, saturation, grayscale, vignette, blur.
- Speed per scene, audio pitch-corrected with atempo.
- 7 xfade transitions.
- Music and sound effects generated locally, or through an optional provider.
- Export MP4 H.264 + AAC: 720p, 1080p, vertical, square. Progress, cancel, dedupe.
- The finished MP4 comes back to the chat as an attachment.

OPTIONAL PROVIDERS (never a requirement)
Works fully offline with the local generator. If the user configures a key,
Nano Banana (VE_GEMINI_KEY) improves image quality and ElevenLabs
(VE_ELEVEN_KEY) replaces the system voice. Without a key the service refuses
before making a single network call — there is no silent fallback to a paid
service, and no key ever appears in an error message.

SECURITY
- Loopback only; rejects any Host header that is not 127.0.0.1 or localhost
  (DNS-rebinding guard).
- Origin allowlist; the file:// case is documented as a known local-CSRF
  trade-off rather than hidden.
- Shared token (X-VE-Token) written by the installer; without it, 401.
- Path jail: media must resolve inside the configured root.
- No telemetry, no accounts, no uploads.

VERIFICATION, STATED PLAINLY
- 408 tests green.
- End-to-end: generate → scene → music → effects → export → ffprobe reports
  H.264/AAC 1280×720.
- Colour measured, not assumed: brightness −0.5 takes mean luma 23.8 → 0.0;
  +0.6 → 199.7. Grayscale: RGB 13/25/39 → 21.8/21.8/21.8. Speed 0.5×: 3.0 s →
  6.0 s.
- Known gap: the pane has not been walked through end to end by a human with a
  mouse. The API path is what is verified. A listing should say so.

Repo: https://github.com/Tormen28/<repo>   ← falta crear
License: MIT
Requires: FFmpeg on PATH (or VIDEO_EDITOR_TOOLS); tested with 9.0.1.

Thanks,
Tormen
```

---

## Antes de enviar: lo que falta

| # | Cosa | Estado |
|---|---|---|
| 1 | Repo en GitHub del editor de vídeo | **No existe**. Hay que crearlo |
| 2 | Push de Argos (`5bd1ddf`) | Pendiente de tu OK |
| 3 | Push de Bots (`5601eed`) | Pendiente de tu OK |
| 4 | Nombre del repo del editor | Propuesta: `hermes-video-editor` |
| 5 | Cuenta de GitHub | `Tormen28` (repos privados hoy) |

**Aviso:** los repos de Argos y Bots son **privados** ahora mismo. Para que Nous
pueda revisarlos hay que hacerlos públicos o dar acceso. Eso lo decides tú.
