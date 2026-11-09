"""E2E por HTTP del servicio del núcleo del editor de vídeo.

Flujo: health → crear proyecto → añadir medios → conflicto de revisión (409)
→ export → seguir job → descargar MP4 → ffprobe → cancelación limpia.

Uso:
  python scripts/e2e_http_check.py --base http://127.0.0.1:8770 \
      --media clipA.mp4 clipB.mp4 --out logs/e2e-output.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
FFPROBE = os.environ.get(
    "VIDEO_EDITOR_FFPROBE",
    r"C:/Users/EgtYP/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffprobe.exe",
)


def call(base: str, method: str, path: str, body: dict | None = None, timeout: float = 30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype:
                return resp.status, json.loads(raw.decode("utf-8"))
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return exc.code, {"raw": raw[:400].decode("utf-8", "replace")}


def wait_job(base: str, job_id: str, timeout: float = 180) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        _, last = call(base, "GET", f"/jobs/{job_id}")
        state = (last or {}).get("state")
        if state in {"succeeded", "failed", "cancelled", "interrupted"}:
            return last
        time.sleep(0.4)
    return last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8770")
    ap.add_argument("--media", nargs="+", default=["clipA.mp4", "clipB.mp4"])
    ap.add_argument("--cancel-delay", type=float, default=0.2)
    ap.add_argument("--out", default=str(HERE / "logs" / "e2e-output.mp4"))
    args = ap.parse_args()
    base = args.base.rstrip("/")
    report: dict = {"base": base, "steps": {}}
    failures: list[str] = []

    status, health = call(base, "GET", "/health")
    report["steps"]["health"] = {"status": status, "ok": health.get("ok"), "mediaRoot": health.get("mediaRoot")}
    if status != 200 or not health.get("ok"):
        failures.append("health")

    status, proj = call(base, "POST", "/projects", {"title": "E2E HTTP", "session_id": "e2e"})
    report["steps"]["create_project"] = {"status": status, "projectId": proj.get("projectId"), "revision": proj.get("revision")}
    if status not in (200, 201):
        print(json.dumps(report, ensure_ascii=False, indent=2)); return 1
    pid = proj["projectId"]

    for name in args.media:
        status, added = call(base, "POST", f"/projects/{pid}/media", {"path": name})
        report["steps"].setdefault("add_media", []).append({"name": name, "status": status, "assets": len(added.get("assets") or []), "scenes": len(added.get("scenes") or [])})
        if status not in (200, 201):
            failures.append(f"add_media:{name}")

    status, current = call(base, "GET", f"/projects/{pid}")
    doc = current.get("project") or current
    report["steps"]["get_project"] = {"status": status, "revision": current.get("revision"), "scenes": len(doc.get("scenes") or [])}
    stale = call(base, "PUT", f"/projects/{pid}", {"revision": 0, "draft": doc})
    report["steps"]["stale_revision"] = {"status": stale[0], "current_revision": stale[1].get("current_revision"), "error": stale[1].get("error")}
    if stale[0] != 409:
        failures.append("stale_revision_no_409")

    status, exp = call(base, "POST", f"/projects/{pid}/export", {"preset": "mp4-720p30", "captions": False})
    report["steps"]["export"] = {"status": status, "jobId": exp.get("jobId"), "deduped": exp.get("deduped")}
    if status != 202:
        failures.append(f"export:{status}:{exp}")
        print(json.dumps(report, ensure_ascii=False, indent=2)); return 1

    job = wait_job(base, exp["jobId"])
    report["steps"]["job"] = {k: job.get(k) for k in ("jobId", "state", "stage", "progress", "wallSeconds", "bytes", "error")}
    if job.get("state") != "succeeded":
        failures.append(f"job:{job.get('state')}:{job.get('error')}")
    else:
        status, payload = call(base, "GET", f"/jobs/{exp['jobId']}/output", timeout=60)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(payload)
        probe = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries",
             "format=duration,size:stream=codec_name,width,height,avg_frame_rate,nb_frames",
             "-of", "json", str(out)],
            capture_output=True, text=True, timeout=60,
        )
        info = json.loads(probe.stdout or "{}")
        report["steps"]["output"] = {"status": status, "path": str(out), "bytes": out.stat().st_size, "probe": info}
        if not info.get("streams"):
            failures.append("ffprobe_empty")

    # cancelación: el dedupe devuelve el job anterior si el documento no cambió,
    # así que primero se modifica el proyecto para forzar un job nuevo.
    mutable = json.loads(json.dumps(doc))
    mutable["title"] = (mutable.get("title") or "E2E") + " · cancel"
    touched_status, touched = call(base, "PUT", f"/projects/{pid}", {"revision": current.get("revision"), "draft": mutable})
    report["steps"]["touch_for_cancel"] = {"status": touched_status, "revision": touched.get("revision")}

    status, exp2 = call(base, "POST", f"/projects/{pid}/export", {"preset": "mp4-720p30", "captions": False})
    if status == 202 and exp2.get("jobId"):
        time.sleep(args.cancel_delay)
        cstatus, cbody = call(base, "POST", f"/jobs/{exp2['jobId']}/cancel", {})
        job2 = wait_job(base, exp2["jobId"], timeout=60)
        report["steps"]["cancel"] = {"export": status, "cancelStatus": cstatus, "state": job2.get("state"), "body": cbody}
        if job2.get("state") not in {"cancelled", "interrupted"}:
            failures.append(f"cancel_state:{job2.get('state')}")

    report["failures"] = failures
    report["ok"] = not failures
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
