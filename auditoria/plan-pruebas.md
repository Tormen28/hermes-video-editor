# Plan de pruebas y matriz de aceptación · editor de vídeo (pre-MVP)

- **Autor:** Dike (QA), 2026-11-08.
- **Estado:** PROPUESTA NORMATIVA. Define «hecho» por escrito **antes** de que exista el MVP; no sustituye la aprobación de Tormen.
- **Ámbito:** plugin editor dentro de Hermes Web (pane nativo) + servicio de jobs + worker FFmpeg. Escenarios U1–U4, los 10 tipos de prueba del plan consolidado, pruebas adversariales y integración.
- **Fuentes:** `PLAN-CONSOLIDADO.md` (MVP l.38-53; fases 2-4; Aceptación l.374-390; Pruebas l.392-409), `auditoria/F0-veredicto.md`, `spike/REPORTE.md`, `docs/ui-spec.md` §5-§12, `docs/licencias.md`, `docs/ADR-001-motor-ffmpeg.md` (aprobada).
- **Regla de lectura:** todo umbral marcado **[P]** es provisional y necesita aprobación (o recalibración con datos) antes de usarse como puerta. Los **[F]** vienen fijados por el plan o por la especificación de UI.
- **Pack v1.1 (música, transiciones, texto, Ken Burns, velocidad, filtros, logo, presets 9:16/1:1/1080p y plantillas):** plan específico en `auditoria/plan-pruebas-v11.md` (88 casos, 2026-11-08). Este documento sigue siendo la referencia del MVP; el anexo v1.1 hereda sus reglas y añade los criterios de regresión `REG-01`/`REG-02`.

---

## 0. Reglas del juego

### 0.1 Veredictos

| Veredicto | Cuándo |
|---|---|
| **PASS** | Todos los pasos ejecutados, artefacto de evidencia presente y reproducible por un tercero, criterio cuantitativo cumplido. |
| **FAIL** | Criterio incumplido, o evidencia no reproducible. |
| **BLOCKED** | No se pudo ejecutar por falta de entorno, permiso o decisión pendiente. **No cuenta como PASS.** Se declara con causa. |
| **N/A** | La funcionalidad no existe por decisión aprobada (p. ej. pausa). Exige cita de la decisión, no silencio. |

Un caso **FAIL** que toca un control crítico invalida el gate completo. Un caso **BLOCKED** en un control crítico también impide declarar el gate cerrado: se cierra como «gate abierto con deuda declarada», nunca como «aprobado».

### 0.2 Severidad y regla de bloqueo

| Sev | Definición | Efecto |
|---|---|---|
| **S1** | Pérdida o corrupción de datos del proyecto, fuga de secretos/datos de terceros, salida inválida promovida como buena, proceso huérfano, escritura fuera de la raíz permitida, ejecución de composición no confiable. | **Bloquea release.** No admite excepción ni «deuda». |
| **S2** | Un escenario U1–U4 no se completa, o se completa con error visible, o el resultado no es reproducible. | **Bloquea el gate** hasta corregir o degradar alcance por escrito. |
| **S3** | Copy incorrecto, desviación visual, atajo ausente, mensaje mejorable. | No bloquea; se registra y se agrupa. |

**Regla dura:** solo bloquea lo **introducido o empeorado** por la tarea. La deuda preexistente se reporta como observación **no bloqueante** con su propia evidencia, salvo que el cambio la agrave (entonces se trata como introducida).

### 0.3 Anti-self-report

Ningún caso se cierra con: «funciona», «lo probé», «el constructor dice que pasa», un `exit_code 0`, una captura del mockup, ni un vídeo del camino feliz sin estado terminal. Ver §5.

### 0.4 Independencia

Quien implementa **no** firma su propia aceptación. Dike ejecuta o reproduce cada caso sobre el artefacto instalado; si un caso exige una decisión de Tormen, se marca BLOCKED y se eleva, no se interpreta.

---

## 1. Entorno de referencia y registro por corrida

### 1.1 Línea base medida de esta máquina (2026-11-08 14:48 -04:00)

| Dato | Valor medido | Comando |
|---|---|---|
| SO / host | Windows 11, usuario `EgtYP` | — |
| RAM | 23,93 GB totales · 11,26 GB libres al medir | `Get-CimInstance Win32_OperatingSystem` |
| Disco C: | 223 GB · 190 GB usados · **34 GB libres (85 %)** | `df -h /c` |
| Paging en reposo | `PagesPersec = 3` | `Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory` |
| FFmpeg | `n9.0.1-11-ge47273f4d9-20260831` | `ffmpeg -version` |
| Ruta FFmpeg en PATH | `C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg` (**única** en PATH) | `which -a ffmpeg` |
| Chrome | ausente | F0 §1.2 + comprobación de rutas |
| Reproductores disponibles | Edge (Chromium) y Windows Media Player (Media Foundation). **No** hay VLC ni mpv | comprobación de rutas |

> Estas cifras **caducan**. Cada corrida debe volver a medirlas y anotarlas; un PASS con otra máquina, otro FFmpeg u otro disco no es el mismo PASS.

### 1.2 Registro obligatorio por corrida (`run.json`)

```jsonc
{
  "run_id": "RUN-20261110-0930-gate2",
  "fecha_local": "2026-11-10T09:30:00-04:00",
  "artefacto": { "plugin_version": "0.1.0", "commit_o_hash": "…", "build_sha256": "…" },
  "runtime": { "hermes_version": "…", "perfil": "prueba", "ffmpeg_path": "…", "ffmpeg_sha256": "…" },
  "maquina": { "ram_total_gb": 0, "ram_libre_gb": 0, "disco_libre_gb": 0, "pages_persec_reposo": 0 },
  "fixtures": { "FX1": "sha256:…", "FX2": "sha256:…", "FX3": "sha256:…" },
  "resultados": [{ "caso": "U1-01", "veredicto": "PASS", "evidencia": ["U1-01_pane.png"] }]
}
```

Sin `run.json` la corrida no existe para efectos de gate. El hash del binario FFmpeg es obligatorio: el plan depende de una versión concreta (ver A-04 y C-3).

---

## 2. Matriz de aceptación U1–U4

Convención de pasos: «usuario» significa **persona que no programa**, sin terminal, sin editar JSON, sin abrir otra app. La evidencia va a `auditoria/evidencia/<run_id>/`.

### U1 · Crear e importar

#### U1-01 · Entrar desde Hermes Web sin abrir otra app `[S2]`
- **Pre:** Hermes Desktop abierto; perfil de prueba; ningún editor externo en ejecución.
- **Pasos:** 1) Abrir el chat de la sesión de prueba. 2) Abrir el pane «Editor de vídeo» desde la superficie Hermes. 3) Observar.
- **Esperado:** el pane monta dentro de la app; sin ventana de otra aplicación; sin CLI; estado A (§7) con «Sin proyecto».
- **Evidencia:** `U1-01_pane.png` (captura completa con barra de título), `U1-01_procesos.txt` (`tasklist` filtrado por editores externos), `gateway.log` con la línea de montaje del pane.
- **PASS/FAIL:** PASS si el pane monta y no hay proceso de app externa. FAIL si aparece una app separada, una pestaña de navegador suelta o una terminal.

#### U1-02 · Crear proyecto con contexto explícito `[S2]`
- **Pre:** estado A; `activeSessionId` no nulo; `cwd` conocido.
- **Pasos:** 1) «Crear proyecto». 2) Nombrar «Lanzamiento Q4». 3) Confirmar.
- **Esperado:** proyecto creado; chip «Sesión 4f2a · lanzamiento-q4»; Rev 1; estado B; `project.session_id` y `cwd` = los del host (no vacíos, no inventados).
- **Evidencia:** `U1-02_chip.png`, `GET /projects/<id>` volcado a `U1-02_project.json`, fila en la BD del servicio.
- **PASS/FAIL:** PASS si `session_id` y `cwd` coinciden **exactamente** con `host.state`. FAIL si el backend recibe `null`, cadena vacía o una ruta distinta.

#### U1-03 · Importar un clip válido (arrastrar y soltar) `[S2]`
- **Pre:** estado B; fixture `FX1.mp4` (6,0 s, 1280×720, 30/1, 180 frames, sin audio).
- **Pasos:** 1) Arrastrar `FX1.mp4` al escenario. 2) Soltar. 3) Esperar fin de subida.
- **Esperado:** una escena «FX1»; duración 6,0 s; miniatura; preview 540p reproducible; documento con `media_id`, `in=0`, `out=6.0`.
- **Evidencia:** `U1-03_escena.png`, `U1-03_media.ffprobe.txt` (del archivo **guardado**, no del original), `U1-03_project.json`.
- **PASS/FAIL:** PASS si la duración mostrada y la del `ffprobe` del medio importado coinciden en ±1 frame y la escena aparece sin recargar. FAIL si hay que recargar, si la duración es 0 o si el preview queda en skeleton.

#### U1-04 · Importar audio y captura (PNG/JPG) `[S2]`
- **Pre:** fixtures `FX5.wav` (tono con voz simulada) y `logo.png`.
- **Pasos:** 1) Importar `FX5.wav`. 2) Importar `logo.png`. 3) Crear escena con el logo.
- **Esperado:** pista A1 con forma de onda y «A1 · Voz»; imagen como escena de duración por defecto declarada (si no hay valor especificado → decisión D-16); sin errores en consola.
- **Evidencia:** `U1-04_rail.png`, `U1-04_consola.txt` (0 errores), `U1-04_project.json`.
- **PASS/FAIL:** PASS si ambos se importan y el audio se reproduce. FAIL si la imagen exige duración manual no documentada o el audio no suena.

#### U1-05 · Rechazo claro de formato no admitido `[S3]`
- **Pre:** `anim.gif` (no permitido por §5.2) y `nota.txt`.
- **Pasos:** 1) Arrastrar `anim.gif` al pane. 2) Repetir con `nota.txt`.
- **Esperado:** badge `destructive` «Formato no admitido: .gif»; ninguna escena creada; proyecto intacto.
- **Evidencia:** `U1-05_rechazo.png`, `U1-05_project_before_after.json` (idénticos salvo `updated_at`).
- **PASS/FAIL:** PASS si el copy es el de §8 y el proyecto no cambia. FAIL si se crea una escena rota o el error es un volcado técnico.

