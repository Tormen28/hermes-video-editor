"""hermes-cinema — the agent half of the package.

The Desktop pane cannot start a process and must not carry a token that an
installer rewrote. This module owns both:

* the local loopback service (``core/``) — ``hermes cinema start|stop|status``
  and the ``cinema_status`` / ``cinema_start`` tools;
* the pairing — the RPC ``plugin.hermes-cinema.pair`` hands the pane
  ``{service, token}``; the token lives in ``plugin-data/hermes-cinema`` and the
  pane caches it in ``ctx.storage``.

Nothing here listens on the network and nothing prints the token to a log.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("plugin.hermes-cinema")

PLUGIN_ID = "hermes-cinema"
ROOT = Path(__file__).resolve().parent
CORE = ROOT / "core"
LAUNCHER = CORE / "start_service.py"
DEFAULT_PORT = 8770
HEALTH_TIMEOUT_S = 3.0

_STATUS_SCHEMA = {
    "name": "cinema_status",
    "description": "Check whether the local Hermes Cinema service is running and on which port.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

_START_SCHEMA = {
    "name": "cinema_start",
    "description": "Start the local Hermes Cinema service (loopback only) if it is not running.",
    "parameters": {
        "type": "object",
        "properties": {"port": {"type": "integer", "minimum": 1024, "maximum": 65535}},
        "additionalProperties": False,
    },
}


# --- settings ---------------------------------------------------------------
def _config() -> dict:
    """Plugin settings with defaults (``ctx.get_config()`` when available)."""
    raw: dict = {}
    ctx = _CTX
    if ctx is not None:
        try:
            raw = ctx.get_config() or {}
        except Exception:  # noqa: BLE001 - settings must never break the plugin
            raw = {}
    port = raw.get("port") or DEFAULT_PORT
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    media = raw.get("mediaRoot") or str(Path.home() / "Videos" / "hermes-cinema")
    return {"port": port, "mediaRoot": str(media), "language": raw.get("language") or "en"}


def _data_dir() -> Path:
    """Per-plugin data dir (survives plugin updates); falls back to the Hermes home."""
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore
        return Path(plugin_data_dir(PLUGIN_ID))
    except Exception:  # noqa: BLE001
        home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
        root = Path(home) / "plugin-data" / PLUGIN_ID
        root.mkdir(parents=True, exist_ok=True)
        return root


def token_path() -> Path:
    return _data_dir() / "service.token"


def _read_token() -> str:
    try:
        return token_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# --- service ----------------------------------------------------------------
def health(port: int | None = None, timeout: float = HEALTH_TIMEOUT_S) -> dict | None:
    port = port or _config()["port"]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - "not running" is a state, not an error
        return None


def start(port: int | None = None) -> dict:
    cfg = _config()
    port = int(port or cfg["port"])
    running = health(port)
    if running:
        return {"ok": True, "alreadyRunning": True, "port": port, "health": running,
                "tokenFile": str(token_path())}
    if not LAUNCHER.is_file():
        return {"ok": False, "error": f"missing {LAUNCHER}"}
    cmd = [sys.executable, str(LAUNCHER), "--ensure",
           "--data-root", str(_data_dir() / "data"),
           "--media-root", cfg["mediaRoot"],
           "--port", str(port),
           "--token-file", str(token_path())]
    try:
        out = subprocess.run(cmd, cwd=str(CORE), capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": f"launcher failed: {exc}"}
    if out.returncode != 0:
        return {"ok": False, "error": (out.stderr or out.stdout or "launcher failed")[-400:]}
    return {"ok": bool(health(port)), "port": port, "tokenFile": str(token_path()),
            "launcher": (out.stdout or "").strip()[-400:]}


def stop(port: int | None = None) -> dict:
    port = int(port or _config()["port"])
    if not LAUNCHER.is_file():
        return {"ok": False, "error": f"missing {LAUNCHER}"}
    cmd = [sys.executable, str(LAUNCHER), "--stop", "--port", str(port),
           "--token-file", str(token_path())]
    try:
        out = subprocess.run(cmd, cwd=str(CORE), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": f"stop failed: {exc}"}
    return {"ok": out.returncode == 0, "port": port, "detail": (out.stdout or "").strip()[-200:]}


# --- pairing ----------------------------------------------------------------
def pair(**_kwargs) -> dict:
    """Hand the pane the service URL and its token (created on first call)."""
    cfg = _config()
    port = cfg["port"]
    if not health(port):
        start(port)
    token = _read_token()
    if not token:
        start(port)  # the service creates the token file on boot
        token = _read_token()
    return {"service": f"http://127.0.0.1:{port}", "token": token,
            "language": cfg["language"], "running": bool(health(port))}


# --- tools ------------------------------------------------------------------
def _tool_status(_args=None, **_kwargs) -> dict:
    cfg = _config()
    info = health(cfg["port"])
    return {"running": bool(info), "port": cfg["port"], "health": info,
            "tokenFile": str(token_path())}


def _tool_start(args=None, **_kwargs) -> dict:
    port = None
    if isinstance(args, dict) and args.get("port"):
        port = args["port"]
    return start(port)


def _cli_setup(parser) -> None:
    sub = parser.add_subparsers(dest="cinema_command", required=True)
    sub.add_parser("start", help="start the loopback service")
    sub.add_parser("stop", help="stop the loopback service")
    sub.add_parser("status", help="is the service running?")
    pair_p = sub.add_parser("pair", help="print the service URL and token (local only)")
    pair_p.add_argument("--show-token", action="store_true", help="print the token too")


def _cli_run(args) -> int:
    cmd = getattr(args, "cinema_command", "status")
    if cmd == "start":
        print(json.dumps(start(), ensure_ascii=False))
        return 0
    if cmd == "stop":
        print(json.dumps(stop(), ensure_ascii=False))
        return 0
    if cmd == "pair":
        info = pair()
        if not getattr(args, "show_token", False):
            info["token"] = "***" if info.get("token") else ""
        print(json.dumps(info, ensure_ascii=False))
        return 0
    info = _tool_status()
    print(json.dumps(info, ensure_ascii=False))
    return 0 if info["running"] else 1


_CTX = None


def register(ctx) -> None:
    global _CTX
    _CTX = ctx
    ctx.register_tool(name="cinema_status", toolset="cinema", schema=_STATUS_SCHEMA,
                      handler=_tool_status)
    ctx.register_tool(name="cinema_start", toolset="cinema", schema=_START_SCHEMA,
                      handler=_tool_start)
    if hasattr(ctx, "register_cli_command"):
        ctx.register_cli_command("cinema", "Hermes Cinema: local video editor service",
                                 _cli_setup, _cli_run,
                                 description="Start, stop or inspect the loopback service "
                                             "the Hermes Cinema pane uses.")
    if hasattr(ctx, "register_rpc"):
        ctx.register_rpc("pair", pair)
    if hasattr(ctx, "register_command"):
        def _slash(_args: str = "") -> str:
            info = _tool_status()
            return (f"Hermes Cinema: {'running' if info['running'] else 'stopped'} "
                    f"on port {info['port']}")
        ctx.register_command("cinema", _slash)
    logger.info("%s: registered (port=%s, token=%s)", PLUGIN_ID, _config()["port"],
                "present" if _read_token() else "not created yet")
