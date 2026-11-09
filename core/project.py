"""Project document: validation, non-destructive migration, deterministic I/O.

The document is the single source of truth for preview and export (PLAN 2.1).
This module owns:

* the canonical shape (schema/project.schema.json is the published mirror),
* validation of every value the renderer will consume,
* non-destructive migration from older shapes (nothing is dropped, nothing is
  rewritten in place; callers always get a new dict),
* deterministic serialization (sorted keys, fixed float precision) so two runs
  over the same document produce byte-identical files and the same hash,
* optimistic concurrency (``baseRevision`` vs stored ``revision``).

No third-party imports: only the standard library.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import paths as path_rules

SCHEMA_VERSION = 1

#: Engine identity written when a document does not carry one.
DEFAULT_ENGINE_TAG = "ffmpeg-9.0.1"

MIN_SCENE_DURATION = 0.3
MAX_SCENE_DURATION = 1200.0
MAX_TOTAL_DURATION = 1200.0  # 20 minutes, C7
MAX_JOB_INPUT_BYTES = 2 * 1024**3  # 2 GiB, C7
MAX_SCENES = 100
MAX_ASSETS = 200
MAX_TEXT_ITEMS = 50
MAX_TEXT_LENGTH = 500
MAX_WIDTH = 7680
MAX_HEIGHT = 8192
MAX_FPS = 240
MVP_MAX_SIDE = 1920  # longest side, either axis
MVP_MAX_PIXELS = 1920 * 1080  # portrait 1080x1920 costs the same as landscape
MVP_MAX_FPS = 60
FLOAT_DECIMALS = 3

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ENGINE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
#: Real crossfade transitions (phase 2B). Every name maps 1:1 to an ffmpeg
#: ``xfade`` transition, so nothing is translated and nothing is invented.
TRANSITION_STYLES = (
    "fade", "slideleft", "slideright", "wipeleft", "wiperight", "circleopen", "zoomin",
)
TRANSITION_MIN_S = 0.1
TRANSITION_MAX_S = 2.0
_TRANSITION_RE = re.compile(
    r"^(?P<style>" + "|".join(TRANSITION_STYLES) + r")-(?P<seconds>[0-9]+(?:\.[0-9]+)?)$"
)
_FADE_RE = re.compile(r"^fade-([0-9]+(?:\.[0-9]+)?)$")
_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

ORIENTATIONS = ("h", "v")
SOURCE_KINDS = ("video", "image")
ASSET_KINDS = ("video", "image", "audio")
TEXT_POSITIONS = ("top", "center", "bottom")
#: ``generated`` is the only status the service writes itself: an asset produced
#: by the generation engine (phase 3A), never uploaded by the user.
RIGHTS_STATUS = ("owned", "licensed", "public-domain", "unknown", "generated")

#: Text styling (pack v1.1, phase 2A). Defaults render old documents unchanged
#: in shape: a document without these keys still validates and renders.
TEXT_SIZE_MIN = 12
TEXT_SIZE_MAX = 120
TEXT_SIZE_DEFAULT = 42
TEXT_COLOR_DEFAULT = "#FFFFFF"
TEXT_BORDER_COLOR_DEFAULT = "#000000"
TEXT_BORDER_MAX = 10
TEXT_SHADOW_MAX = 10
TEXT_ANIMATIONS = ("none", "fade", "slide-up", "slide-down")
TEXT_ANIMATION_DEFAULT = {"in": "none", "out": "none"}

#: Per-scene colour filters, applied before scale/pad.
SCENE_FILTER_RANGES = {
    "brightness": (-1.0, 1.0),
    "contrast": (0.0, 2.0),
    "saturation": (0.0, 3.0),
    "blur": (0.0, 20.0),
}
SCENE_FILTER_FLAGS = ("grayscale", "vignette")

#: Brand watermark (phase 2A).
LOGO_POSITIONS = (
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
)
LOGO_POSITION_DEFAULT = "bottom-right"
LOGO_OPACITY_DEFAULT = 0.8
LOGO_SCALE_DEFAULT = 0.15
LOGO_SCALE_MIN = 0.05
LOGO_SCALE_MAX = 0.5

#: Ken Burns slow camera motion for still images (phase 2C). ``pan`` names the
#: direction the view travels across the picture; a zoom of 1.0 leaves no room
#: to travel, so pan and zoom > 1 ship together.
KEN_BURNS_PANS = ("none", "left", "right", "up", "down")
KEN_BURNS_ZOOM_MIN = 1.0
KEN_BURNS_ZOOM_MAX = 1.5
KEN_BURNS_ZOOM_DEFAULT = 1.2

#: Per-scene playback speed (phase 2C). 1.0 is the identity: a document without
#: ``speed`` renders byte-identically to 2B.
SCENE_SPEED_MIN = 0.5
SCENE_SPEED_MAX = 2.0

#: Sound effects on the timeline (phase 3A). One event pins one audio asset at
#: an absolute second with its own gain and fades; the mixer delays it, fades it
#: and mixes it next to the scene audio and the music bed.
MAX_AUDIO_EVENTS = 50
SFX_VOLUME_DEFAULT = 100
SFX_FADE_MAX = 10.0


class ProjectError(ValueError):
    """Base class for document problems."""


class ValidationError(ProjectError):
    def __init__(self, errors: Iterable[str], warnings: Iterable[str] = ()):
        self.errors = list(errors)
        self.warnings = list(warnings)
        super().__init__("; ".join(self.errors) or "invalid project document")


class RevisionConflict(ProjectError):
    """The document changed under the caller (HTTP 409)."""

    def __init__(self, expected: int, current: int):
        self.expected = expected
        self.current = current
        super().__init__(f"revision conflict: expected {expected}, current {current}")


class UnsupportedSchemaVersion(ProjectError):
    """A document written by a newer core cannot be opened safely."""


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def now_iso() -> str:
    """UTC timestamp with second precision, always ``Z``-terminated."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _round(value: float) -> float:
    rounded = round(float(value), FLOAT_DECIMALS)
    return 0.0 if rounded == 0 else rounded