#### U1-06 · Carpeta protegida de Hermes `[S1]`
- **Pre:** `ctx.files.requestFolder()` devuelve `{ok:false, error:'protected'}` para una carpeta con datos de Hermes (p. ej. `~/.hermes`).
- **Pasos:** 1) «Importar medios» → elegir esa carpeta. 2) Intentar forzar la selección.
- **Esperado:** «Esa carpeta contiene datos de Hermes y no se puede usar como medios.» Sin lectura, sin listado, sin copia.
- **Evidencia:** `U1-06_protegida.png`, `U1-06_servicio.log` sin peticiones de esa ruta, `U1-06_netstat.txt`.
- **PASS/FAIL:** PASS si no se lee ni se lista nada. FAIL si el backend abre la ruta, la lista o registra nombres de archivo de esa carpeta.

#### U1-07 · Archivo corrupto o de 0 bytes `[S2]`
- **Pre:** `FX7.mp4` (6 000 bytes truncados, sin `moov`) y `vacio.mp4` (0 bytes).
- **Pasos:** 1) Importar `FX7.mp4`. 2) Importar `vacio.mp4`.
- **Esperado:** error legible, escena no creada o creada en estado «medio inválido» con export bloqueado; **el proyecto existente no se corrompe**.
- **Evidencia:** `U1-07_error.png`, `U1-07_project.json` antes/después, `U1-07_servicio.log`.
- **PASS/FAIL:** PASS si el proyecto sigue siendo cargable y el error no es un stack trace. FAIL si el proyecto queda ilegible.

#### U1-08 · Archivo grande (>100 MB) `[BLOCKED → D-07]`
- **Pre:** `FX8.mp4` de ~150 MB.
- **Pasos:** 1) Importar por drop. 2) Repetir por carpeta concedida.
- **Esperado:** según se decida: subida con progreso, o mensaje «Archivo demasiado grande» con vía alternativa.
- **Evidencia:** `U1-08_*.png`, tiempo de subida, memoria del pane.
- **PASS/FAIL:** **BLOCKED** hasta D-07. No se puede aprobar U1 completo sin resolver qué pasa con el material real (>100 MB es el caso normal de una grabación).

#### U1-09 · Selección explícita: nada de contexto implícito `[S1]`
- **Pre:** sesión con historial de chat; proyecto nuevo.
- **Pasos:** 1) Importar solo `FX1.mp4`. 2) Guardar. 3) Inspeccionar el documento y el medio en disco.
- **Esperado:** el documento referencia **solo** `FX1`; ningún adjunto del chat, ningún archivo del `cwd`, ninguna credencial viaja al servicio.
- **Evidencia:** `U1-09_project.json`, `U1-09_media_dir.txt` (listado del directorio de medios), `U1-09_canario.txt` (ver A-02).
- **PASS/FAIL:** PASS si el listado coincide con lo importado. FAIL si aparece cualquier archivo no seleccionado.

#### U1-10 · Medio faltante tras mover el original `[S2]`
- **Pre:** proyecto con `FX1` importado; renombrar/mover el original fuera del `cwd`.
- **Pasos:** 1) Reabrir el proyecto. 2) Intentar exportar. 3) «Volver a vincular» al archivo movido.
- **Esperado:** estado H: «Falta FX1.mp4»; export deshabilitado; revincular restaura sin perder cortes ni textos.
- **Evidencia:** `U1-10_faltante.png`, `U1-10_export_disabled.png`, `U1-10_project.json` con `media.missing`.
- **PASS/FAIL:** PASS si el export está bloqueado **y** la revinculación conserva la edición. FAIL si se exporta con el medio ausente o se pierde el documento.

---

### U2 · Editar visualmente

#### U2-01 · Reproducir y pausar `[S2]`
- **Pre:** proyecto con 2 escenas y audio.
- **Pasos:** 1) Play. 2) Pausa a los ~2 s. 3) Play de nuevo.
- **Esperado:** play/pausa con icono y `aria-label` cambiantes; timecode `mm:ss,d`; sin salto al pausar.
- **Evidencia:** `U2-01_play.gif` (≤5 s) o 3 capturas con timecode, `U2-01_aria.txt` (dump del AX tree).
- **PASS/FAIL:** PASS si el tiempo avanza de forma monótona y la pausa conserva la posición ±1 frame.

#### U2-02 · Scrub exacto a frame `[S2]`
- **Pre:** `FX1` en timeline (3 colores, cortes en frame 60 y 120).
- **Pasos:** 1) Arrastrar el scrub a la posición del corte. 2) Soltar. 3) Leer timecode. 4) Repetir con flechas (1 frame) y `Shift+flecha` (1 s).
- **Esperado:** la posición se puede fijar en `02:00,0` exacto; el frame mostrado corresponde al índice pedido; timecode con coma decimal es-ES.
- **Evidencia:** `U2-02_scrub.png` + `U2-02_currentTime.txt` (valor leído del `<video>`), comparado con el índice esperado.
- **PASS/FAIL:** PASS si `currentTime` cae dentro de ±1/30 s del objetivo. FAIL si el scrub solo llega a keyframes.

#### U2-03 · Reordenar dos escenas (ratón y teclado) `[S2]`
- **Pre:** 3 escenas A, B, C.
- **Pasos:** 1) Arrastrar C a la posición 1. 2) Deshacer. 3) Con teclado: seleccionar C y pulsar «Subir escena» dos veces. 4) Escuchar el anuncio.
- **Esperado:** orden C,A,B; timeline y preview coherentes; `aria-live` «Escena 3 movida a la posición 1»; `Esc` cancela el arrastre.
- **Evidencia:** `U2-03_orden.json` (ids en orden), `U2-03_aria.txt`, `U2-03_video.mp4` (5 s).
- **PASS/FAIL:** PASS si ambos caminos producen el mismo resultado y el orden persiste al guardar. FAIL si solo funciona con ratón (WCAG 2.5.7).

#### U2-04 · Recortar entrada y salida `[S2]`
- **Pre:** escena de 6,0 s; cursor en 1,2 s.
- **Pasos:** 1) «Fijar entrada en el cursor». 2) Cursor en 5,0 s → «Fijar salida». 3) Exportar (o previsualizar el clip).
- **Esperado:** duración 3,8 s; el primer frame del render es el frame 36 del original; el último es el 149.
- **Evidencia:** `U2-04_project.json`, `U2-04_frames.txt` (índices), `U2-04_render.ffprobe.txt`.
- **PASS/FAIL:** PASS si la duración es 3,8 s ±1 frame y los índices coinciden ±1. FAIL si se recorta en keyframe o se desfasa.

#### U2-05 · Validación de recorte mínimo `[S3]`
- **Pre:** escena de 6 s.
- **Pasos:** 1) Fijar salida a 0,2 s de la entrada. 2) Intentar confirmar.
- **Esperado:** error inline con `aria-invalid` y texto «La salida debe ser al menos 0,3 s después de la entrada.»; no se corrige en silencio.
- **Evidencia:** `U2-05_error.png`, `U2-05_project.json` sin cambio.
- **PASS/FAIL:** PASS si el valor no se aplica y el mensaje es el de §5.7 R6.

#### U2-06 · Partir un clip en el cursor `[S2]`
- **Pre:** escena de 6 s; cursor en 2,0 s. *(ui-spec T4 lo incluye: el «si es esencial» del plan queda resuelto por la especificación; si se retira, ver D-05.)*
- **Pasos:** 1) Pulsar «Partir en el cursor». 2) Intentar partir a 0,1 s de un borde.
- **Esperado:** dos escenas de 2,0 y 4,0 s, misma fuente, sin hueco ni solape; en el borde, `Tip` «Coloca el cursor a más de 0,3 s del borde» y no parte.
- **Evidencia:** `U2-06_split.json`, `U2-06_timeline.png`, suma de duraciones = original ±1 frame.
- **PASS/FAIL:** PASS si la suma de duraciones es exacta y el export posterior no repite ni pierde frames.

#### U2-07 · Texto en pantalla con acentos, `%`, `:` y comillas `[S1]`
- **Pre:** `FX4.txt` = `Ahorra 50%: it’s “ñandú” — día 3/4` (máx. 90 caracteres, sin normalizar).
- **Pasos:** 1) Escribir el texto. 2) Ver el overlay en el preview. 3) Exportar. 4) Extraer el frame donde aparece el texto.
- **Esperado:** preview y MP4 muestran el texto **literal**, con acentos, `%`, dos puntos y comillas; sin error de filtro; sin truncado.
- **Evidencia:** `U2-07_preview.png`, `U2-07_frame_export.png`, `U2-07_ffmpeg.log` (sin «No option name» ni «Stray %»).
- **PASS/FAIL:** PASS solo si el render termina y el frame muestra el texto literal. FAIL si el job falla o el texto sale alterado. **Este caso es S1 porque un `%` rompe el pipeline con FFmpeg 9 si no se usa `expansion=none`** (ver A-04 y Anexo A.3).

#### U2-08 · Volumen de escena y maestro `[S2]`
- **Pre:** `FX5.wav` como audio; medir loudness del original.
- **Pasos:** 1) Bajar volumen de escena a 40 %. 2) Bajar maestro a 50 %. 3) Exportar. 4) Medir loudness.
- **Esperado:** atenuación monótona y audible; sin clipping; mute silencia de verdad.
- **Evidencia:** `U2-08_ffmpeg_ebur128.txt` del original y del export; diferencia de LUFS coherente con los porcentajes (±3 LU).
- **PASS/FAIL:** PASS si el export medido difiere del original en la dirección esperada y el mute da silencio digital (< -70 LUFS). FAIL si el volumen no afecta al render.

