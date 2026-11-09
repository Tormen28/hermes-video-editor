# ADR-001 · Motor del MVP del plugin editor: pipeline FFmpeg propio

- **Estado:** APROBADA por Gustavo (Tormen), 2026-11-08, chat: «ok para adr-001 cualquier cosa la cambiamos».
- **Ámbito:** motor de render del plugin editor de vídeo dentro de Hermes. No decide la UI (esa es siempre el pane nativo del desktop app).
- **Decisor:** Tormen. **Redacción y evidencia:** Hermes Padre; auditoría de datos: Dike (F0-veredicto).

## Contexto

El plan consolidado proponía evaluar HyperFrames (primer candidato), Remotion (alternativa) y FilmCraft (auxiliar). La verificación de Fase 0 midió esta máquina: FFmpeg n9.0.1 completo ya instalado, sin Chrome, sin Rust, con 23.9 GB de RAM, GT 1030 sin NVENC utilizable (falla por driver) y 31–35 GB libres en disco.

## Decisión

El MVP usa **FFmpeg invocado como proceso externo** desde un worker propio, con un documento de proyecto versionado que compila los argumentos. No se incorpora HyperFrames, Remotion ni FilmCraft al camino crítico.

## Evidencia que la sostiene

1. **Capacidades presentes** (medidas con `ffmpeg -filters/-encoders`): `libx264`, `aac`, `trim`, `concat`, `xfade`, `scale`, `crop`, `overlay`, `drawtext` (libfreetype), `subtitles`/`ass` (libass), `afade`, `acrossfade`, `fade`.
2. **Render real probado** (spike F1): MP4 H.264 1280×720 30 fps, 15 s, AAC; pared 1.359 s, CPU 8.8 s, RSS pico ~436 MB; cadena real scale+drawtext+overlay+xfade+acrossfade.
3. **Cancelación y recuperación probadas**: cancelación en 0.52 s sin huérfanos; crash del servicio con job en curso → reaper mata el ffmpeg huérfano y marca el job `interrupted`.
4. **Licencias** (`docs/licencias.md`, apollo): FFmpeg GPLv3 → **verde** mientras se invoque como proceso externo y no se empaquete el binario; HyperFrames exige GSAP en Studio (amarillo); Remotion es **rojo para distribuir** un editor; FilmCraft es verde pero es GUI nativa, no UI dentro de Hermes.
5. **Cero instalaciones**: no se requiere Node ni Chrome en el camino de render; el `FFmpeg` usado vive en la instalación de Hermes (`hermes/tools/…`).

## Alternativas rechazadas (para el MVP)

| Alternativa | Por qué no ahora |
|---|---|
| HyperFrames | Aporta composición HTML→vídeo, no NLE; su Studio arrastra GSAP 3.15 (licencia con «Competitive Products») y Chrome headless. Queda como opción si el MVP necesita plantillas animadas. |
| Remotion | Player/renderer competentes, pero licencia source-available: **rojo si el plugin se distribuye o vende**; además requiere Chrome Headless Shell. |
| FilmCraft | MIT/Apache y buen NLE, pero es app desktop/MCP: no cumple «UI dentro de Hermes»; sirve como editor auxiliar de demos. |

## Consecuencias

- El render es **CPU (libx264)**; 720p/30 con 1 job es el objetivo inicial. 1080p no está garantizado hasta medirlo con material real.
- El documento de proyecto es la única fuente de verdad: preview y export parten del mismo JSON versionado; el MP4 nunca sustituye al proyecto editable.
- El worker corre en proceso separado con cola SQLite y staging atómico; el gateway no se bloquea (p95 medido +1.9 ms absolutos, pendiente de baseline más robusto).
- Sin Chrome ni Node en el camino de render: menos superficie de fallo y ninguna licencia de render.

## Reversión

Si el MVP no alcanza los escenarios U1–U4 con calidad aceptable (p. ej. animaciones o composición que FFmpeg no exprese), se reevalúa HyperFrames (instalando Chrome headless y auditando GSAP) o Remotion (solo uso personal, nunca distribución). La decisión de cambio exige nueva ADR con la carencia demostrada y el coste medido; no se amplía en silencio.

## Vigencia

Aprobada 2026-11-08. Se revisa en el Gate 4 (calidad) y ante cualquier cambio de alcance que introduzca composición animada, 4K o distribución del plugin.

## Addenda de implementación · 2026-11-08 (no cambia la decisión)

### CORS y parada del servicio (misma fecha, tarde)

Al montar el pane en un navegador real apareció que el servicio **necesita CORS**: el pane
corre en otro origen, así que sin cabeceras el `fetch` muere con `TypeError: Failed to fetch`.

- `OPTIONS` responde 204 con `Access-Control-Allow-Methods/Headers/Max-Age`.
- `Access-Control-Allow-Origin` se emite **solo** si el `Origin` está en la allowlist
  (`127.0.0.1/localhost/[::1]:<port>`, `null`, `file://` y los `--allow-origin` extra).
- Un origen ajeno recibe 403 **sin** cabecera CORS. Reflejar el origen recibido sin
  validarlo convertiría la allowlist en decorativa; lo cazó
  `test_preflight_from_foreign_origin_is_rejected`.
- `Access-Control-Expose-Headers: Content-Range, Content-Length, Accept-Ranges` para que el
  `<video>` pueda hacer Range.
- `Service.stop()` activa un evento que `main()` espera: `/admin/stop` ya no deja el proceso
  vivo en su bucle.
- `GET /jobs/<id>` incluye `outputBytes` para que la UI no tenga que inventar el tamaño.

Al construir el worker de producción aparecieron tres hechos medidos que obligan a ajustes dentro de la misma ADR (sigue siendo FFmpeg como proceso externo, sin dependencias nuevas):

1. **Este binario no tiene `-filter_complex_script`.** `ffmpeg -h full` sólo lista `-filter_complex`. El grafo viaja **inline** como un único argumento. Para que eso no abra la puerta a texto de usuario se añadieron dos invariantes probadas: el grafo se compila aquí (el texto siempre va a `textfile=`) y `assert_args_allowed(..., allow_graph=...)` exige coincidencia **byte a byte** con el grafo recién compilado; cualquier variante se rechaza. Límite duro de 20 000 caracteres con error explícito (la línea de comandos de Windows admite 32 767) en vez de truncar en silencio.
2. **El escapado de rutas en filtros es «comillas + backslash en los dos puntos».** Medido en matriz de 6 variantes sobre n9.0.1: comillas solas, backslash solo, sin `fontfile` y sin comillas fallan todas con *No option name near*; la única forma que renderiza es `'C\:/ruta/archivo'`. Queda cubierto por test unitario y por un render real con acentos.
3. **El log de ffmpeg se redacta en origen.** QA había medido que el log del spike repetía la ruta del usuario 4 veces; ahora `ffmpeg.log` se escribe por job con `<home>`/`<user>` sustituidos y se conserva como evidencia de fallo en lugar de purgarse.
