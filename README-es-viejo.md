# Editor de vÃ­deo para Hermes Desktop

Editor de vÃ­deo **dentro** de Hermes: chat a la izquierda, editor a la derecha. Local-first, sin proveedores obligatorios, con generaciÃ³n opcional desde el chat.

## Arranque rÃ¡pido

```
instalar.cmd
```

Luego en Hermes: **Capacidades â†’ Plugins â†’ Editor de vÃ­deo** (apagar/encender) y **Ctrl+K â†’ Â«Editor de vÃ­deoÂ»**.

GuÃ­as:

- [`docs/README-USUARIO.md`](docs/README-USUARIO.md) â€” instalaciÃ³n, uso, proveedores, problemas.
- [`docs/REGLAS-DEL-PLUGIN.md`](docs/REGLAS-DEL-PLUGIN.md) â€” quÃ© hace y quÃ© nunca harÃ¡.
- [`docs/COMO-VERLO.md`](docs/COMO-VERLO.md) â€” recorrido de prueba.
- [`core/CONTRATO.md`](core/CONTRATO.md) â€” contrato tÃ©cnico del servicio.

## QuÃ© incluye

- Escenas con recorte, orden, split y velocidad 0.5â€“2Ã—.
- MÃºsica de fondo (volumen, fades, loop, ducking, loudnorm) y SFX por eventos.
- Transiciones reales: fundido, deslizar, barrido, cÃ­rculo, zoom.
- Texto con estilo y animaciÃ³n; filtros; Ken Burns; logo con 9 anclas.
- Export 720p30, vertical 9:16, cuadrado 1:1; 1080p experimental.
- GeneraciÃ³n opcional (imagen/mÃºsica) con proveedor local gratis o proveedor HTTP propio.

## Chat + editor, una sola cosa

- **A mano:** reproduce con reloj `mm:ss.ms`, salta a un tiempo exacto, mueve/recorta/reordena escenas, edita textos, silencia o baja el volumen por escena, coloca voces y sonidos en la lÃ­nea de tiempo, previsualiza y exporta (el MP4 se ve dentro del propio editor).
- **Por chat:** Hermes lee y edita **el mismo proyecto por tiempo** (Â«en el 3:13 cambia el textoâ€¦Â») con `core/scripts/ve_timeline.py` o la API; el pane lo muestra solo y tus cambios no se pierden. â†’ [`docs/CHAT-Y-EDITOR.md`](docs/CHAT-Y-EDITOR.md)
- **Skill de Hermes:** [`hermes-skill/editor-video/SKILL.md`](hermes-skill/editor-video/SKILL.md) enseÃ±a todo el flujo (incluido el Cinematic).

## Arranque y seguridad

1. `activar-editor.cmd` (o `python instalar.py`): crea el **token** del servicio, lo incrusta en el plugin instalado (con respaldo `.bak`), arranca el servicio con el lanzador **desacoplado** (sobrevive al cerrar terminales) y, solo con `--restart`, reemplaza un servicio viejo si no hay exportaciones en curso. Opcional: `--autostart` lo arranca al iniciar sesiÃ³n.
2. En Hermes: Capacidades â†’ Plugins â†’ apagar/encender Â«Editor de vÃ­deoÂ».
3. Sin token no hay acceso: la API rechaza peticiones sin `X-VE-Token` o con `Origin` ajeno (otras pÃ¡ginas web no pueden manejar tu editor).

## VersiÃ³n Plus (opcional, solo documentada)

Todo funciona **sin claves**. Si quieres voz profesional (ElevenLabs) o imÃ¡genes con la API de OpenAI, u otros proveedores, el servicio ya trae un hueco HTTP (`VE_PROVIDER_VOICE_URL/KEY`, `VE_PROVIDER_IMAGE_URL/KEY`) y Hermes hace de orquestador. Su ausencia nunca bloquea nada. â†’ [`docs/PLUS.md`](docs/PLUS.md)

## Estructura

- `plugin/` â€” pane de Hermes (`plugin.js`).
- `core/` â€” servicio loopback + motor FFmpeg + tests.
- `docs/` â€” guÃ­as, diseÃ±o, QA.
- `auditoria/` â€” planes de prueba y veredictos.
- `spike/` â€” evidencia del spike inicial (fixtures).

## Estado

VersiÃ³n del servicio: ver [`VERSION`](VERSION). Suite: `cd core && python -m unittest discover -s tests` (+ `node plugin/tests/merge.test.cjs` para la fusión del pane). Smoke de punta a punta contra un servicio en marcha: `python core/scripts/e2e_smoke.py --help`.

Uso privado. La licencia de distribuciÃ³n se decide antes de publicar el plugin.
