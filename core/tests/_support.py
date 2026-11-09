"""Shared test helpers. Importing this module puts ``core/`` on sys.path."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import project  # noqa: E402

#: Absolute ffmpeg tools directory used by the production worker.
TOOLS = Path(os.environ.get("VIDEO_EDITOR_TOOLS", r"C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin"))
FFMPEG = TOOLS / "ffmpeg.exe"
FFPROBE = TOOLS / "ffprobe.exe"


def tooling_available() -> bool:
    return FFMPEG.is_file() and FFPROBE.is_file()


def example_document() -> dict:
    with open(CORE / "schema" / "project.example.json", encoding="utf-8") as handle:
        return json.load(handle)


def small_document(scenes: int = 2, *, width: int = 320, height: int = 240) -> dict:
    """A minimal valid document with *scenes* one-second scenes over fake media."""
    assets = []
    scene_list = []
    for index in range(scenes):
        asset_id = f"md_{index + 1:02d}"
        digest = f"{index + 1:064x}"
        assets.append(
            {
                "id": asset_id,
                "path": f"media/clip{index + 1}.mp4",
                "sha256": digest,
                "kind": "video",
                "bytes": 1024,
                "rights": {"status": "owned", "license": "propio", "notes": ""},
                "addedAt": "2026-11-08T18:40:00Z",
            }
        )
        scene_list.append(
            {
                "id": f"sc_{index + 1:02d}",
                "name": f"Escena {index + 1}",
                "source": {
                    "assetId": asset_id,
                    "path": f"media/clip{index + 1}.mp4",
                    "sha256": digest,
                    "kind": "video",
                },
                "in": 0.0,
                "out": 1.0,
                "transition": "none",
                "text": [],
                "audio": {"volume": 100, "fadeIn": 0.0, "fadeOut": 0.0},
                "needsRelink": False,
            }
        )
    return {
        "schemaVersion": 1,
        "projectId": "prj_test",
        "revision": 3,
        "baseRevision": 2,
        "title": "Proyecto de prueba",
        "sessionId": None,
        "cwd": None,
        "engineTag": project.DEFAULT_ENGINE_TAG,
        "fps": {"num": 30, "den": 1},
        "width": width,
        "height": height,
        "orientation": "h",
        "audio": {"masterVolume": 100},
        "scenes": scene_list,
        "assets": assets,
        "createdAt": "2026-11-08T18:40:00Z",
        "updatedAt": "2026-11-08T18:40:00Z",
    }


def ui_draft_document() -> dict:
    """The shape described by docs/ui-spec.md 6.2 (unversioned, snake_case)."""
    return {
        "project_id": "prj_ui",
        "session_id": "sess_4f2a",
        "cwd": "C:/Users/EgtYP/proyectos/lanzamiento-q4",
        "title": "Lanzamiento Q4",
        "revision": 7,
        "orientation": "h",
        "audio": {"master_volume": 80},
        "scenes": [
            {
                "id": "sc_01",
                "media_id": "md_01",
                "name": "Intro",
                "in": 0.0,
                "out": 3.2,
                "caption": "Exporta en 720p y vuelve al chat con el MP4 listo.",
                "volume": 80,
                "muted": False,
                "transition": "none",
            },
            {
                "id": "sc_02",
                "media_id": "md_missing",
                "name": "Cierre",
                "in": 0.0,
                "out": 2.0,
                "caption": "",
                "volume": 100,
                "muted": False,
                "transition": "fade-0.3",
            },
        ],
        "media": [
            {
                "media_id": "md_01",
                "path": "media/intro.mp4",
                "sha256": "a" * 64,
                "kind": "video",
                "bytes": 2772029,
            }
        ],
        "updated_at": "2026-11-08T18:42:10Z",
    }


class TempDirTestCase(unittest.TestCase):
    """Each test gets its own scratch directory under the profile scratch area."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ve-core-", dir=os.environ.get("TMPDIR") or None))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name: str, doc: dict) -> Path:
        target = self.tmp / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(project.dumps(doc), encoding="utf-8", newline="")
        return target


def run_ffmpeg(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(FFMPEG), "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def make_clip(path: Path, *, seconds: float = 1.5, size: str = "320x240", audio: bool = True, pattern: str = "testsrc2") -> Path:
    """Create a synthetic clip with ffmpeg lavfi (no user media involved)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    args = ["-y", "-f", "lavfi", "-i", f"{pattern}=size={size}:rate=30:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
        args += ["-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "48000"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-t", str(seconds), str(path)]
    result = run_ffmpeg(args)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg fixture failed: {result.stderr[:800]}")
    return path


def copy_document(doc: dict) -> dict:
    return copy.deepcopy(doc)