#### U2-09 · Orientación horizontal ↔ vertical `[S2]`
- **Pre:** `FX1` (16:9).
- **Pasos:** 1) Cambiar a Vertical. 2) Exportar. 3) Volver a Horizontal.
- **Esperado:** preview 9:16; export 720×1280 con recorte lateral centrado (sin deformar); el documento guarda `orientation: "v"`.
- **Evidencia:** `U2-09_preview_v.png`, `U2-09_export.ffprobe.txt` (720×1280), frame exportado.
- **PASS/FAIL:** PASS si no hay deformación (comparar círculo del fixture: relación de aspecto ±2 %) y el encuadre es centrado. FAIL si estira la imagen.

#### U2-10 · Transiciones `[S3]`
- **Pre:** 3 escenas.
- **Pasos:** 1) Fundido 0,3 s en la escena 2. 2) Fundido 0,5 s en la 3. 3) Exportar.
- **Esperado:** duración total = suma − 0,8 s (los fundidos solapan); la primera escena no ofrece transición (control deshabilitado con `Tip`).
- **Evidencia:** `U2-10_project.json`, `U2-10_export.ffprobe.txt`, 2 frames en la zona de mezcla.
- **PASS/FAIL:** PASS si la duración cumple la aritmética y el fundido es visible. FAIL si el total no cuadra (indicaría solape mal calculado).

#### U2-11 · Undo/redo de una edición de cada tipo `[S2]`
- **Pre:** proyecto con 2 escenas.
- **Pasos:** para cada tipo (reordenar, recortar, texto, volumen, split, eliminar): 1) editar; 2) `Ctrl+Z`; 3) `Ctrl+Shift+Z`.
- **Esperado:** el valor anterior se recupera exacto; redo reaplica; la pila se refleja en los botones H6.
- **Evidencia:** `U2-11_undo.json` (valor antes/después por tipo), captura del botón deshabilitado al final.
- **PASS/FAIL:** PASS si los 6 tipos recuperan el valor **exacto** (no aproximado). FAIL si algún tipo no entra en la pila.

#### U2-12 · U2 completo solo con teclado `[S2]`
- **Pre:** proyecto abierto.
- **Pasos:** recorrer U2-01…U2-11 sin ratón (Tab, flechas, `S`, `Ctrl+Z`, `Ctrl+S`).
- **Esperado:** foco visible en todo momento; nada depende solo de arrastre; orden de tabulación lógico.
- **Evidencia:** grabación `U2-12_teclado.mp4` + `U2-12_axe.json` (0 violaciones críticas).
- **PASS/FAIL:** PASS si se completa el recorrido. FAIL si algún control solo responde a puntero.

---

### U3 · Guardar y recuperar

#### U3-01 · Guardado determinista `[S1]`
- **Pre:** proyecto en Rev 3 con 3 escenas.
- **Pasos:** 1) `Ctrl+S`. 2) Guardar otra vez sin cambios. 3) Comparar documentos.
- **Esperado:** Rev 4 una sola vez; el segundo guardado no incrementa revisión (o la incrementa de forma declarada) y el documento es **idéntico** salvo `updated_at`.
- **Evidencia:** dos `GET /projects/<id>` en `U3-01_rev3.json` y `U3-01_rev4.json`, `diff` normalizado, fila de BD.
- **PASS/FAIL:** PASS si el diff solo contiene `updated_at`/`revision`. FAIL si cambia el orden de claves, se pierden campos o se duplica la revisión por un doble clic.

#### U3-02 · Autosave a 4 s y al perder foco `[S2]`
- **Pre:** proyecto abierto; red observable.
- **Pasos:** 1) Escribir en el caption y parar. 2) Cronometrar. 3) Escribir y hacer clic fuera del campo inmediatamente.
- **Esperado:** `PUT` ~4 s tras el último cambio; en blur se guarda de inmediato; indicador «Guardando…» → «Guardado hace 1 s»; nunca dos `PUT` en paralelo.
- **Evidencia:** `U3-02_peticiones.log` con timestamps, `U3-02_indicador.png`.
- **PASS/FAIL:** PASS si el intervalo está entre 3,5 y 5,0 s y no hay `PUT` concurrentes. FAIL si se pierde el último cambio al cerrar.

#### U3-03 · Cerrar y reabrir el proyecto `[S1]`
- **Pre:** proyecto con orden C,A,B; cortes; textos con acentos; volúmenes; orientación vertical; selección de contexto.
- **Pasos:** 1) Guardar. 2) Cerrar el pane. 3) Reabrir Hermes. 4) Abrir el mismo proyecto.
- **Esperado:** todo idéntico, incluida la escena seleccionada y el zoom; `media_id` resueltos; sin «Sin guardar».
- **Evidencia:** `U3-03_antes.json` vs `U3-03_despues.json` (diff vacío), `U3-03_ui.png` ×2.
- **PASS/FAIL:** PASS si el diff del documento es vacío y la UI coincide. FAIL si falta cualquier campo.

#### U3-04 · Reabrir tras reiniciar el gateway `[S2]`
- **Pre:** proyecto guardado; gateway vivo.
- **Pasos:** 1) Reiniciar el gateway (ventana aprobada). 2) Reabrir el pane.
- **Esperado:** proyecto cargado; sin pérdida; si había un job, su estado se reconcilia (no «running» fantasma).
- **Evidencia:** `U3-04_project.json`, `U3-04_jobs.sqlite3` (estados), `U3-04_gateway.log`.
- **PASS/FAIL:** PASS si el documento es idéntico y no quedan jobs en `running`. FAIL si hay job fantasma o proyecto vacío.

#### U3-05 · Conflicto de revisión (409) `[S1]`
- **Pre:** dos clientes (dos ventanas/perfiles) con Rev 7.
- **Pasos:** 1) Cliente A guarda → Rev 8. 2) Cliente B guarda. 3) En el diálogo, «Recargar». 4) Repetir con «Guardar como copia».
- **Esperado:** B recibe 409; copy «La revisión 8 se guardó en otro lugar. Tu copia es la 7.»; recargar muestra Rev 8; «Guardar como copia» crea un proyecto nuevo sin sobrescribir; nunca se pierde en silencio.
- **Evidencia:** `U3-05_409.png`, `U3-05_rev8.json`, `U3-05_copia.json`, respuestas HTTP con código.
- **PASS/FAIL:** PASS si el 409 ocurre y ninguna de las dos acciones sobrescribe. FAIL si el último gana en silencio (S1).

#### U3-06 · Proyecto corrupto o JSON inválido `[S1]`
- **Pre:** copia del proyecto con `scenes` truncado y con un tipo cambiado (`revision: "7"`).
- **Pasos:** 1) Abrir. 2) Observar. 3) Recuperar la revisión anterior.
- **Esperado:** estado D con mensaje claro; no se sobrescribe el archivo bueno; existe copia/revisión anterior recuperable.
- **Evidencia:** `U3-06_error.png`, `U3-06_backup/` (listado), `U3-06_project.json` original intacto.
- **PASS/FAIL:** PASS si el dato original sobrevive y hay camino de recuperación documentado. FAIL si el editor guarda encima y destruye la última versión buena.

#### U3-07 · Autosave durante edición + cierre forzado `[S2]`
- **Pre:** proyecto abierto; cambio sin guardar.
- **Pasos:** 1) Editar el texto. 2) Matar el proceso del renderer antes del autosave. 3) Reabrir.
- **Esperado:** se recupera la última revisión guardada; la UI avisa de que había cambios sin guardar (si aplica) y no inventa recuperación mágica.
- **Evidencia:** `U3-07_journal.txt`, `U3-07_project.json`, `U3-07_aviso.png`.
- **PASS/FAIL:** PASS si el estado es coherente y explícito. FAIL si el proyecto queda bloqueado o se pierde lo ya guardado.

---

### U4 · Preview y export consistentes

#### U4-01 · Preview reproducible dentro del pane `[S2] · depende de D-08`
- **Pre:** proyecto con 2 escenas.
- **Pasos:** 1) Observar el escenario. 2) Hacer scrub. 3) Inspeccionar la URL servida.
- **Esperado:** `<video>` reproduce; URL de proxy 540p; `Range` responde 206; sin poster falso; badge «Preview 540p».
- **Evidencia:** `U4-01_preview.png`, `U4-01_range.txt` (petición y respuesta 206 con `Content-Range`), `U4-01_proxy.ffprobe.txt` (≤960×540).
- **PASS/FAIL:** PASS si hay reproducción real y el proxy no es el original. FAIL si el pane carga el archivo original (coste y fidelidad) o no reproduce.

#### U4-02 · Preview y export usan el mismo documento versionado `[S1]`
- **Pre:** Rev 5.
- **Pasos:** 1) Solicitar export. 2) Sin esperar, cambiar el orden de escenas y guardar (Rev 6). 3) Al terminar, comparar.
- **Esperado:** el job usa el snapshot de Rev 5; el MP4 corresponde a Rev 5; la UI indica con qué revisión se exportó.
- **Evidencia:** `U4-02_job.json` (revision), `U4-02_export.ffprobe.txt`, `U4-02_rev6.json`, comparación de frames.
- **PASS/FAIL:** PASS si el MP4 coincide con Rev 5 y no con Rev 6. FAIL si el job lee el documento vivo (resultado no determinista).

#### U4-03 · Cola y progreso por etapas `[S2]`
- **Pre:** proyecto de 15 s.
- **Pasos:** 1) Exportar. 2) Observar las 4 etapas y el porcentaje.
- **Esperado:** Preparando → Renderizando → Mezclando audio → Escribiendo MP4; % monótono no decreciente; sin ETA inventada; estados de §7 F.
- **Evidencia:** `U4-03_etapas.mp4`, `U4-03_job_events.json` (timestamps de etapa), `U4-03_ui.png`.
- **PASS/FAIL:** PASS si las etapas son reales (coinciden con eventos del backend) y el % no retrocede. FAIL si el % es simulado o hay etapas decorativas.

