# UI-B — Texto con estilo, filtros, Ken Burns, velocidad y logo (verificada y desplegada)

Fecha: 2026-11-08. Implementación por Hephaestus en la fuente; **despliegue y verificación hechos por el Padre** (el subagente agotó iteraciones antes de copiar).

## Qué entró al pane

- **Texto**: tamaño 12–120, color, borde 0–10, sombra 0–10 y animación de entrada/salida (`none|fade|slide-up|slide-down`). Los controles quedan deshabilitados si la escena no tiene texto (el backend rechaza `content` vacío); editar el texto conserva el estilo.
- **Filtros**: brillo −1..1, contraste 0..2, saturación 0..3, B/N, viñeta, desenfoque 0–20 y «Restablecer filtros»; se omiten claves neutras.
- **Ken Burns**: en imágenes, toggle + zoom 1–1.5 + pan; en vídeo aparece deshabilitado con «Solo imágenes».
- **Velocidad**: slider 0.5–2.0 con duración efectiva visible; reajusta ventanas de texto y cruce para que el documento siga validando.
- **Logo**: sección de proyecto con asset de imagen, 9 anclas, opacidad 0–1, escala 0.05–0.5 y «Quitar logo».

## Verificación del Padre (evidencia real)

- Fuente: **3.907 líneas**, `node --check` **exit 0**.
- Desplegado: copiado a `desktop-plugins/editor-video/plugin.js`; **md5 idéntico** `380b2983fffa85386917e3519e1c7b6c` en ambos.
- `node --check` sobre el desplegado: **exit 0**.
- `QA_PROBE`: **0 ocurrencias**.
- Smoke con stubs del SDK sobre la copia **desplegada**: **30/30 PASS**, 13 PUT capturados, `register OK`, 4 contribuciones (pane, titlebar, paleta, atajo).
- Los **13 documentos PUT** generados por el smoke se validaron contra `core/project.py` real: **13/13 válidos** (tras corregir solo campos del fixture: `fps`, `baseRevision`, `rights`, `sha256`, `source.path`). No hay errores de `text.size/color/animation`, `filters`, `kenBurns`, `speed` ni `logo`.
- Servicio vivo: **0.3.3**, 4 presets, 7 transiciones.

## Límite

El pane debe **recargarse** para tomar el plugin nuevo (Ctrl+K o toggle en Capacidades). La prueba con clics reales sigue siendo la aceptación de Tormen.
