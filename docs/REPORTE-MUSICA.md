# Música de fondo — entrega verificada (2026-11-08)

Fase 1 del pack v1.1, implementada y probada por el Padre (el subagente cayó por error del proveedor de modelos).

## Qué se añadió

- **Modelo** (`schema/project.schema.json`): `music` en la raíz `{assetId, volume 0-100, fadeIn 0-10, fadeOut 0-10, loop, in, out, ducking}` y `audio.normalize` (booleano).
- **Validación** (`project.py`): asset de música debe existir y ser `kind:"audio"`; rangos y tipos estrictos; `audio.normalize` booleano.
- **Motor** (`service/worker.py`):
  - `-stream_loop -1` cuando `loop`; entrada de audio extra al final de los inputs.
  - Cadena `aresample=48000,aformat=stereo,volume,atrim,asetpts` + `afade` de entrada/salida.
  - Mezcla con el audio de escenas con `amix=inputs=2:duration=first:normalize=0`.
  - `ducking:true` → `asplit` + `sidechaincompress` (threshold 0.05, ratio 8, attack 20, release 400).
  - `audio.normalize:true` → `loudnorm=I=-16:TP=-1.5:LRA=11`.
  - `assert_args_allowed` acepta valores negativos numéricos (`-stream_loop -1`).
- **API** (`service/app.py`): extensiones de audio `.mp3 .wav .m4a .aac .ogg .oga .flac .opus`; `kind:"audio"` detectado por extensión o por probe; un asset de audio **no crea escena** salvo `{"scene": true}`.
- **Contrato**: `core/CONTRATO.md` documenta `music`, `normalize` y la regla de escena.
- **Versión del servicio**: `0.3.1`.

## Evidencia

- Suite: `python -m unittest discover -s tests` → **267 tests OK (skipped=2)**.
- Tests nuevos: `tests/test_music.py` (8 casos: asset desconocido, tipo no-audio, rangos, tipos, `-stream_loop` presente/ausente).
- E2E real: `core/scripts/e2e_music_check.py` arranca un servicio propio en puerto libre, crea proyecto, importa `clipA.mp4` + `music.wav` sintético, fija `music{volume:40,fadeIn:0.5,fadeOut:1,loop:true,ducking:true}` + `normalize:true`, exporta y verifica:
  - job `succeeded`
  - MP4 3.726.505 B, **8.0 s**, h264 **1280×720**, audio **aac 2 canales 48 kHz**
  - `verdict: PASS`
- JSON de evidencia: `docs/qa/music-e2e.json`.

## Pendiente para la UI

El backend ya acepta música; el pane todavía no tiene el panel para elegirla. Entra en la fase de wire de UI (spec v3.2) junto con transiciones, estilos de texto, filtros y logo.
