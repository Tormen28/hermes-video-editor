# Plan de pruebas · Pack v1.1 — música, transiciones, texto, imagen, velocidad y presets

- **Autora:** Dike (QA), 2026-11-08 21:30 -04:00.
- **Estado:** PROPUESTA NORMATIVA. Fija «hecho» por escrito **antes** de que el pack v1.1 exista. No sustituye la aprobación de Tormen.
- **Ámbito:** ampliación del plan `auditoria/plan-pruebas.md` para las funciones aprobadas del pack v1.1: música de fondo (volumen, fades, loop, ducking, loudnorm), catálogo de transiciones (fade, slide, wipe, circle, zoom), estilos y animaciones de texto, Ken Burns, velocidad 0.5–2×, filtros rápidos y LUT, logo/marca de agua, presets de export 9:16, 1:1 y 1080p (sujeto a medición) y plantillas de proyecto.
- **Relación con el plan base:** este documento **hereda** las reglas de veredicto (§0.1), severidad y bloqueo (§0.2), anti-self-report (§0.3), independencia (§0.4), registro por corrida (§1.2), evidencia válida (§5) y control negativo (§5.3) de `auditoria/plan-pruebas.md`. No las repite; las aplica. Donde hay conflicto, manda el plan base.
- **Regla de lectura:** todo umbral marcado **[P]** es provisional y necesita aprobación o recalibración antes de usarse como puerta. Los **[F]** vienen fijados por el artefacto actual o por una decisión ya tomada y citada.
- **Regla de alcance:** ningún caso de este anexo se cierra contra el mockup (`docs/mockup-v31.html`), contra una captura de diseño ni contra la descripción del constructor. Se ejecuta sobre el artefacto instalado y produce evidencia reproducible según §5 del plan base.
- **Línea base declarada al escribir este plan (medida hoy en esta máquina):** `core` → `python -m unittest discover -s tests` = **Ran 259 tests, OK (skipped=2), 53.6 s**; FFmpeg `n9.0.1` con `xfade` (58 transiciones), `zoompan`, `lut3d`, `sidechaincompress`, `loudnorm`, `atempo`, `ebur128`, `blurdetect`, `vignette`, `drawtext`, `overlay` y `amix` presentes; export actual único `mp4-720p30` 1280×720 30/1 h264+aac.

> **Actualización del Padre — 2026-11-08 22:20 -04:00.** El plan se escribió antes de las fases 2A/2B. Estado real verificado después: `python -m unittest discover -s tests` = **337 tests OK (skipped=2)**; servicio **0.3.2**. La nota «el worker aplica fade in/out por escena y concatena» ya **no aplica**: 2B implementó `xfade` real con offsets y duración final = Σd − Σsolapes, así que **D-V11-01 queda resuelto y TRX-03 se desbloquea** (los umbrales de TRX-03 siguen siendo la referencia). Los casos MUS, TXT, FLT, LOGO siguen válidos; EXP cambia cuando 2C añada presets. Mantener el resto del documento como criterio normativo.


---

## 0. Cómo se usa este anexo

### 0.1 Identificadores y familias

| Familia | Qué cubre | Nº de casos |
|---|---|---|
| `MUS` | Música de fondo, ducking, loudnorm | 16 |
| `TRX` | Catálogo de transiciones | 10 |
| `TXT` | Estilos, animaciones y fuentes de texto | 11 |
| `FLT` | Filtros rápidos y LUT | 9 |
| `KB` | Ken Burns | 5 |
| `SPD` | Velocidad 0.5–2× | 8 |
| `LOGO` | Logo / marca de agua | 8 |
| `EXP` | Presets de export (9:16, 1:1, 1080p) | 9 |
| `TPL` | Plantillas de proyecto | 6 |
| `REG` | Regresión del MVP actual | 6 |
| **Total** | | **88** |

El total y el desglose se recalculan al cerrar la corrida; la tabla es la declaración inicial, no un resultado.

### 0.2 Regla de oro para funciones nuevas

Una función del pack v1.1 solo puede declararse PASS si se cumplen **las tres**:

1. **Aceptación:** el caso funcional principal (el primero de su familia) pasa con umbral medido.
2. **Adversarial:** al menos un caso adverso de su familia devuelve rechazo explícito (400/422 con campo) o degradación declarada, nunca 500, crash, OOM ni artefacto silenciosamente incorrecto.
3. **Regresión:** `REG-01` y `REG-02` siguen verdes en la misma corrida.

Una función nueva que pasa lo bonito pero rompe el contrato 720p30 o borra/afloja un test existente se marca **FAIL**, no «PASS con observaciones».

### 0.3 Estados permitidos por caso

| Veredicto | Cuándo en este anexo |
|---|---|
| **PASS** | Todos los pasos ejecutados, evidencia presente y reproducible, umbral cuantitativo cumplido. |
| **FAIL** | Umbral incumplido, rechazo ausente, crash, artefacto incorrecto o evidencia no reproducible. |
| **BLOCKED** | Falta decisión (D-V11-xx), preset no medido, límite de recursos no aprobado o falta fixture. Se declara con causa y **no cuenta como PASS**. |
| **N/A** | La función no existe por decisión aprobada y citada (p. ej. emoji a color si se decide no soportarlo). Exige cita, no silencio. |

> Cómo leer la columna **Criterio** de cada caso: fija el PASS y el FAIL específicos. Si falta el entorno, un fixture o una decisión **D-V11-xx**, el veredicto es **BLOCKED** aunque el criterio diga PASS/FAIL. Si la función no existe por una decisión aprobada y citada, es **N/A**. Un BLOCKED nunca cuenta como PASS.

---

## 1. Contrato observable que estos casos verifican (propuesta)

> **Esto no es una imposición de implementación.** Es el mínimo observable que QA necesita para poder escribir pruebas antes del código. Los nombres exactos de campos los fija el ADR/schema de F3 (ver **D-V11-00**); los casos verifican **comportamiento, rechazo y round-trip**, y se adaptan al nombre final sin cambiar el umbral.

| Área | Superficie observable mínima | Validación exigida |
|---|---|---|
| Documento | `schemaVersion: 2`; proyectos v1 se abren y migran sin pérdida | lectura v1 → escritura v2 conserva campos y añade versión; nunca «proyecto corrupto» |
| Música | `music: {asset, volume 0–100, fadeIn, fadeOut, loop, ducking{enabled, depthDb, thresholdDb, attackMs, releaseMs}}` | asset debe existir, ser audio y estar dentro de la raíz de medios; fades 0–10 s; loop booleano |
| Transición | `scene.transition` = `<tipo>-<segundos>` con tipo ∈ {`none`,`fade`,`slideleft`,`wipeleft`,`circleopen`,`zoomin`} y 0.1 ≤ s ≤ 2.0 | conserva `fade-N` y `none` actuales (compatibilidad); rechaza tipo desconocido y duración fuera de rango |
| Texto | por ítem: `content`, `at`, `until`, `position`, `style{size,color,border,shadow,background,font}`, `animation{in,out,duration}` | texto siempre dato, nunca filtro; fuente validada por existencia y formato; animación acotada a la ventana visible |
| Imagen | `scene.kenBurns{enabled, from, to, pan}` solo para `kind=image` | sobre vídeo: rechazo explícito o no-op con aviso; nunca zoom silencioso |
| Velocidad | `scene.speed` ∈ [0.5, 2.0] | fuera de rango: 400; audio y vídeo escalan con el mismo factor |
| Filtros | `scene.filters{preset, brightness, contrast, saturation, grayscale, vignette, blur, lut}` | parámetros numéricos acotados; LUT `.cube` válida, dentro de raíz y con tamaño máximo |
| Logo | `logo{asset, x%, y%, scale%, opacity%}` | PNG con alpha; posición y escala acotadas; nunca fuera de encuadre sin aviso |
| Export | `preset` ∈ {`mp4-720p30`, `mp4-1080p30`, `mp4-1080p30-9x16`, `mp4-1080p30-1x1`} (ids exactos **D-V11-08**) | preset desconocido: 400 antes de crear job; el job devuelve el preset solicitado |
| Plantilla | `templates[]` con manifiesto versionado | plantilla inválida o con medios faltantes no produce proyecto a medias ni render silencioso |

**Regla de rechazo:** todo error de validación de estas superficies debe ser **4xx con `errors[]` que incluya el path del campo** (`music.asset`, `scene[2].transition`, `filters.lut`, `logo.x`, …). Un 500, un `KeyError` o un job que falla 20 s después por un dato inválido en el PUT es **FAIL** del caso adversarial correspondiente, aunque el render final «no se haya producido».

---

## 2. Fixtures nuevos y método de medición

### 2.1 Fixtures (se crean una vez por corrida, con hash en `run.json`)

| ID | Contenido | Uso |
|---|---|---|
| **FX8** | Tono 440 Hz estéreo 48 kHz, 8 s, −18 LUFS, sin clipping | música corta, ducking por banda, loop |
| **FX9** | Tono 440 Hz + acorde suave, 60 s, −18 LUFS | música más larga que el vídeo, recorte |
| **FX10** | Vídeo 12 s con «voz» sintética: bursts de 1 kHz con envolvente de habla (1.2 s on / 0.8 s off) y vídeo de color | ducking real, A/V, velocidad con audio |
| **FX11** | Imagen 3840×2160 con carta de gris 18 %, barras de color, círculo y marcadores en el punto medio de cada borde, al 5 % | filtros, crop 9:16/1:1, geometría |
| **FX12** | Logo PNG 512×512 RGBA con cruz central y borde de 8 px | posición, escala, opacidad |
| **FX13** | LUT identidad `.cube` 33³ (~1 MB) + LUT corrupta (cabecera truncada) + LUT 64 MB | filtros y adversariales |
| **FX14** | Fuente TTF válida (copia de `segoeui.ttf`) + archivo `.ttf` corrupto de 1 KB | texto y fuentes |
| **FX15** | 3 escenas de color 4 s cada una con número de frame quemado, CFR 30, 720p, sin audio | transiciones, duración, orden |
| **FX16** | Clip de 0.2 s y clip de 24 fps | velocidad extrema y duplicado de frames |
| **FX17** | Plantilla mínima: 3 escenas + música + logo + 2 textos | plantillas |

Los fixtures existentes FX1–FX7 del plan base se reutilizan sin cambios; **no se regeneran** si el hash no coincide (se declara BLOCKED por fixture distinto).

