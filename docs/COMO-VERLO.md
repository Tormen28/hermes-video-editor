# Cómo verlo en vivo (tras el pack v1.1)

## 1 · Recargar el pane (obligatorio: cambió el plugin)

1. Cierra el pane del editor con la **✕** de su cabecera.
2. Abre **Capacidades → Plugins** y apaga/enciende **Editor de vídeo** (recarga el módulo).
3. Vuelve a abrirlo. Si no aparece, `Ctrl+K` → «Editor de vídeo».

El servicio ya está vivo en **127.0.0.1:8770** versión **0.3.3** (4 presets, 7 transiciones). Si la app se reinició y el servicio no está: doble clic en `core/iniciar-servicio.cmd`.

## 2 · Probar música

1. Crea un proyecto y **importa** un clip y un archivo de audio (`.mp3/.wav/.m4a`).
2. En el rail, sección **Música**: elige la pista, volumen, fade in/out, loop y ducking.
3. Activa **Normalizar volumen** si quieres loudness uniforme.
4. Reproduce: la música suena mezclada con el audio de las escenas.

## 3 · Probar animaciones

- **Transiciones**: selecciona la escena 2 o 3 → «Transición de entrada» (fundido, deslizar, barrido, círculo, zoom) + duración. La primera escena no tiene.
- **Texto**: escribe un texto → tamaño, color, borde, sombra y entrada/salida (fade o slide).
- **Ken Burns**: en una escena de imagen, activa y elige zoom/pan (en vídeo sale deshabilitado).
- **Velocidad**: slider 0.5–2×; mira cómo cambia la duración de la escena.
- **Filtros**: brillo/contraste/saturación, B/N, viñeta, desenfoque.

## 4 · Logo y export

- **Logo**: elige una imagen, 9 posiciones, opacidad y escala; «Quitar logo» lo elimina.
- **Exportar**: elige preset (720p, 1080p «requiere medición», vertical 9:16, cuadrado 1:1) → progreso real → al terminar, «Agregar al chat».

## 5 · Generar desde el chat (sin panel)

Pídelo en el chat y yo ejecuto el puente `core/scripts/ve_generate.py`:

- Imagen que entra como escena: `--kind image --prompt "intro azul" --use scene`
- Música de fondo: `--kind music --prompt "cama épica" --duration 12 --use music`
- Logo: `--kind image --prompt "logo minimal" --use logo`
- SFX en un segundo: `--kind music --prompt "whoosh" --duration 2 --use sfx --at 3.5`

El pane se refresca solo (cada 4 s si no estás escribiendo) y avisa «Proyecto actualizado desde el chat». Proveedor por defecto: **local** (gratis, sin red). Cuando conectes tus proveedores, solo se configuran `VE_PROVIDER_IMAGE_URL` / `VE_PROVIDER_MUSIC_URL` (+ `_KEY`) en el servicio y se usa `--provider http`.

## 6 · Si algo falla

- Pane en blanco: revisa que el servicio responda `curl http://127.0.0.1:8770/health`.
- Error 400 al exportar: el mensaje del job dice qué escena/campo no valida.
- Log del servicio: `core/logs/service.stdout.log`.
