"""Path isolation helpers for the video-editor core.

Every path that comes from a client (project document, job request, media
request) is untrusted. This module is the single place that decides whether a
path is allowed.

Rules (C7 permission matrix):
  * Media references inside a project document are RELATIVE, POSIX-style paths
    below the project media root. No drive letters, no UNC, no "..".
  * Absolute paths are only produced by ``resolve_within`` after the relative
    path has been validated and re-checked against the resolved root.
  * Windows device names (CON, NUL, COM1..) and NTFS alternate data streams
    (``file:stream``) are rejected even on platforms where they are harmless,
    so a document validated on Linux cannot become an escape on Windows.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

__all__ = [
    "PathError",
    "MAX_SEGMENT",
    "MAX_RELATIVE_LEN",
    "normalize_relative",
    "resolve_within",
    "is_within",
    "safe_job_artifact",
]

MAX_SEGMENT = 120
MAX_RELATIVE_LEN = 480

# CON, PRN, AUX, NUL, COM1-9, LPT1-9 with or without extension.
_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)
_DRIVE = re.compile(r"^[A-Za-z]:")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class PathError(ValueError):
    """Raised when a path is not acceptable under the configured root."""


def _reject(reason: str, value: object) -> None:
    raise PathError(f"{reason}: {value!r}")


def normalize_relative(value: str, *, field: str = "path") -> str:
    """Validate a relative POSIX path and return its normalized form.

    Accepts ``media/clip 01.mp4``; rejects ``../x``, ``C:/x``, ``/etc/x``,
    ``\\\\server\\share\\x``, ``a:b``, ``CON``, trailing dots/spaces and
    control characters.
    """
    if not isinstance(value, str):
        _reject(f"{field} must be a string", value)
    raw = value
    if not raw.strip():
        _reject(f"{field} must not be empty", value)
    if raw != raw.strip():
        _reject(f"{field} must not have leading or trailing whitespace", value)
    if len(raw) > MAX_RELATIVE_LEN:
        _reject(f"{field} is longer than {MAX_RELATIVE_LEN} characters", value)
    if _CONTROL.search(raw):
        _reject(f"{field} contains control characters", value)
    if _DRIVE.match(raw):
        _reject(f"{field} must be relative, not a drive path", value)
    if raw.startswith(("/", "\\")):
        _reject(f"{field} must be relative, not absolute", value)
    if "\\" in raw:
        _reject(f"{field} must use '/' separators", value)
    if ":" in raw:
        _reject(f"{field} must not contain ':' (stream or device syntax)", value)

    parts: list[str] = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            _reject(f"{field} must not contain '..'", value)
        if len(part) > MAX_SEGMENT:
            _reject(f"{field} has a segment longer than {MAX_SEGMENT}", value)
        if part.endswith(".") or part.endswith(" "):
            _reject(f"{field} has a segment ending in '.' or space", value)
        if _RESERVED.match(part):
            _reject(f"{field} uses a reserved device name", value)
        if unicodedata.normalize("NFC", part) != part:
            _reject(f"{field} is not NFC-normalized", value)
        parts.append(part)

    if not parts:
        _reject(f"{field} resolves to an empty path", value)
    normalized = "/".join(parts)
    if len(normalized) > MAX_RELATIVE_LEN:
        _reject(f"{field} is longer than {MAX_RELATIVE_LEN} characters", value)
    return normalized


def is_within(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> bool:
    """True when *path* (already absolute) sits inside *root* after resolution."""
    try:
        target = os.path.normcase(os.path.realpath(os.fspath(path)))
        base = os.path.normcase(os.path.realpath(os.fspath(root)))
    except (OSError, ValueError):
        return False
    try:
        return os.path.commonpath([target, base]) == base
    except ValueError:  # different drives on Windows
        return False


def resolve_within(
    root: str | os.PathLike[str],
    relative: str,
    *,
    must_exist: bool = False,
    field: str = "path",
) -> Path:
    """Resolve *relative* under *root*, refusing anything that escapes it.

    Symlinks/junctions are resolved first, so a link inside the root that
    points outside is rejected even though the lexical path looks fine.
    """
    rel = normalize_relative(relative, field=field)
    root_path = Path(root)
    candidate = root_path / rel
    # realpath resolves junctions; the containment check is done on the result.
    resolved = Path(os.path.realpath(candidate))
    if not is_within(resolved, root_path):
        _reject(f"{field} escapes its root", relative)
    if must_exist and not resolved.is_file():
        _reject(f"{field} does not exist as a file", relative)
    return resolved


def safe_job_artifact(name: str, *, allowed: set[str]) -> str:
    """Validate that *name* is one of the job artifacts we published.

    Used by ``GET /media/{job}/{file}``: the URL segment never touches the
    filesystem until it matches a name recorded in the journal, and even then
    it must be a single, clean file name.
    """
    if not isinstance(name, str):
        _reject("artifact name must be a string", name)
    candidate = name.strip()
    if candidate != name or not candidate:
        _reject("artifact name must not be empty or padded", name)
    if "/" in candidate or "\\" in candidate or ":" in candidate:
        _reject("artifact name must be a single file name", name)
    if candidate.startswith("."):
        _reject("artifact name must not be hidden", name)
    if _CONTROL.search(candidate):
        _reject("artifact name contains control characters", name)
    if _RESERVED.match(candidate):
        _reject("artifact name is a reserved device name", name)
    if candidate not in allowed:
        _reject("artifact is not published by this job", name)
    return candidate