### 2.2 Método de medición (comandos de referencia)

Estos comandos son el mínimo reproducible; el ejecutor puede envolverlos en script, pero debe guardar la salida literal.

```bash
# Duración, frames, dimensiones, streams
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,avg_frame_rate,nb_frames,sample_rate,channels -of json out.mp4

# Loudness integrado y true peak (MUS-07)
ffmpeg -nostats -hide_banner -i out.mp4 -map 0:a -af ebur128=peak=true -f null - 2>&1 | tail -25

# Envolvente de una banda (ducking, MUS-06): RMS por ventana de 50 ms
ffmpeg -v error -i out.mp4 -map 0:a -af "bandpass=f=440:width_type=q:w=8,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=band.txt" -f null -

# Bounding box de texto/logo sobre fondo plano (TXT-04, LOGO-01)
ffmpeg -v error -ss 2.0 -i out.mp4 -frames:v 1 -vf "cropdetect=24:2:0" -f null - 2>&1 | tail -3

# PSNR entre dos renders (control de «no cambia», KB-A1, REG-02)
ffmpeg -v error -i con.mp4 -i sin.mp4 -lavfi psnr -f null - 2>&1 | tail -2

# Frames alrededor de una frontera (TRX-01/02)
ffmpeg -v error -ss 3.7 -t 0.6 -i out.mp4 -vsync 0 trx_%03d.png
```

**Regla de medición:** las cifras se toman de la **salida literal** de estos comandos, no de la UI ni del informe del constructor. Cuando el caso hable de «1 frame», se usa 1/30 s = 33.3 ms **[F]** (fps del contrato 720p30; en 1080p30 idéntico).

---

## 3. Casos por función

### 3.1 Música de fondo (`MUS`)

**Precondición común**
- Proyecto de 2 escenas de 5 s (10 s) con FX1 (sin audio) y export `mp4-720p30`; `music.asset` = FX8 o FX9 según el caso; master 100; sin ducking salvo que el caso lo pida.
- Para medir solo música, las escenas no aportan audio (FX1). Para medir ducking, la escena usa FX10 y la música FX8 (bandas separables: 440 Hz música, 1 kHz voz).
- `run.json` con hashes de FX8–FX10 y ruta/hash de FFmpeg.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **MUS-01** · Música básica | Asignar FX8 a `music`, volumen 100, sin fades, exportar. | Sale **una** pista AAC 48 kHz estéreo; la música cubre todo el vídeo; duración = 10.0 s ±1 frame; loudness integrado = fuente ±1.0 LU **[P]**. | `MUS-01_out.ffprobe.json`, `MUS-01_ebur128.txt`, `MUS-01_out.mp4` | PASS si los tres umbrales se cumplen. FAIL si no hay audio, hay silencio o la duración deriva >1 frame. |
| **MUS-02** · Volumen 0/50/100 | Tres exports con volumen 0, 50 y 100; medir loudness relativo al de 100. | v=0 → ≤ −70 LUFS (silencio digital, sin NaN) **[P]**; v=50 → −6.0 ±1.0 dB respecto a 100 **[P]**; v=100 → 0 ±0.5 dB. | `MUS-02_ebur128_{0,50,100}.txt` | PASS si las tres medidas caen en rango. FAIL si el volumen se ignora, invierte o satura. |
| **MUS-03** · Fades de música | `fadeIn=1.5`, `fadeOut=2.0`; medir envolvente al inicio y al final. | Rampa de entrada de −40 dB a −3 dB dentro de 1.5 s ±100 ms; salida termina en el fin del vídeo ±1 frame y los últimos 100 ms ≤ −50 dBFS **[P]**; sin discontinuidad >1.5× la mediana de diferencias de muestra (clic) **[P]**. | `MUS-03_band.txt`, `MUS-03_tail.wav`, `MUS-03_out.ffprobe.json` | PASS si rampa y cola cumplen y no hay clic audible/medible. FAIL si el fade no existe o corta en seco. |
| **MUS-04** · Loop de música corta | FX8 (8 s) con `loop=true` sobre vídeo de 20 s (4 escenas). | Duración total 20.0 s ±1 frame; **3 repeticiones** (ceil(20/8)); 0 silencios ≥20 ms en la región de música **[P]**; transiente en cada empalme ≤2× la mediana de la señal (sin chasquido) **[P]**. | `MUS-04_out.ffprobe.json`, `MUS-04_band.txt`, `MUS-04_seams.png` | PASS si cubre 20 s sin huecos ni chasquidos. FAIL si hay silencio, salto de duración o el loop se detiene en el primer corte. |
| **MUS-05** · Recorte sin loop | FX9 (60 s) con `loop=false` sobre vídeo de 10 s. | El audio termina con el vídeo en 10.0 s ±1 frame; sin cola de 50 s; si no hay fade configurado, el corte cumple la prueba de clic de MUS-03. | `MUS-05_out.ffprobe.json`, `MUS-05_tail.wav` | PASS si recorta exacto. FAIL si arrastra audio, corta antes o deja el MP4 con duración distinta. |
| **MUS-06** · Ducking con «voz» | FX10 (voz 1 kHz) + FX8 (música 440 Hz), `ducking.enabled=true`, `depthDb=8`, ataque 80 ms, release 400 ms. | Durante los bursts, la banda de 440 Hz baja **6–12 dB** respecto al tramo sin voz **[P]**; ataque 10–90 % ≤150 ms **[P]**; recuperación a ±1 dB en ≤800 ms tras el burst **[P]**; sin hueco (no baja a −70 dB). | `MUS-06_band.txt`, `MUS-06_bursts.csv`, `MUS-06_ebur128.txt` | PASS si profundidad, ataque y release caen en rango. FAIL si no bombea, si bombea de más (>15 dB) o si deja la música muda. |
| **MUS-07** · Loudnorm | `loudnorm=true` (o preset de normalización) con FX8 a −18 LUFS. | Integrated **−14.0 ±1.0 LUFS** **[P]**; true peak **≤ −1.0 dBTP** **[P]**; LRA reportado; duración sin cambio ±1 frame; no clipping (0 muestras a full scale). | `MUS-07_ebur128.txt`, `MUS-07_out.ffprobe.json` | PASS si loudness y TP cumplen. FAIL si normaliza a otro target, recorta o alarga. |
| **MUS-08** · Vídeo sin audio + música | Escenas FX1 (sin audio) + música; exportar. | Hay audio continuo: integrated ≥ −30 LUFS **[P]**; 0 silencios ≥100 ms; A/V sin cambio (el vídeo no se alarga). | `MUS-08_ebur128.txt`, `MUS-08_out.ffprobe.json` | PASS si la música suena y el vídeo no cambia. FAIL si `anullsrc` tapa la música o si el MP4 sale mudo. |
| **MUS-09** · Master 0 con música | Master 0, música 100. | Salida ≤ −70 LUFS; el job termina `succeeded`; no hay error. | `MUS-09_ebur128.txt`, `MUS-09_job.json` | PASS si el master manda. FAIL si la música ignora el master. |
| **MUS-A1** · Asset inexistente | Guardar `music.asset` que no existe (o borrar el archivo tras guardar) y exportar. | En guardado: **400** con `errors[]` en `music.asset`; 0 jobs creados. Si el archivo desaparece después: job `failed` ≤5 s, etapa `probing`, mensaje que nombra el asset; 0 bytes en `out/`; servicio vivo. | `MUS-A1_http.txt`, `MUS-A1_jobs.json`, `MUS-A1_out_ls.txt` | PASS si rechaza o falla limpio y no hay render parcial. FAIL si 500, traza, job colgado o MP4 mudo promovido. |
| **MUS-A2** · Tipo vídeo como música | Registrar FX1 (MP4) como `music.asset` y guardar/exportar. | **400** con path `music.asset` y motivo «no es audio»; 0 jobs; `ffprobe` del asset no se usa para inventar una pista de vídeo. | `MUS-A2_http.txt`, `MUS-A2_jobs.json` | PASS si rechaza antes del job. FAIL si acepta y renderiza vídeo como audio, o falla dentro de FFmpeg con traza. |
| **MUS-A3** · Ruta fuera de raíz | `music.asset` = `../../canario.txt`, absoluta fuera de raíz, UNC, ADS. | **400/403**; 0 lecturas del canario; el log no contiene su contenido. | `MUS-A3_http.txt`, `MUS-A3_canario.txt` (grep 0) | PASS si todas las variantes se rechazan. FAIL si una sola lee. |
| **MUS-A4** · Música corrupta o 0 B | Archivo de 0 B, MP3 truncado sin cabecera, WAV con header inválido. | **400** al guardar o job `failed` ≤5 s con mensaje legible; sin `out/`; staging purgado. | `MUS-A4_http.txt`, `MUS-A4_jobs.json`, `MUS-A4_staging.txt` | PASS si falla limpio. FAIL si cuelga, OOM o promueve un MP4 sin audio. |
| **MUS-A5** · Ducking que no bombea | Tono constante 440 Hz + «voz» constante 1 kHz (sin pausas) durante 10 s. | La ganancia de la música varía **≤1.0 dB** en toda la ventana **[P]**; no hay oscilación periódica >2 dB; el ducking no se dispara con señal estacionaria. | `MUS-A5_band.txt`, `MUS-A5_out.mp4` | PASS si no bombea. FAIL si la música pulsa con la señal o si el detector oscila. |
| **MUS-A6** · Loop y fades incompatibles | Loop activo con música de 1 s y fadeIn+fadeOut > 1 s; y `fadeOut` negativo. | **400** con path (`music.fadeIn`/`fadeOut`/`loop`) o recorte declarado que no genere ventanas negativas; nunca NaN ni filtro con duración 0. | `MUS-A6_http.txt`, `MUS-A6_jobs.json` | PASS si valida o acota con aviso. FAIL si el job falla dentro de FFmpeg por parámetro inválido. |
| **MUS-A7** · Música más larga sin loop ni fade | FX9 (60 s), loop off, fades 0, vídeo 10 s. | Corte exacto a 10.0 s ±1 frame; prueba de clic de MUS-03 sobre el corte; no se mezcla audio más allá del vídeo. | `MUS-A7_out.ffprobe.json`, `MUS-A7_tail.wav` | PASS si el corte es limpio. FAIL si el MP4 dura 60 s o el audio se corta antes. |
---

### 3.2 Catálogo de transiciones (`TRX`)

