# Editor de vídeo para Hermes Desktop

Editor de vídeo **dentro** de Hermes: chat a la izquierda, editor a la derecha. Local-first, sin proveedores obligatorios, con generación opcional desde el chat.

## Arranque rápido

```
instalar.cmd
```

Luego en Hermes: **Capacidades → Plugins → Editor de vídeo** (apagar/encender) y **Ctrl+K → «Editor de vídeo»**.

Guías:

- [`docs/README-USUARIO.md`](docs/README-USUARIO.md) — instalación, uso, proveedores, problemas.
- [`docs/REGLAS-DEL-PLUGIN.md`](docs/REGLAS-DEL-PLUGIN.md) — qué hace y qué nunca hará.
- [`docs/COMO-VERLO.md`](docs/COMO-VERLO.md) — recorrido de prueba.
- [`core/CONTRATO.md`](core/CONTRATO.md) — contrato técnico del servicio.

## Qué incluye

- Escenas con recorte, orden, split y velocidad 0.5–2×.
- Música de fondo (volumen, fades, loop, ducking, loudnorm) y SFX por eventos.
- Transiciones reales: fundido, deslizar, barrido, círculo, zoom.
- Texto con estilo y animación; filtros; Ken Burns; logo con 9 anclas.
- Export 720p30, vertical 9:16, cuadrado 1:1; 1080p experimental.
- Generación opcional (imagen/música) con proveedor local gratis o proveedor HTTP propio.

## Estructura

- `plugin/` — pane de Hermes (`plugin.js`).
- `core/` — servicio loopback + motor FFmpeg + tests.
- `docs/` — guías, diseño, QA.
- `auditoria/` — planes de prueba y veredictos.
- `spike/` — evidencia del spike inicial (fixtures).

## Estado

Versión del servicio: ver [`VERSION`](VERSION). Suite: `cd core && python -m unittest discover -s tests`.

Uso privado. La licencia de distribución se decide antes de publicar el plugin.
