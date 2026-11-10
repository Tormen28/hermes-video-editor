"""E2E real de música: servicio propio, dos escenas + música con loop/ducking/normalize, MP4 verificado."""

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
SCRATCH = Path.home() / "AppData" / "Local" / "hermes" / "cache" / "scratch" / "ve-music-e2e"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def main() -> int:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)
    data_root = SCRATCH / "data"
    media_root = SCRATCH / "media"
    data_root.mkdir(parents=True)
    media_root.mkdir(parents=True)

    clip = CORE.parent / "spike" / "fixtures" / "clipA.mp4"
    shutil.copy2(clip, media_root / "clipA.mp4")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:a", "pcm_s16le", str(media_root / "music.wav")],
        check=True,
    )

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    log = open(SCRATCH / "service.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "service.app", "--data-root", str(data_root),
         "--media-root", str(media_root), "--port", str(port), "--no-token"],
        cwd=str(CORE), stdout=log, stderr=subprocess.STDOUT,
    )
    report: dict = {"base": base, "steps": {}}
    try:
        for _ in range(60):
            try:
                status, health = call(base, "GET", "/health")
                if status == 200:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        else:
            print(json.dumps({"error": "service did not start", "log": str(SCRATCH / "service.log")}))
            return 1
        report["steps"]["health"] = {"status": status, "service": health.get("service")}

        status, proj = call(base, "POST", "/projects", {"title": "E2E música", "session_id": "e2e-music"})
        pid = proj.get("projectId")
        report["steps"]["create"] = {"status": status, "projectId": pid, "revision": proj.get("revision")}
        if status not in (200, 201):
            print(json.dumps(report)); return 1

        for name in ("clipA.mp4", "music.wav"):
            status, added = call(base, "POST", f"/projects/{pid}/media", {"path": name})
            report["steps"][f"media:{name}"] = {
                "status": status, "assets": len(added.get("assets") or []), "scenes": len(added.get("scenes") or []),
            }
            if status not in (200, 201):
                print(json.dumps(report)); return 1

        status, current = call(base, "GET", f"/projects/{pid}")
        doc = current.get("project") or current
        revision = current.get("revision")
        music_asset = next(a for a in doc["assets"] if a["path"] == "music.wav")
        expected_duration = sum(float(s["out"]) - float(s["in"]) for s in doc["scenes"])
        doc["music"] = {
            "assetId": music_asset["id"], "volume": 40, "fadeIn": 0.5, "fadeOut": 1.0,
            "loop": True, "ducking": True,
        }
        doc["audio"]["normalize"] = True
        status, saved = call(base, "PUT", f"/projects/{pid}", {"revision": revision, "draft": doc})
        report["steps"]["put_music"] = {"status": status, "revision": saved.get("revision")}
        if status != 200:
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        status, exp = call(base, "POST", f"/projects/{pid}/export", {"preset": "mp4-720p30", "captions": False})
        job_id = exp.get("jobId")
        report["steps"]["export"] = {"status": status, "jobId": job_id}
        if status != 202:
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        deadline = time.time() + 180
        job = {}
        while time.time() < deadline:
            _s, job = call(base, "GET", f"/jobs/{job_id}")
            if job.get("state") in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.5)
        report["steps"]["job"] = {"state": job.get("state"), "error": job.get("error"), "output": job.get("output")}
        if job.get("state") != "succeeded":
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        out = SCRATCH / "music.mp4"
        req = urllib.request.Request(base + f"/jobs/{job_id}/output")
        with urllib.request.urlopen(req, timeout=60) as resp:
            out.write_bytes(resp.read())

        probe = subprocess.run(
            ["ffprobe", "-hide_banner", "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", str(out)],
            capture_output=True, text=True, check=True,
        )
        payload = json.loads(probe.stdout)
        streams = payload.get("streams") or []
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        report["output"] = {
            "bytes": out.stat().st_size,
            "duration": float(payload["format"].get("duration") or 0),
            "video": {"codec": video and video.get("codec_name"), "size": video and f"{video.get('width')}x{video.get('height')}"},
            "audio": {"codec": audio and audio.get("codec_name"), "channels": audio and audio.get("channels"), "rate": audio and audio.get("sample_rate")},
            "expectedDuration": expected_duration,
        }
        ok = bool(audio) and bool(video) and abs(report["output"]["duration"] - expected_duration) < 1.0
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