**Precondición común**
- Proyecto de 3 escenas de 4 s con FX15 (colores distintos y número de frame quemado), 720p30, sin texto ni música; `scene[i].transition` entrante según el caso.
- Medición por extracción de frames alrededor de cada frontera (3.7–4.3 s) y por `ffprobe` de duración/frames.
- Tipos exigidos: `fade`, `slideleft`, `wipeleft`, `circleopen`, `zoomin`; `none` como control.

> **Hallazgo de partida (leer antes de TRX-03).** Hoy `worker.py:676-679` aplica `fade=t=in` / `fade=t=out` **dentro de cada escena** y luego concatena (`worker.py:716`), sin solape. Por tanto, el `fade-N` actual **no resta duración**: el total es Σd. El plan base, en cambio, exige solape: U2-10 («duración total = suma − 0,8 s (los fundidos solapan)», `plan-pruebas.md:226`) y §4 («Σ(escenas) − Σ(fundidos) − recortes», l.469). Esa contradicción **ya existe** y el pack v1.1 no puede heredarla en silencio: o se corrige el worker a `xfade` real, o se corrige el plan base y se declara. **D-V11-01** lo decide. Mientras no se decida, TRX-03 se marca BLOCKED, no PASS.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **TRX-01** · Cada tipo renderiza | Cinco exports, uno por tipo con `d=0.5`, mismos clips. | Cada tipo produce un MP4 decodificable; en la ventana de transición hay **≥1 frame que difiere de A y de B** (PSNR <35 dB contra ambos) **[P]**; el frame medio no es negro completo (luma media entre 15 y 240) **[P]**; los cinco resultados **no son idénticos entre sí** (hash de frames distinto). | `TRX-01_{tipo}.mp4`, `TRX-01_{tipo}_frames/`, `TRX-01_psnr.txt`, `TRX-01_hashes.txt` | PASS si los cinco tipos existen y son distinguibles. FAIL si un tipo cae a `fade`, si sale negro o si el job falla. |
| **TRX-02** · Duración exacta | Medir la ventana de mezcla en cada frontera (clasificación de frames A/mixto/B). | Ventana = 0.5 s ±1 frame (15 frames ±1) **[P]**; empieza en la frontera declarada ±1 frame; no hay frames «A puro» dentro de la ventana ni «B puro» antes de que termine. | `TRX-02_windows.csv`, `TRX-02_frames/` | PASS si la ventana medida coincide. FAIL si la transición dura más/menos o se desplaza. |
| **TRX-03** · Duración total con solape | Proyecto 3×4 s con dos transiciones de 0.5 s; `ffprobe` de duración y frames. | **Contrato v1.1: solape real** → total = 12.0 − 1.0 = **11.0 s ±1 frame** (330 frames ±1) **[F, D-V11-01]**. Si el artefacto mantiene fundido a negro sin solape, el total sería 12.0 s y **este caso es FAIL de contrato**, no un PASS alternativo. | `TRX-03_out.ffprobe.json`, `TRX-03_frames/` | PASS si el total es 11.0 s ±1 frame. FAIL si no solapa o si la aritmética no cuadra. **Si Tormen elige el modelo sin solape, este caso se reescribe y el plan base §2 U4 debe corregirse; hoy el plan base ya asume Σ−Σ.** |
| **TRX-04** · Transiciones encadenadas | 4 escenas, 3 transiciones de tipos distintos (slide→wipe→zoom), 0.3 s. | PTS estrictamente crecientes; 0 PTS duplicados; 0 huecos >1 frame; duración = Σd − Σt ±1 frame; los tres tipos se distinguen en sus ventanas. | `TRX-04_pts.txt`, `TRX-04_out.mp4`, `TRX-04_frames/` | PASS si no hay saltos ni frames repetidos. FAIL si aparece un frame congelado, negro intermedio o PTS no monótono. |
| **TRX-05** · A/V en la frontera | FX3 (clics en 0/2/4 s) con transición de 0.5 s en cada frontera; medir clics de salida. | Δ A/V ≤33.3 ms en cada clic **[F]**; el audio de escenas se cruza (no hay corte seco >6 dB) o, si el contrato decide corte seco, se declara y se marca S3; no hay silencio >100 ms en la transición **[P]**. | `TRX-05_clics.csv`, `TRX-05_band.txt`, `TRX-05_out.mp4` | PASS si el sincronía se mantiene y no hay hueco audible. FAIL si el audio se desfasa >1 frame o desaparece durante la transición. |
| **TRX-06** · Control `none` | Mismo proyecto con `transition="none"` en las tres escenas; comparar con el render base sin transiciones. | Duración 12.0 s; PSNR contra el render base ≥45 dB (mismo encoder) **[P]**; 0 frames mixtos detectados. | `TRX-06_out.mp4`, `TRX-06_psnr.txt` | PASS si `none` no altera nada. FAIL si `none` aplica un fundido por defecto. |
| **TRX-A1** · Transición más larga que el clip | Escenas de 2 s con `fade-3.0` y con `fade-2.0`. | **400** con path `scene[i].transition` y máximo permitido (`≤ min(d_i, d_{i+1})/2` = 1.0 s) **[P]**; si el contrato permite clamp, se aplica a 1.0 s **con aviso en la respuesta** y la duración total cuadra; nunca duración negativa, escena de 0 frames ni job colgado. | `TRX-A1_http.txt`, `TRX-A1_jobs.json`, `TRX-A1_out.ffprobe.json` | PASS si rechaza o acota con aviso medible. FAIL si genera un MP4 con escena vacía, duración absurda o error interno. |
| **TRX-A2** · Valores inválidos e inyección | `0.05`, `2.1`, `-0.5`, `NaN`, `1e9`, `"fade; rm -rf"`, `"slideleft:0.5"`, objeto en vez de string. | **400** en todos, con path; el argv de FFmpeg no cambia (comparar comando registrado); 0 jobs. | `TRX-A2_http.txt`, `TRX-A2_cmd.txt` | PASS si todos se rechazan sin tocar argv. FAIL si uno llega a FFmpeg o se interpreta como filtro. |
| **TRX-A3** · Transición en la primera escena | `scenes[0].transition="slideleft-0.5"`. | Debe estar **definido**: o se ignora con aviso (no hay escena previa) o se rechaza 400. En ningún caso se recorta la primera escena ni se pierde duración; el total cuadra con la política declarada ±1 frame. | `TRX-A3_http.txt`, `TRX-A3_out.ffprobe.json` | PASS si la política es explícita y la duración cuadra. FAIL si la primera escena desaparece o el total no cuadra. |
| **TRX-A4** · Estrés de grafo | 100 escenas de 2 s, todas con transición de 0.2 s y texto; exportar. | El grafo compilado <20 000 caracteres **[F: límite actual de worker]** o falla limpio con mensaje «filter graph…»; si se rechaza, 400/422 antes del job; RSS pico ≤2 GB (Job Object) y servicio vivo. | `TRX-A4_cmd.txt`, `TRX-A4_jobs.json`, `TRX-A4_rss.txt` | PASS si renderiza dentro de límites o falla limpio antes de FFmpeg. FAIL si OOM, crash del servicio o MP4 truncado. |

---

### 3.3 Texto: estilos, animaciones y fuentes (`TXT`)

