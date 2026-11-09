"""E2E Fase 3A: generar imagen/música locales, insertarlas y exportar con SFX."""

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
SCRATCH = Path.home() / "AppData" / "Local" / "hermes" / "cache" / "scratch" / "ve-3a-e2e"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def call(base: str, method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def wait_job(base: str, job_id: str, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    job: dict = {}
    while time.time() < deadline:
        _s, job = call(base, "GET", f"/jobs/{job_id}")
        if job.get("state") in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(0.4)
    return job


def main() -> int:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)
    data_root = SCRATCH / "data"; media_root = SCRATCH / "media"
    data_root.mkdir(parents=True); media_root.mkdir(parents=True)
    shutil.copy2(CORE.parent / "spike" / "fixtures" / "clipA.mp4", media_root / "clipA.mp4")

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
            print(json.dumps({"error": "service did not start", "log": str(SCRATCH / "service.log")}))
            return 1
        report["steps"]["health"] = {"service": health.get("service"), "providers": health.get("providers"),
                                     "modes": health.get("providerModes")}

        status, proj = call(base, "POST", "/projects", {"title": "E2E 3A", "session_id": "e2e-3a"})
        pid = proj.get("projectId"); report["steps"]["create"] = {"status": status, "projectId": pid}
        status, _ = call(base, "POST", f"/projects/{pid}/media", {"path": "clipA.mp4"})
        report["steps"]["media"] = {"status": status}

        # 1) generar imagen local
        status, gen = call(base, "POST", f"/projects/{pid}/generate",
                           {"kind": "image", "prompt": "fondo azul para intro", "provider": "local"})
        report["steps"]["generate_image"] = {"status": status, "jobId": gen.get("jobId")}
        image_job = wait_job(base, gen.get("jobId"))
        report["steps"]["generate_image"]["job"] = image_job.get("state")

        # 2) generar música local
        status, gen2 = call(base, "POST", f"/projects/{pid}/generate",
                            {"kind": "music", "prompt": "cama suave", "provider": "local", "duration": 4})
        report["steps"]["generate_music"] = {"status": status, "jobId": gen2.get("jobId")}
        music_job = wait_job(base, gen2.get("jobId"))
        report["steps"]["generate_music"]["job"] = music_job.get("state")

        # 3) proveedor http sin configurar → 400
        status, err = call(base, "POST", f"/projects/{pid}/generate",
                           {"kind": "image", "prompt": "x", "provider": "http"})
        report["steps"]["http_unconfigured"] = {"status": status, "error": err.get("error")}

        status, current = call(base, "GET", f"/projects/{pid}")
        doc = current.get("project") or current
        revision = current.get("revision")
        assets = doc.get("assets") or []
        image_asset = next((a for a in assets if a.get("kind") == "image"), None)
        music_asset = next((a for a in assets if a.get("kind") == "audio"), None)
        report["assets"] = {
            "image": image_asset and {"id": image_asset["id"], "path": image_asset["path"], "rights": image_asset["rights"]["status"]},
            "music": music_asset and {"id": music_asset["id"], "path": music_asset["path"], "rights": music_asset["rights"]["status"]},
        }
        if not image_asset or not music_asset:
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        # 4) insertar imagen como escena, música como cama y SFX en t=1
        status, _ = call(base, "POST", f"/projects/{pid}/media", {"path": image_asset["path"]})
        report["steps"]["insert_image"] = {"status": status}
        status, current = call(base, "GET", f"/projects/{pid}")
        doc = current.get("project") or current
        revision = current.get("revision")
        doc["music"] = {"assetId": music_asset["id"], "volume": 35, "fadeIn": 0.5, "fadeOut": 1.0, "loop": True}
        doc["audioEvents"] = [{"id": "ae_1", "assetId": music_asset["id"], "at": 1.0, "volume": 60}]
        status, saved = call(base, "PUT", f"/projects/{pid}", {"revision": revision, "draft": doc})
        report["steps"]["put"] = {"status": status, "revision": saved.get("revision")}
        if status != 200:
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        status, exp = call(base, "POST", f"/projects/{pid}/export", {"preset": "mp4-720p30", "captions": False})
        job = wait_job(base, exp.get("jobId"))
        report["steps"]["export"] = {"status": status, "job": job.get("state"), "error": job.get("error")}
        if job.get("state") != "succeeded":
            print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

        out = SCRATCH / "out.mp4"
        with urllib.request.urlopen(base + f"/jobs/{job['jobId']}/output", timeout=120) as resp:
            out.write_bytes(resp.read())
        probe = subprocess.run(["ffprobe", "-hide_banner", "-v", "error", "-print_format", "json",
                                "-show_streams", "-show_format", str(out)],
                               capture_output=True, text=True, check=True)
        payload = json.loads(probe.stdout)
        video = next(s for s in payload["streams"] if s["codec_type"] == "video")
        audio = next((s for s in payload["streams"] if s["codec_type"] == "audio"), None)
        report["output"] = {"bytes": out.stat().st_size, "duration": float(payload["format"]["duration"]),
                            "size": f"{video['width']}x{video['height']}", "audio": audio and audio["codec_name"]}
        ok = bool(audio) and status == 202
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
