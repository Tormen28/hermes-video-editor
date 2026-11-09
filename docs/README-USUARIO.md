# Editor de vídeo para Hermes Desktop — guía de usuario

Un editor dentro de Hermes: el chat a la izquierda, el editor a la derecha. Importa tus clips, monta, pone música, títulos y efectos, previsualiza y exporta MP4. **Funciona sin conexión y sin proveedores externos.**

## Requisitos

- Windows 10/11.
- Hermes Desktop con plugins de escritorio (pane).
- **FFmpeg y ffprobe** en el `PATH` o en la carpeta `hermes/tools` (el servicio los autodetecta; si no, define `VIDEO_EDITOR_TOOLS` con la carpeta que los contiene).
- Python 3.10+ para el servicio local.
- 8 GB de RAM recomendados; 4 GB mínimos con clips cortos.
- Espacio libre para datos temporales (1–3 GB según proyectos).

## Instalar

1. Descomprime/clona esta carpeta donde quieras.
2. Doble clic en **`instalar.cmd`** (o `python instalar.py`).
   - Copia el plugin a `%LOCALAPPDATA%\hermes\desktop-plugins\editor-video`.
   - Crea la carpeta de medios (por defecto `%USERPROFILE%\Videos\hermes-video`; cámbiala con `--media-root`).
   - Escribe la config del servicio y lo arranca.
3. En Hermes: **Capacidades → Plugins**, apaga/enciende **Editor de vídeo**.
4. Abre el pane con **Ctrl+K → «Editor de vídeo»**.

Si algo falla, revisa `http://127.0.0.1:8770/health`. Para arrancar el servicio a mano: `core/iniciar-servicio.cmd`.

## Uso básico

1. **Crear proyecto** y ponerle nombre.
2. **Importar medios**: MP4/MOV/MKV, PNG/JPG, MP3/WAV/M4A.
3. **Montar**: arrastra escenas al orden, recorta inicio/fin, parte clips.
4. **Música**: elige una pista de audio, volumen, fades, loop, ducking y normalización.
5. **Texto**: tamaño, color, borde, sombra y animación de entrada/salida.
6. **Transiciones**: fundido, deslizar, barrido, círculo o zoom, con duración.
7. **Imagen**: filtros rápidos, Ken Burns (solo imágenes), velocidad 0.5–2×.
8. **Logo**: imagen, 9 posiciones, opacidad y escala.
9. **Preview** y **Exportar**: 720p30, vertical 9:16, cuadrado 1:1. 1080p está marcado como experimental hasta medir recursos.
10. Al terminar, **«Agregar al chat»** devuelve el resultado al proyecto.

## Generar desde el chat (opcional)

Sin configurar nada hay un **proveedor local** (imagen y música sintéticas, gratis y sin red). Pídelo en el chat:

- «Mete una intro con fondo azul» → imagen → escena.
- «Pon música épica de fondo» → música → pista.
- «Un whoosh en el segundo 3» → SFX en el timeline.
- «Pon el logo abajo a la derecha».

Con proveedores propios (imagen/música): define en el entorno del servicio
`VE_PROVIDER_IMAGE_URL`, `VE_PROVIDER_MUSIC_URL` y sus `_KEY`. El chat usará
`--provider http`. Si no hay proveedor configurado, el plugin sigue funcionando
igual: la generación externa es un extra, nunca un requisito.

## Límites conocidos

- Una pista de música por proyecto; los SFX van por eventos con tiempo.
- 1080p experimental; 4K/60 fuera de alcance.
- No es un NLE profesional: sin multicámara, keyframes ni grading avanzado.
- El proyecto no se sincroniza en la nube; todo es local.
- El material generado depende de los términos/licencia de cada proveedor.

## Privacidad y seguridad

- Servicio en `127.0.0.1` únicamente; no se expone a la LAN.
- Los medios se leen solo de la carpeta concedida; no se copian a la nube.
- Las claves de proveedores viven en el entorno del servicio, nunca en el proyecto, el chat ni el vault.
- El editor no publica, no envía mensajes ni gasta dinero: exportar es local.

## Desinstalar

```
python instalar.py --uninstall           # quita el plugin, conserva datos
python instalar.py --uninstall --purge   # quita plugin, datos y config
```

Tus archivos de la carpeta de medios **no** se borran.

## Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| Pane en blanco o «Failed to fetch» | Servicio caído: `core/iniciar-servicio.cmd`; comprueba `/health`. |
| «FFmpeg no encontrado» | Instala FFmpeg en PATH o define `VIDEO_EDITOR_TOOLS`. |
| No aparece el plugin | Capacidades → Plugins → apagar/encender; o revisa el id en `desktop-plugins`. |
| Error al exportar | El job dice qué escena/campo falla; revisa duración, transición más larga que el clip o asset faltante. |
| 1080p falla o va lento | Es experimental: usa 720p o mide RAM/CPU antes de insistir. |
