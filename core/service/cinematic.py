"""Cinematic engine: the `cinematic-film` skill, wired into the editor service.

The vendored skill lives in ``core/cinematic/`` and does the hard part itself:
``script.json`` decides the narration, ``scene.py`` places the items and the
camera keys on the voiceover timing, and ``render.py`` turns that into frames.
This module is only the seam between that folder and the HTTP service.

Three stages, each one its own subprocess so a failure names the stage that
broke instead of a 900-line traceback:

1. ``new_project.py``  — scaffold the folder.
2. ``build_narration.py`` / ``build_sfx.py`` — the voice and the sound cues.
3. ``render.py``       — the frames and the MP4.

Hard rules, same as the rest of the service:

* No network and no key: the local path is the only one this module takes.
  Whatever a project needs to download is the caller's business, not ours.
* Rendering is long (a 30 s film can take 40 minutes), so it always runs in a
  background thread and reports through a ``status.json`` next to the project.
  Nothing here blocks a request.
* Every path handed back is re-checked against the cinematic root before use.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

# ``core/service/cinematic.py`` -> ``core/cinematic``
HERE = Path(__file__).resolve().parent
CINEMATIC_ROOT = HERE.parent / "cinematic"
SCRIPTS = CINEMATIC_ROOT / "scripts"

NOMBRE_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# La voz de Windows, sin red y sin clave. PowerShell no admite llaves aqui porque
# tts_say.py pasa el comando por str.format() y se romperia.
VOZ_WINDOWS = (
    "powershell -NoProfile -Command \"Add-Type -AssemblyName System.Speech; "
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$s.SelectVoice('Microsoft Zira Desktop'); "
    "$s.SetOutputToWaveFile('{out}'); "
    "$s.Speak([IO.File]::ReadAllText('{txt}')); $s.Dispose()\""
)

# El orden lo manda el skill: no hay imagen sin voz, porque la pelicula se
# cronometra contra la narracion (timing.json).
ETAPAS = (
    ("voz", "tts_say.py", ("--cmd", VOZ_WINDOWS)),
    ("cortes", "split_takes.py", ()),
    ("narracion", "build_narration.py", ()),
    ("assets", "prep_assets.py", ()),
    ("render", "render.py", ("--out", "out/film.mp4", "--audio", "audio/narration.m4a")),
    ("cues", "render.py", ("--cues",)),
    ("efectos", "build_sfx.py", ()),
    ("mezcla", "mix_soundtrack.py", ("--out", "out/film-final.mp4")),
)

#: Cual de las salidas existe al terminar, en orden de preferencia.
SALIDAS = ("out/film-final.mp4", "out/film.mp4")

_lock = threading.Lock()
_en_curso: dict[str, dict] = {}


def _python() -> str:
    """El interprete actual: los scripts necesitan sus dependencias instaladas."""
    return sys.executable or "python"


def disponible() -> dict:
    """¿Esta el skill puesto y completo? Sin red, sin adivinar."""
    faltan = [s for s in ("new_project.py", "render.py", "build_narration.py")
              if not (SCRIPTS / s).is_file()]
    return {
        "disponible": not faltan and CINEMATIC_ROOT.is_dir(),
        "raiz": str(CINEMATIC_ROOT),
        "scripts": len(list(SCRIPTS.glob("*.py"))) if SCRIPTS.is_dir() else 0,
        "faltan": faltan,
        "python": _python(),
        "nota": (
            "El skill hace el trabajo: script.json manda la narracion, scene.py "
            "coloca items y camara sobre la voz, render.py saca los fotogramas."
        ),
    }


def _carpeta(base: Path, nombre: str) -> Path:
    """Resuelve la carpeta del proyecto y comprueba que no se escapa de la raiz."""
    if not NOMBRE_VALIDO.match(nombre):
        raise ValueError(f"nombre de proyecto no valido: {nombre!r}")
    destino = (base / nombre).resolve()
    if base.resolve() not in destino.parents and destino != base.resolve():
        raise ValueError("la carpeta del proyecto se sale de la raiz")
    return destino


def crear_proyecto(base: Path, nombre: str, titulo: str) -> dict:
    """Andamia el proyecto con el script del skill. No renderiza nada."""
    base.mkdir(parents=True, exist_ok=True)
    destino = _carpeta(base, nombre)
    if destino.exists():
        raise ValueError(f"ya existe un proyecto llamado {nombre!r}")

    resultado = subprocess.run(
        [_python(), str(SCRIPTS / "new_project.py"), str(destino), "--title", titulo],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            f"new_project.py fallo: {(resultado.stderr or resultado.stdout).strip()[:400]}"
        )
    return {
        "proyecto": nombre,
        "carpeta": str(destino),
        "titulo": titulo,
        "archivos": sorted(p.name for p in destino.iterdir()) if destino.is_dir() else [],
    }


def _estado_path(carpeta: Path) -> Path:
    return carpeta / "out" / "status.json"


def _escribir_estado(carpeta: Path, datos: dict) -> None:
    ruta = _estado_path(carpeta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporal, ruta)


def estado(carpeta: Path) -> dict:
    """Lo que el pane necesita: etapa actual, porcentaje, error y salida."""
    vivo = _en_curso.get(carpeta.name)
    ruta = _estado_path(carpeta)
    guardado: dict = {}
    if ruta.is_file():
        try:
            guardado = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            guardado = {}

    salida = None
    for nombre_salida in SALIDAS:
        candidata = carpeta / nombre_salida
        if candidata.is_file():
            salida = str(candidata)
            break
    return {
        "proyecto": carpeta.name,
        "existe": carpeta.is_dir(),
        "corriendo": bool(vivo and vivo.get("corriendo")),
        "etapa": (vivo or guardado).get("etapa"),
        "porcentaje": (vivo or guardado).get("porcentaje", 0),
        "error": (vivo or guardado).get("error"),
        "terminado": bool(guardado.get("terminado")),
        "salida": salida,
        "segundos": guardado.get("segundos"),
    }


def _correr_etapa(carpeta: Path, script: str, extra: tuple[str, ...]) -> None:
    comando = [_python(), str(SCRIPTS / script), "--project", str(carpeta), *extra]
    resultado = subprocess.run(comando, capture_output=True, text=True, timeout=3600)
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout or "").strip()
        raise RuntimeError(f"{script}: {detalle[-600:]}")


def _renderizar(carpeta: Path) -> None:
    """Corre el pipeline en un hilo. Nunca lanza: el error va al estado."""
    arranque = time.time()
    datos = {"corriendo": True, "terminado": False, "porcentaje": 0, "error": None}
    _en_curso[carpeta.name] = datos
    try:
        for i, (etapa, script, extra) in enumerate(ETAPAS, start=1):
            datos["etapa"] = etapa
            datos["porcentaje"] = round((i - 1) / len(ETAPAS) * 100)
            _escribir_estado(carpeta, {**datos, "corriendo": True})
            _correr_etapa(carpeta, script, extra)

        datos.update(
            etapa="listo",
            porcentaje=100,
            terminado=True,
            corriendo=False,
            salida=SALIDAS[0],
            segundos=round(time.time() - arranque, 1),
        )
    except Exception as exc:  # noqa: BLE001 - el estado es el contrato
        datos.update(corriendo=False, terminado=False, error=str(exc)[:800], etapa="error")
    finally:
        _escribir_estado(carpeta, datos)
        with _lock:
            _en_curso.pop(carpeta.name, None)


def lanzar_render(carpeta: Path) -> dict:
    """Arranca el render si no hay otro en marcha. Devuelve el estado al momento."""
    if not carpeta.is_dir():
        raise ValueError(f"no existe el proyecto {carpeta.name!r}")
    with _lock:
        if carpeta.name in _en_curso:
            return estado(carpeta)
        _en_curso[carpeta.name] = {"corriendo": True, "etapa": "arrancando", "porcentaje": 0}
    hilo = threading.Thread(target=_renderizar, args=(carpeta,), daemon=True,
                            name=f"cinematic-{carpeta.name}")
    hilo.start()
    return estado(carpeta)


def guion(carpeta: Path) -> dict:
    """El script.json del proyecto, para que el pane muestre las lineas."""
    ruta = carpeta / "script.json"
    if not ruta.is_file():
        return {"lineas": [], "existe": False}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"lineas": [], "existe": True, "error": str(exc)}
    return {"lineas": datos.get("lines") or datos.get("narration") or [], "existe": True}
