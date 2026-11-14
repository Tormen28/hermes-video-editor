"""Generation engine (phase 3A): one contract, two providers.

* ``local`` — no network, no keys, no cost: an image is a graded gradient
  backdrop (no burned-in text unless ``options.caption``), a music bed is a
  synthetic chord pad (``options.mood``), a voice is Windows SAPI (offline).
* ``edge``  — voice only: Microsoft Edge neural voices via the ``edge-tts``
  package. Free, no key, but the text goes to Microsoft: explicit opt-in.
* ``web``   — image only: ``image.pollinations.ai`` (free, no key). The prompt goes
  to that service: explicit opt-in.
* ``http``  — POST the request as JSON to ``VE_PROVIDER_IMAGE_URL`` /
  ``VE_PROVIDER_MUSIC_URL`` with ``Authorization: Bearer $VE_PROVIDER_*_KEY``,
  then store whatever comes back (binary body, ``{url}``, ``{base64}`` or a
  ``{path}`` the provider wrote itself).

Hard rules:

* The API key is never printed, logged or stored: errors carry the kind and the
  HTTP status only. The key travels in one header and nowhere else.
* No URL configured means *no* HTTP attempt. The HTTP provider never falls back
  to a paid service behind the user's back — the caller gets a 400 and a message.
* Files always land under ``<mediaRoot>/generated/<projectId>/`` and the
  resulting relative path is re-checked against the media root before use.
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

import paths as path_rules
from service import worker

KINDS = ("image", "music", "voice")
PROVIDERS = ("local", "http", "edge", "web", "gemini", "eleven")
#: Which providers make sense for which kind.
#:
#: `gemini` (Nano Banana) and `eleven` (ElevenLabs) son OPCIONES, no requisitos:
#: si no hay clave configurada el servicio lo dice y se sigue con `local`. Ninguno
#: se usa nunca a espaldas del usuario.
KIND_PROVIDERS = {
    "image": ("local", "http", "web", "gemini"),
    "music": ("local", "http"),
    "voice": ("local", "http", "edge", "eleven"),
}

PROMPT_MIN = 1
PROMPT_MAX = 500
VOICE_TEXT_MAX = 1500
VOICE_DEFAULT_VOICE_EDGE = "es-ES-ElviraNeural"
IMAGE_STYLES = ("cinematic", "noir", "warm", "neon", "studio", "forest")
MUSIC_MOODS = ("calm", "epic", "tension", "bright")
ASPECTS = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1024, 1024)}
DURATION_MIN = 1.0
DURATION_MAX = 120.0
MUSIC_DURATION_DEFAULT = 8.0

IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
SAMPLE_RATE = 48000
IMAGE_BACKGROUND = "0x101828"
IMAGE_ACCENT = "0x38BDF8"

HTTP_TIMEOUT_S = float(os.environ.get("VE_PROVIDER_TIMEOUT_S", "60") or 60)
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
MAX_OPTIONS_JSON = 4096
SLUG_MAX = 40

CREATE_NO_WINDOW = 0x08000000

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class GenerationError(RuntimeError):
    """A provider could not produce the asset. Message is user-facing."""


class RequestError(ValueError):
    """The request body is invalid. The HTTP layer turns it into a 400."""


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #


def provider_url(kind: str) -> str:
    """Configured HTTP provider URL for *kind*, or ``""`` when unset."""
    return (os.environ.get(f"VE_PROVIDER_{kind.upper()}_URL") or "").strip()


def provider_key(kind: str) -> str:
    """Bearer key for *kind*. Never log, never echo, never persist."""
    return (os.environ.get(f"VE_PROVIDER_{kind.upper()}_KEY") or "").strip()


def http_configured(kind: str) -> bool:
    return bool(provider_url(kind))


def voice_status() -> dict:
    """Which voice engines this machine can use right now (never contacts the network)."""
    return {"local": _sapi_available(), "edge": _edge_python() is not None, "http": http_configured("voice")}


def provider_status() -> dict:
    """Lo que anuncia `/health`: `local` siempre está; el resto, solo si hay clave.

    La app lee esto para mostrar qué opciones puede ofrecer. Ningún proveedor de
    pago aparece como disponible si no lo está: nada de botones que fallen.
    """
    from service import proveedores_externos as ext

    tiene_gemini = ext.gemini_disponible()
    tiene_eleven = ext.eleven_disponible()

    modos: dict[str, dict[str, bool]] = {}
    for kind in KINDS:
        disponible = {"local": True, "http": http_configured(kind)}
        if kind == "image":
            disponible["web"] = True
            disponible["gemini"] = tiene_gemini
        if kind == "voice":
            disponible["edge"] = _edge_python() is not None
            disponible["eleven"] = tiene_eleven
        modos[kind] = disponible

    return {
        "providers": {kind: True for kind in KINDS},
        "providerModes": modos,
    }


# --------------------------------------------------------------------------- #
# request validation
# --------------------------------------------------------------------------- #


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalize_request(body: Any) -> dict:
    """Validate ``POST /projects/<id>/generate`` and apply the documented defaults."""
    if not isinstance(body, dict):
        raise RequestError("body must be a JSON object")

    kind = body.get("kind")
    if kind not in KINDS:
        raise RequestError("kind must be 'image', 'music' or 'voice'")

    prompt = body.get("prompt")
    if not isinstance(prompt, str):
        raise RequestError("prompt must be a string")
    prompt = prompt.strip()
    prompt_max = VOICE_TEXT_MAX if kind == "voice" else PROMPT_MAX
    if not (PROMPT_MIN <= len(prompt) <= prompt_max):
        raise RequestError(f"prompt must be between {PROMPT_MIN} and {prompt_max} characters")

    provider = body.get("provider", "local")
    if provider not in PROVIDERS:
        raise RequestError("provider must be 'local', 'http', 'edge' or 'web'")
    if provider not in KIND_PROVIDERS[kind]:
        raise RequestError(f"provider '{provider}' is not available for kind '{kind}'")
    if provider == "edge" and _edge_python() is None:
        raise RequestError("edge-tts no está instalado: pip install edge-tts (o usa provider 'local')")

    duration = body.get("duration", MUSIC_DURATION_DEFAULT if kind == "music" else 0)
    if kind == "music" or duration:
        if not _is_number(duration) or not (DURATION_MIN <= float(duration) <= DURATION_MAX):
            raise RequestError(f"duration must be a number between {DURATION_MIN:g} and {DURATION_MAX:g} seconds")
        duration = float(duration)
    else:
        duration = 0.0

    options = body.get("options", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise RequestError("options must be a JSON object")
    try:
        encoded = json.dumps(options, ensure_ascii=False)
    except (TypeError, ValueError):
        raise RequestError("options must be JSON-serialisable") from None
    if len(encoded.encode("utf-8")) > MAX_OPTIONS_JSON:
        raise RequestError(f"options is larger than {MAX_OPTIONS_JSON} bytes")

    for key, allowed in (("style", IMAGE_STYLES), ("mood", MUSIC_MOODS)):
        value = options.get(key)
        if value is not None and value not in allowed:
            raise RequestError(f"options.{key} must be one of {', '.join(allowed)}")
    aspect = options.get("aspect")
    if aspect is not None and aspect not in ASPECTS:
        raise RequestError(f"options.aspect must be one of {', '.join(ASPECTS)}")
    rate = options.get("rate")
    if rate is not None and (not _is_number(rate) or not (-50 <= float(rate) <= 50)):
        raise RequestError("options.rate must be a number between -50 and 50 (percent)")

    if provider == "http" and not http_configured(kind):
        raise RequestError(
            f"proveedor no configurado: define VE_PROVIDER_{kind.upper()}_URL para generar {kind} por HTTP"
        )

    # Nano Banana y ElevenLabs son opcionales: se comprueba la clave aquí para dar
    # un mensaje claro ANTES de crear el trabajo, en vez de fallar a medias.
    if provider == "gemini":
        from service import proveedores_externos as ext

        if not ext.gemini_disponible():
            raise RequestError(
                "Nano Banana no está configurado: define VE_GEMINI_KEY (o usa provider 'local')"
            )
    if provider == "eleven":
        from service import proveedores_externos as ext

        if not ext.eleven_disponible():
            raise RequestError(
                "ElevenLabs no está configurado: define VE_ELEVEN_KEY (o usa 'edge' o 'local')"
            )

    return {
        "kind": kind,
        "prompt": prompt,
        "provider": provider,
        "duration": duration,
        "options": options,
    }


# --------------------------------------------------------------------------- #
# filesystem
# --------------------------------------------------------------------------- #


def asset_extension(kind: str) -> str:
    return "png" if kind == "image" else "wav"  # music and voice are WAV


def slugify(prompt: str, *, limit: int = SLUG_MAX) -> str:
    """ASCII, lowercase, dash-separated. Never empty, never a path fragment."""
    text = unicodedata.normalize("NFKD", prompt).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    slug = slug[:limit].strip("-")
    return slug or "generado"


def target_path(media_root: str | os.PathLike[str], project_id: str, kind: str, prompt: str) -> Path:
    """``<mediaRoot>/generated/<projectId>/<slug>-<random>.<ext>``, verified inside."""
    root = Path(media_root).resolve()
    folder = (root / "generated" / project_id).resolve()
    stem = f"{slugify(prompt)}-{secrets.token_hex(4)}"
    candidate = (folder / f"{stem}.{asset_extension(kind)}").resolve()
    for path in (folder, candidate):
        if not path_rules.is_within(path, root):
            raise GenerationError("generated file would land outside the media root")
    folder.mkdir(parents=True, exist_ok=True)
    return candidate


# --------------------------------------------------------------------------- #
# local provider (ffmpeg lavfi, zero network)
# --------------------------------------------------------------------------- #


def _run_ffmpeg(tools: worker.Tools, args: list[str], *, workdir: Path, timeout: float = 180.0) -> None:
    command = [str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", *args]
    env = worker.filtered_env(workdir)
    try:
        result = subprocess.run(
            command,
            cwd=str(workdir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        raise GenerationError(f"ffmpeg excedió {timeout:g}s generando el asset") from None
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {result.returncode}"
        raise GenerationError(f"ffmpeg falló generando el asset: {tail}"[:400])


def _wrap_prompt(prompt: str, *, width: int = 42, max_lines: int = 6) -> list[str]:
    words = prompt.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or [prompt[:width]]


_PALETTES = {
    # c0 (top-left), c1 (middle), c2 (bottom-right), accent
    "cinematic": ("0x0B1020", "0x1E3A5F", "0xC2703D", "0xF2B880"),
    "noir": ("0x050505", "0x2A2A2E", "0x5C5C66", "0xE5E5E5"),
    "warm": ("0x2B0F14", "0x8A3B2B", "0xF0A04B", "0xFFE2B0"),
    "neon": ("0x0A0221", "0x4B1D8F", "0x00C2D1", "0xFF4FD8"),
    "studio": ("0x151A22", "0x2B3445", "0x55627A", "0x38BDF8"),
    "forest": ("0x07140E", "0x14532D", "0x7DB46C", "0xD9F99D"),
}


def _pick_style(prompt: str, options: dict) -> str:
    style = options.get("style")
    if style in _PALETTES:
        return style
    return "cinematic"  # el look que más gusta; elige otro con options.style


def image_size(options: dict) -> tuple[int, int]:
    return ASPECTS.get(options.get("aspect") or "16:9", (IMAGE_WIDTH, IMAGE_HEIGHT))


def generate_local_image(
    prompt: str, path: Path, *, tools: worker.Tools, job_dir: Path, options: dict | None = None
) -> None:
    """A graded backdrop: 3-stop gradient, film grain and vignette.

    No text is burned in: titles belong to the scene text overlay, so they are
    never drawn twice. ``options.caption=true`` brings the old caption card back.
    """
    options = options or {}
    width, height = image_size(options)
    c0, c1, c2, accent = _PALETTES[_pick_style(prompt, options)]
    seed = sum(prompt.encode("utf-8")) % 997
    x1, y1 = (width, height) if seed % 2 else (width, int(height * 0.35))
    source = (
        f"gradients=s={width}x{height}:c0={c0}:c1={c1}:c2={c2}:nb_colors=3"
        f":x0=0:y0=0:x1={x1}:y1={y1}:seed={seed}:speed=0:d=1:rate=1"
    )
    chain = [
        "noise=alls=9:allf=t",
        "vignette=angle=PI/4.5",
        f"drawbox=x=0:y={height - 6}:w={width}:h=6:color={accent}@0.9:t=fill",
    ]
    if options.get("caption"):
        text_file = job_dir / "generate-prompt.txt"
        text_file.write_text("\n".join(_wrap_prompt(prompt)), encoding="utf-8", newline="\n")
        font = worker._find_font()
        if font is not None:
            chain.append(
                f"drawtext=fontfile={worker._filter_path(font)}:textfile={worker._filter_path(text_file)}"
                ":fontcolor=white:fontsize=40:line_spacing=12:box=1:boxcolor=black@0.35:boxborderw=28"
                ":x=(w-text_w)/2:y=(h-text_h)/2"
            )
    _run_ffmpeg(
        tools,
        ["-f", "lavfi", "-i", source, "-vf", ",".join(chain), "-frames:v", "1", str(path)],
        workdir=job_dir,
    )


def generate_web_image(prompt: str, path: Path, *, tools: worker.Tools, job_dir: Path, options: dict) -> str:
    """Pollinations (free, no key). The prompt leaves this machine: opt-in only."""
    width, height = image_size(options)
    seed = secrets.randbelow(10**6)
    url = (
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt, safe="")
        + f"?width={width}&height={height}&nologo=true&seed={seed}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "hermes-video-editor/0.4"})
    try:
        with urllib.request.urlopen(request, timeout=max(HTTP_TIMEOUT_S, 90.0)) as response:
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise GenerationError(f"el servicio web de imágenes respondió {exc.code}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GenerationError(f"no se pudo contactar el servicio web de imágenes: {getattr(exc, 'reason', exc)}") from None
    if len(data) < 1024 or len(data) > MAX_DOWNLOAD_BYTES:
        raise GenerationError("el servicio web de imágenes devolvió una respuesta inválida")
    raw = job_dir / "web-image.bin"
    raw.write_bytes(data)
    # Normalise to PNG (and prove it is a real image) with ffmpeg.
    _run_ffmpeg(tools, ["-i", str(raw), "-frames:v", "1", str(path)], workdir=job_dir)
    return "web:pollinations"


_MOOD_EXPR = {
    "calm": "0.20*sin(2*PI*220*t)+0.16*sin(2*PI*277.18*t)+0.14*sin(2*PI*329.63*t)+0.05*sin(2*PI*110*t)",
    "epic": "(0.22*sin(2*PI*146.83*t)+0.18*sin(2*PI*174.61*t)+0.16*sin(2*PI*220*t)+0.14*sin(2*PI*73.42*t))*(0.75+0.25*sin(2*PI*0.25*t))",
    "tension": "0.18*sin(2*PI*123.47*t)+0.16*sin(2*PI*146.83*t)+0.14*sin(2*PI*174.61*t)+0.05*sin(2*PI*(311+4*sin(2*PI*0.3*t))*t)",
    "bright": "0.20*sin(2*PI*261.63*t)+0.17*sin(2*PI*329.63*t)+0.15*sin(2*PI*392*t)+0.05*sin(2*PI*130.81*t)",
}


def pick_mood(prompt: str, options: dict) -> str:
    mood = options.get("mood")
    if mood in _MOOD_EXPR:
        return mood
    text = unicodedata.normalize("NFKD", prompt.lower()).encode("ascii", "ignore").decode("ascii")
    for key, words in (
        ("epic", ("epic", "cinematic", "cinemat", "trailer", "heroic")),
        ("tension", ("tens", "suspense", "dark", "oscur", "misterio", "mystery")),
        ("bright", ("alegre", "bright", "happy", "feliz", "energ", "upbeat")),
    ):
        if any(word in text for word in words):
            return key
    return "calm"


def generate_local_music(
    duration: float, path: Path, *, tools: worker.Tools, job_dir: Path,
    prompt: str = "", options: dict | None = None,
) -> None:
    """A synthetic chord pad (mood: calm/epic/tension/bright) with a soft fade in/out."""
    expression = _MOOD_EXPR[pick_mood(prompt, options or {})]
    fade = min(0.8, max(0.25, duration / 8.0))
    _run_ffmpeg(
        tools,
        [
            "-f", "lavfi",
            "-i", f"aevalsrc={expression}:s={SAMPLE_RATE}:d={duration:.3f}",
            "-af", f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f}",
            "-ac", "2", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le",
            str(path),
        ],
        workdir=job_dir,
    )


# --------------------------------------------------------------------------- #
# voice (TTS): SAPI offline, edge-tts opt-in
# --------------------------------------------------------------------------- #

_SAPI_SCRIPT = r"""
param([string]$TextFile, [string]$Out, [string]$Voice, [int]$Rate, [string]$Culture)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  if ($Voice) { $s.SelectVoice($Voice) }
  else {
    $match = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like ($Culture + '*') } | Select-Object -First 1
    if ($match) { $s.SelectVoice($match.VoiceInfo.Name) }
  }
  $s.Rate = $Rate
  $s.SetOutputToWaveFile($Out)
  $s.Speak([IO.File]::ReadAllText($TextFile, [Text.Encoding]::UTF8))
} finally { $s.Dispose() }
"""


def _powershell() -> str | None:
    root = os.environ.get("SystemRoot") or os.environ.get("windir")
    if not root:
        return None
    candidate = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(candidate) if candidate.is_file() else None


def _sapi_available() -> bool:
    return _powershell() is not None


def _edge_python() -> list[str] | None:
    """Command prefix of a Python that can ``import edge_tts`` (cached), or None."""
    global _EDGE_CACHE
    if _EDGE_CACHE is not _UNSET:
        return _EDGE_CACHE
    candidates: list[list[str]] = []
    env = (os.environ.get("VE_EDGE_PYTHON") or "").strip()
    if env:
        candidates.append([env])
    candidates.append([sys.executable])
    launcher = shutil.which("py")
    if launcher:
        candidates.append([launcher, "-3.12"])
        candidates.append([launcher, "-3"])
    found = None
    for command in candidates:
        try:
            result = subprocess.run(
                [*command, "-c", "import edge_tts"], capture_output=True, timeout=20,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            found = command
            break
    _EDGE_CACHE = found
    return found


_UNSET = object()
_EDGE_CACHE: Any = _UNSET


def _speech_env() -> dict[str, str]:
    keep = ("SystemRoot", "windir", "PATH", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "ComSpec", "PATHEXT")
    return {key: os.environ[key] for key in keep if key in os.environ}


def generate_local_voice(
    text: str, path: Path, *, tools: worker.Tools, job_dir: Path, options: dict
) -> str:
    shell = _powershell()
    if shell is None:
        raise GenerationError("voz local no disponible (se necesita Windows SAPI); usa provider 'edge' o 'http'")
    text_file = job_dir / "voice-text.txt"
    text_file.write_text(text, encoding="utf-8", newline="\n")
    script = job_dir / "voice.ps1"
    script.write_text(_SAPI_SCRIPT, encoding="utf-8")
    raw = job_dir / "voice-raw.wav"
    rate = int(round(float(options.get("rate") or 0) / 5))  # percent -> SAPI -10..10
    command = [
        shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
        "-TextFile", str(text_file), "-Out", str(raw),
        "-Voice", str(options.get("voice") or ""), "-Rate", str(max(-10, min(10, rate))),
        "-Culture", str(options.get("lang") or "es"),
    ]
    try:
        result = subprocess.run(
            command, cwd=str(job_dir), env=_speech_env(), capture_output=True, text=True,
            timeout=120, creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        raise GenerationError("la voz local tardó más de 120 s") from None
    if result.returncode != 0 or not raw.is_file() or raw.stat().st_size < 1024:
        tail = ((result.stderr or "").strip().splitlines() or ["sin detalle"])[-1]
        raise GenerationError(f"la voz local falló: {tail}"[:300])
    _finish_voice(raw, path, tools=tools, job_dir=job_dir)
    return "local:sapi"


def generate_edge_voice(
    text: str, path: Path, *, tools: worker.Tools, job_dir: Path, options: dict
) -> str:
    prefix = _edge_python()
    if prefix is None:
        raise GenerationError("edge-tts no está instalado: pip install edge-tts")
    text_file = job_dir / "voice-text.txt"
    text_file.write_text(text, encoding="utf-8", newline="\n")
    raw = job_dir / "voice-raw.mp3"
    voice = str(options.get("voice") or VOICE_DEFAULT_VOICE_EDGE)
    if not re.fullmatch(r"[A-Za-z]{2,3}-[A-Za-z0-9]{2,8}-[A-Za-z0-9]+", voice):
        raise GenerationError("nombre de voz edge inválido")
    rate = int(round(float(options.get("rate") or 0)))
    command = [
        *prefix, "-m", "edge_tts", "--file", str(text_file), "--voice", voice,
        f"--rate={rate:+d}%", "--write-media", str(raw), "--no-progress",
    ]
    try:
        result = subprocess.run(
            command, cwd=str(job_dir), env=_speech_env(), capture_output=True, text=True,
            timeout=90, creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        raise GenerationError("edge-tts no respondió en 90 s (¿sin internet?)") from None
    if result.returncode != 0 or not raw.is_file() or raw.stat().st_size < 512:
        tail = ((result.stderr or "").strip().splitlines() or ["sin detalle"])[-1]
        raise GenerationError(f"edge-tts falló: {tail}"[:300])
    _finish_voice(raw, path, tools=tools, job_dir=job_dir)
    return f"edge:{voice}"


def _finish_voice(raw: Path, path: Path, *, tools: worker.Tools, job_dir: Path) -> None:
    """Mono 48 kHz WAV, leading/trailing silence trimmed, loudness levelled."""
    _run_ffmpeg(
        tools,
        [
            "-i", str(raw),
            "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                   "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                   "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(path),
        ],
        workdir=job_dir,
    )


# --------------------------------------------------------------------------- #
# generic HTTP provider
# --------------------------------------------------------------------------- #


def _post_json(url: str, payload: dict, *, key: str) -> tuple[bytes, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, application/octet-stream, */*")
    if key:
        # The only place the key is used. It never reaches a log line.
        request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise GenerationError(f"el proveedor HTTP respondió {exc.code} para {payload['kind']}") from None
    except urllib.error.URLError as exc:
        raise GenerationError(f"no se pudo contactar el proveedor HTTP: {exc.reason}") from None
    except TimeoutError:
        raise GenerationError(f"el proveedor HTTP no respondió en {HTTP_TIMEOUT_S:g}s") from None
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise GenerationError(f"respuesta del proveedor mayor a {MAX_DOWNLOAD_BYTES} bytes")
    if not data:
        raise GenerationError("el proveedor HTTP devolvió una respuesta vacía")
    return data, content_type


def _download(url: str) -> bytes:
    # Only https: a provider reply must never make us read file:// or talk to
    # plain http / link-local metadata endpoints.
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise GenerationError("el proveedor devolvió una URL que no es https")
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as response:
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise GenerationError(f"el proveedor HTTP respondió {exc.code} al descargar el asset") from None
    except urllib.error.URLError as exc:
        raise GenerationError(f"no se pudo descargar el asset del proveedor: {exc.reason}") from None
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise GenerationError(f"asset descargado mayor a {MAX_DOWNLOAD_BYTES} bytes")
    return data


def generate_http(request: dict, path: Path, *, job_dir: Path) -> str:
    """POST the request, accept binary/JSON and write the bytes to *path*.

    Returns a short provider note (used in ``rights.notes``); it never contains
    the URL or the key.
    """
    kind = request["kind"]
    url = provider_url(kind)
    if not url:
        raise GenerationError(f"proveedor no configurado para {kind}")
    key = provider_key(kind)
    payload = {
        "kind": kind,
        "prompt": request["prompt"],
        "duration": request["duration"],
        "options": request["options"],
    }
    data, content_type = _post_json(url, payload, key=key)

    if content_type in {"application/json", "text/json"} or data[:1] in (b"{", b"["):
        try:
            envelope = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GenerationError("el proveedor HTTP devolvió JSON inválido") from None
        if not isinstance(envelope, dict):
            raise GenerationError("el proveedor HTTP devolvió un JSON inesperado")
        if isinstance(envelope.get("base64"), str):
            try:
                data = base64.b64decode(envelope["base64"], validate=True)
            except (ValueError, base64.binascii.Error):
                raise GenerationError("el proveedor HTTP devolvió base64 inválido") from None
        elif isinstance(envelope.get("url"), str):
            data = _download(envelope["url"])
        elif isinstance(envelope.get("path"), str):
            # A provider that writes the file itself (local gateway), but only
            # inside this job: a reply must not read arbitrary files.
            try:
                candidate = Path(envelope["path"]).resolve()
                inside = candidate.is_relative_to(job_dir.resolve())
            except OSError:
                inside = False
            if not inside:
                raise GenerationError("el proveedor devolvió un path fuera de la carpeta del trabajo")
            if not candidate.is_file():
                raise GenerationError("el proveedor HTTP devolvió un path que no existe")
            data = candidate.read_bytes()
        else:
            raise GenerationError("el proveedor HTTP no devolvió path, url, base64 ni binario")

    path.write_bytes(data)
    return f"http:{kind}"


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #


def run(
    request: dict,
    *,
    media_root: str | os.PathLike[str],
    project_id: str,
    tools: worker.Tools,
    job_dir: Path,
    cancel: Callable[[], bool] | None = None,
    progress: Callable[[str, float, str], None] | None = None,
) -> dict:
    """Produce one asset and return its registration data.

    ``cancel`` is polled between the (few) blocking steps: the local provider is
    a single ffmpeg call, so a cancel lands before or right after it.
    """
    kind = request["kind"]
    provider = request["provider"]
    job_dir.mkdir(parents=True, exist_ok=True)

    def report(stage: str, percent: float, message: str) -> None:
        if progress is not None:
            progress(stage, percent, message)

    def check() -> None:
        if cancel is not None and cancel():
            raise worker._Cancelled("cancelado durante la generación")

    report("generating", 10.0, f"generando {kind} con {provider}")
    path = target_path(media_root, project_id, kind, request["prompt"])
    check()

    started = time.monotonic()
    options = request.get("options") or {}
    if provider == "local":
        if kind == "image":
            generate_local_image(request["prompt"], path, tools=tools, job_dir=job_dir, options=options)
            note = "local:image"
        elif kind == "voice":
            note = generate_local_voice(request["prompt"], path, tools=tools, job_dir=job_dir, options=options)
        else:
            generate_local_music(
                float(request["duration"]), path, tools=tools, job_dir=job_dir,
                prompt=request["prompt"], options=options,
            )
            note = "local:music"
    elif provider == "edge":
        note = generate_edge_voice(request["prompt"], path, tools=tools, job_dir=job_dir, options=options)
    elif provider == "web":
        note = generate_web_image(request["prompt"], path, tools=tools, job_dir=job_dir, options=options)
    elif provider == "gemini":
        # Nano Banana: opcional. Sin clave, el mensaje lo dice y no se gasta nada.
        from service import proveedores_externos as ext

        note = ext.generar_imagen_gemini(request["prompt"], path, options=options)
    elif provider == "eleven":
        # ElevenLabs: opcional. Se guarda el MP3 y se convierte a WAV (48 kHz mono),
        # que es lo que come el resto del motor.
        from service import proveedores_externos as ext

        temporal = path.with_suffix(".mp3")
        note = ext.generar_voz_eleven(request["prompt"], temporal, options=options)
        worker.run_ffmpeg(
            tools,
            ["-v", "error", "-y", "-i", str(temporal), "-ar", "48000", "-ac", "1", str(path)],
            cwd=job_dir,
        )
        try:
            temporal.unlink()
        except OSError:
            pass
    else:
        note = generate_http(request, path, job_dir=job_dir)
    check()

    if not path.is_file() or path.stat().st_size == 0:
        raise GenerationError("el proveedor no produjo un archivo válido")

    report("registering", 80.0, "registrando el asset generado")
    relative = path.relative_to(Path(media_root).resolve()).as_posix()
    if not path_rules.is_within(path, Path(media_root).resolve()):
        raise GenerationError("el asset generado quedó fuera de la raíz de medios")

    return {
        "kind": kind,
        "path": relative,
        "absolutePath": str(path),
        "bytes": path.stat().st_size,
        "sha256": worker.sha256_file(path),
        "provider": provider,
        "providerNote": note,
        "elapsedS": round(time.monotonic() - started, 3),
    }