**Precondición común**
- Escena de imagen FX11 (o fondo negro liso para medir geometría) de 6 s, 720p30; un ítem de texto por caso; export completo.
- Medición: frame PNG en `at+0.5 s`, `until−0.5 s`, y fuera de ventana; `cropdetect` para bbox; muestreo de píxel para color; hash del `textfile` generado; OCR **si** `tesseract` está instalado, si no inspección visual sobre frame 2× con timecode (E3).
- Fuente por defecto actual: `segoeui.ttf` vía `_find_font()` (`core/service/worker.py:1091`).

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **TXT-01** · Acentos, símbolos y emoji | Texto: `Ahorra 50%: it's «ñandú» — día 3/4; ¿café? 🎬✅`. | El job termina `succeeded`; el texto se renderiza **literal**: `%` y `:` no rompen el filtro; el bbox existe y está dentro del encuadre; OCR/inspección confirma ≥95 % de caracteres **[P]**; `%{pts}` (si se incluye) aparece literal, no evaluado. El emoji se evalúa aparte en `TXT-A3`: con la fuente por defecto puede salir «tofu» y **eso no hace fallar TXT-01**, siempre que el texto ASCII/acentuado esté correcto. | `TXT-01_frame.png`, `TXT-01_textfile.txt` + `sha256`, `TXT-01_cmd.txt` | PASS si el texto no rompe el render y se lee correcto. FAIL si hay error de filtro, texto cortado o `%` interpretado. |
| **TXT-02** · Estilos | Tres variantes: size 24/64/120, color `#FF3B30`, borde 4 px, sombra, caja de fondo al 50 %. | Altura de glifo escala con size dentro de ±10 % **[P]**; color muestreado ±8/255 por canal **[P]**; borde/sombra presentes (≥2 px de contraste en el contorno) **[P]**; caja de fondo con alpha 50 % ±5 % **[P]**. | `TXT-02_{size}_frame.png`, `TXT-02_pixels.txt` | PASS si estilo y geometría se corresponden. FAIL si el estilo se ignora o desborda. |
| **TXT-03** · Animaciones de entrada/salida | `animation.in=fade`, `out=slide`, `duration=0.5`; frames en `at`, `at+0.25`, `at+0.5`, `until−0.5`, `until`. | En `at` opacidad ≈0; a `at+0.5` opacidad 100 % ±1 frame; en `until−0.5` empieza la salida; texto ausente fuera de `[at−1f, until+1f]` **[P]**; el movimiento de slide recorre ≥80 % de la distancia en la ventana **[P]**. | `TXT-03_frames/`, `TXT-03_alpha.csv` | PASS si la animación ocurre dentro de la ventana. FAIL si el texto aparece antes, queda visible después o no anima. |
| **TXT-04** · Posiciones y área segura | `top`, `center`, `bottom`; texto de 2 líneas. | Bbox dentro de los márgenes del 5 % en los tres casos **[P]**; `center` centrado en X ±2 px y en Y ±2 px; no se solapa con el borde inferior en `bottom`. | `TXT-04_{pos}_frame.png`, `TXT-04_bbox.txt` | PASS si las tres posiciones respetan el área segura. FAIL si se sale del encuadre o pisa el borde. |
| **TXT-05** · Varios textos y z-order | 3 textos solapados en el mismo instante, colores distintos, el último debe quedar encima. | Los 3 se renderizan; en la zona de solape el color es el del **último** ítem ±8/255; ninguno desaparece. | `TXT-05_frame.png`, `TXT-05_pixels.txt` | PASS si se ven los tres y el orden es el declarado. FAIL si se pisan en orden inverso o se pierde uno. |
| **TXT-06** · Texto largo | 500 caracteres (límite `MAX_TEXT_LENGTH=500`) en 720p. | O el texto se ajusta (wrap o tamaño reducido) y el bbox queda dentro del 90 % del ancho, o se rechaza con 400 explicando el límite; nunca se sale del encuadre en silencio. | `TXT-06_frame.png`, `TXT-06_http.txt` | PASS si cabe o se rechaza con motivo. FAIL si se desborda o se corta sin aviso. |
| **TXT-A1** · Fuente inexistente | `style.font` apunta a `no-existe.ttf`. | **400** con path `text[0].style.font`; o fallback **declarado** en la respuesta y en el log del job, con el mismo texto legible; nunca sustitución silenciosa. | `TXT-A1_http.txt`, `TXT-A1_job.log` | PASS si rechaza o declara el fallback. FAIL si renderiza con otra fuente sin decirlo o falla dentro de FFmpeg. |
| **TXT-A2** · Fuente corrupta o no-TTF | FX14 corrupto, `.exe` renombrado a `.ttf`, archivo de 0 B. | **400** al guardar o job `failed` ≤5 s con mensaje de fuente; sin `out/`; staging purgado. | `TXT-A2_http.txt`, `TXT-A2_jobs.json` | PASS si falla limpio. FAIL si cuelga o promueve vídeo sin texto. |
| **TXT-A3** · Emoji sin glifo / fallback | Texto `OK 🎬✅ fin` con la fuente por defecto (`segoeui.ttf`) y con `seguiemj.ttf` (presente en esta máquina, 12.9 MB). **Medido hoy:** `segoeui.ttf` → `OK □□ fin` (tofu); `seguiemj.ttf` → `OK 🎬 ✅ fin` en monocromo; ambos exit 0. | El job no falla en ningún caso; el texto ASCII/acentuado queda intacto y legible; **con fallback a una fuente con glifos, el emoji debe ser reconocible y no tofu** **[P]**; si no hay fuente con glifos, placeholder documentado y visible; el color es opcional (S3 si sale monocromo). La cadena de fallback no puede desplazar ni recortar el resto del texto. | `TXT-A3_{font}_frame.png`, `TXT-A3_font.txt`, `TXT-A3_job.json` | PASS si no hay tofu cuando existe fuente con glifos, y el texto no se rompe. FAIL si el job falla, el texto se corrompe o se declara soporte emoji y sale tofu. |
| **TXT-A4** · Inyección en texto | `%{pts}`, `:`, `;`, `[`, `]`, `'`, `"`, `\`, salto de línea, `drawtext=text=...`. | Todo se trata como **dato**: exit 0 y texto literal; el comando registrado no añade opciones; 0 ejecución de filtros inyectados. | `TXT-A4_cmd.txt`, `TXT-A4_frame.png`, `TXT-A4_jobs.json` | PASS si ningún texto altera el argv. FAIL si un `:` o `%` rompe el job (regresión de A-04 del plan base). |
| **TXT-A5** · Animación más larga que la ventana | `until−at=0.3 s` con `animation.duration=2.0`. | **400** o clamp a 0.3 s **con aviso**; el texto no queda visible después de `until` ni antes de `at`; duración del vídeo sin cambio. | `TXT-A5_http.txt`, `TXT-A5_frames/` | PASS si valida o acota. FAIL si invade otros tramos o desaparece sin aviso. |
---

### 3.4 Filtros rápidos y LUT (`FLT`)

**Precondición común**
- Imagen FX11 (carta de gris 18 %, barras de color, círculo, marcadores) como escena de 5 s, 720p30; un filtro por export salvo el caso combinado.
- Medición sobre frames PNG extraídos a 1 s; regiones: centro, esquina (5 % del lado) y parches de gris 64/128/192.
- Fuerza de filtro normalizada 0–100; **el mapeo exacto a parámetros de FFmpeg lo fija el ADR de F3**, el caso mide monotonía y efecto, no un valor interno.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **FLT-01** · Brillo, contraste y saturación | Exports a −100, −50, 0, +50, +100 para cada control; medir luma en parches y croma en barras. | En 0: luma del parche 128 sin cambio ±2/255 y croma sin cambio ±3 % **[P]**. Brillo monótono y rango ≥60/255 entre extremos **[P]**. Contraste: pendiente entre parches 64→192 ≥1.3× a +100 y ≤0.8× a −100 **[P]**. Saturación: croma medio 0.5×–1.5× entre extremos, 0 = sin cambio **[P]**. | `FLT-01_{control}_{v}_frame.png`, `FLT-01_medidas.csv` | PASS si cada control es monótono, el 0 es neutro y el rango es visible. FAIL si un control no hace nada, invierte o satura el vídeo. |
| **FLT-02** · Blanco y negro | `grayscale=100`. | En todos los frames muestreados: `max abs(R−G) ≤2` y `max abs(G−B) ≤2` (8 bits) **[P]**; luma conservada ±3/255 respecto al original; no hay tinte. | `FLT-02_frame.png`, `FLT-02_channels.txt` | PASS si los tres canales coinciden. FAIL si queda color o cambia el brillo. |
| **FLT-03** · Viñeta | `vignette=0` y `vignette=100` sobre fondo liso. | A 100: luma esquina/centro ≤0.75 **[P]**; a 0: ≥0.95; simetría radial ±5 % entre las cuatro esquinas **[P]**; el centro no cambia ±3/255. | `FLT-03_{v}_frame.png`, `FLT-03_ratio.txt` | PASS si oscurece solo los bordes y de forma simétrica. FAIL si tinta el centro, es asimétrica o no actúa. |
| **FLT-04** · Desenfoque | `blur=0` y `blur=100`; medir `blurdetect` y PSNR. | A 100: score de `blurdetect` ≥2× el de 0 **[P]** y PSNR contra el original ≤35 dB **[P]**; a 0: PSNR ≥45 dB (no-op) **[P]**. | `FLT-04_blurdetect.txt`, `FLT-04_psnr.txt` | PASS si el efecto es medible y el 0 es no-op. FAIL si el filtro no actúa o degrada con 0. |
| **FLT-05** · LUT válida | FX13 identidad y una LUT cálida; comparar con el render sin LUT. | Identidad: PSNR ≥45 dB contra sin LUT **[P]** (ΔE ≤2 en parches). Cálida: desplazamiento de tono medio ≥5° en la dirección esperada y luma ±10 %; sin banding visible en el degradado. | `FLT-05_{lut}_frame.png`, `FLT-05_psnr.txt`, `FLT-05_hue.txt` | PASS si identidad no altera y la cálida aplica el cambio esperado. FAIL si la LUT se ignora o rompe el color. |
| **FLT-A1** · LUT corrupta | FX13 corrupta (cabecera truncada) y `.cube` con valores `NaN`. | **400** al guardar (preferido) o job `failed` ≤5 s con mensaje que nombre la LUT; 0 bytes en `out/`; staging purgado ≤60 s; servicio `/health` 200 después; sin volcado de FFmpeg. | `FLT-A1_http.txt`, `FLT-A1_jobs.json`, `FLT-A1_staging.txt` | PASS si rechaza o falla limpio. FAIL si 500, crash, job colgado o MP4 sin filtro promovido como bueno. |
| **FLT-A2** · LUT fuera de raíz o formato no admitido | `../../x.cube`, absoluta fuera de raíz, `.png` renombrado a `.cube`, archivo de 64 MB (>16 MB) **[P]**. | **400/403** con path `filters.lut`; 0 lecturas del canario; nunca se pasa la ruta del usuario como opción de filtro. | `FLT-A2_http.txt`, `FLT-A2_canario.txt` | PASS si todas se rechazan. FAIL si una se acepta o se lee fuera de la raíz. |
| **FLT-A3** · Pila completa | 5 filtros + 2 transiciones + 3 textos + logo + música en 3 escenas. | Render `succeeded`; grafo <20 000 caracteres; pared ≤2× el mismo proyecto sin efectos (n=3, mediana) **[P]**; RSS pico ≤2 GB (Job Object); sin errores en stderr salvo warnings permitidos. | `FLT-A3_cmd.txt`, `FLT-A3_times.json`, `FLT-A3_rss.txt`, `FLT-A3_out.mp4` | PASS si compone todo y el coste está acotado. FAIL si el grafo explota, OOM o el resultado pierde una capa. |
| **FLT-A4** · Parámetros inválidos | `brightness=1e9`, `contrast="50; rm"`, `lut` objeto, `blur=-5`, `grayscale=2`. | **400** con path del campo; sin job; el argv no cambia. | `FLT-A4_http.txt`, `FLT-A4_cmd.txt` | PASS si todos se rechazan. FAIL si uno llega a FFmpeg o se satura en silencio. |

---

### 3.5 Ken Burns (`KB`)

**Precondición común**
- Escena de imagen FX11 de 6 s, 720p30; `kenBurns{from,to,pan}`; para medir escala, un cuadrado blanco de 100×100 px en el centro del fixture y su bbox en el primer y último frame.
- Regla de producto: Ken Burns es **solo para imágenes**; sobre vídeo se ignora con aviso o se rechaza (D-V11-06).

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **KB-01** · Zoom in | `from=1.00`, `to=1.10`, sin pan; medir bbox del cuadrado en frame 0 y en el último. | Escala inicial 1.00 ±2 %; final 1.10 ±2 % **[P]**; duración 6.0 s ±1 frame; 0 barras negras (borde negro ≤0.5 % del área) **[P]**; el centro no se desplaza >2 px. | `KB-01_first.png`, `KB-01_last.png`, `KB-01_bbox.txt`, `KB-01_out.ffprobe.json` | PASS si el zoom es suave y termina en la escala pedida. FAIL si no hay movimiento, si salta o si aparecen bordes. |
| **KB-02** · Zoom out + pan | `from=1.15`, `to=1.00`, `pan=left`; medir desplazamiento por frame. | Movimiento monótono; desplazamiento máximo ≤2 px/frame a 30 fps **[P]**; sin reversiones >1 px; escala final 1.00 ±2 %; 0 frames negros. | `KB-02_frames/`, `KB-02_motion.csv` | PASS si el paneo es continuo. FAIL si tiembla, invierte o deja hueco. |
| **KB-03** · KB + texto + transición | KB + 2 textos + `fade-0.5` de entrada; comprobar que el texto **no** se zoomea. | El texto mantiene su bbox (±2 px) durante toda la escena, aunque la imagen se mueva **[P]**; la transición dura 0.5 s ±1 frame; composición correcta. | `KB-03_{t}_frame.png`, `KB-03_bbox.csv` | PASS si el texto queda fijo sobre la imagen. FAIL si el texto se amplía con la imagen o desaparece. |
| **KB-A1** · Ken Burns sobre vídeo | `kenBurns.enabled=true` en escena `kind=video` (FX1). | **400** con path `scene[i].kenBurns` («solo imágenes») **o** no-op con aviso explícito; si es no-op, PSNR contra el mismo render sin KB ≥50 dB **[P]** y el aviso aparece en respuesta/log. Nunca zoom silencioso. | `KB-A1_http.txt`, `KB-A1_psnr.txt`, `KB-A1_job.log` | PASS si rechaza o ignora con aviso verificable. FAIL si aplica zoom al vídeo sin decirlo. |
| **KB-A2** · Parámetros extremos | `to=0.5`, `to=3.0`, `pan=diagonal`, duración 0.1 s y 1200 s. | **400** fuera del rango aprobado (`1.00 ≤ escala ≤ 1.50` **[P]**); duración <1 frame → 400 o mínimo 1 frame declarado; sin división por cero, NaN ni grafo inválido; la duración total no cambia. | `KB-A2_http.txt`, `KB-A2_jobs.json` | PASS si valida o acota sin romper. FAIL si produce frames negros, cuelgue o duración distinta. |

---

### 3.6 Velocidad 0.5×–2.0× (`SPD`)

**Precondición común**
- FX1 (6 s, sin audio) y FX10 (6 s, con audio y clics) como escenas; `scene.speed` en el rango aprobado; export 720p30.
- Fórmula de control: `duración_salida = (out − in) / speed` ±1 frame; `frames = round(duración × 30)` ±1.
- Pitch: FX8 es un tono puro de 440 Hz; la tasa de cruces por cero (ZCR) a 48 kHz para 440 Hz es 2×440/48000 = **0.01833**; `atempo` debe conservarla ±5 % **[P]**.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **SPD-01** · 0.5× | Clip de 6 s a `speed=0.5`. | Duración 12.0 s ±1 frame (360 frames ±1); PTS monótonos; sin frame congelado >2 frames seguidos (a 30 fps, 0.5× de 30 fps no debería duplicar) **[P]**. | `SPD-01_out.ffprobe.json`, `SPD-01_pts.txt` | PASS si la duración y los frames cuadran. FAIL si no ralentiza o pierde frames. |
| **SPD-02** · 2.0× | Clip de 6 s a `speed=2.0`. | Duración 3.0 s ±1 frame (90 frames ±1); PTS monótonos; 0 PTS duplicados. | `SPD-02_out.ffprobe.json`, `SPD-02_pts.txt` | PASS si acelera exacto. FAIL si el audio o el vídeo no escalan. |
| **SPD-03** · Sincronía A/V | FX10 con clics a 0/2/4 s a 0.5× y 2.0×; medir clics de salida. | Δ A/V ≤33.3 ms en los tres puntos **[F]**; audio y vídeo con la misma duración ±1 frame; sin deriva acumulada al final (≤1 frame). | `SPD-03_{speed}_clics.csv`, `SPD-03_out.ffprobe.json` | PASS si los tres clics siguen alineados. FAIL si el audio se desfasa o se corta. |
| **SPD-04** · Pitch preservado | FX8 (440 Hz) como audio de escena a 0.5× y 2.0×; medir ZCR. | ZCR 0.01833 ±5 % en ambos casos **[P]**; loudness sin cambio >2 LU; no hay efecto «voz de pato» (si el contrato elige varispeed, se declara **N/A** y se documenta, D-V11-09). | `SPD-04_zcr.txt`, `SPD-04_ebur128.txt` | PASS si el tono se mantiene. FAIL si el pitch sube/baja con la velocidad sin decisión escrita. |
| **SPD-05** · Velocidad + transición + texto | 3 escenas de 4 s con speeds 0.5/1.0/2.0, dos transiciones de 0.5 s, texto con `at`/`until` dentro de la escena 1. | Total = (4/0.5 + 4/1 + 4/2) − 1.0 = **11.0 s ±1 frame** **[P]**; el texto aparece en el tiempo de salida correspondiente ±1 frame; transiciones correctas. | `SPD-05_out.ffprobe.json`, `SPD-05_text_frames/` | PASS si la aritmética y el texto cuadran. FAIL si el texto se descoloca o el total no cuadra. |
| **SPD-A1** · Fuera de rango | `0.25`, `0.49`, `2.01`, `3.0`, `0`, `-1`, `NaN`, `"2x"`. | **400** con path `scene[i].speed` y rango permitido; 0 jobs; el argv no cambia. | `SPD-A1_http.txt`, `SPD-A1_jobs.json` | PASS si todos se rechazan. FAIL si uno se acepta o se satura. |
| **SPD-A2** · Clip mínimo a 2× | FX16 de 0.2 s a 2.0× → 0.1 s. | Salida ≥1 frame (4 frames a 30 fps sería lo esperado: 0.1 s = 3 frames); si el contrato exige mínimo, **400** con motivo; nunca MP4 de 0 frames ni job `succeeded` sin stream. | `SPD-A2_out.ffprobe.json`, `SPD-A2_http.txt` | PASS si hay salida válida o rechazo claro. FAIL si el MP4 no decodifica. |
| **SPD-A3** · 24 fps a 0.5× y 2× | FX16 (24 fps) a 0.5× y 2× con salida 30 fps. | 0.5×: contenido a 12 fps → duplicados esperados; el hueco máximo entre frames distintos ≤83 ms +1 frame **[P]**. 2×: contenido a 48 fps → se descartan frames; no hay PTS duplicados ni salto >1 frame. | `SPD-A3_{speed}_frames.csv`, `SPD-A3_out.ffprobe.json` | PASS si el patrón de duplicado/descarte es el esperado. FAIL si hay tirones >2 frames o frames negros. |

---

### 3.7 Logo / marca de agua (`LOGO`)

**Precondición común**
- Logo FX12 (512×512 RGBA, cruz y borde) sobre escena FX11 de 5 s, 720p30; posición en % del ancho/alto, escala en % del ancho, opacidad 0–100.
- Medición: bbox del logo por `cropdetect` sobre el frame; color en la cruz para opacidad; comparación con el render sin logo.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **LOGO-01** · Cuatro esquinas y centro | `(5,5)`, `(95,5)`, `(5,95)`, `(95,95)`, `(50,50)` con escala 12 %. | Centro del logo a ±2 px de la posición pedida **[P]**; logo **completamente** dentro del encuadre (0 px fuera); tamaño 12 % del ancho ±2 % **[P]**. | `LOGO-01_{pos}_frame.png`, `LOGO-01_bbox.csv` | PASS si las cinco posiciones caen donde se pide. FAIL si se desplaza, se recorta o cambia de tamaño. |
| **LOGO-02** · Opacidad | 25 %, 50 %, 100 % sobre fondo liso. | Mezcla alfa medida ±5/255 del valor esperado **[P]**; a 0 % el logo es invisible pero el job termina `succeeded`; no hay halo. | `LOGO-02_{op}_frame.png`, `LOGO-02_pixels.txt` | PASS si la opacidad es lineal y medible. FAIL si ignora el valor o deja restos. |
| **LOGO-03** · Escala | 5 %, 25 %, 50 % del ancho. | Ancho medido ±2 % del esperado **[P]**; proporción 1:1 ±1 %; no se pixela en exceso (blurdetect estable ±20 %). | `LOGO-03_{s}_frame.png`, `LOGO-03_bbox.txt` | PASS si escala proporcional. FAIL si deforma o no escala. |
| **LOGO-04** · Logo en 9:16 y 1:1 | Exportar el mismo proyecto a `9x16` y `1x1` con logo al 12 %. | El logo sigue dentro del encuadre, con el mismo % de ancho ±2 %; no se recorta; la posición relativa se respeta ±2 px. | `LOGO-04_{preset}_frame.png`, `LOGO-04_bbox.csv` | PASS si se recoloca con el cambio de lienzo. FAIL si queda fuera o se estira. |
| **LOGO-A1** · Logo fuera de encuadre | `x=150`, `y=-50`, `x=-10`, `y=120`. | **400** con path `logo.x`/`logo.y`, **o** clamp al interior con aviso; si clamp: 0 px fuera del frame y aviso verificable en respuesta/log. Nunca logo parcial. | `LOGO-A1_http.txt`, `LOGO-A1_frame.png`, `LOGO-A1_job.log` | PASS si rechaza o clamp con aviso. FAIL si aparece recortado o desaparece en silencio. |
| **LOGO-A2** · Formato no admitido | SVG, GIF animado, MP4, PNG sin alpha. | **400** con path `logo.asset` y motivo; el MP4 no se usa como overlay; si se acepta PNG sin alpha, se declara (fondo opaco) o se rechaza. | `LOGO-A2_http.txt`, `LOGO-A2_jobs.json` | PASS si el formato se valida por contenido. FAIL si un SVG/vídeo llega a FFmpeg o produce basura. |
| **LOGO-A3** · Logo enorme o corrupto | 8000×8000, 0 B, PNG truncado, 20 MP. | **400** por límite (≤20 MP y ≤16 MB **[P]**) o escalado declarado; corrupto → job `failed` ≤5 s; sin OOM; staging purgado. | `LOGO-A3_http.txt`, `LOGO-A3_jobs.json` | PASS si rechaza o degrada limpio. FAIL si OOM, cuelgue o crash. |
| **LOGO-A4** · Ruta fuera de raíz | `../../canario.png`, UNC, ADS, absoluta. | **400/403**; 0 lecturas del canario; logo no se aplica. | `LOGO-A4_http.txt`, `LOGO-A4_canario.txt` | PASS si todas se rechazan. FAIL si una lee fuera de la raíz. |
---

### 3.8 Presets de export 9:16, 1:1 y 1080p (`EXP`)

**Precondición común**
- Proyecto de 3 escenas de 4 s con FX11 (marcadores en el punto medio de cada borde, al 5 %, círculo central y rejilla) a 16:9; audio FX3 con clics.
- Preset actual `mp4-720p30` **[F]** y presets nuevos con ids a fijar (**D-V11-08**); el caso verifica dimensiones, geometría, duración y contrato, no el nombre.
- El worker impone un techo de memoria de **2048 MB** por Job Object (`core/service/worker.py:75`), por lo que 1080p debe medirse **dentro de ese techo o con una decisión explícita**.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **EXP-01** · 9:16 con recorte correcto | Exportar a 1080×1920. | Dimensiones exactas 1080×1920; `sample_aspect_ratio` 1:1 y DAR 9:16 **[F]**; recorte **central**: los marcadores **izquierdo/derecho desaparecen** y los **superior/inferior permanecen**; simetría del recorte ±4 px **[P]**; 0 barras negras (≤0,5 % del área) **[P]**; duración y fps ±1 frame. | `EXP-01_out.ffprobe.json`, `EXP-01_frame.png`, `EXP-01_markers.txt` | PASS si el encuadre es central, sin deformación ni barras. FAIL si estira, deja bandas o recorta descentrado. |
| **EXP-02** · 1:1 | Exportar a 1080×1080. | Dimensiones exactas; DAR 1:1; recorte simétrico arriba/abajo ±4 px; los marcadores **superior/inferior desaparecen** y los **laterales permanecen**; el círculo central sigue siendo círculo (ratio de ejes ±1 %) **[P]**; sin barras. | `EXP-02_out.ffprobe.json`, `EXP-02_frame.png`, `EXP-02_circle.txt` | PASS si no hay deformación y el recorte es el declarado. FAIL si el círculo se vuelve elipse, aparecen bandas o se recorta el eje equivocado. |
| **EXP-03** · 1080p medido | Exportar a 1920×1080 30 fps; medir pared, RSS pico del árbol y memoria libre. | 1920×1080, 30/1, h264+aac; **RSS pico ≤1,8 GB** (10 % bajo el techo de 2 GB) **[P]**; pared ≤2,5× el mismo proyecto en 720p (n=3, mediana) **[P]**; RAM libre ≥2 GB al terminar; sin paging >50 páginas/s **[P]**; decodifica sin errores. | `EXP-03_out.ffprobe.json`, `EXP-03_times.json`, `EXP-03_rss.txt`, `EXP-03_maquina.txt` | PASS si cumple los cuatro umbrales. **Si el RSS pico >1,8 GB o el pared >2,5×: BLOCKED por D-V11-04**, no PASS ni FAIL de implementación. |
| **EXP-04** · 720p30 sin cambios | Exportar el mismo proyecto con `mp4-720p30` y comparar con la línea base actual. | 1280×720, 30/1, h264+aac 48 kHz estéreo; duración esperada ±1 frame; faststart (`moov` antes de `mdat`); PSNR contra el render de `REG-02` ≥45 dB **[P]**; preset devuelto = solicitado. | `EXP-04_out.ffprobe.json`, `EXP-04_psnr.txt` | PASS si el contrato actual no cambia. FAIL si el pack altera dimensiones, fps, códec o duración. |
| **EXP-05** · Round-trip y dedupe por preset | Exportar el mismo documento con 720p, 1080p y 9:16; consultar jobs y repetir. | Cada respuesta devuelve su `preset`; tres jobs distintos (no se deduplican entre presets) **[P]**; repetir el mismo preset con la misma revisión sigue la política D-06 del plan base; 0 escrituras cruzadas al mismo `out/`. | `EXP-05_jobs.json`, `EXP-05_out_ls.txt` | PASS si preset y dedupe son correctos. FAIL si un preset reutiliza el job de otro o devuelve dimensiones ajenas. |
| **EXP-A1** · 1080p excede recursos | Forzar `memory_limit_mb=512` en el job (parámetro de prueba) y exportar 1080p de 60 s; repetir con 1024 MB. | Job `failed` ≤15 s, mensaje que mencione memoria/límite/exit code; **no** muere el servicio (`/health` 200 después); 0 bytes en `out/`; staging purgado ≤60 s; sin volcado ni OOM killer. | `EXP-A1_jobs.json`, `EXP-A1_error.txt`, `EXP-A1_health.txt`, `EXP-A1_out_ls.txt` | PASS si falla limpio y el servicio sobrevive. FAIL si el proceso desaparece, el error es un crash o queda un parcial. |
| **EXP-A2** · 9:16 desde fuente ya vertical | Fuente 1080×1920 → preset 9:16. | Sin doble recorte: ancho conservado al 100 % (pérdida ≤2 %) **[P]**; escala ≤1,0 (no reescala hacia arriba) **[P]**; sin barras; duración intacta. | `EXP-A2_out.ffprobe.json`, `EXP-A2_frame.png` | PASS si no vuelve a recortar. FAIL si pierde laterales o amplía de más. |
| **EXP-A3** · 9:16 desde 4:3 | Fuente 4:3 con círculo y marcadores. | Recorte central declarado; círculo sigue círculo (ejes ±2 %) **[P]**; no hay estiramiento; los marcadores laterales se recortan simétricamente ±4 px. | `EXP-A3_frame.png`, `EXP-A3_circle.txt` | PASS si la geometría es correcta. FAIL si deforma o recorta asimétrico. |
| **EXP-A4** · 1080p con disco lleno | Aplicar A-06 del plan base al preset 1080p (VHDX o inyección `ENOSPC`). | Job `failed` legible; staging borrado; proyecto y salidas previas intactos; editor usable; 0 archivos de 0 B en `out/`. | `EXP-A4_error.png`, `EXP-A4_jobs.json`, `EXP-A4_out_ls.txt` | PASS si falla limpio. FAIL si corrompe o deja restos. **BLOCKED** si D-09 sigue sin resolverse, con causa declarada. |

---

### 3.9 Plantillas de proyecto (`TPL`)

**Precondición común**
- Plantilla FX17 (manifiesto versionado: 3 escenas, 1 música, 1 logo, 2 textos, duración esperada 12 s) y una copia corrupta.
- Medición: `GET /projects/<id>` tras crear, `ffprobe` del export, hash del archivo de plantilla antes/después.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **TPL-01** · Crear desde plantilla | Crear proyecto desde FX17. | **201**; `revision=0`; 3 escenas, 1 música, 1 logo y 2 textos; duraciones y transiciones iguales al manifiesto ±1 frame; el proyecto abre y previsualiza. | `TPL-01_http.txt`, `TPL-01_project.json`, `TPL-01_pane.png` | PASS si el proyecto es editable y coincide. FAIL si faltan capas, duplica escenas o nace corrupto. |
| **TPL-02** · Exportar la instancia | Exportar TPL-01 sin editar. | Duración = esperada del manifiesto ±1 frame; música audible (≥−30 LUFS); logo visible en el frame; textos presentes; sin errores. | `TPL-02_out.mp4`, `TPL-02_out.ffprobe.json`, `TPL-02_frame.png` | PASS si el export materializa la plantilla. FAIL si alguna capa se pierde. |
| **TPL-03** · Editar sin mutar la plantilla | Cambiar texto, recortar una escena y exportar; comparar hash de la plantilla. | El proyecto editado guarda y exporta; **hash de la plantilla sin cambios**; una segunda instancia nace del original, no de la editada. | `TPL-03_sha256_antes.txt`, `TPL-03_sha256_despues.txt`, `TPL-03_out.mp4` | PASS si la plantilla es inmutable. FAIL si editarla la modifica o contamina otras instancias. |
| **TPL-A1** · Plantilla con medio faltante | Borrar un asset referenciado y crear/exportar. | **400** al crear, **o** proyecto con `needsRelink=true` y export **bloqueado** (400/409) con mensaje que nombre el asset; nunca render con negro/silencio silencioso; no se crea proyecto a medias. | `TPL-A1_http.txt`, `TPL-A1_project.json`, `TPL-A1_jobs.json` | PASS si detecta y bloquea. FAIL si exporta un MP4 incompleto o crea un proyecto irrecuperable. |
| **TPL-A2** · Plantilla corrupta o futura | JSON inválido, `schemaVersion` desconocida, 101 escenas, ruta con `../`. | **400** con motivo y path; el contador de proyectos no cambia (sin residuo); no se lee fuera de la raíz. | `TPL-A2_http.txt`, `TPL-A2_projects.json`, `TPL-A2_canario.txt` | PASS si rechaza sin residuo. FAIL si deja un proyecto huérfano o lee fuera. |
| **TPL-A3** · Plantilla al límite | 100 escenas + música + logo + textos, con transiciones. | Crea y exporta dentro de los límites (grafo <20 000 caracteres, RSS ≤2 GB); o falla limpio indicando el límite; sin OOM ni MP4 truncado. | `TPL-A3_cmd.txt`, `TPL-A3_jobs.json`, `TPL-A3_rss.txt` | PASS si respeta límites o falla limpio. FAIL si cuelga o corrompe. |

---

## 4. Adversariales exigidos: índice de cobertura

Esta tabla es la lista de control que pidió Tormen. Cada fila apunta al caso que la ejecuta; **no se cuenta dos veces**.

| # | Adversario exigido | Caso(s) | Resultado exigido |
|---|---|---|---|
| 1 | Música de asset inexistente | `MUS-A1` | 400 en `music.asset`; si desaparece después, job `failed` limpio |
| 2 | Música de tipo vídeo | `MUS-A2` | 400; nunca render de vídeo como audio |
| 3 | Música más larga que el vídeo | `MUS-05`, `MUS-04`, `MUS-A7` | recorte exacto ±1 frame o loop sin huecos |
| 4 | Vídeo sin audio + música | `MUS-08` | música audible; 0 silencios ≥100 ms |
| 5 | Ducking que no bombea | `MUS-A5` (+`MUS-06`) | variación ≤1 dB con señal estacionaria; 6–12 dB solo con voz |
| 6 | Transición más larga que el clip | `TRX-A1` | 400 con máximo, o clamp con aviso; nunca escena vacía |
| 7 | Texto con acentos y emojis | `TXT-01`, `TXT-A3` | literal, sin romper filtro; emoji con glifo o fallback declarado |
| 8 | Fuente inexistente | `TXT-A1` (+`TXT-A2`) | 400 o fallback declarado |
| 9 | LUT corrupta | `FLT-A1` | 400 o job `failed` ≤5 s; sin crash ni parcial |
| 10 | Ken Burns sobre vídeo | `KB-A1` | 400 o no-op con aviso; PSNR ≥50 dB si se ignora |
| 11 | Velocidad extrema 0.5/2.0 (sincronía A/V) | `SPD-01`, `SPD-02`, `SPD-03` | duración exacta ±1 frame; Δ A/V ≤33,3 ms |
| 12 | Logo fuera de encuadre | `LOGO-A1` | 400 o clamp con aviso; 0 px fuera |
| 13 | 1080p que excede recursos | `EXP-A1` (+`EXP-03`) | `failed` ≤15 s, servicio vivo, 0 restos; nunca OOM |
| 14 | Export 9:16 con recorte correcto | `EXP-01` | 1080×1920, recorte central simétrico, sin barras |

---

## 5. Regresión del MVP actual (`REG`)

**Regla:** el pack v1.1 no puede avanzar si el MVP retrocede. Estos seis casos se ejecutan **en la misma corrida** que los casos nuevos y con el mismo artefacto.

| Caso | Pasos | Esperado y umbral | Evidencia | Criterio |
|---|---|---|---|---|
| **REG-01** · Los 259 tests siguen verdes | `cd core && python -m unittest discover -s tests` y comparar la lista de IDs con la línea base. | `Ran N tests`, `OK (skipped=2)`, **N ≥ 259**, 0 failures/errors **[F]**; **ninguno de los 259 IDs existentes desaparece ni se renombra**; los nuevos se suman. | `REG-01_unittest.txt`, `REG-01_testids.txt`, `REG-01_baseline_ids.txt` | PASS si N≥259, OK y los 259 IDs siguen presentes. FAIL si falta un test, se salta uno nuevo sin justificar o hay rojo. |
| **REG-02** · E2E 720p30 sin cambio de contrato | `python core/scripts/e2e_http_check.py` (o el comando documentado en `core/README.md`) con el fixture del e2e. | `ok:true`, `failures:[]`; health 200; crear 201; añadir medios 201; GET 200; revisión vieja 409; export 202; job `succeeded/done/100`; salida **1280×720, 30/1, h264+aac 48 kHz estéreo**, duración = esperada ±1 frame; `Range` 206; `moov` delante de `mdat`; **0 warnings nuevos no declarados** (los `Fontconfig error` de drawtext ya están declarados en el Anexo A.3) **[F]**. | `REG-02_e2e-report.json`, `REG-02_out.ffprobe.json`, `REG-02_range.txt` | PASS si el contrato es idéntico al de `core/logs/e2e-http-report.json` (2026-11-08). FAIL si cambia dimensión, fps, códec, duración, estados o códigos. |
| **REG-03** · Compatibilidad de esquema v1→v2 | Abrir un proyecto v1 real del repo, guardarlo sin cambios, reabrir; exportar; repetir con campos desconocidos. | v1 se abre sin «corrupto»; al guardar sube a v2 conservando **todos** los campos y valores; los campos desconocidos se preservan o se rechazan con aviso explícito (nunca se borran en silencio); export idéntico al de v1 ±1 frame; `baseRevision` sigue devolviendo 409 cuando toca. | `REG-03_v1_project.json`, `REG-03_v2_project.json`, `REG-03_migracion.txt`, `REG-03_out.mp4` | PASS si migra sin pérdida y exporta igual. FAIL si rompe proyectos existentes o borra campos. |
| **REG-04** · Smoke U1–U4 | Subconjunto: U1-03/05, U2-03/04/07/08/10, U3-01/03/05, U4-03/04/07. | Los 12 casos siguen PASS con sus criterios originales; ningún 500 nuevo; el proyecto se guarda, reabre y exporta; el texto con acentos (U2-07) sigue literal. | `REG-04_*.png/json` según plan base | PASS si los 12 mantienen veredicto. FAIL si alguno degrada; se reporta como regresión introducida, no como deuda. |
| **REG-05** · Rendimiento no degradado | Export 720p del mismo fixture, n=3; p95 del gateway durante el export. | Pared mediana ≤1,2× la línea base de REG-02 **[P]**; p95 ≤ `max(1,2×base, base+5 ms)` **[F: D-01]**; RSS pico ≤1,1× la línea base **[P]**. | `REG-05_times.json`, `REG-05_p95.txt`, `REG-05_rss.txt` | PASS si no hay degradación >20 %. FAIL si el pack duplica el coste del caso base. |
| **REG-06** · Control negativo de los controles nuevos | En una copia del artefacto, desactivar **uno por uno**: validación de `music.asset`, parseo de LUT, clamp de logo, límite de transición, guardia de memoria 1080p y validación de preset. | Cada desactivación hace **fallar al menos un test nuevo** y el fallo nombra el control; si un control desactivado no rompe nada, el test es decorativo y se reescribe **[F: §5.3 del plan base]**. | `REG-06_mutaciones.diff`, `REG-06_resultados.txt` | PASS si los 6 controles tienen test que los protege. FAIL si alguno pasa con el control roto. |

---

## 6. Trazabilidad función → casos → decisión

| Función v1.1 | Casos funcionales | Adversariales | Decisión que la puede bloquear |
|---|---|---|---|
| Música | MUS-01…MUS-09 | MUS-A1…A7 | D-V11-02, D-V11-03, D-V11-05 |
| Transiciones | TRX-01…TRX-06 | TRX-A1…A4 | D-V11-01 |
| Texto | TXT-01…TXT-06 | TXT-A1…A5 | D-V11-10 |
| Filtros/LUT | FLT-01…FLT-05 | FLT-A1…A4 | D-V11-00 |
| Ken Burns | KB-01…KB-03 | KB-A1, KB-A2 | D-V11-06 |
| Velocidad | SPD-01…SPD-05 | SPD-A1…A3 | D-V11-09 |
| Logo | LOGO-01…LOGO-04 | LOGO-A1…A4 | D-V11-07 |
| Presets/export | EXP-01…EXP-05 | EXP-A1…A4 | D-V11-04, D-V11-08 |
| Plantillas | TPL-01…TPL-03 | TPL-A1…A3 | D-V11-11 |
| Regresión | REG-01…REG-06 | — | D-V11-12 |

---

## 7. Puerta del pack v1.1 (propuesta)

El pack no se declara listo por «los casos nuevos pasan». Se cierra cuando:

1. **Todos los casos funcionales principales** de cada familia están en PASS: MUS-01, TRX-01/02/03, TXT-01/02/03, FLT-01/02/05, KB-01, SPD-01/02/03, LOGO-01, EXP-01/02/03, TPL-01/02.
2. **Cero S1/S2 abiertos** en los adversariales de §4. Un solo S1 (path traversal, audio de vídeo como música, OOM, parcial promovido) cierra la puerta.
3. **REG-01 y REG-02 en PASS** en la misma corrida; REG-03 en PASS o BLOCKED con decisión declarada.
4. **Los 6 controles negativos** de REG-06 demuestran que sus tests muerden.
5. Todo **BLOCKED** tiene decisión D-V11-xx abierta, dueño y fecha; se cierra como «pack con deuda declarada», nunca como «aprobado».
6. Ningún umbral **[P]** se usa como puerta sin que Tormen lo apruebe o sin recalibración documentada con datos de esta máquina.

---

## 8. Decisiones necesarias

Ninguna la resuelve Dike. Cada una bloquea casos concretos.

| # | Decisión | Bloquea | Propuesta de Dike |
|---|---|---|---|
| **D-V11-00** | Superficie exacta del modelo v1.1 (nombres, `schemaVersion`, ubicación de música/logo/filtros) | Todos los round-trip y los paths de error | Fijarla en un ADR corto antes de implementar; que los tests validen comportamiento y no acoplen al nombre. |
| **D-V11-01** | ¿Las transiciones **solapan** (xfade real, total = Σd − Σt) o se mantiene fundido a negro sin solape? | TRX-03, TRX-04, SPD-05, TPL-01 | Solape real: es lo que el plan base ya exige (U2-10 y §4, Σ−Σ). **Medido hoy:** el worker hace fade in/out por escena y concatena (`worker.py:676-679`, `:716`), así que el `fade-N` actual no solapa y el total es Σd; el contrato del plan base y el artefacto **no coinciden**. Decidir cuál se corrige y hacerlo antes de construir el catálogo encima. |
| **D-V11-02** | Política de música: loop por defecto, recorte sin loop, fade por defecto | MUS-04, MUS-05, MUS-A6, MUS-A7 | `loop=false` por defecto, recorte exacto al fin del vídeo con fade-out de 0,5 s si el usuario no puso otro. |
| **D-V11-03** | Parámetros y medición del ducking | MUS-06, MUS-A5 | Profundidad 6–12 dB objetivo 8, ataque ≤150 ms, release ≤800 ms, ventana RMS 50 ms; medir por banda para aislar música de voz. |
| **D-V11-04** | 1080p: ¿se sube el techo de 2 GB del Job Object o se exige caber en 1,8 GB? ¿Se publica en v1.1 o queda BLOCKED? | EXP-03, EXP-A1 | Medir primero con material real; si RSS pico >1,8 GB, no publicar 1080p en v1.1 hasta decidir techo nuevo. No subir el límite «por si acaso». |
| **D-V11-05** | Target de loudnorm y si se aplica por defecto o solo al export | MUS-07 | −14 LUFS / −1 dBTP, solo si el usuario activa «normalizar»; no tocar el audio por sorpresa. |
| **D-V11-06** | Ken Burns sobre vídeo: rechazo 400 o no-op con aviso | KB-A1 | Rechazo 400 con mensaje «Ken Burns solo para imágenes»; el no-op silencioso confunde. |
| **D-V11-07** | Logo fuera de encuadre: clamp o rechazo | LOGO-A1 | Clamp al interior con aviso visible; rechazar por un decimal de posición es hostil. |
| **D-V11-08** | Ids de preset y política de recorte (centro vs «inteligente») | EXP-01/02/05 | Centro determinista; ids `mp4-1080p30-9x16`, `mp4-1080p30-1x1`, `mp4-1080p30`; el recorte inteligente no se promete sin medición. |
| **D-V11-09** | Velocidad: ¿`atempo` (preserva pitch) o varispeed (cambia pitch)? | SPD-04 | `atempo`: la voz no debe sonar a pato; si se quiere varispeed, que sea una opción explícita y el caso cambia a N/A documentado. |
| **D-V11-10** | Fuentes: allowlist de fuentes del sistema, emoji a color y fallback | TXT-A1, TXT-A3 | Permitir un directorio de fuentes propio + `segoeui`/`seguiemj`; fallback declarado; emoji sin glifo = S3, no S2. |
| **D-V11-11** | Plantillas: ¿copian assets o los referencian? ¿Qué pasa si falta uno? | TPL-01, TPL-02, TPL-A1 | Referenciar por ruta relativa con `needsRelink` y export bloqueado; copiar multiplica disco sin necesidad. |
| **D-V11-12** | Línea base de tests: ¿259 congelados o se permite crecer? | REG-01 | Congelar los 259 IDs; crecimiento permitido; cualquier baja exige justificación escrita y reemplazo equivalente. |

---

## 9. Límites de este anexo

- **No cubre** calidad artística (si la transición «queda bonita»), color management profesional, HDR, 4K, multicámara ni keyframes.
- **No cubre** publicación en redes ni requisitos de cada plataforma; solo el archivo de salida y su geometría.
- **No cubre** concurrencia de varios exports: el contrato sigue siendo 1 job; si cambia, repetir T02/EXP.
- **No cubre** macOS/Linux: los PASS son solo Windows 11 en esta máquina.
- **No decide** producto: los umbrales **[P]** son propuestas y las decisiones D-V11-xx son de Tormen.
- **No sustituye** la matriz U1–U4: el pack v1.1 se suma; si un caso nuevo contradice el plan base, se detiene y se eleva.
---

## Anexo A · Fixtures y recetas verificadas hoy (2026-11-08, 21:35–21:45 -04:00)

> Estas recetas **no son la función bajo prueba**: solo garantizan que el ejecutor y Dike miran el mismo material. Se corrieron en esta máquina con `ffmpeg n9.0.1`; los tamaños y duraciones son los medidos, no estimados.

### A.1 Fixtures

| ID | Receta (bash, desde el directorio de fixtures) | Medido |
|---|---|---|
| **FX8** | `ffmpeg -y -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=8" -af "loudnorm=I=-18:TP=-2:LRA=7" -ac 2 -c:a pcm_s16le fx8.wav` | 8.000000 s · 6 144 102 B · **−18.0 LUFS**, peak −17.3 dBFS |
| **FX9** | `ffmpeg -y -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=60" -f lavfi -i "sine=frequency=554.37:sample_rate=48000:duration=60" -filter_complex "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.5,volume=0.8,loudnorm=I=-18:TP=-2:LRA=7[a]" -map "[a]" -ac 2 -c:a pcm_s16le fx9.wav` | 60.000000 s · 46 080 102 B |
| **FX10** | `ffmpeg -y -f lavfi -i "color=c=0x224466:s=1280x720:r=30:d=12" -f lavfi -i "aevalsrc=0.3*sin(2*PI*1000*t)*lt(mod(t\,2)\,1.2):s=48000:d=12" -shortest -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 128k fx10.mp4` | 12.000000 s · 30/1 · 152 183 B (bursts de 1 kHz: 1.2 s on / 0.8 s off) |
| **FX11** | `ffmpeg -y -f lavfi -i "testsrc2=size=3840x2160:rate=1:duration=1" -vf "drawbox=x=200:y=200:w=400:h=400:color=0x404040:t=fill,drawbox=x=700:y=200:w=400:h=400:color=0x808080:t=fill,drawbox=x=1200:y=200:w=400:h=400:color=0xC0C0C0:t=fill,drawbox=x=1824:y=108:w=192:h=192:color=red:t=fill,drawbox=x=1824:y=1860:w=192:h=192:color=lime:t=fill,drawbox=x=108:y=984:w=192:h=192:color=blue:t=fill,drawbox=x=3540:y=984:w=192:h=192:color=yellow:t=fill" -frames:v 1 fx11.png` | 3840×2160 · rgb24 · 777 613 B · parches de gris 0x40/0x80/0xC0 · marcadores rojo/verde arriba-abajo y azul/amarillo izq.-der., al 5 % |
| **FX12** | `ffmpeg -y -f lavfi -i "color=c=black@0.0:s=512x512:d=1,format=rgba" -vf "drawbox=x=0:y=0:w=512:h=512:color=white@1.0:t=8,drawbox=x=248:y=64:w=16:h=384:color=white@1.0:t=fill,drawbox=x=64:y=248:w=384:h=16:color=white@1.0:t=fill" -frames:v 1 fx12.png` | 512×512 · **rgba** · 2 285 B |
| **FX13** | `python mklut.py` con un generador de LUT identidad 33³ (3 líneas de cabecera + 35 937 filas) | `fx13-identity.cube` 970 349 B · `fx13-corrupt.cube` 34 B (cabecera truncada) |
| **FX14** | `cp /c/Windows/Fonts/segoeui.ttf fx14-ok.ttf`; `head -c 1048576 /dev/urandom > fx14-corrupt.ttf` | 960 076 B válida · 1 048 576 B corrupta |
| **FX15** | 3×`color` 4 s (rojo/verde/azul) + `drawtext=text='%{n}'` + `concat=n=3:v=1:a=0` | 12.000000 s · **360 frames** · 30/1 · 257 605 B |
| **FX16a** | `color=gray` 1280×720 30 fps, `-t 0.2` | 0.200000 s · **6 frames** |
| **FX16b** | `testsrc2=size=640x360:rate=24:duration=3` | 3.000000 s · 24/1 · 72 frames |
| **FX17** | Manifiesto JSON de plantilla (A.4) | JSON válido; 3 escenas, 2 textos, música, logo; duración esperada 11.0 s |

