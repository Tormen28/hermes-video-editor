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
import shutil
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
# cronometra contra la narracion (timing.json). Ojo: mix_soundtrack.py devuelve
# AUDIO, no video; el MP4 final se arma aparte, uniendo imagen y mezcla.
ETAPAS = (
    ("voz", "tts_say.py", ("--cmd", VOZ_WINDOWS)),
    ("cortes", "split_takes.py", ()),
    ("narracion", "build_narration.py", ()),
    ("assets", "prep_assets.py", ()),
    ("render", "render.py", ("--out", "out/film.mp4", "--audio", "audio/narration.m4a")),
    ("cues", "render.py", ("--cues",)),
    ("efectos", "build_sfx.py", ()),
    ("mezcla", "mix_soundtrack.py", ("--out", "audio/mix.m4a")),
)

#: La imagen que produce render.py y la mezcla que produce mix_soundtrack.py.
IMAGEN = "out/film.mp4"
MEZCLA = "audio/mix.m4a"
#: Cual de las salidas existe al terminar, en orden de preferencia.
SALIDAS = ("out/film-final.mp4",)

#: Las pieles del motor. Cambian tablero, color base, grano, brillo y viñeta.
PIELES = {
    "studio": "Estudio claro, sin costuras. Lanzamientos y explicadores con tarjetas.",
    "blueprint": "Azul de plano técnico con rejilla. Ingeniería y cómo funcionan las cosas.",
    "night": "Azul marino oscuro con mucho brillo. Tecnología y tráiler.",
    "slate": "Gris azulado frío. Política, negocio, investigación.",
    "charcoal": "Negro neutro: deja que las fotos lleven el color.",
    "wall": "Corcho oscuro cálido. Historia, crimen, historias reales.",
    "paper": "Papel claro. Educación, historias suaves.",
}

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


def crear_proyecto(base: Path, nombre: str, titulo: str, piel: str | None = None) -> dict:
    """Andamia el proyecto con el script del skill. No renderiza nada.

    Si se pide una `piel`, se reescribe el `Film(look=...)` del `scene.py` recien
    creado. Es la forma de cambiar el color sin que nadie edite Python a mano.
    """
    if piel is not None and piel not in PIELES:
        raise ValueError(f"piel desconocida: {piel!r}")
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

    piel_aplicada = None
    if piel:
        escena = destino / "scene.py"
        if escena.is_file():
            texto = escena.read_text(encoding="utf-8")
            nuevo, cambios = re.subn(r'Film\(([^)]*?)look="[^"]*"', f'Film(\\1look="{piel}"', texto)
            if not cambios:
                nuevo, cambios = re.subn(r"Film\(([^)]*?)\)", f'Film(\\1, look="{piel}")', texto, count=1)
            if cambios:
                escena.write_text(nuevo, encoding="utf-8")
                piel_aplicada = piel

    return {
        "proyecto": nombre,
        "carpeta": str(destino),
        "titulo": titulo,
        "piel": piel_aplicada,
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


def _unir(carpeta: Path) -> None:
    """Pega la imagen y la mezcla en el MP4 final.

    `mix_soundtrack.py` devuelve audio, no video: darselo a `--out` como si
    fuera un MP4 produce un archivo sin imagen. Aqui se juntan los dos.
    """
    imagen = carpeta / IMAGEN
    mezcla = carpeta / MEZCLA
    if not imagen.is_file():
        raise RuntimeError(f"falta la imagen renderizada: {IMAGEN}")
    if not mezcla.is_file():
        raise RuntimeError(f"falta la mezcla de audio: {MEZCLA}")

    destino = carpeta / SALIDAS[0]
    destino.parent.mkdir(parents=True, exist_ok=True)
    resultado = subprocess.run(
        [
            _ffmpeg(), "-v", "error", "-y",
            "-i", str(imagen), "-i", str(mezcla),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0", "-shortest",
            str(destino),
        ],
        capture_output=True, text=True, timeout=1800,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"no se pudo unir imagen y audio: {(resultado.stderr or '')[-400:]}")


def _ffmpeg() -> str:
    """El ffmpeg que el servicio ya valida, o el del PATH."""
    entorno = os.environ.get("VE_FFMPEG")
    if entorno and Path(entorno).is_file():
        return entorno
    encontrado = shutil.which("ffmpeg")
    if encontrado:
        return encontrado
    raise RuntimeError("no hay ffmpeg: el servicio lo necesita para unir imagen y audio")


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

        # Ultima etapa, en Python: imagen + mezcla -> MP4.
        datos["etapa"] = "union"
        datos["porcentaje"] = 96
        _escribir_estado(carpeta, {**datos, "corriendo": True})
        _unir(carpeta)

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
    """Las lineas del script.json, ya aplanadas: el pane las pinta tal cual.

    El skill las guarda agrupadas por toma (``takes[].lines[]``), no en una lista
    plana; aplanarlas aqui evita que la pantalla tenga que saber esa forma.
    """
    ruta = carpeta / "script.json"
    if not ruta.is_file():
        return {"lineas": [], "existe": False}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"lineas": [], "existe": True, "error": str(exc)}

    lineas: list[dict] = []
    for toma in datos.get("takes") or []:
        for linea in toma.get("lines") or []:
            lineas.append({**linea, "take": toma.get("take")})
    if not lineas:
        # Proyectos escritos a mano pueden traer la lista plana.
        lineas = list(datos.get("lines") or datos.get("narration") or [])
    return {"lineas": lineas, "existe": True, "takes": len(datos.get("takes") or [])}