def _is_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _is_iso(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def scene_speed(scene: dict) -> float:
    """Playback multiplier for one scene (1.0 when absent or unusable).

    The renderer consumes whatever a document says, valid or not, so this can
    never raise: an unvalidated value degrades to the identity speed.
    """
    value = scene.get("speed") if isinstance(scene, dict) else None
    if not _is_num(value) or float(value) <= 0:
        return 1.0
    return round(float(value), FLOAT_DECIMALS)


def scene_source_duration(scene: dict) -> float:
    """Seconds of source material the trim covers (``out - in``)."""
    return round(float(scene.get("out", 0)) - float(scene.get("in", 0)), FLOAT_DECIMALS)


def scene_duration(scene: dict) -> float:
    """Seconds the scene occupies on screen: source span divided by ``speed``.

    Every timeline calculation (overlaps, starts, total length) goes through
    here, so a sped-up scene shortens the render everywhere at once.
    """
    return round(scene_source_duration(scene) / scene_speed(scene), FLOAT_DECIMALS)


def ken_burns(scene: dict) -> dict | None:
    """Resolved Ken Burns motion for a scene, or ``None`` when it is a still.

    ``zoom`` defaults to 1.2 and is clamped to the documented range; the
    validator is what rejects out-of-range values. The renderer only skips the
    motion when it would be invisible (zoom 1.0 with no pan).
    """
    motion = scene.get("kenBurns") if isinstance(scene, dict) else None
    if not isinstance(motion, dict):
        return None
    zoom = motion.get("zoom")
    zoom = float(zoom) if _is_num(zoom) else KEN_BURNS_ZOOM_DEFAULT
    pan = motion.get("pan") or "none"
    if pan not in KEN_BURNS_PANS:
        pan = "none"
    zoom = max(KEN_BURNS_ZOOM_MIN, min(KEN_BURNS_ZOOM_MAX, zoom))
    if zoom <= KEN_BURNS_ZOOM_MIN and pan == "none":
        return None
    return {"zoom": zoom, "pan": pan}



def total_duration(doc: dict) -> float:
    return round(sum(scene_duration(s) for s in doc.get("scenes", []) if isinstance(s, dict)), FLOAT_DECIMALS)


def transition_parts(value: Any) -> tuple[str, float]:
    """``"none"`` -> ``("none", 0.0)``; ``"slideleft-0.5"`` -> ``("slideleft", 0.5)``.

    The style is the half of the wire format that ffmpeg's ``xfade`` also uses
    as a literal value, so this is the only place that knows the catalogue.
    Raises :class:`ProjectError` on anything outside it.
    """
    if value in (None, "", "none"):
        return "none", 0.0
    if isinstance(value, str):
        match = _TRANSITION_RE.match(value)
        if match:
            return match.group("style"), _round(float(match.group("seconds")))
    raise ProjectError(f"unsupported transition: {value!r}")


def transition_style(value: Any) -> str:
    """Transition name only (``"none"`` when the scene enters with a cut)."""
    return transition_parts(value)[0]


def transition_seconds(value: Any) -> float:
    """``"none"`` -> 0.0, ``"fade-0.3"`` -> 0.3. Raises on anything else."""
    return transition_parts(value)[1]


def scene_overlap(scene: dict) -> float:
    """Seconds this scene shares with the one before it (0.0 for a cut)."""
    return transition_seconds(scene.get("transition", "none"))


def transition_overlaps(doc: dict) -> list[float]:
    """Overlap entering each scene, index-aligned with ``doc["scenes"]``.

    ``scenes[0]`` never overlaps: there is no previous scene to blend with, so
    its transition is ignored by the renderer (documented in CONTRATO.md). Every
    other value is clamped to the shorter of the two neighbours so an unvalidated
    document can never produce a negative offset in the filtergraph.
    """
    scenes = [s for s in doc.get("scenes") or [] if isinstance(s, dict)]
    durations = [scene_duration(scene) for scene in scenes]
    overlaps = [0.0]
    for index in range(1, len(scenes)):
        requested = scene_overlap(scenes[index])
        limit = min(durations[index], durations[index - 1])
        overlaps.append(_round(min(requested, limit)) if requested > 0 else 0.0)
    return overlaps


def scene_starts(doc: dict) -> list[float]:
    """Absolute start of every scene on the final timeline, overlaps removed."""
    scenes = [s for s in doc.get("scenes") or [] if isinstance(s, dict)]
    overlaps = transition_overlaps(doc)
    starts: list[float] = []
    cursor = 0.0
    for index, scene in enumerate(scenes):
        starts.append(_round(cursor))
        cursor += scene_duration(scene)
        if index + 1 < len(scenes):
            cursor -= overlaps[index + 1]
    return starts


def timeline_duration(doc: dict) -> float:
    """Final render length: scene sum minus every crossfade overlap."""
    scenes = [s for s in doc.get("scenes") or [] if isinstance(s, dict)]
    overlaps = transition_overlaps(doc)
    return _round(sum(scene_duration(s) for s in scenes) - sum(overlaps[1:]))


def has_crossfade(doc: dict) -> bool:
    """True when at least one scene overlaps the previous one."""
    return any(overlap > 0 for overlap in transition_overlaps(doc)[1:])


# --------------------------------------------------------------------------- #
# construction
# --------------------------------------------------------------------------- #


def new_project(
    project_id: str,
    title: str,
    *,
    width: int = 1280,
    height: int = 720,
    fps_num: int = 30,
    fps_den: int = 1,
    engine_tag: str = DEFAULT_ENGINE_TAG,
    session_id: str | None = None,
    cwd: str | None = None,
) -> dict:
    stamp = now_iso()
    doc = {
        "schemaVersion": SCHEMA_VERSION,
        "projectId": project_id,
        "revision": 0,
        "baseRevision": 0,
        "title": title,
        "sessionId": session_id,
        "cwd": cwd,
        "engineTag": engine_tag,
        "fps": {"num": int(fps_num), "den": int(fps_den)},
        "width": int(width),
        "height": int(height),
        "orientation": "h" if width >= height else "v",
        "audio": {"masterVolume": 100},
        "scenes": [],
        "assets": [],
        "createdAt": stamp,
        "updatedAt": stamp,
    }
    check(doc)
    return normalize(doc)


def _fresh_id(prefix: str, used: set[str]) -> str:
    """A short id that is unique inside the document being built."""
    while True:
        candidate = prefix + secrets.token_hex(4)
        if candidate not in used:
            used.add(candidate)
            return candidate


def _copy_title(title: Any) -> str:
    """``"<título> (copia)"`` without ever exceeding the title limit (200)."""
    base = title if isinstance(title, str) and title.strip() else "Proyecto sin título"
    base = base.strip()
    suffix = " (copia)"
    if len(base) + len(suffix) > 200:
        base = base[: 200 - len(suffix)].rstrip()
    return base + suffix


def clone_document(doc: dict, project_id: str, *, title: str | None = None) -> dict:
    """Deep-copy *doc* under a new project id, ready to be stored as revision 0.

    Asset and scene ids are regenerated and every ``scene.source.assetId`` is
    remapped, so the original and the copy never share ids even though both
    point at the same files on disk. Timestamps and revision counters restart:
    a duplicate is a brand-new project, not a branch of the old one.
    """
    if not _is_id(project_id):
        raise ProjectError(f"invalid project id: {project_id!r}")
    check(doc)

    clone = copy.deepcopy(doc)
    stamp = now_iso()
    used: set[str] = set()
    asset_map: dict[str, str] = {}

    assets: list[dict] = []
    for asset in clone.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        new_id = _fresh_id("md_", used)
        old_id = asset.get("id")
        if isinstance(old_id, str) and old_id and old_id not in asset_map:
            asset_map[old_id] = new_id
        assets.append({**asset, "id": new_id})
    clone["assets"] = assets

    scenes: list[dict] = []
    for scene in clone.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        scene = dict(scene)
        scene["id"] = _fresh_id("sc_", used)
        source = scene.get("source")
        if isinstance(source, dict):
            source = dict(source)
            mapped = asset_map.get(source.get("assetId"))
            if mapped:
                source["assetId"] = mapped
            scene["source"] = source
        scenes.append(scene)
    clone["scenes"] = scenes

    events: list[dict] = []
    for event in clone.get("audioEvents") or []:
        if not isinstance(event, dict):
            continue
        event = dict(event)
        mapped = asset_map.get(event.get("assetId"))
        if mapped:
            event["assetId"] = mapped
        events.append(event)
    if "audioEvents" in clone:
        clone["audioEvents"] = events

    clone["projectId"] = project_id
    clone["revision"] = 0
    clone["baseRevision"] = 0
    clone["title"] = _copy_title(title if title is not None else doc.get("title"))
    clone["createdAt"] = stamp
    clone["updatedAt"] = stamp
    clone.pop("migrationLog", None)

    check(clone)
    return normalize(clone)


def remove_asset(doc: dict, asset_id: str) -> tuple[dict, list[str]]:
    """Return ``(document_without_asset, removed_scene_ids)``.

    A scene whose source is the removed asset cannot be rendered any more
    (validation refuses dangling ``assetId``), so it goes with the asset. The
    caller decides whether the asset existed at all; nothing here mutates *doc*.
    """
    assets = [asset for asset in doc.get("assets") or [] if isinstance(asset, dict)]
    target = next((asset for asset in assets if asset.get("id") == asset_id), None)
    kept_assets = [asset for asset in assets if asset.get("id") != asset_id]
    if target is None:
        return copy.deepcopy(doc), []

    kept_scenes: list = []
    removed: list[str] = []
    for scene in doc.get("scenes") or []:
        source = scene.get("source") if isinstance(scene, dict) else None
        if isinstance(source, dict) and source.get("assetId") == asset_id:
            removed.append(str(scene.get("id")))
            continue
        kept_scenes.append(scene)

    clone = copy.deepcopy(doc)
    clone["assets"] = kept_assets
    clone["scenes"] = kept_scenes
    if isinstance(clone.get("audioEvents"), list):
        # A sound event without its asset cannot be mixed, so it goes with it.
        clone["audioEvents"] = [
            event for event in clone["audioEvents"]
            if not (isinstance(event, dict) and event.get("assetId") == asset_id)
        ]
    return clone, removed


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #


def _inspect_text_style(where: str, item: dict, err, warn) -> None:
    """Validate the optional styling keys of one ``scene.text[]`` entry."""

    size = item.get("size")
    if size is not None and (not _is_int(size) or not (TEXT_SIZE_MIN <= size <= TEXT_SIZE_MAX)):
        err(f"{where}.size", f"must be an integer between {TEXT_SIZE_MIN} and {TEXT_SIZE_MAX}")

    for key, default in (("color", TEXT_COLOR_DEFAULT), ("borderColor", TEXT_BORDER_COLOR_DEFAULT)):
        value = item.get(key)
        if value is not None and (not isinstance(value, str) or not _COLOR_RE.match(value)):
            err(f"{where}.{key}", f"must be a #RRGGBB colour (default {default})")

    for key, maximum in (("border", TEXT_BORDER_MAX), ("shadow", TEXT_SHADOW_MAX)):
        value = item.get(key)
        if value is not None and (not _is_int(value) or not (0 <= value <= maximum)):
            err(f"{where}.{key}", f"must be an integer between 0 and {maximum}")

    animation = item.get("animation")
    if animation is not None:
        if not isinstance(animation, dict):
            err(f"{where}.animation", "must be an object {in?, out?}")
        else:
            for key in ("in", "out"):
                value = animation.get(key)
                if value is not None and value not in TEXT_ANIMATIONS:
                    err(f"{where}.animation.{key}", f"must be one of {', '.join(TEXT_ANIMATIONS)}")
            for key in sorted(set(animation) - {"in", "out"}):
                warn(f"{where}.animation.{key}", "unknown property preserved but not used by this version")

    known = {"content", "at", "until", "position", "size", "color", "border", "borderColor", "shadow", "animation"}
    for key in sorted(set(item) - known):
        warn(f"{where}.{key}", "unknown property preserved but not used by this version")


def _inspect_scene_filters(where: str, filters: Any, err, warn) -> None:
    """Validate ``scene.filters`` (colour correction applied before scale/pad)."""

    if filters is None:
        return
    if not isinstance(filters, dict):
        err(where, "must be an object {brightness?, contrast?, saturation?, grayscale?, vignette?, blur?}")
        return
    for key, (low, high) in SCENE_FILTER_RANGES.items():
        value = filters.get(key)
        if value is not None and (not _is_num(value) or not (low <= float(value) <= high)):
            err(f"{where}.{key}", f"must be a number between {low} and {high}")
    for key in SCENE_FILTER_FLAGS:
        if key in filters and not isinstance(filters[key], bool):
            err(f"{where}.{key}", "must be a boolean")
    for key in sorted(set(filters) - set(SCENE_FILTER_RANGES) - set(SCENE_FILTER_FLAGS)):
        warn(f"{where}.{key}", "unknown property preserved but not used by this version")


def inspect(doc: Any) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for *doc*. Never raises, never mutates."""
    errors: list[str] = []
    warnings: list[str] = []

    def err(where: str, message: str) -> None:
        errors.append(f"{where}: {message}")

    def warn(where: str, message: str) -> None:
        warnings.append(f"{where}: {message}")

    if not isinstance(doc, dict):
        return ["document: must be a JSON object"], warnings

    known_top = {
        "schemaVersion", "projectId", "revision", "baseRevision", "title", "sessionId",
        "cwd", "engineTag", "fps", "width", "height", "orientation", "audio", "scenes",
        "assets", "createdAt", "updatedAt", "migrationLog", "music", "logo", "audioEvents",
    }
    for key in sorted(set(doc) - known_top):
        warn(f"document.{key}", "unknown property preserved but not used by this version")

    version = doc.get("schemaVersion")
    if not _is_int(version):
        err("schemaVersion", "must be an integer (run migrate first)")
    elif version != SCHEMA_VERSION:
        err("schemaVersion", f"must be {SCHEMA_VERSION}, got {version}")

    project_id = doc.get("projectId")
    if not _is_id(project_id):
        err("projectId", "must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

    revision = doc.get("revision")
    if not _is_int(revision) or revision < 0:
        err("revision", "must be an integer >= 0")

    base_revision = doc.get("baseRevision")
    if not _is_int(base_revision) or base_revision < 0:
        err("baseRevision", "must be an integer >= 0")
    elif _is_int(revision) and base_revision > revision:
        err("baseRevision", f"must not be greater than revision ({revision})")

    title = doc.get("title")
    if not isinstance(title, str) or not title.strip():
        err("title", "must be a non-empty string")
    elif len(title) > 200:
        err("title", "must be at most 200 characters")
    elif _CONTROL_RE.search(title):
        err("title", "must not contain control characters")

    for key, limit in (("sessionId", 120), ("cwd", 500)):
        value = doc.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            err(key, f"must be null or a string of at most {limit} characters")

    engine_tag = doc.get("engineTag")
    if not isinstance(engine_tag, str) or not _ENGINE_RE.match(engine_tag):
        err("engineTag", "must match ^[a-z0-9][a-z0-9._-]{0,63}$")

    fps = doc.get("fps")
    if not isinstance(fps, dict):
        err("fps", "must be an object {num, den}")
    else:
        num, den = fps.get("num"), fps.get("den")
        if not _is_int(num) or not (1 <= num <= MAX_FPS):
            err("fps.num", f"must be an integer between 1 and {MAX_FPS}")
        if not _is_int(den) or not (1 <= den <= 1001):
            err("fps.den", "must be an integer between 1 and 1001")
        if _is_int(num) and _is_int(den) and den and num / den > MAX_FPS:
            err("fps", f"effective rate must be <= {MAX_FPS} fps")

    width, height = doc.get("width"), doc.get("height")
    for name, value, maximum in (("width", width, MAX_WIDTH), ("height", height, MAX_HEIGHT)):
        if not _is_int(value) or not (16 <= value <= maximum):
            err(name, f"must be an integer between 16 and {maximum}")
        elif value % 2:
            err(name, "must be even (yuv420p)")

    orientation = doc.get("orientation")
    if orientation not in ORIENTATIONS:
        err("orientation", "must be 'h' or 'v'")
    elif _is_int(width) and _is_int(height):
        if orientation == "h" and width < height:
            warn("orientation", "declared 'h' but height is greater than width")
        if orientation == "v" and height < width:
            warn("orientation", "declared 'v' but width is greater than height")

    audio = doc.get("audio")
    if not isinstance(audio, dict):
        err("audio", "must be an object {masterVolume}")
    else:
        volume = audio.get("masterVolume")
        if not _is_int(volume) or not (0 <= volume <= 100):
            err("audio.masterVolume", "must be an integer between 0 and 100")

    assets = doc.get("assets")
    asset_index: dict[str, dict] = {}
    if not isinstance(assets, list):
        err("assets", "must be a list")
        assets = []
    elif len(assets) > MAX_ASSETS:
        err("assets", f"must contain at most {MAX_ASSETS} entries")

    for index, asset in enumerate(assets):
        where = f"assets[{index}]"
        if not isinstance(asset, dict):
            err(where, "must be an object")
            continue
        asset_id = asset.get("id")
        if not _is_id(asset_id):
            err(f"{where}.id", "must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
        elif asset_id in asset_index:
            err(f"{where}.id", f"duplicate asset id {asset_id!r}")
        else:
            asset_index[asset_id] = asset

        asset_path = asset.get("path")
        if not isinstance(asset_path, str):
            err(f"{where}.path", "must be a string")
        else:
            try:
                normalized = path_rules.normalize_relative(asset_path, field=f"{where}.path")
            except path_rules.PathError as exc:
                err(f"{where}.path", str(exc))
            else:
                if normalized != asset_path:
                    err(f"{where}.path", f"must be normalized ({normalized!r})")

        digest = asset.get("sha256")
        if not isinstance(digest, str) or not _SHA256_RE.match(digest):
            err(f"{where}.sha256", "must be 64 lowercase hex characters")

        if asset.get("kind") not in ASSET_KINDS:
            err(f"{where}.kind", f"must be one of {', '.join(ASSET_KINDS)}")

        byte_count = asset.get("bytes")
        if byte_count is not None and (not _is_int(byte_count) or not (0 <= byte_count <= MAX_JOB_INPUT_BYTES)):
            err(f"{where}.bytes", f"must be an integer between 0 and {MAX_JOB_INPUT_BYTES}")

        rights = asset.get("rights")
        if not isinstance(rights, dict):
            err(f"{where}.rights", "must be an object {status, license?, notes?}")
        else:
            if rights.get("status") not in RIGHTS_STATUS:
                err(f"{where}.rights.status", f"must be one of {', '.join(RIGHTS_STATUS)}")
            for key, limit in (("license", 200), ("notes", 500)):
                value = rights.get(key)
                if value is not None and (not isinstance(value, str) or len(value) > limit):
                    err(f"{where}.rights.{key}", f"must be a string of at most {limit} characters")

        added_at = asset.get("addedAt")
        if added_at is not None and not _is_iso(added_at):
            err(f"{where}.addedAt", "must be an ISO-8601 timestamp")

    music = doc.get("music")
    if music is not None:
        if not isinstance(music, dict):
            err("music", "must be an object {assetId, volume, fadeIn?, fadeOut?, loop?, ducking?}")
        else:
            music_asset = music.get("assetId")
            if not _is_id(music_asset):
                err("music.assetId", "must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
            elif music_asset not in asset_index:
                err("music.assetId", f"unknown asset {music_asset!r}")
            elif asset_index[music_asset].get("kind") != "audio":
                err("music.assetId", "must reference an audio asset")
            music_volume = music.get("volume")
            if not _is_int(music_volume) or not (0 <= music_volume <= 100):
                err("music.volume", "must be an integer between 0 and 100")
            for key in ("fadeIn", "fadeOut"):
                value = music.get(key)
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, (int, float)) or not (0 <= float(value) <= 10)
                ):
                    err(f"music.{key}", "must be a number between 0 and 10")
            for key in ("in", "out"):
                value = music.get(key)
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0
                ):
                    err(f"music.{key}", "must be a non-negative number")
            for key in ("loop", "ducking"):
                if key in music and not isinstance(music[key], bool):
                    err(f"music.{key}", "must be a boolean")

    audio_events = doc.get("audioEvents")
    if audio_events is not None:
        if not isinstance(audio_events, list):
            err("audioEvents", "must be a list of {id, assetId, at, volume?, fadeIn?, fadeOut?}")
        elif len(audio_events) > MAX_AUDIO_EVENTS:
            err("audioEvents", f"must contain at most {MAX_AUDIO_EVENTS} entries")
        else:
            seen_events: set[str] = set()
            for index, event in enumerate(audio_events):
                where = f"audioEvents[{index}]"
                if not isinstance(event, dict):
                    err(where, "must be an object {id, assetId, at, volume?, fadeIn?, fadeOut?}")
                    continue
                event_id = event.get("id")
                if not _is_id(event_id):
                    err(f"{where}.id", "must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
                elif event_id in seen_events:
                    err(f"{where}.id", f"duplicate audio event id {event_id!r}")
                else:
                    seen_events.add(event_id)

                event_asset = event.get("assetId")
                if not _is_id(event_asset):
                    err(f"{where}.assetId", "must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
                elif event_asset not in asset_index:
                    err(f"{where}.assetId", f"references unknown asset {event_asset!r}")
                elif asset_index[event_asset].get("kind") != "audio":
                    err(f"{where}.assetId", "must reference an audio asset")

                at = event.get("at")
                if not _is_num(at) or at < 0:
                    err(f"{where}.at", "must be a number >= 0")
                elif float(at) > MAX_TOTAL_DURATION:
                    err(f"{where}.at", f"must be <= {MAX_TOTAL_DURATION}s")

                volume = event.get("volume", SFX_VOLUME_DEFAULT)
                if not _is_int(volume) or not (0 <= volume <= 100):
                    err(f"{where}.volume", "must be an integer between 0 and 100")

                for key in ("fadeIn", "fadeOut"):
                    value = event.get(key)
                    if value is not None and (
                        isinstance(value, bool) or not _is_num(value) or not (0 <= float(value) <= SFX_FADE_MAX)
                    ):
                        err(f"{where}.{key}", f"must be a number between 0 and {SFX_FADE_MAX}")

                known_event = {"id", "assetId", "at", "volume", "fadeIn", "fadeOut"}
                for key in sorted(set(event) - known_event):
                    warn(f"{where}.{key}", "unknown property preserved but not used by this version")

    if isinstance(audio, dict):
        normalize = audio.get("normalize")
        if normalize is not None and not isinstance(normalize, bool):
            err("audio.normalize", "must be a boolean")

    logo = doc.get("logo")
    if logo is not None:
        if not isinstance(logo, dict):
            err("logo", "must be an object {assetId, position?, opacity?, scale?}")
        else:
            logo_asset = logo.get("assetId")
            if not _is_id(logo_asset):
                err("logo.assetId", "must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
            elif logo_asset not in asset_index:
                err("logo.assetId", f"unknown asset {logo_asset!r}")
            elif asset_index[logo_asset].get("kind") != "image":
                err("logo.assetId", "must reference an image asset")
            position = logo.get("position")
            if position is not None and position not in LOGO_POSITIONS:
                err("logo.position", f"must be one of {', '.join(LOGO_POSITIONS)}")
            opacity = logo.get("opacity")
            if opacity is not None and (
                isinstance(opacity, bool) or not _is_num(opacity) or not (0 <= float(opacity) <= 1)
            ):
                err("logo.opacity", "must be a number between 0 and 1")
            scale = logo.get("scale")
            if scale is not None and (
                isinstance(scale, bool)
                or not _is_num(scale)
                or not (LOGO_SCALE_MIN <= float(scale) <= LOGO_SCALE_MAX)
            ):
                err("logo.scale", f"must be a number between {LOGO_SCALE_MIN} and {LOGO_SCALE_MAX}")
            known_logo = {"assetId", "position", "opacity", "scale"}
            for key in sorted(set(logo) - known_logo):
                warn(f"logo.{key}", "unknown property preserved but not used by this version")

    scenes = doc.get("scenes")
    if not isinstance(scenes, list):
        err("scenes", "must be a list")
        scenes = []
    elif len(scenes) > MAX_SCENES:
        err("scenes", f"must contain at most {MAX_SCENES} entries")

    seen_scene_ids: set[str] = set()
    previous_duration: float | None = None
    for index, scene in enumerate(scenes):
        where = f"scenes[{index}]"
        if not isinstance(scene, dict):
            err(where, "must be an object")
            previous_duration = None
            continue

        scene_id = scene.get("id")
        if not _is_id(scene_id):
            err(f"{where}.id", "must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
        elif scene_id in seen_scene_ids:
            err(f"{where}.id", f"duplicate scene id {scene_id!r}")
        else:
            seen_scene_ids.add(scene_id)

        name = scene.get("name")
        if name is not None and (not isinstance(name, str) or len(name) > 120):
            err(f"{where}.name", "must be a string of at most 120 characters")

        source = scene.get("source")
        if not isinstance(source, dict):
            err(f"{where}.source", "must be an object {path, sha256, kind}")
            source = {}

        source_path = source.get("path")
        needs_relink = scene.get("needsRelink")
        if needs_relink is not None and not isinstance(needs_relink, bool):
            err(f"{where}.needsRelink", "must be a boolean")

        if source_path is None:
            if needs_relink is not True:
                err(f"{where}.source.path", "may only be null when needsRelink is true")
        elif not isinstance(source_path, str):
            err(f"{where}.source.path", "must be a string or null")
        else:
            try:
                normalized = path_rules.normalize_relative(source_path, field=f"{where}.source.path")
            except path_rules.PathError as exc:
                err(f"{where}.source.path", str(exc))
            else:
                if normalized != source_path:
                    err(f"{where}.source.path", f"must be normalized ({normalized!r})")
            if needs_relink is True:
                err(f"{where}.needsRelink", "must be false when a source path is present")

        digest = source.get("sha256")
        if source_path is not None:
            if not isinstance(digest, str) or not _SHA256_RE.match(digest):
                err(f"{where}.source.sha256", "must be 64 lowercase hex characters")
        elif digest is not None and (not isinstance(digest, str) or not _SHA256_RE.match(digest)):
            err(f"{where}.source.sha256", "must be null or 64 lowercase hex characters")

        kind = source.get("kind")
        if kind not in SOURCE_KINDS:
            err(f"{where}.source.kind", f"must be one of {', '.join(SOURCE_KINDS)}")

        asset_id = source.get("assetId")
        if asset_id is not None:
            if not _is_id(asset_id):
                err(f"{where}.source.assetId", "must be a valid asset id")
            elif asset_id not in asset_index:
                err(f"{where}.source.assetId", f"references unknown asset {asset_id!r}")
            else:
                asset = asset_index[asset_id]
                if asset.get("path") == source_path and asset.get("sha256") != digest:
                    err(f"{where}.source.sha256", "does not match the referenced asset")
                if asset.get("path") == source_path and asset.get("kind") != kind:
                    err(f"{where}.source.kind", "does not match the referenced asset")

        start, end = scene.get("in"), scene.get("out")
        speed_value = scene.get("speed")
        speed_ok = True
        if speed_value is not None:
            if (
                isinstance(speed_value, bool)
                or not _is_num(speed_value)
                or not (SCENE_SPEED_MIN <= float(speed_value) <= SCENE_SPEED_MAX)
            ):
                err(f"{where}.speed", f"must be a number between {SCENE_SPEED_MIN} and {SCENE_SPEED_MAX}")
                speed_ok = False
        duration: float | None = None
        if not _is_num(start) or start < 0:
            err(f"{where}.in", "must be a number >= 0")
        if not _is_num(end) or end <= 0:
            err(f"{where}.out", "must be a number > 0")
        if _is_num(start) and _is_num(end):
            if end <= start:
                err(f"{where}.out", "must be greater than 'in'")
            else:
                span = round(float(end) - float(start), FLOAT_DECIMALS)
                factor = float(speed_value) if speed_ok and speed_value is not None else 1.0
                # la duración que cuenta es la que se ve: span / speed
                duration = round(span / factor, FLOAT_DECIMALS)
                if duration < MIN_SCENE_DURATION:
                    err(f"{where}", f"scene duration must be at least {MIN_SCENE_DURATION}s")
                if end > MAX_SCENE_DURATION:
                    err(f"{where}.out", f"must be <= {MAX_SCENE_DURATION}s")

        motion = scene.get("kenBurns")
        if motion is not None:
            if not isinstance(motion, dict):
                err(f"{where}.kenBurns", "must be an object {zoom?, pan?}")
            else:
                if kind == "video":
                    err(f"{where}.kenBurns", "only applies to image scenes (source.kind must be 'image')")
                zoom = motion.get("zoom")
                if zoom is not None and (
                    isinstance(zoom, bool)
                    or not _is_num(zoom)
                    or not (KEN_BURNS_ZOOM_MIN <= float(zoom) <= KEN_BURNS_ZOOM_MAX)
                ):
                    err(
                        f"{where}.kenBurns.zoom",
                        f"must be a number between {KEN_BURNS_ZOOM_MIN} and {KEN_BURNS_ZOOM_MAX}",
                    )
                pan = motion.get("pan")
                if pan is not None and pan not in KEN_BURNS_PANS:
                    err(f"{where}.kenBurns.pan", f"must be one of {', '.join(KEN_BURNS_PANS)}")
                for key in sorted(set(motion) - {"zoom", "pan"}):
                    warn(f"{where}.kenBurns.{key}", "unknown property preserved but not used by this version")


        transition = scene.get("transition")
        if not isinstance(transition, str):
            err(f"{where}.transition", "must be a string ('none' or '<style>-<seconds>')")
        else:
            try:
                style, fade = transition_parts(transition)
            except ProjectError:
                err(
                    f"{where}.transition",
                    "must be 'none' or '<style>-<seconds>' with style in "
                    + ", ".join(TRANSITION_STYLES),
                )
            else:
                if style != "none":
                    if not (TRANSITION_MIN_S <= fade <= TRANSITION_MAX_S):
                        err(
                            f"{where}.transition",
                            f"fade duration must be between {TRANSITION_MIN_S} and {TRANSITION_MAX_S} seconds",
                        )
                    elif duration is not None and fade > duration + 1e-9:
                        err(f"{where}.transition", "fade is longer than the scene")
                    elif previous_duration is not None and fade > previous_duration + 1e-9:
                        # an xfade eats the tail of the previous scene as well
                        err(f"{where}.transition", "transition is longer than the previous scene")

        text_items = scene.get("text")
        if not isinstance(text_items, list):
            err(f"{where}.text", "must be a list")
        elif len(text_items) > MAX_TEXT_ITEMS:
            err(f"{where}.text", f"must contain at most {MAX_TEXT_ITEMS} entries")
        else:
            for t_index, item in enumerate(text_items):
                t_where = f"{where}.text[{t_index}]"
                if not isinstance(item, dict):
                    err(t_where, "must be an object")
                    continue
                content = item.get("content")
                if not isinstance(content, str) or not content.strip():
                    err(f"{t_where}.content", "must be a non-empty string")
                elif len(content) > MAX_TEXT_LENGTH:
                    err(f"{t_where}.content", f"must be at most {MAX_TEXT_LENGTH} characters")
                elif _CONTROL_RE.search(content):
                    err(f"{t_where}.content", "must not contain control characters")
                at, until = item.get("at"), item.get("until")
                if not _is_num(at) or at < 0:
                    err(f"{t_where}.at", "must be a number >= 0")
                if not _is_num(until) or until <= 0:
                    err(f"{t_where}.until", "must be a number > 0")
                if _is_num(at) and _is_num(until):
                    if until <= at:
                        err(f"{t_where}.until", "must be greater than 'at'")
                    elif duration is not None and until > duration + 0.05:
                        err(f"{t_where}.until", "must not exceed the scene duration")
                position = item.get("position")
                if position is not None and position not in TEXT_POSITIONS:
                    err(f"{t_where}.position", f"must be one of {', '.join(TEXT_POSITIONS)}")
                _inspect_text_style(t_where, item, err, warn)

        _inspect_scene_filters(f"{where}.filters", scene.get("filters"), err, warn)

        scene_audio = scene.get("audio")
        if not isinstance(scene_audio, dict):
            err(f"{where}.audio", "must be an object {volume, fadeIn?, fadeOut?}")
        else:
            volume = scene_audio.get("volume")
            if not _is_int(volume) or not (0 <= volume <= 100):
                err(f"{where}.audio.volume", "must be an integer between 0 and 100")
            fades = {}
            for key in ("fadeIn", "fadeOut"):
                value = scene_audio.get(key, 0)
                if not _is_num(value) or not (0 <= value <= 10):
                    err(f"{where}.audio.{key}", "must be a number between 0 and 10")
                else:
                    fades[key] = float(value)
            if duration is not None and len(fades) == 2:
                if fades["fadeIn"] + fades["fadeOut"] > duration + 1e-9:
                    err(f"{where}.audio", "fadeIn + fadeOut must not exceed the scene duration")

        previous_duration = duration

    if isinstance(scenes, list) and scenes and not errors:
        total = total_duration(doc)
        if total > MAX_TOTAL_DURATION:
            err("scenes", f"total duration {total}s exceeds {MAX_TOTAL_DURATION}s")

    for key in ("createdAt", "updatedAt"):
        if not _is_iso(doc.get(key)):
            err(key, "must be an ISO-8601 timestamp")

    log = doc.get("migrationLog")
    if log is not None:
        if not isinstance(log, list):
            err("migrationLog", "must be a list")
        else:
            for index, entry in enumerate(log):
                if not isinstance(entry, dict) or not all(_is_int(entry.get(k)) for k in ("from", "to")):
                    err(f"migrationLog[{index}]", "must record integer 'from' and 'to'")

    return errors, warnings


def validate(doc: Any) -> list[str]:
    """Return the list of validation errors (empty when the document is valid)."""
    return inspect(doc)[0]


def check(doc: Any) -> list[str]:
    """Raise :class:`ValidationError` when invalid; return the warnings."""
    errors, warnings = inspect(doc)
    if errors:
        raise ValidationError(errors, warnings)
    return warnings


def validate_for_export(doc: Any) -> list[str]:
    """Extra rules that only matter when a render is about to be queued."""
    errors, _ = inspect(doc)
    if errors:
        return errors

    scenes = doc.get("scenes") or []
    if not scenes:
        return ["scenes: at least one scene is required to export"]

    unresolved = [
        f"scenes[{index}]: media not relinked ({scene.get('id')!r})"
        for index, scene in enumerate(scenes)
        if scene.get("needsRelink") or (scene.get("source") or {}).get("path") is None
    ]
    errors.extend(unresolved)

    if total_duration(doc) > MAX_TOTAL_DURATION:
        errors.append(f"scenes: total duration exceeds {MAX_TOTAL_DURATION}s")

    declared = sum(int(a.get("bytes") or 0) for a in doc.get("assets") or [] if isinstance(a, dict))
    if declared > MAX_JOB_INPUT_BYTES:
        errors.append(f"assets: declared size {declared} exceeds {MAX_JOB_INPUT_BYTES} bytes")

    width, height = int(doc["width"]), int(doc["height"])
    if max(width, height) > MVP_MAX_SIDE or width * height > MVP_MAX_PIXELS:
        errors.append(
            f"width/height: MVP render is capped at {MVP_MAX_PIXELS} pixels "
            f"and {MVP_MAX_SIDE} px per side"
        )
    rate = doc["fps"]["num"] / doc["fps"]["den"]
    if rate > MVP_MAX_FPS:
        errors.append(f"fps: MVP render is capped at {MVP_MAX_FPS} fps")

    return errors


# --------------------------------------------------------------------------- #
# normalization
# --------------------------------------------------------------------------- #


def _normalize_floats(value: Any) -> Any:
    if isinstance(value, float):
        return _round(value)
    if isinstance(value, dict):
        return {key: _normalize_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_floats(item) for item in value]
    return value


def normalize(doc: dict) -> dict:
    """Return a canonical copy: defaults filled, floats rounded, no mutation."""
    result = copy.deepcopy(doc)
    result.setdefault("baseRevision", result.get("revision", 0))
    result.setdefault("sessionId", None)
    result.setdefault("cwd", None)
    if not result.get("orientation"):
        result["orientation"] = "h" if result.get("width", 0) >= result.get("height", 0) else "v"
    audio = result.setdefault("audio", {})
    if isinstance(audio, dict):
        audio.setdefault("masterVolume", 100)

    for scene in result.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        scene.setdefault("name", "")
        scene.setdefault("needsRelink", False)
        scene.setdefault("transition", "none")
        scene.setdefault("text", [])
        scene_audio = scene.setdefault("audio", {})
        if isinstance(scene_audio, dict):
            scene_audio.setdefault("volume", 100)
            scene_audio.setdefault("fadeIn", 0.0)
            scene_audio.setdefault("fadeOut", 0.0)
        for item in scene.get("text") or []:
            if isinstance(item, dict):
                item.setdefault("position", "bottom")
                item.setdefault("size", TEXT_SIZE_DEFAULT)
                item.setdefault("color", TEXT_COLOR_DEFAULT)
                item.setdefault("border", 0)
                item.setdefault("borderColor", TEXT_BORDER_COLOR_DEFAULT)
                item.setdefault("shadow", 0)
                animation = item.setdefault("animation", dict(TEXT_ANIMATION_DEFAULT))
                if isinstance(animation, dict):
                    animation.setdefault("in", "none")
                    animation.setdefault("out", "none")
                for key in ("color", "borderColor"):
                    value = item.get(key)
                    if isinstance(value, str):
                        item[key] = value.upper()
        filters = scene.get("filters")
        if isinstance(filters, dict):
            for key in ("grayscale", "vignette"):
                if key in filters:
                    filters[key] = bool(filters[key])

    logo = result.get("logo")
    if isinstance(logo, dict):
        logo.setdefault("position", LOGO_POSITION_DEFAULT)
        logo.setdefault("opacity", LOGO_OPACITY_DEFAULT)
        logo.setdefault("scale", LOGO_SCALE_DEFAULT)

    for asset in result.get("assets") or []:
        if isinstance(asset, dict) and isinstance(asset.get("rights"), dict):
            asset["rights"].setdefault("license", "")
            asset["rights"].setdefault("notes", "")

    return _normalize_floats(result)


# --------------------------------------------------------------------------- #
# migration (non-destructive)
# --------------------------------------------------------------------------- #


def _migrate_v0_to_v1(doc: dict) -> dict:
    """Map the UI draft shape (ui-spec 6.2) onto the canonical document.

    Nothing is removed: any key the old shape carried is copied over, and the
    media list, when present, becomes the asset table. Scenes whose media is
    not described can still be opened, flagged ``needsRelink``.
    """
    stamp = now_iso()
    media: dict[str, dict] = {}
    for item in doc.get("media") or []:
        if not isinstance(item, dict):
            continue
        media_id = item.get("media_id") or item.get("id")
        if not isinstance(media_id, str):
            continue
        media[media_id] = item

    assets: list[dict] = []
    for media_id, item in media.items():
        source_path = item.get("path")
        digest = item.get("sha256")
        kind = item.get("kind") or "video"
        if not isinstance(source_path, str) or not isinstance(digest, str):
            continue
        try:
            source_path = path_rules.normalize_relative(source_path, field="media.path")
        except path_rules.PathError:
            continue
        assets.append(
            {
                "id": media_id,
                "path": source_path,
                "sha256": digest,
                "kind": kind,
                "bytes": int(item.get("bytes") or 0),
                "rights": item.get("rights") or {"status": "unknown", "license": "", "notes": ""},
                "addedAt": item.get("added_at") or stamp,
            }
        )

    scenes: list[dict] = []
    for index, scene in enumerate(doc.get("scenes") or []):
        if not isinstance(scene, dict):
            continue
        media_id = scene.get("media_id")
        asset = media.get(media_id) if isinstance(media_id, str) else None
        source_path = asset.get("path") if asset else None
        digest = asset.get("sha256") if asset else None
        kind = (asset or {}).get("kind") or "video"
        start = scene.get("in", 0.0)
        end = scene.get("out", 0.0)
        duration = max(0.0, float(end) - float(start)) if _is_num(end) and _is_num(start) else 0.0
        volume = 0 if scene.get("muted") else int(scene.get("volume", 100) or 0)
        caption = scene.get("caption") or ""
        text_items = []
        if isinstance(caption, str) and caption.strip():
            text_items.append({"content": caption, "at": 0.0, "until": duration, "position": "bottom"})
        scenes.append(
            {
                "id": scene.get("id") or f"sc_{index + 1:02d}",
                "name": scene.get("name") or "",
                "source": {
                    "assetId": media_id if asset else None,
                    "path": source_path,
                    "sha256": digest,
                    "kind": kind,
                },
                "in": float(start) if _is_num(start) else 0.0,
                "out": float(end) if _is_num(end) else 0.0,
                "transition": scene.get("transition") or "none",
                "text": text_items,
                "audio": {"volume": max(0, min(100, volume)), "fadeIn": 0.0, "fadeOut": 0.0},
                "needsRelink": source_path is None,
            }
        )

    width = doc.get("width") or (1280 if doc.get("orientation", "h") == "h" else 720)
    height = doc.get("height") or (720 if doc.get("orientation", "h") == "h" else 1280)
    updated = doc.get("updated_at") or doc.get("updatedAt") or stamp
    migrated = {
        "schemaVersion": 1,
        "projectId": doc.get("projectId") or doc.get("project_id"),
        "revision": int(doc.get("revision") or 0),
        "baseRevision": int(doc.get("baseRevision") or doc.get("revision") or 0),
        "title": doc.get("title") or "Proyecto sin título",
        "sessionId": doc.get("sessionId") or doc.get("session_id"),
        "cwd": doc.get("cwd"),
        "engineTag": doc.get("engineTag") or DEFAULT_ENGINE_TAG,
        "fps": doc.get("fps") if isinstance(doc.get("fps"), dict) else {"num": 30, "den": 1},
        "width": int(width),
        "height": int(height),
        "orientation": doc.get("orientation") or ("h" if width >= height else "v"),
        "audio": {"masterVolume": int((doc.get("audio") or {}).get("master_volume", 100))}
        if isinstance(doc.get("audio"), dict)
        else {"masterVolume": 100},
        "scenes": scenes,
        "assets": assets,
        "createdAt": doc.get("createdAt") or doc.get("created_at") or updated,
        "updatedAt": updated,
    }
    # Preserve every key the old shape had, under the same name, so nothing is lost.
    for key, value in doc.items():
        migrated.setdefault(key, copy.deepcopy(value))
    return migrated


def _looks_canonical(doc: dict) -> bool:
    """True when an unversioned document already uses the v1 shape."""
    scenes = doc.get("scenes")
    return (
        isinstance(doc.get("projectId"), str)
        and isinstance(doc.get("fps"), dict)
        and isinstance(scenes, list)
        and all(isinstance(s, dict) and isinstance(s.get("source"), dict) for s in scenes)
    )


def _stamp_v1(doc: dict) -> dict:
    """Accept an unversioned but already-canonical document, stamping version 1."""
    result = copy.deepcopy(doc)
    result["schemaVersion"] = 1
    result.setdefault("baseRevision", result.get("revision", 0))
    result.setdefault("engineTag", DEFAULT_ENGINE_TAG)
    result.setdefault("audio", {"masterVolume": 100})
    result.setdefault("assets", [])
    stamp = now_iso()
    result.setdefault("createdAt", result.get("updatedAt") or stamp)
    result.setdefault("updatedAt", stamp)
    for scene in result.get("scenes") or []:
        if isinstance(scene, dict):
            scene.setdefault("needsRelink", (scene.get("source") or {}).get("path") is None)
    return result


MIGRATIONS = {0: _migrate_v0_to_v1}



def migrate(doc: dict, *, to_version: int = SCHEMA_VERSION) -> tuple[dict, list[dict]]:
    """Upgrade *doc* to *to_version* without mutating the input.

    Returns ``(migrated_document, applied_steps)``. Refuses to downgrade.
    """
    if not isinstance(doc, dict):
        raise ValidationError(["document: must be a JSON object"])
    version = doc.get("schemaVersion")
    current = version if _is_int(version) else 0
    if current > to_version:
        raise UnsupportedSchemaVersion(
            f"document schemaVersion {current} is newer than supported {to_version}"
        )

    result = copy.deepcopy(doc)
    applied: list[dict] = []
    while current < to_version:
        if current == 0 and _looks_canonical(result):
            step = _stamp_v1
        else:
            step = MIGRATIONS.get(current)
        if step is None:
            raise UnsupportedSchemaVersion(f"no migration from schemaVersion {current}")
        result = step(result)
        entry = {"from": current, "to": current + 1, "at": now_iso(), "tool": "video-editor-core/1"}
        log = result.setdefault("migrationLog", [])
        if isinstance(log, list):
            log.append(entry)
        applied.append(entry)
        current += 1
    result["schemaVersion"] = current
    return result, applied


# --------------------------------------------------------------------------- #
# serialization
# --------------------------------------------------------------------------- #


def dumps(doc: Any) -> str:
    """Deterministic JSON text: sorted keys, 3-decimal floats, trailing newline."""
    payload = _normalize_floats(doc)
    return json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ": "),
    ) + "\n"


def canonical_bytes(doc: Any) -> bytes:
    return dumps(doc).encode("utf-8")


def document_hash(doc: Any) -> str:
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def save_atomic(path: str | os.PathLike[str], doc: dict, *, backup: bool = True) -> Path:
    """Write *doc* atomically, keeping a ``.bak`` copy of the previous file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(doc)
    temp = target.parent / f".{target.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if backup and target.exists():
            backup_path = target.with_name(target.name + ".bak")
            backup_path.write_bytes(target.read_bytes())
        os.replace(temp, target)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass
    return target


def load(path: str | os.PathLike[str], *, apply_migrations: bool = True) -> dict:
    """Read, migrate and validate a document file. The file is never modified."""
    raw = Path(path).read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError([f"file: not valid JSON ({exc})"]) from exc
    if apply_migrations:
        doc, _ = migrate(doc)
    check(doc)
    return normalize(doc)


# --------------------------------------------------------------------------- #
# concurrency
# --------------------------------------------------------------------------- #


def bump_revision(doc: dict, base_revision: Any) -> dict:
    """Apply an edit and return the next revision.

    Raises :class:`RevisionConflict` when *base_revision* is not the stored
    revision, so a concurrent save can never be overwritten silently.
    """
    if not _is_int(base_revision):
        raise ValidationError(["baseRevision: must be an integer"])
    current = doc.get("revision")
    if not _is_int(current):
        raise ValidationError(["revision: document has no integer revision"])
    if base_revision != current:
        raise RevisionConflict(expected=base_revision, current=current)
    updated = copy.deepcopy(doc)
    updated["baseRevision"] = current
    updated["revision"] = current + 1
    updated["updatedAt"] = now_iso()
    return updated


def dedupe_key(doc: dict, preset: str, *, captions: bool = True) -> str:
    """Stable key for "same snapshot + same preset" render requests."""
    payload = {"captions": bool(captions), "document": doc, "preset": preset}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


# --------------------------------------------------------------------------- #
# UI adapters (ui-spec 6.2 shape)
# --------------------------------------------------------------------------- #


def to_ui_document(doc: dict) -> dict:
    """Project the canonical document onto the shape the pane already uses."""
    scenes = []
    for scene in doc.get("scenes") or []:
        source = scene.get("source") or {}
        text_items = scene.get("text") or []
        scenes.append(
            {
                "id": scene.get("id"),
                "media_id": source.get("assetId"),
                "name": scene.get("name") or "",
                "in": scene.get("in"),
                "out": scene.get("out"),
                "caption": text_items[0]["content"] if text_items else "",
                "volume": (scene.get("audio") or {}).get("volume", 100),
                "muted": (scene.get("audio") or {}).get("volume", 100) == 0,
                "transition": scene.get("transition") or "none",
                "needs_relink": bool(scene.get("needsRelink")),
            }
        )
    return {
        "project_id": doc.get("projectId"),
        "session_id": doc.get("sessionId"),
        "cwd": doc.get("cwd"),
        "title": doc.get("title"),
        "revision": doc.get("revision"),
        "base_revision": doc.get("baseRevision"),
        "orientation": doc.get("orientation"),
        "width": doc.get("width"),
        "height": doc.get("height"),
        "fps": doc.get("fps"),
        "engine_tag": doc.get("engineTag"),
        "audio": {"master_volume": (doc.get("audio") or {}).get("masterVolume", 100)},
        "scenes": scenes,
        "assets": doc.get("assets") or [],
        "media": [
            {
                "media_id": asset.get("id"),
                "path": asset.get("path"),
                "sha256": asset.get("sha256"),
                "kind": asset.get("kind"),
                "bytes": asset.get("bytes", 0),
                "rights": asset.get("rights") or {},
            }
            for asset in doc.get("assets") or []
        ],
        "created_at": doc.get("createdAt"),
        "updated_at": doc.get("updatedAt"),
    }


def from_ui_document(ui: dict) -> dict:
    """Accept the pane's draft shape and return a migrated canonical document."""
    migrated, _ = migrate(ui)
    check(migrated)
    return normalize(migrated)


def normalize_incoming(draft: Any) -> dict:
    """Accept either shape, migrate, validate and normalize."""
    if not isinstance(draft, dict):
        raise ValidationError(["document: must be a JSON object"])
    if "schemaVersion" not in draft and ("project_id" in draft or "projectId" not in draft):
        return from_ui_document(draft)
    migrated, _ = migrate(draft)
    check(migrated)
    return normalize(migrated)