### A.2 Verificaciones hechas al escribir el plan

| Comprobación | Comando | Resultado literal |
|---|---|---|
| Suite actual | `cd core && python -m unittest discover -s tests` | `Ran 259 tests in 53.562s` · `OK (skipped=2)` |
| Filtros disponibles | `ffmpeg -filters` | presentes `xfade`, `zoompan`, `lut3d`, `sidechaincompress`, `loudnorm`, `atempo`, `ebur128`, `blurdetect`, `vignette`, `drawtext`, `overlay`, `amix` |
| Catálogo xfade | `ffmpeg -h filter=xfade` | `transition <int> from -1 to 57`; incluye `fade`, `slideleft`, `wipeleft`, `circleopen`, `zoomin` |
| LUT identidad | `ffmpeg -i fx11.png -vf lut3d=fx13-identity.cube …` + PSNR contra el original | **PSNR average 86.761 dB** → el umbral ≥45 dB de FLT-05 es holgado |
| LUT corrupta | `lut3d=fx13-corrupt.cube` | `Error initializing filters` · `Invalid data found when processing input`; exit ≠ 0, sin crash |
| Emoji con fuente por defecto | `drawtext` con `segoeui.ttf` | frame: `OK □□ fin` (**tofu**), exit 0 |
| Emoji con `seguiemj.ttf` | `drawtext … fontfile=seguiemj.ttf` | frame: `OK 🎬 ✅ fin` en **monocromo**, exit 0 |
| Techo de memoria del worker | `core/service/worker.py:75` | `DEFAULT_MEMORY_LIMIT_MB = 2048` |
| Contrato 720p actual | `core/logs/e2e-http-report.json` | 1280×720 · 30/1 · h264+aac · 8 310 551 B · 25.566667 s · `ok:true` |

