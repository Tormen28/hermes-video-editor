"""Banco de pruebas del pane: fixtures sintéticos + servicio real en marcha.

Crea clips 720p, un PNG, escribe media.json (para el ctx.files simulado) y
arranca core/service/app.py en un puerto fijo con un origen extra permitido.
Imprime JSON con lo que el navegador necesita.

    python plugin/harness/setup_fixtures.py --port 8765 --harness-origin http://127.0.0.1:8800
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORE = ROOT / "core"
TOOLS = r"C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin"
FFMPEG = str(Path(TOOLS) / "ffmpeg.exe")


def harness_dir() -> Path:
    """Carpeta de trabajo del banco de pruebas, SIEMPRE absoluta.

    ``TMPDIR`` sólo existe en el bash de Hermes: en cmd.exe o PowerShell la
    versión anterior caía en ``.`` y el servicio recibía una raíz relativa,
    con lo que ``POST /projects/<id>/media`` respondía 400 ("…does not exist").
    ``tempfile.gettempdir()`` funciona en las tres consolas y ``VE_HARNESS_DIR``
    permite fijar otra raíz sin tocar el código.
    """
    override = os.environ.get("VE_HARNESS_DIR")
    root = Path(override).expanduser() if override else Path(tempfile.gettempdir())
    return (root / "ve-harness").resolve()



def run(*args: str) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"falló: {' '.join(args[:3])}\n{result.stderr[-800:]}")


TOKEN_PATH: Path | None = None


def service_token() -> str:
    """Token del servicio: el del banco (data/service.token) o el global con --reuse."""
    if TOKEN_PATH is None:
        return ""
    try:
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    token = service_token()
    if token:
        request.add_header("X-VE-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode() or "{}")
        finally:
            exc.close()


def wait_health(base: str, seconds: float = 25.0) -> dict:
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base + "/health", timeout=3) as response:
                return json.loads(response.read().decode())
        except Exception as exc:  # noqa: BLE001 - sondeo
            last = exc
            time.sleep(0.3)
    raise SystemExit(f"el servicio no respondió: {last}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--harness-origin", default="http://127.0.0.1:8800")
    parser.add_argument("--reuse", action="store_true", help="usar el servicio ya arrancado")
    args = parser.parse_args(argv)

    base_dir = harness_dir()
    media = base_dir / "media"
    data = base_dir / "data"
    media.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    global TOKEN_PATH
    token_file = data / "service.token"
    TOKEN_PATH = (token_file if not args.reuse else
                  Path(os.environ.get("LOCALAPPDATA", Path.home()))
                  / "hermes" / "video-editor" / "service.token")

    # El pane vive en desktop/plugin.js; el harness lo importa como ../plugin.js.
    pane_src = ROOT / "desktop" / "plugin.js"
    pane_copy = HERE.parent / "plugin.js"
    if pane_src.is_file():
        shutil.copy2(pane_src, pane_copy)

    clips = [
        ("intro.mp4", ["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=3",
                       "-f", "lavfi", "-i", "sine=frequency=440:duration=3"]),
        ("demo.mp4", ["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=2.5",
                      "-f", "lavfi", "-i", "sine=frequency=560:duration=2.5"]),
        # pane_ui_e2e imports intro/demo/tutorial/cierre: keep them all here.
        ("tutorial.mp4", ["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=2",
                          "-f", "lavfi", "-i", "sine=frequency=700:duration=2"]),
    ]
    for name, inputs in clips:
        target = media / name
        if not target.exists():
            run(FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *inputs,
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "48000", "-shortest", str(target))
    poster = media / "cierre.png"
    if not poster.exists():
        run(FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=1", "-frames:v", "1", str(poster))

    listing = {
        "root": str(media).replace("\\", "/"),
        "entries": [
            {"name": entry.name, "size": entry.stat().st_size}
            for entry in sorted(media.iterdir())
            if entry.is_file() and entry.suffix.lower() in {".mp4", ".png", ".jpg", ".wav", ".mp3"}
        ],
    }
    (HERE / "media.json").write_text(json.dumps(listing, ensure_ascii=False, indent=2), encoding="utf-8")

    base = f"http://127.0.0.1:{args.port}"
    started = False
    if not args.reuse:
        try:
            wait_health(base, seconds=1.5)
            print(json.dumps({"note": "ya había un servicio en ese puerto"}, ensure_ascii=False))
        except SystemExit:
            # En Windows el servicio se lanza DETACHED_PROCESS: sin consola
            # propia y fuera del Job Object del terminal, así sobrevive a que
            # se cierre la ventana desde la que se lanzó el banco.
            spawn: dict = {"cwd": str(CORE), "close_fds": True,
                           "stdout": subprocess.DEVNULL, "stderr": subprocess.STDOUT}
            if os.name == "nt":
                spawn["creationflags"] = (subprocess.DETACHED_PROCESS
                                          | subprocess.CREATE_NEW_PROCESS_GROUP)
                spawn["stdin"] = subprocess.DEVNULL
            else:
                spawn["start_new_session"] = True
            with open(base_dir / "service.log", "wb") as log:
                spawn["stdout"] = log
                process = subprocess.Popen(
                    [sys.executable, str(CORE / "service" / "app.py"),
                     "--data-root", str(data), "--media-root", str(media),
                     "--tools-root", TOOLS, "--port", str(args.port),
                     "--token-file", str(token_file),
                     "--allow-origin", args.harness_origin],
                    **spawn,
                )
            (base_dir / "service.pid").write_text(str(process.pid), encoding="utf-8")
            # El hijo es independiente: marcarlo como "terminado" evita que el
            # finalizador de subprocess lo sondee al apagar el intérprete, que en
            # Python 3.14/Windows revienta con OSError [WinError 6]
            # "Controlador no válido" sobre un handle ya cerrado.
            process.returncode = 0
            started = True

    health = wait_health(base)
    status, projects = call(base, "GET", "/projects")
    if status != 200:
        raise SystemExit(f"/projects devolvió {status}: {projects}")
    existing = [item for item in projects.get("projects") or [] if item.get("title") == "Lanzamiento Q4 (harness)"]
    project_id = existing[0]["projectId"] if existing else None

    if not project_id:
        status, created = call(base, "POST", "/projects", {
            "title": "Lanzamiento Q4 (harness)", "session_id": "sess_harness", "cwd": "C:/proyectos/harness",
        })
        if status != 201:
            raise SystemExit(f"crear proyecto devolvió {status}: {created}")
        project_id = created["projectId"]
        for name in ("intro.mp4", "demo.mp4", "tutorial.mp4", "cierre.png"):
            status, body = call(base, "POST", f"/projects/{project_id}/media", {"path": str(media / name).replace("\\", "/")})
            if status != 201:
                raise SystemExit(f"importar {name} devolvió {status}: {body}")
        status, current = call(base, "GET", f"/projects/{project_id}")
        draft = current["project"]
        draft["title"] = "Lanzamiento Q4 (harness)"
        if draft["scenes"]:
            draft["scenes"][0]["text"] = [{
                "at": 0.0, "until": 2.8, "position": "bottom",
                "content": "Exporta en 720p y vuelve al chat — ñandú, año, ¿acentos?",
            }]
        if len(draft["scenes"]) > 1:
            draft["scenes"][1]["transition"] = "fade-0.3"
            draft["scenes"][1]["text"] = [{"at": 0.0, "until": 1.6, "position": "top", "content": "Segunda escena con transición"}]
        status, saved = call(base, "PUT", f"/projects/{project_id}", {"revision": current["revision"], "project": draft})
        if status != 200:
            raise SystemExit(f"guardar devolvió {status}: {saved}")

    print(json.dumps({
        "service": base,
        "health": health,
        "projectId": project_id,
        "projectUrl": f"{base}/projects/{project_id}",
        "media": str(media).replace("\\", "/"),
        "data": str(data).replace("\\", "/"),
        "tokenFile": str(TOKEN_PATH).replace("\\", "/") if TOKEN_PATH else "",
        "startedNow": started,
        "servicePid": (base_dir / "service.pid").read_text(encoding="utf-8").strip()
        if (base_dir / "service.pid").exists() else None,
        "listUrl": f"{base}/projects",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
