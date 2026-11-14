"""Arranca el servicio del núcleo DESACOPLADO del proceso que lo invoca.

El servicio del spike murió con el árbol de procesos del agente que lo lanzó y el
pane mostró «Failed to fetch». Este lanzador evita que se repita: DETACHED_PROCESS
+ nuevo grupo, log a core/logs/service.stdout.log, y verificación inmediata de /health.

Uso:
  python start_service.py --data-root core/data --media-root <carpeta de medios> --port 8770
  python start_service.py --ensure ...      # si ya responde, no hace nada; si no, lo arranca
  python start_service.py --stop            # pide /admin/stop (con el token del servicio)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from service import auth  # noqa: E402

HERE = Path(__file__).resolve().parent
LOG_DIR = HERE / "logs"
LOG = LOG_DIR / "service.stdout.log"

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def health(port: int, timeout: float = 3.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="JSON con dataRoot/mediaRoot/port/toolsRoot")
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--media-root", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--tools-root", default=None)
    ap.add_argument("--no-admin", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--ensure", action="store_true", help="no relanza si ya hay un servicio sano en el puerto")
    ap.add_argument("--token-file", default=None, help="archivo del token (por defecto el de Hermes)")
    args = ap.parse_args()

    config: dict = {}
    if args.config:
        config_path = Path(args.config).expanduser().resolve()
        if not config_path.is_file():
            print(f"config no encontrada: {config_path}")
            return 1
        config = json.loads(config_path.read_text(encoding="utf-8"))
        base = config_path.parent
        for key in ("dataRoot", "mediaRoot"):
            value = config.get(key)
            if isinstance(value, str) and not Path(value).is_absolute():
                config[key] = str((base / value).resolve())
    data_root = args.data_root or config.get("dataRoot") or str(HERE / "data")
    media_root = args.media_root or config.get("mediaRoot") or str(HERE / "media")
    port = int(args.port or config.get("port") or 8770)
    tools_root = args.tools_root or config.get("toolsRoot")

    if args.stop:
        try:
            token = auth.read_token(args.token_file)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/admin/stop", data=b"{}", method="POST",
                headers={auth.TOKEN_HEADER: token} if token else {},
            )
            urllib.request.urlopen(req, timeout=5).read()
            print(f"stop solicitado en {port}")
        except Exception as exc:  # noqa: BLE001
            print(f"no se pudo parar: {exc}")
            return 1
        return 0

    if args.ensure:
        info = health(port)
        if info:
            print(json.dumps({"port": port, "health": info, "alreadyRunning": True}, ensure_ascii=False))
            return 0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(HERE / "service" / "app.py"),
        "--data-root", str(Path(data_root).resolve()),
        "--media-root", str(Path(media_root).resolve()),
        "--port", str(port),
    ]
    if tools_root:
        cmd += ["--tools-root", str(tools_root)]
    if args.no_admin:
        cmd.append("--no-admin")
    if args.token_file:
        cmd += ["--token-file", str(Path(args.token_file).expanduser().resolve())]

    if os.name == "nt":
        base_flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        # Primero intenta salir del Job Object del proceso que lanza (si no,
        # Windows mata el servicio al cerrar el terminal del agente). Si el job
        # no permite breakaway, cae al modo simple.
        attempts = (base_flags | CREATE_BREAKAWAY_FROM_JOB, base_flags)
    else:
        # POSIX no tiene creationflags: un grupo de sesión nuevo basta para que el
        # servicio sobreviva al proceso que lo lanzó.
        attempts = (0,)
    last_error: OSError | None = None
    proc = None
    for flags in attempts:
        try:
            with open(LOG, "ab") as log:
                detached = ({"creationflags": flags} if os.name == "nt"
                            else {"start_new_session": True})
                proc = subprocess.Popen(
                    cmd, cwd=str(HERE), stdout=log, stderr=log,
                    stdin=subprocess.DEVNULL, close_fds=True, **detached,
                )
            break
        except OSError as exc:  # job sin permiso de breakaway
            last_error = exc
    if proc is None:
        raise SystemExit(f"no se pudo lanzar el servicio: {last_error}")

    for _ in range(40):
        info = health(port)
        if info:
            print(json.dumps({
                "launcherPid": proc.pid,
                "port": port,
                "health": info,
            }, ensure_ascii=False))
            return 0
        time.sleep(0.25)

    print(f"servicio lanzado (pid {proc.pid}) pero /health no responde en el puerto {port}")
    print(f"revisa {LOG}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
