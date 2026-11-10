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
sys.path.insert(0, str(HERE / "core"))
from service import auth  # noqa: E402
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


def token_path(hermes_home: Path) -> Path:
    return Path(hermes_home) / SERVICE_NAME / "service.token"


def stop_service(port: int, token_file: Path | None = None) -> bool:
    token = auth.read_token(token_file)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/admin/stop", data=b"{}", method="POST",
        headers={auth.TOKEN_HEADER: token} if token else {},
    )
    try:
        urllib.request.urlopen(request, timeout=5).read()
        return True
    except Exception:
        return False


def queue_busy(port: int, token_file: Path) -> bool | None:
    """True if an export is queued/running; None if we cannot tell."""
    token = auth.read_token(token_file)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/health", headers={auth.TOKEN_HEADER: token} if token else {}
    )
    try:
        data = json.loads(urllib.request.urlopen(request, timeout=3).read().decode("utf-8"))
    except Exception:
        return None
    queue = data.get("queue")
    if not isinstance(queue, dict):
        return None
    return bool(queue.get("queued") or queue.get("running"))


def startup_script() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "hermes-video-editor.cmd"


def set_autostart(enable: bool, config_path: Path) -> None:
    target = startup_script()
    if target is None:
        print("autoarranque: solo disponible en Windows")
        return
    if not enable:
        if target.is_file():
            target.unlink()
            print(f"autoarranque quitado: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    launcher = HERE / "core" / "start_service.py"
    target.write_text(
        "@echo off\r\n"
        f'"{sys.executable}" "{launcher}" --ensure --config "{config_path}" --token-file "{config_path.parent / "service.token"}" >nul 2>&1\r\n',
        encoding="utf-8",
    )
    print(f"autoarranque activado (al iniciar sesión): {target}")


def install(args: argparse.Namespace) -> int:
    hermes_home = Path(args.hermes_home).expanduser().resolve()
    plugin_target = hermes_home / "desktop-plugins" / PLUGIN_ID / "plugin.js"
    source = HERE / "plugin" / "plugin.js"
    if not source.is_file():
        print(f"ERROR: no encuentro {source}")
        return 1

    config_dir = hermes_home / SERVICE_NAME
    config_path = config_dir / "config.json"
    previous: dict = {}
    if config_path.is_file():
        try:
            previous = json.loads(config_path.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
    # Lo que ya tienes manda: reinstalar nunca cambia de carpeta de datos/medios por sorpresa.
    media_root = Path(args.media_root or previous.get("mediaRoot") or Path.home() / "Videos" / "hermes-video").expanduser().resolve()
    data_root = Path(args.data_root or previous.get("dataRoot") or config_dir / "data").expanduser().resolve()
    media_root.mkdir(parents=True, exist_ok=True)

    plugin_target.parent.mkdir(parents=True, exist_ok=True)
    if plugin_target.is_file() and not args.force:
        backup = plugin_target.with_suffix(".js.bak")
        shutil.copy2(plugin_target, backup)
        print(f"respaldo del plugin anterior: {backup}")
    tfile = token_path(hermes_home)
    token = auth.load_or_create_token(tfile)
    code = source.read_text(encoding="utf-8")
    marker = "const SERVICE_TOKEN = '__VE_TOKEN__'"
    if marker not in code:
        print("ERROR: el plugin no tiene el marcador del token; no se instala")
        return 1
    plugin_target.write_text(code.replace(marker, f"const SERVICE_TOKEN = '{token}'", 1), encoding="utf-8")
    print(f"plugin instalado: {plugin_target}")
    print(f"token del servicio: {tfile} (solo tu usuario; no lo compartas)")

    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "dataRoot": str(data_root),
        "mediaRoot": str(media_root),
        "port": int(args.port),
    }
    if args.tools_root:
        config["toolsRoot"] = str(Path(args.tools_root).expanduser().resolve())
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"config: {config_path}")
    print(f"medios: {media_root}")
    print(f"datos:  {data_root}")

    if args.no_start:
        print("servicio NO arrancado (--no-start). Arráncalo con: core/iniciar-servicio.cmd")
        return 0

    if args.autostart is not None:
        set_autostart(args.autostart, config_path)

    current = health(args.port)
    if current and args.restart:
        busy = queue_busy(args.port, tfile)
        if busy is not False:
            print("NO se reinicia: hay una exportación en curso (o no se pudo comprobar). Reintenta cuando acabe.")
            return 2
        if not stop_service(args.port, tfile):
            print("ERROR: el servicio no aceptó parar (¿ya usa token y falta el archivo?).")
            return 1
        wait_stopped(args.port)
        current = None
    if current:
        secured = bool(current.get("authRequired"))
        print(f"servicio ya activo en {args.port} (v{current.get('service')}); no se reinicia")
        if not secured:
            print("AVISO: ese servicio es una versión anterior SIN protección por token.")
            print("       Cuando no tengas exportaciones en curso, ejecuta:  python instalar.py --restart")
    else:
        command = [sys.executable, str(HERE / "core" / "start_service.py"), "--config", str(config_path),
                   "--token-file", str(tfile)]
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
    stopped = stop_service(args.port, token_path(hermes_home))
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
    parser.add_argument("--media-root", default=None, help="carpeta de medios (por defecto la ya configurada)")
    parser.add_argument("--data-root", default=None, help="carpeta de datos/proyectos (por defecto la ya configurada)")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--tools-root", default=None, help="carpeta con ffmpeg/ffprobe (autodetectado si se omite)")
    parser.add_argument("--no-start", action="store_true")
    parser.add_argument("--restart", action="store_true", help="reinicia el servicio (solo si no hay exportaciones en curso)")
    parser.add_argument("--autostart", dest="autostart", action="store_true", default=None,
                        help="arrancar el servicio al iniciar sesión de Windows (opcional)")
    parser.add_argument("--no-autostart", dest="autostart", action="store_false", help="quitar el autoarranque")
    parser.add_argument("--force", action="store_true", help="sobrescribe sin respaldo")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args()
    return uninstall(args) if args.uninstall else install(args)


if __name__ == "__main__":
    raise SystemExit(main())
