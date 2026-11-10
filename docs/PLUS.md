# Versión Plus (opcional · solo documentada)

**La base funciona sin claves ni cuentas**: crear vídeos, editar a mano, voz local si ya la tienes
(SAPI de Windows, sin red), imágenes generadas en local, música sintética, exportar MP4.
Nada de lo de abajo es necesario, y su ausencia nunca bloquea nada: sin configurar, el editor
simplemente no ofrece ese modo.

Esto **no está implementado como producto de pago**; es el hueco (slot) que ya existe en el servicio y
cómo enchufarlo cuando el usuario quiera. Hermes actúa de orquestador: lee la configuración, y si hay
claves, usa el proveedor; si no, usa el local.

## El hueco que ya existe: proveedor HTTP

El servicio habla con **un endpoint HTTP tuyo** por tipo de contenido (`image`, `music`, `voice`):

| Variable de entorno (la lee el servicio al arrancar) | Para qué |
|---|---|
| `VE_PROVIDER_VOICE_URL` / `VE_PROVIDER_VOICE_KEY` | voz (TTS) |
| `VE_PROVIDER_IMAGE_URL` / `VE_PROVIDER_IMAGE_KEY` | imágenes |
| `VE_PROVIDER_MUSIC_URL` / `VE_PROVIDER_MUSIC_KEY` | música |
| `VE_PROVIDER_TIMEOUT_S` | tiempo máximo por petición |

La clave viaja solo como `Authorization: Bearer …`; nunca se registra, ni se devuelve, ni se guarda.

Contrato (el servicio hace `POST` JSON):

```json
{"kind":"voice","prompt":"texto a decir","duration":0,"options":{"voice":"…","rate":0}}
```

y espera **bytes del archivo** (audio/imagen) **o** JSON con `{"base64": "..."}`, `{"url": "..."}` o `{"path": "..."}`.

Los proveedores comerciales no hablan exactamente ese formato, así que se pone delante una **pasarela mínima**
(un script local de ~30 líneas, o un servicio tuyo) que traduce. Ejemplos de traducción (sin probar con claves reales):

| Quieres | La pasarela llama a | Notas |
|---|---|---|
| Voz profesional con **ElevenLabs** (el usuario lo llama «LevelX») | `POST https://api.elevenlabs.io/v1/text-to-speech/<voice_id>` con cabecera `xi-api-key: <tu clave>`, cuerpo `{"text": prompt, "model_id": "eleven_multilingual_v2"}` | devuelve `audio/mpeg`: se pasa tal cual como bytes |
| Imágenes con la **API de imágenes de OpenAI** | `POST https://api.openai.com/v1/images/generations` con `Authorization: Bearer <clave>`, cuerpo `{"model":"gpt-image-1","prompt":prompt,"size":"1536x1024"}` | la respuesta trae `data[0].b64_json`: se devuelve como `{"base64": …}` |
| Otros (Replicate, Stability, Suno, un modelo local…) | su API | mientras la pasarela devuelva bytes o `base64/url/path` funciona igual |

Pasos para el usuario que lo quiera:

1. Poner la pasarela a escuchar en `127.0.0.1` (puerto libre).
2. Definir `VE_PROVIDER_VOICE_URL=http://127.0.0.1:<puerto>/voice` (y la clave que **tu pasarela** use; el servicio la manda como Bearer).
3. Reiniciar el servicio con el lanzador (`core/start_service.py`); `/health` (con token) mostrará `voiceModes.http: true`.
4. Hermes: `ve_generate.py voice --provider http "texto"`; si falla o no hay clave, vuelve a `--provider local`.

Privacidad: con proveedores externos **el texto o el prompt sale de la máquina**. El editor lo marca como opt-in
(igual que `edge` y `web`, que ya están como opciones desactivadas por defecto).

## Qué NO hace la versión Plus

No compra nada, no guarda claves en el proyecto, no es requisito para publicar ni para usar el editor.