#### U4-04 · Cancelar a mitad y no dejar restos `[S1]`
- **Pre:** export de 60 s 1080p (`FX6`) en curso, ≥20 % de progreso.
- **Pasos:** 1) «Cancelar exportación» → confirmar. 2) Cronometrar hasta estado terminal. 3) Revisar procesos y staging a +1, +5 y +10 s.
- **Esperado:** estado `cancelled`; árbol FFmpeg muerto; `out/` sin MP4 parcial; staging borrado; UI «Cancelando…» hasta el terminal real.
- **Evidencia:** `U4-04_cancel.json` (latencia), `U4-04_tasklist_*.txt` (3 momentos), `U4-04_out_ls.txt`, `U4-04_staging_ls.txt`.
- **PASS/FAIL:** PASS si latencia ≤10 s (techo del plan), 0 huérfanos en los 3 muestreos y 0 archivos parciales promovidos. FAIL si queda un proceso, un MP4 truncado en `out/` o staging (S1).

#### U4-05 · Reintentar tras cancelar o fallar `[S2]`
- **Pre:** job cancelado; y job fallido (p. ej. medio faltante).
- **Pasos:** 1) «Reintentar». 2) Comparar nombres y contenidos.
- **Esperado:** job nuevo con id nuevo; un solo MP4 final; sin duplicados ni `out (1).mp4`; el fallo no reutiliza staging sucio.
- **Evidencia:** `U4-05_jobs.json`, `U4-05_out_ls.txt`, `U4-05_hashes.txt`.
- **PASS/FAIL:** PASS si hay exactamente un archivo por export exitoso. FAIL si hay dos o el nombre colisiona.

#### U4-06 · Doble clic / job duplicado `[S1]`
- **Pre:** proyecto listo.
- **Pasos:** 1) Pulsar «Exportar» 5 veces rápido. 2) Repetir con dos ventanas a la vez.
- **Esperado:** un solo job (misma clave de idempotencia); la UI muestra «1 en cola» como máximo; un solo MP4.
- **Evidencia:** `U4-06_jobs.sqlite3` (conteo por `dedupe_key`), `U4-06_out_ls.txt`, captura de la cola.
- **PASS/FAIL:** PASS si `count(distinct job) = 1`. FAIL si se encolan 2+ renders del mismo documento (S1: coste y duplicados).

#### U4-07 · Salida correcta y verificable `[S1]`
- **Pre:** export de timeline conocida: 2 escenas de 4,0 s, fundido 0,3, 720p30, con subtítulos.
- **Pasos:** 1) Exportar. 2) `ffprobe` completo. 3) Abrir en Edge y en Windows Media Player. 4) Comprobar el frame final.
- **Esperado:** H.264, 1280×720, 30/1, yuv420p, AAC, duración 7,7 s ±1 frame, `moov` presente, reproducible en ambos, último frame no negro.
- **Evidencia:** `U4-07_export.ffprobe.json`, `U4-07_edge.png`, `U4-07_wmp.png`, `U4-07_ultimo_frame.png`, `U4-07_sha256.txt`.
- **PASS/FAIL:** PASS si **todas** las propiedades coinciden y ambos reproductores abren sin error. FAIL si hay que descargar códecs, el audio falta o la duración no cuadra.

#### U4-08 · El resultado vuelve al chat/proyecto, sin publicación `[S1] · depende de D-12`
- **Pre:** sesión de origen identificada.
- **Pasos:** 1) Exportar. 2) «Volver al chat». 3) Verificar qué aparece en la sesión.
- **Esperado:** el MP4 se referencia/adjunta en la sesión y el proyecto de origen; ningún envío a servicio externo; ninguna URL pública.
- **Evidencia:** `U4-08_chat.png`, `U4-08_netstat_durante.txt`, `U4-08_egress.txt` (ver A-03).
- **PASS/FAIL:** PASS si el artefacto queda accesible desde la sesión y no hay egress. FAIL si se publica, se sube o se pierde el vínculo con el proyecto.

#### U4-09 · El gateway sigue respondiendo durante el export `[S2]`
- **Pre:** export de 60 s; sonda al gateway.
- **Pasos:** ejecutar T02 en paralelo al export.
- **Esperado:** p95 dentro del umbral de T02; sin 5xx; UI del chat sin bloqueo.
- **Evidencia:** `U4-09_p95.json`, `U4-09_gateway_errors.txt`.
- **PASS/FAIL:** PASS si se cumple T02 durante todo el render. FAIL si el chat se congela o hay timeouts.

#### U4-10 · Export bloqueado con medio faltante o documento inválido `[S2]`
- **Pre:** estado H; y documento con `out <= in`.
- **Pasos:** 1) Intentar exportar. 2) Forzar la petición por API.
- **Esperado:** UI deshabilitada con motivo; el backend rechaza con 4xx y no crea job.
- **Evidencia:** `U4-10_ui.png`, `U4-10_http.txt` (código y cuerpo), `U4-10_jobs_count.txt`.
- **PASS/FAIL:** PASS si no se crea ningún job. FAIL si el backend acepta y falla a mitad (desperdicio y estado sucio).

#### U4-11 · Subtítulos incluidos/excluidos `[S2]`
- **Pre:** escenas con caption; switch «Incluir subtítulos».
- **Pasos:** 1) Exportar con subtítulos. 2) Exportar sin. 3) Comparar.
- **Esperado:** con → hay pista de subtítulos o texto quemado según se decida (D-17); sin → no aparece; el texto no se duplica.
- **Evidencia:** `U4-11_con.ffprobe.txt`, `U4-11_sin.ffprobe.txt`, frames de ambos.
- **PASS/FAIL:** PASS si la diferencia es la esperada y el texto es literal. FAIL si el switch no tiene efecto o rompe el render.

---

## 3. Los 10 tipos de prueba (umbrales y datos)

Cada tipo tiene casos concretos; los IDs T se referencian desde U.

### T01 · Sincronía y seek
**Objetivo (plan l.398):** A/V ≤1 frame con referencia; cortes y captions correctos con VFR y proxy CFR.
**Umbral [F]:** ≤1 frame (33,3 ms) = PASS; entre 1 y 2 frames = no aprueba, investigar; >2 frames persistente = FAIL del candidato.
**Datos:** `FX1` (CFR), `FX2` (VFR real: 154 frames, `avg_frame_rate 4620/179`), `FX3` (CFR + clics en 0/2/4 s), `FX6` (1080p).
**Procedimiento (verificado, Anexo A.1):**
1. Render de prueba con recorte conocido (`trim=start=0.5`).
2. Índice de transición de color por frame con `signalstats` + `metadata=print` (YAVG).
3. Onset de audio por `silencedetect` (ignorar el `silence_end` final que coincide con la duración).
4. Δ = |t_video − t_audio|; comparar con 1/30 s.
5. Para VFR: comparar conjuntos de PTS, no conteos: frames de salida = frames de entrada con `pts ∈ [in,out)`, tolerancia ±1 frame.
**Pass/Fail:** PASS si Δ ≤33,3 ms en cada frontera y el seek cae a ±1 frame del objetivo. FAIL si el desfase crece con la duración (deriva) o si el seek solo llega a keyframes.
**Parada:** si el motor no puede con VFR tras dos intentos documentados, se limita el soporte a CFR con proxy y se declara (no se maquilla).

### T02 · Recursos + gateway
**Objetivo (plan l.399):** sin OOM ni paginación sostenida; p95 ≤20 % sobre baseline comparable; RSS del árbol registrado.
**Umbral [P]:** p95_durante ≤ `max(1,2 × p95_antes, p95_antes + 5 ms)`; n ≥100 muestras por fase; 3 corridas; se reporta la mediana de los p95. RSS pico del árbol ≤2,0 GB para 720p30 con 1 job; RAM libre ≥4 GB; `PagesPersec` medio ≤50.
**Justificación del 2 GB:** medido en spike 435,8 MB (árbol) y 498,3 MiB (`ffmpeg maxrss`) → margen ×4. **No es un número universal**; se recalibra con material real y el cambio se documenta.
**Datos:** `FX1` 6 s; `FX6` 60 s 1080p; sonda al gateway cada 100 ms.
**Procedimiento:** `probe_gateway`/cliente HTTP propio (el del spike solo imprime el rendezvous, no mide latencia: usar el bucle de `test_demo.py`), muestreo de RSS con `Get-Process -Id <pid> | % WorkingSet64` cada 250 ms y del árbol con `tasklist`.
**Pass/Fail:** PASS si se cumplen los 4 umbrales en 2 de 3 corridas y ninguna da OOM. FAIL si hay paging sostenido, p95 fuera de umbral en 2 de 3, o el árbol supera 2 GB.
**Parada:** si falla a 720p, repetir a 540p/proxy; si sigue degradando, se descarta la automatización local o se cambia el alcance (plan l.399).

### T03 · Cancelación
**Objetivo (plan l.400):** árbol propio liberado, estado terminal correcto, objetivo inicial ≤10 s.
**Umbral [F]:** ≤10 s desde la petición hasta estado terminal. **[P]** objetivo real ≤2 s a 720p.
**Datos:** `FX6` 1080p 60 s; cancelar a ~10 %, ~50 %, ~90 %.
**Procedimiento:** `POST /jobs/{id}/cancel`; medir con reloj monótono; `tasklist /FI "IMAGENAME eq ffmpeg.exe" /FO CSV` a +1/+5/+10 s; comprobar que `out/` no contiene el parcial y que staging desaparece en ≤60 s [P].
**Pass/Fail:** PASS si latencia ≤10 s, estado `cancelled`, 0 huérfanos en los 3 muestreos y 0 parciales promovidos. FAIL si hay huérfano, borrado ajeno o un MP4 truncado en `out/`.
**Parada:** nunca `taskkill` global de Chrome/Node; si la cancelación requiere matar el árbol entero del host, el diseño es FAIL.