**Consecuencias que ya están incorporadas al plan:**
1. `TXT-A3` exige **no tofu** cuando hay fuente con glifos; hoy `seguiemj.ttf` existe y produce glifos monocromos, así que «soporte emoji» es alcanzable. El color es S3, no bloqueo.
2. `FLT-A1` puede exigir que la LUT corrupta falle **antes** de FFmpeg (400) o que el job falle con mensaje legible; el fallo de FFmpeg es limpio, no un crash.
3. `EXP-03` usa 1,8 GB de RSS como umbral porque el Job Object mata a 2 GB; no es un número inventado.
4. `REG-02` permite los `Fontconfig error` de `drawtext` como warnings conocidos de esta máquina, pero **ningún warning nuevo**.

### A.3 Notas de entorno

- `ffmpeg` y `ffprobe` en PATH: `C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/`. En Git Bash, pasar rutas nativas `C:/...` a FFmpeg; `/c/...` no se traduce.
- `drawtext` emite `Fontconfig error: Cannot load default config file` en esta máquina incluso con `fontfile=`; no impide el render. Es warning declarado, no defecto del pack.
- Las rutas de fixtures deben ir bajo la raíz de medios del servicio; los casos adversariales de traversal usan un canario fuera de esa raíz y comprueban 0 lecturas.
- Los hashes de FX8–FX17 van a `run.json`; si un fixture no coincide, el caso es **BLOCKED por fixture distinto**, no PASS.

