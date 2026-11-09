"""Manual smoke: render a 2-scene project with the real ffmpeg binary."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))

import project  # noqa: E402
from service import worker  # noqa: E402

TOOLS_DIR = os.environ.get("VIDEO_EDITOR_TOOLS", r"C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> int:
    root = Path(tempfile.mkdtemp(prefix="ve-smoke-", dir=os.environ.get("TMPDIR")))
    media = root / "media"
    media.mkdir()
    data = root / "data"
    tools = worker.resolve_tools(TOOLS_DIR)
    print("tools:", tools.ffmpeg.name, worker.tool_version(tools))

    def ff(args):
        result = subprocess.run([str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", *args],
                                capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(result.stderr)

    ff(["-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "2", "-ar", "48000", str(media / "clip1.mp4")])
    ff(["-f", "lavfi", "-i", "color=c=0x1b2430:size=320x240:duration=1", "-frames:v", "1", str(media / "card.png")])

    clip = media / "clip1.mp4"
    card = media / "card.png"
    doc = {
        "schemaVersion": 1, "projectId": "prj_smoke", "revision": 0, "baseRevision": 0,
        "title": "Smoke", "sessionId": None, "cwd": None, "engineTag": "ffmpeg-9.0.1",
        "fps": {"num": 30, "den": 1}, "width": 320, "height": 240, "orientation": "h",
        "audio": {"masterVolume": 80},
        "assets": [
            {"id": "md_1", "path": "media/clip1.mp4", "sha256": digest(clip), "kind": "video",
             "bytes": clip.stat().st_size, "rights": {"status": "owned", "license": "propio", "notes": ""},
             "addedAt": "2026-11-08T18:40:00Z"},
            {"id": "md_2", "path": "media/card.png", "sha256": digest(card), "kind": "image",
             "bytes": card.stat().st_size, "rights": {"status": "owned", "license": "propio", "notes": ""},
             "addedAt": "2026-11-08T18:40:00Z"},
        ],
        "scenes": [
            {"id": "sc_01", "name": "Intro",
             "source": {"assetId": "md_1", "path": "media/clip1.mp4", "sha256": digest(clip), "kind": "video"},
             "in": 0.0, "out": 1.2, "transition": "none",
             "text": [{"content": "Añó — ñandú 日本語", "at": 0.0, "until": 1.1, "position": "bottom"}],
             "audio": {"volume": 80, "fadeIn": 0.0, "fadeOut": 0.2}, "needsRelink": False},
            {"id": "sc_02", "name": "Cierre",
             "source": {"assetId": "md_2", "path": "media/card.png", "sha256": digest(card), "kind": "image"},
             "in": 0.0, "out": 1.0, "transition": "fade-0.3", "text": [],
             "audio": {"volume": 100, "fadeIn": 0.0, "fadeOut": 0.0}, "needsRelink": False},
        ],
        "createdAt": "2026-11-08T18:40:00Z", "updatedAt": "2026-11-08T18:40:00Z",
    }
    doc = project.normalize(doc)
    project.check(doc)
    layout = worker.Layout(data, root).ensure()
    samples: list[tuple[str, float]] = []
    result = worker.run_job(
        doc, job_id="jsmoke001", layout=layout, tools=tools,
        progress_cb=lambda stage, pct, eta: samples.append((stage, round(pct, 1))),
        memory_limit_mb=2048, timeout_s=180,
    )
    print("state:", result.state, "error:", result.error)
    print("wall:", result.wall_s, "limits_enforced:", result.limits_enforced,
          "peak_MB:", round((result.peak_memory_bytes or 0) / 1048576, 1))
    print("output:", result.output_path, "artifacts:", result.artifacts)
    print("progress samples:", samples[:5], "...", samples[-3:])
    if result.output_path:
        probe = subprocess.run(
            [str(tools.ffprobe), "-v", "error", "-show_entries",
             "format=duration,size:stream=codec_name,width,height,r_frame_rate,channels",
             "-of", "json", result.output_path],
            capture_output=True, text=True,
        )
        print(probe.stdout)
        print("job dir:", sorted(p.name for p in layout.job_dir("jsmoke001").iterdir()))
        print("staging empty:", not any(layout.staging_dir("jsmoke001").iterdir()))
        frame = root / "frame.png"
        subprocess.run([str(tools.ffmpeg), "-v", "error", "-y", "-ss", "0.5", "-i", result.output_path,
                        "-frames:v", "1", str(frame)], check=False)
        print("frame:", frame)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