### T04 · Pause y recovery
**Objetivo (plan l.401):** pausa diferida visible con checkpoint íntegro; reinicio/reintento sin perder proyecto ni duplicar salida.
**Decisión vigente:** la UI **no expone pausa** (`ui-spec` §5.8, l.260; §12.7). Por tanto:
- **T04-a (N/A):** «Pausar» no debe existir. PASS si no hay control ni estado `paused`; FAIL si aparece un botón deshabilitado permanente o un estado falso.
- **T04-b (S1):** matar el servicio con job en curso → al relanzar, reaper marca `interrupted`, mata el FFmpeg huérfano y no promueve salida.
- **T04-c (S1):** matar el servicio con job en `queued` → al relanzar, el job no queda `queued` para siempre.
- **T04-d (S2):** reiniciar Hermes durante el render → el proyecto sigue íntegro y la cola se reconcilia.
**Evidencia:** `jobs.sqlite3` (estado + PID), `service.reaper.log`, `tasklist` antes/después, `U4-04_*`.
**Pass/Fail:** PASS si ningún estado queda `running` fantasma y no hay huérfanos. FAIL si el job sigue `running`, si quedan procesos o si el proyecto pierde datos.

### T05 · UX y guardado
**Objetivo (plan l.402):** tareas críticas y reabrir sin pérdida; 80 % ponderado como pista.
**Umbral [P]:** propuesta de pesos — U1 20, U2 30, U3 25, U4 25. **Regla que prevalece:** cualquier S1 = FAIL global; cualquier escenario por debajo del 70 % = FAIL de ese escenario, con independencia del total.
**Datos:** checklist de las 12 tareas críticas (U1-01…U4-11, una por escenario como mínimo).
**Procedimiento:** persona no técnica ejecuta; se cronometra y se anota dónde duda; se registran clics y errores.
**Pass/Fail:** PASS si ≥80 % ponderado **y** ninguna tarea crítica falla. FAIL si una tarea crítica no se completa aunque el porcentaje sea alto.

### T06 · Offline y aislamiento
**Objetivo (plan l.403):** export sin egress no permitido ni acceso a secretos o fuera de la raíz.
**Umbral [F]:** 0 conexiones salientes durante el render (excepto loopback del propio servicio y del gateway); 0 lecturas fuera de las raíces concedidas.
**Datos:** regla de firewall/bloqueo de red (requiere permiso, D-10); canario de secretos (A-02).
**Procedimiento:** ejecutar export completo con red bloqueada; `netstat -ano` muestreado; intentar importar rutas fuera de la raíz y leer el canario.
**Pass/Fail:** PASS si el render termina igual y no hay conexiones ni lecturas prohibidas. FAIL si el motor exige red, descarga algo o toca secretos (se declara «no apto para offline estricto», plan l.403).
**Parada:** si el bloqueo de red no se puede aplicar sin admin, el caso queda BLOCKED y **no** se sustituye por «confío en que no llama».

### T07 · Compatibilidad
**Objetivo (plan l.404):** 3 grabaciones habituales; export reproducible en dos reproductores y parámetros correctos.
**Datos:** 3 grabaciones reales autorizadas (pendiente, D-13) + matriz sintética: H.264/MP4, HEVC/MOV, audio ausente, VFR de móvil, rotación de metadatos, 4:2:0 y 4:2:2.
**Umbral [F]:** 100 % de los 3 materiales habituales importan y exportan; 2 reproductores abren sin error (Edge + Windows Media Player, únicos disponibles).
**Procedimiento:** importar, reproducir, exportar, `ffprobe`, abrir en ambos.
**Pass/Fail:** PASS si los 3 materiales se completan y los parámetros son correctos. FAIL si un formato habitual no se resuelve → limitar soporte declarado o descartar para MVP.
**Nota:** sin material real el caso es **BLOCKED**; los sintéticos no lo sustituyen (el plan pide «grabaciones habituales»).

### T08 · Privacidad y derechos
**Objetivo (plan l.405):** cero secretos o datos de terceros en capturas, logs y entregables; activos y consentimiento identificados.
**Umbral [F]:** 0 coincidencias de los canarios en cualquier artefacto; 0 rutas de usuario en el MP4; logs con rutas redactadas.
**Datos:** canarios sintéticos (`CANARY-7f3a…`) en un `.env` de prueba, en `config.yaml` de prueba y en el nombre de un archivo; consentimiento escrito del material.
**Procedimiento:** buscar los canarios en `out/`, `logs/`, capturas, `run.json`, `auditoria/evidencia/`; `strings` sobre el MP4; revisar `format_tags`.
**Pass/Fail:** PASS si 0 coincidencias y el consentimiento está identificado. FAIL si aparece cualquier canario, dato de tercero o derecho desconocido → detener la entrega y corregir (plan l.405).
**Hallazgo ya medido:** el MP4 del spike **no** filtra la ruta del usuario (0 coincidencias de `EgtYP` en 2,77 MB), pero `logs/j16f22b2a29.ffmpeg.log` contiene la ruta **4 veces**. Los logs son artefacto de entrega: deben redactarse.

### T09 · Integración
**Objetivo (plan l.406):** identidad namespaced, exclusiones y ciclo Panteón reales; cola sobrevive desconexión de Hermes.
**Umbral [F]:** nombre de plugin único; permisos mínimos declarados; la cola sigue viva y termina si Hermes se desconecta; ningún proyecto de otra sesión visible.
**Datos:** dos sesiones y dos perfiles; reinicio del gateway; desactivación del plugin en caliente (ventana aprobada, D-14).
**Procedimiento:** crear proyecto en sesión A; abrir sesión B; reiniciar Hermes con job en curso; desactivar/activar el plugin.
**Pass/Fail:** PASS si B no ve A, el job sobrevive y la reactivación no duplica datos. FAIL si hay fuga entre sesiones o la cola muere con Hermes.
**Nota:** «suite aislada o solo archivos instalados» **no** cumple el gate runtime (plan l.406).

### T10 · Salida y rollback
**Objetivo (plan l.407):** duración/fps/resolución/audio verificados; staging atómico; restauración ensayada.
**Umbral [F]:** duración ±1 frame; fps exacto `30/1`; 1280×720 (o 720×1280 en vertical); audio AAC presente y audible; `moov` presente; `ffprobe` sin errores; originales con hash intacto.
**Datos:** `FX1` + `FX3`; export con y sin subtítulos.
**Procedimiento:** `ffprobe -count_frames`; decodificar completo (`ffmpeg -v error -i out.mp4 -f null -`) para detectar corrupción; comparar `sha256` de los originales antes/después; restaurar versión anterior del plugin (rollback) y comprobar que los proyectos siguen abriendo.
**Pass/Fail:** PASS si todo cuadra y el rollback abre los proyectos. FAIL si el MP4 es parcial, el proyecto no abre tras rollback o se tocó un original.
**Aritmética obligatoria:** duración esperada = Σ(escenas) − Σ(fundidos) − recortes. Se calcula en el test, no se copia del reporte.

---

## 4. Pruebas adversariales

> Estas pruebas **no** son opcionales ni «nice to have»: el plan las exige (l.403, l.415) y son S1. Se ejecutan sobre el artefacto construido, con datos sintéticos y canarios propios, sin tocar datos reales.

### A-01 · Path traversal y junction `[S1]`
**Ataque:** `../../secret.txt`, `....//....//`, `%2e%2e%2f`, UNC `\\host\share`, `\\?\C:\`, ADS `out.mp4:secreto`, y un **junction** creado dentro de la carpeta de medios que apunta a `C:/Windows`.
**Pasos:** enviar cada ruta en `{folder_id, path}` de `/media`, en el nombre de archivo de `upload`, y en la ruta de preview. Crear el junction con `cmd /c mklink /J`.
**Esperado:** 400/403; ningún byte del destino; el listado no lo muestra; log sin contenido del archivo.
**Evidencia:** `A01_http.txt` (códigos), `A01_junction.png`, `A01_servicio.log`, `A01_hashes.txt` (no se copió nada).
**PASS/FAIL:** PASS si todas las variantes se rechazan. FAIL si una sola devuelve contenido o crea archivo fuera de la raíz.
**Nota de diseño:** `os.path.basename` (usado por el servidor de archivos del spike) bloquea `../` simple, pero **no** valida un junction que ya está dentro de la raíz. La comprobación correcta es `realpath` + prefijo permitido, y rechazo de reparse points.

### A-02 · Lectura de secretos `[S1]`
**Ataque:** canario en `~/.hermes/config.yaml` de prueba, `.env` del proyecto, y un archivo llamado `token-abc123.txt`.
**Pasos:** intentar importarlos por carpeta concedida, por drop y por ruta; exportar después y buscar el canario en el MP4, logs y capturas.
**Esperado:** rechazo; 0 apariciones del canario en cualquier artefacto.
**Evidencia:** `A02_canario_busqueda.txt` (grep con 0 resultados), `A02_carpeta_protegida.png`.
**PASS/FAIL:** PASS si 0 apariciones. FAIL si el canario aparece en log, documento o vídeo.

### A-03 · Egress no permitido `[S1]`
**Ataque/condición:** bloqueo de red saliente (regla de firewall o adaptador sin ruta) y monitorización.
**Pasos:** export completo offline; `netstat -ano` cada 500 ms; revisar logs de intentos DNS/HTTP; comprobar telemetría.
**Esperado:** render idéntico, 0 conexiones salientes, 0 intentos DNS, 0 telemetría.
**Evidencia:** `A03_netstat.csv`, `A03_export.ffprobe.txt`, `A03_egress.txt`.
**PASS/FAIL:** PASS si no hay egress y el export funciona. FAIL si el motor descarga algo o «llama a casa».
**Bloqueo:** aplicar la regla requiere permisos (D-10); sin ella el caso es BLOCKED, no PASS.

### A-04 · Inyección de argumentos/filtros FFmpeg `[S1]`
**Ataque:** caption con `:`, `%`, `'`, `"`, `,`, `[`, `]`, `;`, salto de línea, `%{pts}`, `\`; nombre de archivo que empieza por `-` (`-i /etc/passwd`) y con `\n`; parámetros con tipo erróneo (`width: "1280:1280"`, `crf: "23 -f null"`, `preset: "veryfast -y"`, negativo, 1e9).
**Esperado:** o se rechaza con validación, o se renderiza el texto **literal**; jamás se añaden argumentos al argv ni se ejecuta un filtro inyectado; el argv registrado coincide con la lista blanca.
**Evidencia:** `A04_casos.json` (entrada → resultado), `A04_cmd.txt` (argv real), `A04_render.txt`, frames.
**PASS/FAIL:** PASS si el texto se trata como dato en todos los casos. FAIL si un `:` rompe el job, si el `%` aborta el render o si aparece una opción no prevista.
**Medido hoy (no es teoría):**
- `text='Hola: it's 50% done'` → `No option name near ' its 50% done…'` y `Error parsing a filter description` → **el job falla**.
- `textfile=` con `Ahorra 50%: it's "ñandú" — día 3/4` → `Stray % near ': it's…'` → **falla igual**.
- Con `expansion=none` → **exit 0** y texto correcto.
- `-preset "veryfast -f null -y"` → `invalid preset` (no hay inyección de argv porque se usa lista, pero sí fallo no validado).
**Consecuencia para el MVP:** el compilador de argumentos debe usar `textfile=` + `expansion=none` (o escapar `%` como `%%` y `:` como `\:`), validar tipos y **nunca** construir el filtro por concatenación de texto de usuario.

