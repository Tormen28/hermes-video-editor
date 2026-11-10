"""Service token: one shared secret between the service, its tools and the pane.

Threat model: the service listens on 127.0.0.1, but the pane runs from ``file://``
(``Origin: null``). A page the user merely visits (sandboxed iframe, downloaded
HTML) also sends ``Origin: null`` and could drive the API (CSRF). So the origin
check alone is not enough: every API call must carry ``X-VE-Token``. A foreign
page cannot read the token (it lives in a file under the user profile and inside
the installed ``plugin.js``), so it cannot make an authorised request.

The token is never put in a URL, never logged and never echoed by the API.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

TOKEN_HEADER = "X-VE-Token"
TOKEN_ENV = "VE_SERVICE_TOKEN"
TOKEN_FILE_ENV = "VE_TOKEN_FILE"
MIN_TOKEN_LENGTH = 24


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def default_token_path() -> Path:
    override = os.environ.get(TOKEN_FILE_ENV)
    if override:
        return Path(override).expanduser()
    return hermes_home() / "video-editor" / "service.token"


def _valid(token: str) -> bool:
    return len(token) >= MIN_TOKEN_LENGTH and token.isprintable() and not any(c.isspace() for c in token)


def load_or_create_token(path: str | os.PathLike[str] | None = None) -> str:
    """Return the token: env var first, then the token file (created if missing)."""
    env = (os.environ.get(TOKEN_ENV) or "").strip()
    if env:
        if not _valid(env):
            raise ValueError(f"{TOKEN_ENV} is too short (min {MIN_TOKEN_LENGTH} chars)")
        return env
    target = Path(path) if path else default_token_path()
    if target.is_file():
        token = target.read_text(encoding="utf-8").strip()
        if _valid(token):
            return token
    target.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(token + "\n", encoding="utf-8")
    os.replace(tmp, target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return token


def read_token(path: str | os.PathLike[str] | None = None) -> str | None:
    """Read-only variant for client tools: never creates a file."""
    env = (os.environ.get(TOKEN_ENV) or "").strip()
    if env:
        return env
    target = Path(path) if path else default_token_path()
    try:
        token = target.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token if _valid(token) else None


def matches(expected: str | None, supplied: str | None) -> bool:
    """Constant-time comparison; an unset expectation never matches."""
    if not expected or not supplied:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), supplied.strip().encode("utf-8"))