"""End-to-end evidence run: plugin contract → render → MP4 on disk.

Starts the real service on an ephemeral port, drives it only through HTTP (the
same calls the pane makes), renders a 720p project with a caption and a
transition, then leaves a JSON report plus extracted frames for visual review.

    python core/scripts/e2e_evidence.py --out evidence/e2e-<tag> [--keep]

Fixtures are synthetic (lavfi); no user media is read or copied.
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

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))

import project  # noqa: E402
from service import app as service_app  # noqa: E402
from service import worker  # noqa: E402

TOOLS_DIR = os.environ.get("VIDEO_EDITOR_TOOLS", r"C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin")


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        finally:
            exc.close()


def make_clip(ffmpeg: Path, target: Path, *, seconds: float, size: str, tone: int) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency={tone}:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "48000",
        "-t", str(seconds), str(target),
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr[:800])
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    parser.add_argument("--keep", action="store_true", help="do not delete the temp workspace")
    args = parser.parse_args(argv)

    tools = worker.resolve_tools(TOOLS_DIR)
    root = Path(tempfile.mkdtemp(prefix="ve-e2e-", dir=os.environ.get("TMPDIR")))
    media = root / "media"
    data = root / "data"
    out_dir = Path(args.out) if args.out else CORE.parent / "evidence" / f"e2e-{time.strftime('%Y%m%d-%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "startedAt": project.now_iso(),
        "workspace": str(root),
        "tools": {"ffmpeg": str(tools.ffmpeg), "version": worker.tool_version(tools)},
        "machine": {
            "ram_total_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 2)
            if hasattr(os, "sysconf") else None,
            "cpu_count": os.cpu_count(),
        },
        "steps": [],
    }

    size = "1280x720"
    clips = [
        make_clip(tools.ffmpeg, media / "intro.mp4", seconds=3.0, size=size, tone=440),
        make_clip(tools.ffmpeg, media / "demo.mp4", seconds=3.0, size=size, tone=560),
        make_clip(tools.ffmpeg, media / "cierre.mp4", seconds=2.0, size=size, tone=680),
    ]
    report["fixtures"] = [{"name": clip.name, "bytes": clip.stat().st_size} for clip in clips]

    service = service_app.build_service(data, media, tools_root=TOOLS_DIR, port=0).start()
    base = service.base_url
    report["service"] = {"url": base, "version": service_app.SERVICE_VERSION}
    try:
        status, health = call(base, "GET", "/health")
        report["steps"].append({"step": "health", "status": status, "payload": health})

        status, created = call(base, "POST", "/projects", {"title": "Evidencia e2e", "session_id": "sess_e2e"})
        report["steps"].append({"step": "create_project", "status": status,
                                "projectId": created.get("projectId"), "revision": created.get("revision")})
        project_id = created["projectId"]

        for clip in clips:
            status, body = call(base, "POST", f"/projects/{project_id}/media", {"path": clip.name})
            report["steps"].append({"step": "add_media", "file": clip.name, "status": status,
                                    "scenes": len(body.get("project", {}).get("scenes") or []),
                                    "revision": body.get("revision")})

        status, current = call(base, "GET", f"/projects/{project_id}")
        draft = current["project"]
        draft["title"] = "Evidencia e2e · 720p"
        draft["scenes"][0]["text"] = [{
            "at": 0.2, "until": 2.6, "position": "bottom",
            "content": "Exporta en 720p y vuelve al chat — ñandú, año, ¿acentos?",
        }]
        draft["scenes"][1]["transition"] = "fade-0.3"
        draft["scenes"][1]["text"] = [{"at": 0.1, "until": 1.8, "position": "top",
                                       "content": "Segunda escena con transición"}]
        status, saved = call(base, "PUT", f"/projects/{project_id}",
                             {"revision": current["revision"], "project": draft})
        report["steps"].append({"step": "save_document", "status": status,
                                "revision": saved.get("revision")})
        if status != 200:
            report["error"] = saved
            raise SystemExit(2)

        queued_at = time.monotonic()
        status, queued = call(base, "POST", f"/projects/{project_id}/export", {"preset": "mp4-720p30", "captions": True})
        report["steps"].append({"step": "export", "status": status, "jobId": queued.get("jobId")})
        job_id = queued["jobId"]

        stages: list[tuple[float, str, float]] = []
        job = {}
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            _, job = call(base, "GET", f"/jobs/{job_id}")
            stages.append((round(time.monotonic() - queued_at, 2), job.get("stage"), job.get("progress")))
            if job.get("state") in ("succeeded", "failed", "cancelled", "interrupted"):
                break
            time.sleep(0.2)
        render_wall = round(time.monotonic() - queued_at, 2)

        status, events = call(base, "GET", "/events?since=0&timeout=0")
        status_range, _ = 0, None
        request = urllib.request.Request(base + f"/jobs/{job_id}/output", method="GET")
        request.add_header("Range", "bytes=0-4095")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status_range = response.status
                first_bytes = response.read()
        except urllib.error.HTTPError as exc:
            exc.close()
            first_bytes = b""

        report["render"] = {
            "jobId": job_id,
            "state": job.get("state"),
            "error": job.get("error"),
            "wall_s": render_wall,
            "stages": stages,
            "events": len(events.get("events") or []),
            "peek_status": status_range,
            "peek_bytes": len(first_bytes),
        }

        if job.get("state") == "succeeded":
            output = Path(job["outputPath"])
            info = worker.probe_media(output, tools)
            report["output"] = {
                "path": str(output),
                "bytes": output.stat().st_size,
                "duration_s": info.get("duration"),
                "video": info.get("video_codec"),
                "audio": info.get("audio_codec"),
                "width": info.get("width"),
                "height": info.get("height"),
            }
            log_path = data / "jobs" / job_id / "ffmpeg.log"
            if log_path.is_file():
                body = log_path.read_text(encoding="utf-8")
                report["log"] = {
                    "exists": True,
                    "bytes": len(body),
                    "mentions_home": str(Path.home()) in body,
                    "mentions_caption": "ñandú" in body,
                }
            for tag, at in (("t0.6", 0.6), ("t3.2", 3.2), ("t5.0", 5.0)):
                frame = out_dir / f"frame-{tag}.png"
                subprocess.run([str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                                "-ss", str(at), "-i", str(output), "-frames:v", "1", str(frame)],
                               check=False)
            report["frames"] = sorted(p.name for p in out_dir.glob("frame-*.png"))
        else:
            report["error"] = job.get("error")
    finally:
        service.stop()
        report["finishedAt"] = project.now_iso()
        (out_dir / "e2e-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({
            "report": str(out_dir / "e2e-report.json"),
            "state": report.get("render", {}).get("state"),
            "wall_s": report.get("render", {}).get("wall_s"),
            "output": report.get("output"),
            "frames": report.get("frames"),
        }, ensure_ascii=False, indent=2))
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)
    return 0 if report.get("render", {}).get("state") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