### A-05 · MP4 parcial `[S1]`
**Ataque/condición:** matar FFmpeg a mitad (`taskkill /F`), y también matar el servicio; luego relanzar y reexportar.
**Esperado:** el parcial vive solo en staging, `out/` intacto; `ffprobe` del parcial falla con `moov atom not found`; no se promueve; al reexportar no hay duplicados.
**Evidencia:** `A05_staging_ls.txt`, `A05_ffprobe_parcial.txt`, `A05_out_ls.txt`, `A05_jobs.json`.
**PASS/FAIL:** PASS si `out/` no contiene el parcial en ningún momento. FAIL si un MP4 truncado llega a `out/` o el reproductor lo abre a medias sin aviso.
**Medido hoy:** matar un encode a los 2 s deja 786 480 bytes sin `moov`; `ffprobe` → `moov atom not found`. Es exactamente el artefacto que **no** debe promoverse.

### A-06 · Disco lleno `[S1]`
**Condición:** volumen de prueba de 2 GB (VHDX) o inyección de `ENOSPC` en el worker; **no** llenar C:.
**Pasos:** exportar 1080p de 60 s hasta agotar; observar error, limpieza y estado.
**Esperado:** job `failed` con mensaje legible; staging borrado; proyecto intacto; salidas anteriores intactas; el editor sigue usable.
**Evidencia:** `A06_error.png`, `A06_jobs.json`, `A06_disk.txt`, `A06_out_hashes.txt`.
**PASS/FAIL:** PASS si falla limpio y no corrompe nada. FAIL si deja staging huérfano, corrompe el proyecto o el error es un volcado.
**Bloqueo:** el método (VHDX o inyección) requiere decisión y permisos (D-09).

### A-07 · Job duplicado e idempotencia `[S1]`
**Ataque:** 5 `POST /jobs` simultáneos con la misma clave; reintento tras éxito; misma clave desde dos clientes; clave vacía y clave con 10 KB.
**Esperado:** un job activo por clave; tras estado terminal, la política es explícita (D-06): o se reutiliza el output si el documento no cambió, o se crea uno nuevo con nombre distinto; nunca dos escrituras al mismo `out/`.
**Evidencia:** `A07_jobs.sqlite3` (`group by dedupe_key`), `A07_out_ls.txt`, `A07_http.txt`.
**PASS/FAIL:** PASS si no hay dos jobs que escriban el mismo destino. FAIL si se pisan archivos o se renderiza dos veces el mismo documento.
**Medido en spike:** dos `POST` con `dedupe_key='kanban-42'` → mismo id (`jf2aefa6cc4`). Limitación: el dedupe solo cubre `queued|running`; tras `succeeded`, la misma clave crea otro job (verificado en el `SELECT` del servicio).

### A-08 · Kill-tree dirigido `[S1]`
**Ataque/condición:** dos renders en cola; cancelar uno; comprobar que el otro y el propio servicio siguen vivos. Repetir con un `ffmpeg` lanzado por el usuario fuera del servicio.
**Esperado:** se mata solo el árbol del job; el otro job continúa; ningún proceso ajeno muere; nunca `taskkill /IM` global.
**Evidencia:** `A08_tasklist_antes_despues.txt`, `A08_jobs.json`, `A08_arbol.txt` (`wmic process` con ParentProcessId).
**PASS/FAIL:** PASS si el árbol ajeno sobrevive. FAIL si muere un proceso no relacionado o si el servicio se mata a sí mismo.

### A-09 · Proceso huérfano y reutilización de PID `[S1]`
**Ataque/condición:** matar el servicio con job en curso; dejar pasar 10 s; relanzar; además, simular un PID reciclado (job antiguo cuyo PID ahora pertenece a otro proceso).
**Esperado:** el reaper mata el FFmpeg huérfano, marca `interrupted`, y **no** mata un PID reciclado ajeno (debe verificar identidad/tiempo de creación).
**Evidencia:** `A09_reaper.log`, `A09_jobs.json`, `A09_tasklist.txt`, `A09_pid_reuse.txt`.
**PASS/FAIL:** PASS si no quedan huérfanos y no se mata un PID ajeno. FAIL si queda un FFmpeg vivo o si el reaper mata el proceso equivocado.
**Riesgo ya visible en el código del spike:** `kill_tree(pid)` confía en el PID guardado en la BD sin verificar identidad. No se ha observado daño, pero el control no existe.

### A-10 · Abuso de subida y nombres `[S2]`
**Ataque:** archivo de 0 bytes; nombre con `../`; nombre con NUL; nombre de 300 caracteres; Unicode RTL (`factura\u202Egnp.exe`); extensión doble (`clip.mp4.exe`); MIME declarado falso (`video/mp4` con bytes PNG); zip renombrado.
**Esperado:** rechazo claro o normalización segura; el archivo se guarda con nombre generado, no con el del usuario; el tipo se detecta por contenido, no por MIME.
**Evidencia:** `A10_casos.json`, `A10_media_dir.txt`, `A10_ffprobe.txt`.
**PASS/FAIL:** PASS si no se escribe fuera del directorio de medios y el tipo se valida por contenido. FAIL si un nombre controla la ruta o el MIME decide el parser.

### A-11 · Carreras de guardado y export `[S1]`
**Ataque:** dos `PUT` con la misma revisión; `PUT` mientras se exporta; cancelar mientras el job termina; reabrir el pane durante un autosave; dos clics en «Guardar».
**Esperado:** un solo ganador por revisión (409 al otro); el job nunca lee un documento a medio escribir; el estado terminal es único; no hay doble guardado.
**Evidencia:** `A11_http.txt` (códigos y orden), `A11_project_revs.json`, `A11_jobs.json`.
**PASS/FAIL:** PASS si el invariante «una revisión, un escritor» se mantiene. FAIL si se pierde una edición o el mismo job termina dos veces.

### A-12 · Acceso al servicio desde origen no confiable `[S1]`
**Ataque:** el servicio escucha en loopback **sin autenticación**. Probar: `fetch` desde una página de otro origen (DNS rebinding), `POST /jobs` desde otro proceso local, lectura de `/files/<id>` desde una pestaña cualquiera, y `Origin: null` (que es el caso del renderer `file://`).
**Esperado:** allowlist de origen + token efímero por sesión; rechazo 403 a orígenes no permitidos; el token no aparece en logs.
**Evidencia:** `A12_http.txt`, `A12_pagina.html` (prueba), `A12_servicio.log`, `A12_headers.txt`.
**PASS/FAIL:** PASS si un origen ajeno no puede encolar, cancelar ni leer archivos. FAIL si cualquier página local puede lanzar renders o leer el `out/`.
**Contexto medido:** el spike acepta `POST /probe` desde el renderer con `origin: file://`. Eso es correcto para el pane, pero **no** distingue al pane de cualquier otra página local: la allowlist debe incluir exactamente `file://` del app y rechazar el resto.

---

## 5. Qué es evidencia válida y qué no

### 5.1 Válida

| Tipo | Formato mínimo | Ejemplo |
|---|---|---|
| **E1 · Comando + salida** | Comando exacto, salida completa, `exit_code`, fecha | `ffprobe … -of json` → `U4-07_export.ffprobe.json` |
| **E2 · Archivo:línea** | Ruta y línea del código/config que causa el comportamiento | `service.py:657` (409 en job terminado) |
| **E3 · Captura** | PNG con barra de título o timecode visible; sin recortes que oculten contexto; hash en el manifiesto | `U2-07_preview.png` |
| **E4 · Log** | Fragmento con timestamp y sin secretos | `U4-04_tasklist_+5s.txt` |
| **E5 · Estado persistido** | Consulta y resultado (SQLite/JSON) | `select state,count(*) from jobs group by state` |
| **E6 · Hash** | `sha256` de entrada y salida | originales intactos tras el render |

Cada evidencia se nombra `<CASE-ID>_<artefacto>.<ext>`, se guarda en `auditoria/evidencia/<run_id>/` y se lista en `manifest.json` con su `sha256`. Una captura sin manifiesto no es evidencia.

### 5.2 No válida (se rechaza aunque acompañe al reporte)

- **Self-report**: «funciona», «probado», «el agente dice que pasa».
- **`exit_code 0` solo**, sin la salida que demuestre el efecto.
- **Captura del mockup** (`docs/mockup.html`) o de datos inyectados por props: sirve para diseño (V1), **no** para aceptación.
- **Vídeo del camino feliz** sin estado terminal, sin `ffprobe` y sin hashes.
- **Captura recortada** que oculta la barra de título, el timecode o el mensaje de error.
- **Logs sin comando** o con la salida resumida por el constructor.
- **«Lo probé antes»** o resultados de otra máquina/versión.
- **Prueba que pasa con la función desactivada** (sin control negativo): si el caso no falla cuando se rompe a propósito el control, la prueba no mide nada.
- **Números sin unidad, sin `n` y sin ventana temporal** (el caso del p95 del spike: n=32, una corrida, sin baseline comparable).

