"""Adaptadores para dos proveedores que el usuario pidió: Nano Banana y ElevenLabs.

Son OPCIONES, no requisitos. Si no hay clave, el servicio lo dice con un mensaje
claro y la app sigue funcionando con el proveedor `local` (que no necesita red ni
clave y no cuesta nada).

Por qué no se resuelven con el proveedor `http` genérico: los dos tienen su propia
forma de pedir y de devolver, y meterlos a martillo en el contrato genérico habría
obligado al usuario a montar un traductor en medio. Con un adaptador, basta con
poner la clave.

Claves (variables de entorno, nunca en un archivo del proyecto):

    VE_GEMINI_KEY    · Nano Banana (Gemini 2.5 Flash Image)
    VE_ELEVEN_KEY    · ElevenLabs (texto a voz)

Modelo de imagen configurable con `VE_GEMINI_MODEL` (por defecto
`gemini-2.5-flash-image`). Voz con `VE_ELEVEN_VOICE` (por defecto una voz
española) y `VE_ELEVEN_MODEL` (por defecto `eleven_multilingual_v2`).
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

GEMINI_MODEL_DEFAULT = "gemini-2.5-flash-image"
ELEVEN_MODEL_DEFAULT = "eleven_multilingual_v2"
ELEVEN_VOICE_DEFAULT = "pNInz6obpgDQGcFmaJgB"  # voz neutra multilingüe

TIEMPO_MAX = 120.0


class ProveedorNoConfigurado(Exception):
    """Falta la clave. El mensaje es para el usuario, no un volcado técnico."""


def _clave(nombre: str) -> str:
    return (os.environ.get(nombre) or "").strip()


def gemini_disponible() -> bool:
    return bool(_clave("VE_GEMINI_KEY"))


def eleven_disponible() -> bool:
    return bool(_clave("VE_ELEVEN_KEY"))


# --------------------------------------------------------------------------- #
# Nano Banana (Gemini 2.5 Flash Image)
# --------------------------------------------------------------------------- #


def generar_imagen_gemini(prompt: str, destino: Path, *, options: dict | None = None) -> str:
    """Pide una imagen a Nano Banana y la escribe en *destino*.

    Devuelve una nota corta para `rights.notes`; nunca incluye la clave.
    """
    clave = _clave("VE_GEMINI_KEY")
    if not clave:
        raise ProveedorNoConfigurado(
            "Nano Banana no está configurado: define VE_GEMINI_KEY para generar imágenes con Gemini"
        )

    modelo = (os.environ.get("VE_GEMINI_MODEL") or GEMINI_MODEL_DEFAULT).strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{modelo}:generateContent"
    )

    # El estilo y el aspecto, si vienen, se añaden al prompt: la API de imagen
    # solo entiende texto.
    texto = prompt
    opciones = options or {}
    if opciones.get("style"):
        texto += f"\n\nEstilo: {opciones['style']}."
    if opciones.get("aspect"):
        texto += f"\nFormato: {opciones['aspect']}."

    payload = {
        "contents": [{"role": "user", "parts": [{"text": texto}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }

    datos = _post_json(url, payload, headers={"x-goog-api-key": clave}, que="Nano Banana")

    # La imagen viene en base64 dentro de la primera parte que la traiga.
    try:
        candidatos = json.loads(datos.decode("utf-8")).get("candidates") or []
        partes = (candidatos[0].get("content") or {}).get("parts") or []
    except (UnicodeDecodeError, json.JSONDecodeError, IndexError, AttributeError):
        raise RuntimeError("Nano Banana devolvió una respuesta que no se pudo leer") from None

    for parte in partes:
        crudo = (parte.get("inlineData") or parte.get("inline_data") or {}).get("data")
        if isinstance(crudo, str):
            destino.write_bytes(base64.b64decode(crudo, validate=True))
            return f"gemini:{modelo}"

    raise RuntimeError("Nano Banana no devolvió ninguna imagen (¿bloqueó el prompt?)")


# --------------------------------------------------------------------------- #
# ElevenLabs (texto a voz)
# --------------------------------------------------------------------------- #


def generar_voz_eleven(texto: str, destino: Path, *, options: dict | None = None) -> str:
    """Pide la voz a ElevenLabs y escribe el MP3 en *destino*.

    El llamador convierte a WAV si hace falta; aquí se guarda lo que llega.
    """
    clave = _clave("VE_ELEVEN_KEY")
    if not clave:
        raise ProveedorNoConfigurado(
            "ElevenLabs no está configurado: define VE_ELEVEN_KEY para generar voces"
        )

    voz = (os.environ.get("VE_ELEVEN_VOICE") or ELEVEN_VOICE_DEFAULT).strip()
    modelo = (os.environ.get("VE_ELEVEN_MODEL") or ELEVEN_MODEL_DEFAULT).strip()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voz}"

    opciones = options or {}
    payload = {
        "text": texto,
        "model_id": modelo,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    # La velocidad, si viene, se traduce a la estabilidad que entiende la API.
    if isinstance(opciones.get("rate"), (int, float)):
        payload["voice_settings"]["speed"] = max(0.7, min(1.2, 1 + opciones["rate"] / 100.0))

    datos = _post_json(
        url,
        payload,
        headers={"xi-api-key": clave, "Accept": "audio/mpeg"},
        que="ElevenLabs",
        espera_audio=True,
    )

    if not datos or datos[:1] == b"{":
        raise RuntimeError("ElevenLabs devolvió un error en vez de audio")

    destino.write_bytes(datos)
    return f"elevenlabs:{modelo}"


# --------------------------------------------------------------------------- #
# común
# --------------------------------------------------------------------------- #


def _post_json(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str],
    que: str,
    espera_audio: bool = False,
) -> bytes:
    cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    cabeceras = {"Content-Type": "application/json", "User-Agent": "hermes-video-editor"}
    cabeceras.update(headers)

    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_MAX) as respuesta:
            return respuesta.read()
    except urllib.error.HTTPError as exc:
        # El código, no la clave: el mensaje va a la interfaz.
        if exc.code in (401, 403):
            raise RuntimeError(f"{que} rechazó la clave (HTTP {exc.code})") from None
        if exc.code == 429:
            raise RuntimeError(f"{que} está al límite de peticiones (HTTP 429)") from None
        raise RuntimeError(f"{que} respondió HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError(f"no se pudo hablar con {que} (sin red o tardó demasiado)") from None
