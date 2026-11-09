# Funciones que faltan en el editor (menú de alcance)

Fecha: 2026-11-08. Base: modelo real (`core/schema/project.schema.json`) y motor (`core/service/worker.py`).
Hoy el proyecto soporta: escenas con in/out, orden, **transición solo `none`/`fade-N`**, texto (contenido + posición top/center/bottom, **sin estilo ni animación**), audio por escena (volumen + fade in/out) y volumen maestro. Export único 720p30.

> **Actualización 2026-11-08 22:50 — pack v1.1 implementado.** Música de fondo (volumen/fades/loop/ducking/loudnorm), transiciones reales (fade/slide/wipe/circle/zoom con duración), texto con estilo y animación (fade/slide), filtros por escena, Ken Burns, velocidad 0.5–2×, logo con 9 anclas y presets de export (720p, 1080p experimental, 9:16, 1:1) ya están en el backend **0.3.3** y en el pane (UI-A + UI-B). **Pendiente real:** plantillas de proyecto, medición de 1080p para habilitarlo como opción normal, y biblioteca de música con licencias (hoy se importa audio propio). Lo de abajo queda como referencia del alcance.


## A · Sonido (lo que pediste primero)

| Función | Qué implica | Esfuerzo |
|---|---|---|
| **Música de fondo** | Pista propia (archivo), volumen, fade in/out, loop y recorte; mezcla con el audio de escenas (`amix`/`volume`/`aloop`) | Modelo: `music{}` + filtro + UI. **Medio** |
| **Ducking** | Bajar la música cuando habla una escena (`sidechaincompress`) | Bajo, si hay música |
| **Normalizar volumen** | `loudnorm` al exportar (evita saltos) | Bajo |
| **SFX puntuales** | Efectos en un tiempo concreto (aplausos, whoosh) | Modelo nuevo. Medio |

## B · Animaciones y transiciones

| Función | Qué implica | Esfuerzo |
|---|---|---|
| **Catálogo de transiciones** | Además del fundido: `slideleft`, `wipeleft`, `circleopen`, `zoomin`… con duración (`xfade` real entre escenas) | Modelo + grafo + UI. **Medio** |
| **Animaciones de texto** | Entrada/salida fade/slide/pop; tamaño, color, borde, fuente, sombra (ASS/libass) | Modelo + UI. **Medio** |
| **Ken Burns** | Zoom/pan lento sobre imágenes (`zoompan`) | Bajo |
| **Velocidad de clip** | 0,5×–2× con `atempo`+`setpts` | Bajo |
| **Intro/outro con plantillas animadas** | Requiere motor HTML (HyperFrames) o presets ASS | Alto. F4+ |

## C · Imagen y estilo

| Función | Qué implica | Esfuerzo |
|---|---|---|
| **Filtros rápidos** | Brillo/contraste/saturación, B/N, viñeta, desenfoque, LUT | Bajo (ffmpeg `eq`, `curves`, `vignette`, `lut3d`) |
| **Logo/marca de agua** | Overlay con posición/opacidad/escala | Bajo (`overlay`) |
| **9:16 / 1:1 de export** | Recorte/escala al preset (hoy solo flag h/v) | Bajo-Medio |
| **1080p** | Medir CPU/RAM antes; hoy solo 720p30 | Medio (medición + preset) |

## D · Flujo

- Plantillas de proyecto (intro + escenas + cierre).
- Presets de export por red social.
- Historial de versiones visible (hoy autosave + undo).

## E · Fuera del MVP (decirlo claro)

Multicámara, keyframes, color grading profesional, colaboración, transcripción automática (Whisper local), biblioteca de música con licencias y publicación automática.

## Pack recomendado v1.1 (mayor impacto / menor riesgo)

1. **Música de fondo** (con ducking y normalización).
2. **Catálogo de transiciones** reales entre escenas.
3. **Estilos y animaciones de texto**.
4. **Ken Burns + filtros rápidos + logo**.

Eso convierte el editor de «cortador de escenas» en editor útil para piezas reales, sin cambiar de motor ni de licencias (FFmpeg sigue siendo el motor).