### 5.3 Control negativo obligatorio

Cada control crítico (cancelación, dedupe, atomicidad, aislamiento, validación de entrada) debe demostrarse **una vez** con el control roto: se desactiva la comprobación y el test **debe** fallar. Si sigue pasando, el test es decorativo y se reescribe. Esta es la única forma de saber que la suite protege algo.

---

## 6. Smoke mínimo por gate

### 6.1 Gate 1 · motor apto (antes de construir UI encima) — ~90 min

Objetivo: confirmar con datos que el motor elegido en ADR-001 sostiene U1–U4, sin UI.

| # | Caso | Criterio | Tiempo |
|---|---|---|---|
| 1 | Preparar fixtures FX1–FX7 y hashes | `sha256sum -c` OK | 10 min |
| 2 | T01-CFR (recorte 0,5 s) | Δ A/V ≤33,3 ms; frames exactos | 15 min |
| 3 | T01-VFR (`FX2`) | PTS containment ±1 frame; sin deriva | 15 min |
| 4 | T02 recursos + p95 | 100 muestras × 3 fases; umbral [P] | 20 min |
| 5 | T03 cancelación a 50 % | ≤10 s; 0 huérfanos a +10 s | 10 min |
| 6 | T10 salida + atomicidad | `ffprobe` OK; `out/` sin parciales | 10 min |
| 7 | A-04 caption con `%`/`:` | render correcto o rechazo validado | 5 min |
| 8 | A-05 MP4 parcial | parcial nunca en `out/` | 5 min |
| 9 | A-09 huérfano + reaper | 0 huérfanos; `interrupted` | 5 min |

**PASS del gate 1:** los 9 en PASS. Un FAIL en 2, 3, 5 o 8 detiene la construcción de UI: se corrige el motor o se reabre ADR-001 con la carencia demostrada.

### 6.2 Gate 2 · MVP aceptable — ~4 h

Objetivo: U1–U4 completos por una persona no técnica, más los controles que no pueden quedar para después.

| Bloque | Casos | Tiempo |
|---|---|---|
| Preparación (fixtures, `run.json`, línea base) | — | 20 min |
| U1 | U1-01…U1-07, U1-09, U1-10 (U1-08 BLOCKED si no hay D-07) | 35 min |
| U2 | U2-01…U2-12 | 45 min |
| U3 | U3-01…U3-07 | 40 min |
| U4 | U4-01…U4-11 | 45 min |
| T03 + T04 | cancelación 3 puntos + crash/reaper | 20 min |
| T06 + A-02 + A-03 | aislamiento, canarios, egress | 20 min |
| A-01 + A-07 + A-11 | traversal, dedupe, carreras | 20 min |
| T10 | salida + rollback | 15 min |
| Empaquetar evidencia | manifiesto + hashes | 20 min |

**PASS del gate 2:** U1–U4 sin FAIL de escenario; 0 S1 abiertos; BLOCKED solo en casos con decisión pendiente **declarada** (U1-08, T07, A-03, A-06 si no se resuelven). El gate **no** se cierra con un S1 abierto ni con un BLOCKED en un control crítico.

---

## 7. Auditoría breve de ADR-001

Contraste de cada afirmación con lo medido. No reabre la decisión de motor: verifica si sus frases se sostienen.

| # | Afirmación del ADR | Evidencia disponible | Veredicto |
|---|---|---|---|
| C-1 | FFmpeg n9.0.1 con `libx264`, `aac`, `trim`, `concat`, `xfade`, `scale`, `crop`, `overlay`, `drawtext`, `subtitles`, `afade`, `acrossfade`, `fade` | F0 §1.3 y re-verificación de hoy (`ffmpeg -version`, `-encoders`, `-filters`): **las 13 capacidades listadas están presentes** | **SOSTENIDA** |
| C-2 | Render real 1280×720 30 fps 15 s, pared 1,359 s, CPU 8,8 s, RSS pico 435,8 MB | `spike/logs/test_demo.json`: `wall_s 1.359`, `cpu_s 8.828`, `rss_peak_kb 435800`, `ffmpeg_maxrss_kb 498328`; `ffprobe` del MP4 confirma 1280×720, 30/1, 15,0 s | **SOSTENIDA CON MATIZ**: el fixture es `testsrc2`/`smptebars`, preset `veryfast`; la cifra **no** representa material real y el propio ADR lo dice. |
| C-3 | Cancelación en 0,52 s sin huérfanos | `test_cancel.json`: `cancel_latency_s 0.52`, `final_state cancelled`, `ffmpeg_after_cancel []` | **PARCIAL**: una sola medición; el chequeo de huérfanos es inmediato (no a +10 s); `taskkill` devolvió cadena vacía y `kill_tree` **no registra el código de salida** de `taskkill`; el progreso siguió de 8,17 % a 11,4 % tras la petición (normal por buffering, pero conviene medir latencia desde el estado terminal, no desde la respuesta HTTP). |
| C-4 | Crash con job en curso → reaper mata el huérfano y marca `interrupted` | `jobs.sqlite3`: `interrupted 1`; `service.reaper.log` con el kill; `test_cancel.json` con `crash_job_id` | **SOSTENIDA CON MATIZ**: funciona en el caso probado; el reaper confía en el PID almacenado sin verificar identidad (riesgo de PID reciclado, A-09). |
| C-5 | Gateway no se bloquea; p95 +1,9 ms absolutos | `test_demo.json`: p95 4,60 → 6,49 ms (n=32), después 1,94 ms | **NO SOSTENIDA AL UMBRAL DEL PLAN**: +41 % relativo supera el 20 % del plan (l.399); una corrida, n=32 y la fase «después» más baja que «antes» indican ruido/deriva. La frase «el gateway no se bloquea» va más allá de la evidencia; el propio ADR lo marca «pendiente de baseline más robusto». Medir con T02 antes de Gate 2. |
| C-6 | Licencias: FFmpeg GPLv3 verde como proceso externo; HyperFrames amarillo; Remotion rojo para distribuir; FilmCraft verde pero GUI | `docs/licencias.md` l.14-21, l.25-80 (texto de licencia leído; patentes H.264 documentadas l.74-78) | **SOSTENIDA**, con dos matices que el ADR omite: (a) el build es **GPLv3-or-later estático con libx264 dentro** (licencias.md l.40), así que la única vía verde es invocación CLI sin enlazar `libav*`; (b) **patentes H.264/MPEG** son un riesgo independiente de la GPL y no aparecen en el ADR. |
| C-7 | Cero instalaciones; sin Node ni Chrome en el camino de render | Chrome ausente (F0 §1.2); `which -a ffmpeg` resuelve a `hermes/tools/...`; el render no invoca Node | **SOSTENIDA**, con matiz: `service.py` llama `ffmpeg` **por PATH**, no por ruta fijada. Hoy resuelve al binario de Hermes (única entrada en PATH), pero el ADR afirma que «vive en la instalación de Hermes» como si estuviera garantizado. Debe fijarse ruta + `sha256` (F0 ya pedía release fijada). |
| C-8 | Worker en proceso separado, cola SQLite, staging atómico | `service.py`: proceso propio, tabla `jobs`, `os.replace` al promover | **SOSTENIDA CON MATIZ**: separado **del gateway**, pero dentro del servicio es un **hilo**, no un proceso; `os.replace` es atómico solo en el mismo volumen (staging y `out/` deben compartirlo; hoy comparten `spike/out`). |
| C-9 | Preview y export parten del mismo JSON versionado | No existe documento de proyecto en el spike | **NO MEDIDA**: es un compromiso de diseño, no un hecho. Se verifica en U4-02. |
| C-10 | 1080p no garantizado hasta medirlo | No hay medición 1080p de material real | **CORRECTA Y HONESTA** (declara el límite). |

**Veredicto sobre ADR-001: SOSTENIDA CON OBSERVACIONES.** La decisión de motor no se cuestiona: las capacidades y el render están medidos. Pero tres frases no deben citarse como hechos cerrados:
1. «El gateway no se bloquea» → no medido al umbral del plan (C-5).
2. «Sin huérfanos» → medido una vez y con verificación inmediata (C-3, C-4).
3. «El FFmpeg de Hermes» → resuelto por PATH, no fijado (C-7).

**Recomendación (no bloqueante, no toco el ADR):** añadir un addendum de 4 líneas con (a) protocolo de baseline p95, (b) ruta + `sha256` del binario, (c) precisión «worker = hilo dentro de proceso separado», (d) nota de patentes H.264 remitiendo a licencias.md l.74-78. Tormen decide si se redacta.

---

## 8. Decisiones necesarias

Ninguna se resuelve por mi cuenta. Cada una bloquea casos concretos.

