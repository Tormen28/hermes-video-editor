# VIDEO-EDITOR · Fase 0 · Deltas al plan y decisiones necesarias

Fecha: 2026-11-08. Fuente: plan consolidado (8-nov) + mediciones propias (00-inventario) + verificación UI (01-superficie-ui).

## Deltas al plan (hechos que cambian supuestos)

| # | Supuesto del plan | Realidad medida | Consecuencia |
|---|---|---|---|
| 1 | «Si realmente hay 8 GB» de RAM | **23.9 GB totales** (libres 10.9–12.9 según momento) | El riesgo de memoria baja de P1 a P2; aun así 1 job y medición real antes de subir concurrencia. |
| 2 | HyperFrames/Remotion como motor principal (Node + Chrome + FFmpeg) | **Chrome no está instalado**; FFmpeg n9.0.1 **completo** ya presente (x264, ass, drawtext, xfade) | El motor del MVP puede ser FFmpeg directo: cero instalaciones, cero Chrome, sin las licencias de Remotion ni el gate GSAP. Se propone ADR-001. |
| 3 | Reutilizar componentes/UI de HyperFrames Studio dentro de Hermes Web | La superficie real es el **SDK de plugins de escritorio** (React propio del app + UI kit nativo) | La premisa de «reutilizar Studio» no aplica: la UI nativa del app ES la base correcta y ya está probada aquí. HyperFrames/Remotion quedan como alternativas de render, no de UI. |
| 4 | API/extensión UI «no demostrada» | **Demostrada en runtime**: doc de 132 KB en disco + pane NUEVO `editor-video-spike` montado con `fetch` OK (Hermes.exe ↔ 127.0.0.1:8765, probes 200) | Gate 0 desbloqueado; quedan picking de archivos y preview `<video>` |
| 5 | Reparación de Hermes (0R) como incógnita principal del calendario | Hermes v0.23.0 estable, autorreporte 178 skills sin verificar | 0R se hace read-only: reconciliar conteos y ciclo real; no bloquea el spike del editor. |

## ADR-001 (APROBADA por Tormen, 8-nov-2026: «ok para adr-001 cualquier cosa la cambiamos»)

**Motor del MVP: pipeline FFmpeg directo, no HyperFrames ni Remotion.**

- A favor (medido): binario completo ya instalado; cubre escenas/trim/concat/xfade/texto/captions/audio/scale; sin Chrome; sin licencia de render; sin Node en el camino crítico; CPU Ryzen 5 3600 suficiente para 720p/30 en 1 job.
- En contra/limites: no da composiciones HTML animadas ni plantillas ricas tipo HyperFrames/Remotion; animaciones complejas quedarían fuera del MVP (el plan ya excluye NLE profesional).
- Condición de reversión: si el spike demuestra que FFmpeg no alcanza los escenarios U1–U4 con calidad aceptable, se reevalúa HyperFrames (instalando Chrome headless) o Remotion (licencia y Chrome Headless Shell), previa revisión de apollo.
- Revisión de licencias: apollo audita igual HyperFrames/Remotion/FFmpeg GPL para que la decisión no dependa de un solo camino.

## Decisiones necesarias (Tormen)

1. **Autorización de ejecución del spike F1** (pane nuevo + servicio + render sintético). Se interpreta dada con «dar inicio este plan … darle con todo»; confirmar si alguna parte la quiere limitar.
2. **Medios**: hasta que autorice material real, todo se prueba con **fixtures sintéticos** generados localmente (sin datos privados, sin capturas).
3. **Ventana de recarga del gateway**: ya **no hace falta para el MVP**: el renderer habla con el servicio en loopback (`fetch` 200 desde origin `file://`). `plugin_api.py` solo se necesitaría para empaquetar el backend dentro del gateway; eso queda para una fase posterior con ventana aprobada.
4. **Disco**: 10 GB temporales dentro de 31 GB libres. Aceptable si se limpian derivados por job; confirmar.
5. **Alcance del motor**: aceptar FFmpeg directo como motor del MVP si el spike pasa (ADR-001), o mantener HyperFrames como obligatorio aunque implique instalar Chrome y asumir su gate de licencias.

## Matriz de permisos del plugin (C7 — requerida por el gate 0)

| Ámbito | Regla propuesta |
|---|---|
| Procesos que puede lanzar el worker | Solo `ffmpeg.exe` y `ffprobe.exe` (allowlist por ruta absoluta, verificada en cada job) + el propio worker Python. Nada de shells, nada de argumentos arbitrarios: el job se compila desde el documento de proyecto. |
| Rutas de lectura | Raíz del proyecto elegida por Tormen + assets seleccionados explícitamente, en **solo lectura**. Nunca `~/.ssh`, credenciales, `.env`, historial de chats. |
| Rutas de escritura | `video-editor/jobs/<job_id>/` (staging), `video-editor/out/`, journal SQLite del servicio. Fuera de ahí, nada. |
| Puerto | Loopback `127.0.0.1:8765` (configurable); nunca LAN; sin autenticación de red porque no sale de la máquina. |
| Límite de entrada | Max 2 GB por job y 20 min de duración total; rechazo temprano con mensaje claro. |
| Progreso/cancelación | `taskkill /T /F` **solo** al PID del job; jamás kill global de Chrome/Node/Python. |
| Retención/purga | Derivados (proxies, staging, frames) se borran al terminar el job; `out/` conserva el MP4 final hasta decisión de Tormen. |
| Secretos | El worker arranca con entorno filtrado (sin claves) y nunca recibe el proyecto entero ni chats. |

## Orden F1 vs gate 0 (H-9 de Dike)

El spike arrancó en paralelo al veredicto de gate 0 por autorización expresa de Gustavo («darle con todo», 8-nov). Se acepta como desviación documentada: el propio spike produjo la evidencia de runtime que el gate exigía (pane montado + fetch). Las correcciones C1–C8 de Dike ya están aplicadas en la revisión 2 de estos documentos.

## Lo que NO se hace en Fase 0

- No instalaciones globales, no compras, no cloud, no capturas de pantalla reales, no publicación.
- No reinicio del gateway en vivo.
- No se presentan demos como sustituto del plugin.