### A.4 Manifiesto FX17 (plantilla mínima)

```json
{
  "templateId": "tpl_lanzamiento_v11",
  "schemaVersion": 2,
  "name": "Lanzamiento · 3 escenas + música + logo",
  "assets": [
    {"id": "md_t1", "kind": "video", "path": "fx15.mp4"},
    {"id": "md_t2", "kind": "audio", "path": "fx8.wav"},
    {"id": "md_t3", "kind": "image", "path": "fx12.png"}
  ],
  "music": {"assetId": "md_t2", "volume": 80, "fadeIn": 1.0, "fadeOut": 1.5, "loop": true},
  "logo": {"assetId": "md_t3", "x": 92, "y": 8, "scale": 8, "opacity": 80},
  "scenes": [
    {"name": "A", "assetId": "md_t1", "in": 0.0, "out": 4.0, "transition": "fade-0.5", "text": [{"content": "Hola ñandú", "position": "bottom", "at": 0.5, "until": 3.5}]},
    {"name": "B", "assetId": "md_t1", "in": 4.0, "out": 8.0, "transition": "slideleft-0.5", "text": []},
    {"name": "C", "assetId": "md_t1", "in": 8.0, "out": 12.0, "transition": "circleopen-0.5", "text": [{"content": "Fin 🎬", "position": "center", "at": 0.5, "until": 3.0}]}
  ],
  "expected": {"duration": 11.0, "scenes": 3, "texts": 2, "transitions": 2}
}
```

> `expected.duration = 12.0 − 2×0.5 = 11.0 s` bajo el modelo de solape de **D-V11-01**. Si Tormen elige no solapar, el manifiesto y `TRX-03` cambian juntos; no se deja la discrepancia.