| # | Decisión | Bloquea | Propuesta de Dike |
|---|---|---|---|
| **D-01** | Umbral p95: ¿relativo puro (20 %) o relativo con suelo absoluto? | T02, U4-09, C-5 | `max(1,2×base, base+5 ms)`, n≥100, 3 corridas; documentar el método. |
| **D-02** | Definición exacta de «1 frame» y puntos de medida para A/V | T01 | 1/30 s; medir en cada frontera de escena y en 3 puntos intermedios; ignorar el `silence_end` de EOF. |
| **D-03** | Pesos del «80 % ponderado» y peso de una carencia crítica | T05 | U1 20 / U2 30 / U3 25 / U4 25; cualquier S1 = FAIL global; escenario <70 % = FAIL del escenario. |
| **D-04** | Pausa: ¿se elimina del MVP o se exige al motor? | T04-a | Eliminarla (ui-spec §12.7); el test verifica su **ausencia** explícita y el camino cancel/restart. |
| **D-05** | Split: ¿esencial? (ui-spec lo incluye; el plan lo condicionaba) | U2-06 | Mantenerlo: ya está especificado (T4, §5.4). |
| **D-06** | Idempotencia tras estado terminal: ventana y reutilización | A-07, U4-06 | Clave `(project_id, revision, preset)` con TTL 24 h; si el documento no cambió, devolver el mismo `output_path` en lugar de re-renderizar. |
| **D-07** | Subida >100 MB y comportamiento del drop de Electron | U1-08 | Probar 150 MB en Gate 1; si el `upload` no lo soporta, importar por carpeta concedida y declararlo en la UI. |
| **D-08** | Preview `<video>` con CSP/red (incógnita §12.4) | U4-01, P1/P6 | Validar en Gate 1 con el proxy 540p y `Range`; si falla, el pane no está listo. |
| **D-09** | Cómo simular disco lleno sin dañar C: | A-06 | VHDX de 2 GB o inyección de `ENOSPC` en el worker; nunca llenar C:. |
| **D-10** | Cómo simular egress bloqueado (requiere admin) | T06, A-03 | Regla de firewall temporal con ventana aprobada, o adaptador sin ruta; sin esto, BLOCKED. |
| **D-11** | Dónde viven los canarios de secretos y quién los crea | A-02, U1-09 | Perfil de prueba aislado, canarios sintéticos, borrado al terminar; nunca datos reales. |
| **D-12** | Mecanismo de retorno del MP4 al chat/proyecto | U4-08 | Adjunto en la sesión de origen + ruta en el proyecto; sin subida externa. |
| **D-13** | Material real: 3 grabaciones y consentimiento escrito | T07, T01 real | Sin esto, T07 queda BLOCKED y U1–U4 solo se aceptan con sintéticos (confianza menor). |
| **D-14** | Ventana para reiniciar gateway y recargar `plugins.enabled` | U3-04, T09 | Ventana corta acordada, con `run.json` y sin usuarios activos. |
| **D-15** | ¿El historial de undo persiste tras reabrir? | U2-11, U3-03 | No persistirlo en el MVP; declararlo («el undo vive en la sesión del pane»). |
| **D-16** | Duración por defecto de una imagen importada | U1-04 | 5,0 s (valor de producto, no técnico); debe estar en la ui-spec o decidirse aquí. |
| **D-17** | Subtítulos: pista separada o texto quemado | U4-11 | Pista `mov_text` si el reproductor la muestra; si no, quemado con `subtitles`/`ass`; decidir antes de implementar el switch. |

---

## 9. Trazabilidad y límites

### 9.1 Cobertura U → T → A

| Escenario | Tipos | Adversariales |
|---|---|---|
| U1 | T01, T02, T06, T07, T08, T09 | A-01, A-02, A-10, A-12 |
| U2 | T01, T05, T10 | A-04, A-11 |
| U3 | T05, T09, T10 | A-07, A-11 |
| U4 | T02, T03, T04, T06, T10 | A-03, A-05, A-06, A-07, A-08, A-09, A-12 |

### 9.2 Lo que este plan no cubre

- Publicación, venta, distribución y términos legales (decisión de Tormen, fuera de QA).
- Calidad artística, gusto o idoneidad del montaje.
- 4K, animación por keyframes, composición HTML→vídeo (fuera del MVP por ADR-001).
- Accesibilidad completa más allá de V1–V8 de la ui-spec y del recorrido U2-12.
- macOS y Linux: no medidos en esta máquina; cualquier PASS es solo Windows 11.
- Rendimiento con más de 1 job concurrente (el MVP es 1 job; si se cambia, T02 debe repetirse).

### 9.3 Deuda de evidencia declarada

- El spike **no** probó VFR, preview `<video>`, selección de archivos, acentos ni `plugin_api.py` (`spike/REPORTE.md` l.50-57). Por eso T01-VFR y U4-01 no pueden heredar ningún PASS previo: se ejecutan de cero.
- Los fixtures del spike son CFR 30/30 y sintéticos. T07 exige material real; sin él, la confianza en compatibilidad es **baja** y así se reporta.

---

## Anexo A · Recetas verificadas en esta máquina (2026-11-08)

Todo lo de este anexo se ejecutó hoy. Sirve para que el ejecutor de Gate 1 no improvise comandos.

### A.1 Fixtures sintéticos

```bash
S="$LOCALAPPDATA/Temp/qa-fx"; mkdir -p "$S"; cd "$S"

# FX1 · 3 escenas de color, CFR 30, 2 s cada una, sin audio (6,0 s · 180 frames)
ffmpeg -hide_banner -loglevel error -y \
 -f lavfi -i "color=c=red:s=1280x720:r=30:d=2" \
 -f lavfi -i "color=c=lime:s=1280x720:r=30:d=2" \
 -f lavfi -i "color=c=blue:s=1280x720:r=30:d=2" \
 -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]" -map "[v]" \
 -c:v libx264 -preset veryfast -pix_fmt yuv420p FX1.mp4

# FX2 · VFR real derivado (drop 1 de cada 7 frames, PTS conservados)
ffmpeg -hide_banner -loglevel error -y -i FX1.mp4 \
 -vf "select='not(eq(mod(n,7),3))'" -fps_mode passthrough \
 -c:v libx264 -preset veryfast -pix_fmt yuv420p FX2.mp4
# medido: 154 frames · r_frame_rate 30/1 · avg_frame_rate 4620/179 · 5,9667 s

# FX3 · FX1 + clics de 50 ms en 0,0 / 2,0 / 4,0 s (referencia A/V)
ffmpeg -hide_banner -loglevel error -y -i FX1.mp4 \
 -f lavfi -i "aevalsrc='0.8*sin(2*PI*1000*t)*(between(t\,0\,0.05)+between(t\,2.0\,2.05)+between(t\,4.0\,4.05))':s=48000:d=6" \
 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest FX3.mp4

# FX7 · MP4 truncado sin moov
head -c 6000 FX1.mp4 > FX7.mp4
```

### A.2 Medición de corte y de A/V (probada punta a punta)

```bash
# Render de prueba: recorte de 0,5 s al inicio (equivalente a trim in=0.5)
ffmpeg -hide_banner -loglevel error -y -i FX3.mp4 \
 -vf "trim=start=0.5,setpts=PTS-STARTPTS" -af "atrim=start=0.5,asetpts=PTS-STARTPTS" \
 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 160k out_trim.mp4

# Transición de color por frame (YAVG)
ffmpeg -hide_banner -nostdin -i out_trim.mp4 \
 -vf "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=stats.txt" -f null -

# Onsets de audio
ffmpeg -hide_banner -nostdin -i out_trim.mp4 \
 -af "silencedetect=noise=-30dB:d=0.2" -f null -
```

Salida real obtenida:

```
transicion video: frame=45  t=1.500s  YAVG 81->145
transicion video: frame=105 t=3.500s  YAVG 145->41
frames totales: 165
silence_end: 1.500021
silence_end: 3.500021
silence_end: 5.5          ← fin de archivo: IGNORAR
```

Δ = |1,500021 − 1,500| = **21 µs** ≤ 33,3 ms → PASS del método. Duración 5,5 s y 165 frames = 6,0 s − 0,5 s exactos.

### A.3 El fallo de caption que hay que prevenir (medido)

```bash
# FALLA: dos puntos sin escapar
ffmpeg -i FX1.mp4 -vf "drawtext=text='Hola: it's 50% done':fontsize=28" -f null -
#   → No option name near ' its 50% done…' · Error parsing a filter description

# FALLA igual con textfile (el % se expande)
#   → Stray % near ': it's "ñandú" — día 3/4'

# FUNCIONA: expansion=none (+ textfile o texto escapado)
ffmpeg -i FX1.mp4 -vf "drawtext=textfile='C\:/ruta/cap.txt':expansion=none:fontsize=36" -f null -
#   → exit 0
```

### A.4 Otras comprobaciones hechas hoy

| Comprobación | Resultado |
|---|---|
| `ffmpeg -version` | `n9.0.1-11-ge47273f4d9-20260831` |
| `-vsync` | **eliminado en FFmpeg 9** (`Unrecognized option 'vsync'`) → usar `-fps_mode passthrough` |
| `which -a ffmpeg` | una sola entrada: `hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg` |
| `kill -9` a mitad de encode | 786 480 bytes, `ffprobe` → `moov atom not found`, sin `moov` |
| Metadatos del MP4 del spike | solo `major_brand`, `minor_version`, `compatible_brands`, `encoder=Lavf63.1.101`; **0** apariciones de `EgtYP` |
| Log del spike | `EgtYP` aparece **4 veces** → los logs filtran rutas de usuario |
| Estados en `jobs.sqlite3` | `succeeded 1`, `cancelled 2`, `interrupted 1`; **no existen** `draft`, `validated` ni `paused` |
| `os.path.basename` | neutraliza `..\`, `....//`, `C:/`, `/etc/`; **no** distingue un junction dentro de la raíz |
| `PagesPersec` en reposo | 3 |
| Reproductores | Edge + Windows Media Player (no VLC/mpv) |

---

## Anexo B · Plantilla de reporte de corrida

```markdown
# RUN-<fecha>-<gate> · <artefacto>

## Entorno
- plugin: <versión/hash> · hermes: <versión> · perfil: <perfil>
- ffmpeg: <ruta> · sha256: <hash>
- RAM libre / disco libre / PagesPersec al inicio: …

## Resultado por caso
| Caso | Veredicto | Evidencia | Nota |
|---|---|---|---|
| U1-01 | PASS | U1-01_pane.png | — |

## S1 abiertos
- <ninguno | lista con enlace a evidencia>

## BLOCKED y causa
- <caso> — <decisión D-xx pendiente>

## Veredicto del gate
<PASS | OBSERVADO | FAIL> + una frase de justificación

## Decisiones necesarias
- <D-xx> — <qué falta>
```

Regla final: si no está en el manifiesto con hash, no ocurrió.
