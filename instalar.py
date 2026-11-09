"""Instalador del plugin Editor de vídeo para Hermes Desktop.

Instala el pane en Hermes, crea la carpeta de medios y el servicio, y lo arranca.
No publica nada ni toca configuración de modelos/proveedores de Hermes.

Uso:
  python instalar.py                       # instala y arranca
  python instalar.py --media-root D:/clips # carpeta de medios concreta
  python instalar.py --no-start            # solo instala
  python instalar.py --uninstall           # quita el plugin (conserva datos)
  python instalar.py --uninstall --purge   # quita plugin, datos y config
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ID = "editor-video"
SERVICE_NAME = "video-editor"


def default_hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def health(port: int, timeout: float = 3.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def wait_stopped(port: int, timeout: float = 12.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health(port) is None:
            return True
        time.sleep(0.35)
    return False


def stop_service(port: int) -> bool:
    request = urllib.request.Request(f"http://127.0.0.1:{port}/admin/stop", data=b"{}", method="POST")
    try:
        urllib.request.urlopen(request, timeout=5).read()
        return True
    except Exception:
        return False


def install(args: argparse.Namespace) -> int:
    hermes_home = Path(args.hermes_home).expanduser().resolve()
    plugin_target = hermes_home / "desktop-plugins" / PLUGIN_ID / "plugin.js"
    source = HERE / "plugin" / "plugin.js"
    if not source.is_file():
        print(f"ERROR: no encuentro {source}")
        return 1

    media_root = Path(args.media_root).expanduser().resolve()
    media_root.mkdir(parents=True, exist_ok=True)

    plugin_target.parent.mkdir(parents=True, exist_ok=True)
    if plugin_target.is_file() and not args.force:
        backup = plugin_target.with_suffix(".js.bak")
        shutil.copy2(plugin_target, backup)
        print(f"respaldo del plugin anterior: {backup}")
    shutil.copy2(source, plugin_target)
    print(f"plugin instalado: {plugin_target}")

    config_dir = hermes_home / SERVICE_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "dataRoot": str(config_dir / "data"),
        "mediaRoot": str(media_root),
        "port": int(args.port),
    }
    if args.tools_root:
        config["toolsRoot"] = str(Path(args.tools_root).expanduser().resolve())
    config_path = config_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"config: {config_path}")
    print(f"medios: {media_root}")

    if args.no_start:
        print("servicio NO arrancado (--no-start). Arráncalo con: core/iniciar-servicio.cmd")
        return 0

    current = health(args.port)
    if current:
        print(f"servicio ya activo en {args.port} (v{current.get('service')}); no se reinicia")
    else:
        command = [sys.executable, str(HERE / "core" / "start_service.py"), "--config", str(config_path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        print(result.stdout.strip() or result.stderr.strip())
        current = health(args.port)
        if not current:
            print("ERROR: el servicio no respondió tras arrancarlo")
            return 1

    print("")
    print("LISTO. Para verlo: cierra el pane del editor, ve a Capacidades → Plugins")
    print("y apaga/enciende «Editor de vídeo». Luego ábrelo desde Ctrl+K.")
    print(f"Servicio: http://127.0.0.1:{args.port}/health (v{current.get('service')})")
    print(f"Proveedores de generación: locales activos; HTTP solo si defines VE_PROVIDER_*_URL")
    return 0


def uninstall(args: argparse.Namespace) -> int:
    hermes_home = Path(args.hermes_home).expanduser().resolve()
    plugin_dir = hermes_home / "desktop-plugins" / PLUGIN_ID
    stopped = stop_service(args.port)
    if stopped:
        wait_stopped(args.port)
    print("servicio detenido" if stopped else "servicio no estaba activo o no se pudo parar")

    if plugin_dir.is_dir():
        backup = plugin_dir.with_name(f"{PLUGIN_ID}.removed-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.move(plugin_dir, backup)
        print(f"plugin retirado (respaldo en {backup})")
    else:
        print("plugin no estaba instalado")

    if args.purge:
        config_dir = hermes_home / SERVICE_NAME
        if config_dir.is_dir():
            last_error: Exception | None = None
            for _attempt in range(6):
                try:
                    shutil.rmtree(config_dir)
                    last_error = None
                    break
                except PermissionError as exc:  # sqlite tarda en soltar el handle
                    last_error = exc
                    time.sleep(0.6)
            if last_error is None:
                print(f"datos y config eliminados: {config_dir}")
            else:
                print(f"AVISO: no se pudieron borrar todos los datos ({last_error}); ciérralo y reintenta")
    else:
        print("datos y config conservados (usa --purge para borrarlos)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Instalador del Editor de vídeo para Hermes Desktop")
    parser.add_argument("--hermes-home", default=str(default_hermes_home()))
    parser.add_argument("--media-root", default=str(Path.home() / "Videos" / "hermes-video"))
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--tools-root", default=None, help="carpeta con ffmpeg/ffprobe (autodetectado si se omite)")
    parser.add_argument("--no-start", action="store_true")
    parser.add_argument("--force", action="store_true", help="sobrescribe sin respaldo")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args()
    return uninstall(args) if args.uninstall else install(args)


if __name__ == "__main__":
    raise SystemExit(main())
