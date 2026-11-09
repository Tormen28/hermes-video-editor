"""E2E Fase 2C: preset vertical + velocidad 2x + Ken Burns, con ffprobe del MP4."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
SCRATCH = Path.home() / "AppData" / "Local" / "hermes" / "cache" / "scratch" / "ve-2c-e2e"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def call(base: str, method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def main() -> int:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)
    data_root = SCRATCH / "data"; media_root = SCRATCH / "media"
    data_root.mkdir(parents=True); media_root.mkdir(parents=True)
    shutil.copy2(CORE.parent / "spike" / "fixtures" / "clipA.mp4", media_root / "clipA.mp4")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "color=c=0x204060:s=1280x720:d=1", "-frames:v", "1", str(media_root / "still.png")],
        check=True,
    )

    port = free_port(); base = f"http://127.0.0.1:{port}"
    log = open(SCRATCH / "service.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "service.app", "--data-root", str(data_root),
         "--media-root", str(media_root), "--port", str(port)],
        cwd=str(CORE), stdout=log, stderr=subprocess.STDOUT,
    )
    report: dict = {"base": base, "steps": {}}
    try:
        for _ in range(80):
            try:
                status, health = call(base, "GET", "/health")
                if status == 200:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        else:
            print(json.dumps({"error": "service did not start"})); return 1
        report["steps"]["health"] = {"status": status, "service": health.get("service"),
                                     "presets": health.get("presets"), "transitions": len(health.get("transitions") or [])}

        status, proj = call(base, "POST", "/projects", {"title": "E2E 2C", "session_id": "e2e-2c"})
        pid = proj.get("projectId")
        report["steps"]["create"] = {"status": status, "projectId": pid}
        for name in ("clipA.mp4", "still.png"):
            status, _ = call(base, "POST", f"/projects/{pid}/media", {"path": name})
            report["steps"][f"media:{name}"] = {"status": status}
            if status not in (200, 201):
                print(json.dumps(report)); return 1

        status, current = call(base, "GET", f"/projects/{pid}")
        doc = current.get("project") or current
        revision = current.get("revision")
        video_scene = next(s for s in doc["scenes"] if s["source"]["kind"] == "video")
        image_scene = next(s for s in doc["scenes"] if s["source"]["kind"] == "image")
        video_scene["speed"] = 2.0
        image_scene["kenBurns"] = {"zoom": 1.2, "pan": "right"}
        image_scene["transition"] = "slideleft-0.5"
        status, saved = call(base, "PUT", f"/projects/{pid}", {"revision": revision, "draft": doc})
        report["steps"]["put"] = {"status": status, "revision": saved.get("revision")}
        if status != 200:
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        status, exp = call(base, "POST", f"/projects/{pid}/export",
                           {"preset": "mp4-720p30-vertical", "captions": False})
        job_id = exp.get("jobId"); report["steps"]["export"] = {"status": status, "jobId": job_id}
        if status != 202:
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1
        deadline = time.time() + 180; job = {}
        while time.time() < deadline:
            _s, job = call(base, "GET", f"/jobs/{job_id}")
            if job.get("state") in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.5)
        report["steps"]["job"] = {"state": job.get("state"), "error": job.get("error")}
        if job.get("state") != "succeeded":
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        out = SCRATCH / "out.mp4"
        with urllib.request.urlopen(base + f"/jobs/{job_id}/output", timeout=60) as resp:
            out.write_bytes(resp.read())
        probe = subprocess.run(["ffprobe", "-hide_banner", "-v", "error", "-print_format", "json",
                                "-show_streams", "-show_format", str(out)],
                               capture_output=True, text=True, check=True)
        payload = json.loads(probe.stdout)
        video = next(s for s in payload["streams"] if s["codec_type"] == "video")
        audio = next((s for s in payload["streams"] if s["codec_type"] == "audio"), None)
        duration = float(payload["format"].get("duration") or 0)
        durations = []
        overlaps = []
        for index, scene in enumerate(doc["scenes"]):
            span = float(scene["out"]) - float(scene["in"])
            speed = float(scene.get("speed") or 1.0)
            durations.append(span / speed)
            style = str(scene.get("transition") or "none")
            if index > 0 and style != "none":
                overlaps.append(float(style.rsplit("-", 1)[1]))
        expected = sum(durations) - sum(overlaps)
        report["timeline"] = {"durations": durations, "overlaps": overlaps, "expected": expected}
        report["output"] = {"bytes": out.stat().st_size, "duration": duration, "expected": expected,
                            "size": f"{video['width']}x{video['height']}", "codec": video["codec_name"],
                            "audio": audio and audio["codec_name"]}
        ok = video["width"] == 720 and video["height"] == 1280 and abs(duration - expected) < 0.4 and audio is not None
        report["verdict"] = "PASS" if ok else "FAIL"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
