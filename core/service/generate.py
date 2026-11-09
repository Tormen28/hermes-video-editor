"""Generation engine (phase 3A): one contract, two providers.

* ``local`` — ffmpeg ``lavfi`` only. No network, no keys, no cost: an image is a
  gradient card with the prompt burned in, a music bed is a synthetic chord.
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
import subprocess
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

import paths as path_rules
from service import worker

KINDS = ("image", "music")
PROVIDERS = ("local", "http")

PROMPT_MIN = 1
PROMPT_MAX = 500
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


def provider_status() -> dict:
    """What ``/health`` advertises: local is always there, http only if set."""
    return {
        "providers": {kind: True for kind in KINDS},
        "providerModes": {
            kind: {"local": True, "http": http_configured(kind)} for kind in KINDS
        },
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
        raise RequestError("kind must be 'image' or 'music'")

    prompt = body.get("prompt")
    if not isinstance(prompt, str):
        raise RequestError("prompt must be a string")
    prompt = prompt.strip()
    if not (PROMPT_MIN <= len(prompt) <= PROMPT_MAX):
        raise RequestError(f"prompt must be between {PROMPT_MIN} and {PROMPT_MAX} characters")

    provider = body.get("provider", "local")
    if provider not in PROVIDERS:
        raise RequestError("provider must be 'local' or 'http'")

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

    if provider == "http" and not http_configured(kind):
        raise RequestError(
            f"proveedor no configurado: define VE_PROVIDER_{kind.upper()}_URL para generar {kind} por HTTP"
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
    return "png" if kind == "image" else "wav"


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


def generate_local_image(prompt: str, path: Path, *, tools: worker.Tools, job_dir: Path) -> None:
    """A 1280x720 card: flat background + the prompt, burned with drawtext."""
    text_file = job_dir / "generate-prompt.txt"
    text_file.write_text("\n".join(_wrap_prompt(prompt)), encoding="utf-8", newline="\n")
    source = f"color=c={IMAGE_BACKGROUND}:s={IMAGE_WIDTH}x{IMAGE_HEIGHT}:d=1"
    font = worker._find_font()
    if font is None:
        # No usable TTF: a test pattern still proves the pipeline end to end.
        _run_ffmpeg(
            tools,
            ["-f", "lavfi", "-i", f"testsrc2=size={IMAGE_WIDTH}x{IMAGE_HEIGHT}:rate=1",
             "-frames:v", "1", str(path)],
            workdir=job_dir,
        )
        return
    drawtext = (
        f"drawtext=fontfile={worker._filter_path(font)}:textfile={worker._filter_path(text_file)}"
        f":fontcolor=white:fontsize=40:line_spacing=12"
        ":box=1:boxcolor=black@0.35:boxborderw=28"
        ":x=(w-text_w)/2:y=(h-text_h)/2"
    )
    border = (
        f"drawbox=x=0:y=0:w={IMAGE_WIDTH}:h=8:color={IMAGE_ACCENT}@1.0:t=fill"
    )
    _run_ffmpeg(
        tools,
        ["-f", "lavfi", "-i", source, "-vf", f"{border},{drawtext}", "-frames:v", "1", str(path)],
        workdir=job_dir,
    )


def generate_local_music(duration: float, path: Path, *, tools: worker.Tools, job_dir: Path) -> None:
    """A synthetic A-major chord (A3/C#4/E4) with a soft fade in/out."""
    expression = (
        "0.20*sin(2*PI*220*t)+0.16*sin(2*PI*277.18*t)+0.14*sin(2*PI*329.63*t)"
        "+0.05*sin(2*PI*110*t)"
    )
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
            # A provider that writes the file itself (local gateway).
            candidate = Path(envelope["path"])
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
    if provider == "local":
        if kind == "image":
            generate_local_image(request["prompt"], path, tools=tools, job_dir=job_dir)
        else:
            generate_local_music(float(request["duration"]), path, tools=tools, job_dir=job_dir)
        note = f"local:{kind}"
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
