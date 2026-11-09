"""Puente chat→editor: genera un asset y lo aplica al proyecto en un paso.

Ejemplos:
  python scripts/ve_generate.py --project prj_x --kind image --prompt "intro azul" --use scene
  python scripts/ve_generate.py --project prj_x --kind music --prompt "cama suave" --duration 12 --use music
  python scripts/ve_generate.py --project prj_x --kind music --prompt "whoosh" --duration 2 --use sfx --at 3.5
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8770"


def call(base: str, method: str, path: str, body: dict | None = None, timeout: float = 60.0):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def wait_job(base: str, job_id: str, timeout: float) -> dict:
    deadline = time.time() + timeout
    last_state = None
    while time.time() < deadline:
        _status, job = call(base, "GET", f"/jobs/{job_id}")
        state = job.get("state")
        if state != last_state:
            progress = job.get("progress")
            if isinstance(progress, (int, float)):
                pct = progress * 100 if progress <= 1 else progress
                print(f"[{state} {round(pct)}%]", file=sys.stderr)
            else:
                print(f"[{state}]", file=sys.stderr)
            last_state = state
        if state in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(0.5)
    return {"state": "timeout", "jobId": job_id}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un asset y opcionalmente lo aplica al proyecto")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--project", required=True)
    parser.add_argument("--kind", required=True, choices=["image", "music"])
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--provider", default="local", choices=["local", "http"])
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--use", default="none", choices=["none", "scene", "music", "logo", "sfx"])
    parser.add_argument("--at", type=float, default=0.0)
    parser.add_argument("--volume", type=int, default=60)
    parser.add_argument("--position", default="bottom-right")
    parser.add_argument("--opacity", type=float, default=0.8)
    parser.add_argument("--scale", type=float, default=0.15)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    body: dict = {"kind": args.kind, "prompt": args.prompt, "provider": args.provider}
    if args.duration is not None:
        body["duration"] = args.duration
    status, generated = call(args.base, "POST", f"/projects/{args.project}/generate", body)
    if status not in (200, 202):
        print(json.dumps({"error": generated, "status": status}, ensure_ascii=False))
        return 1
    job = wait_job(args.base, generated["jobId"], args.timeout)
    if job.get("state") != "succeeded":
        print(json.dumps(job, ensure_ascii=False))
        return 1

    asset_id = job.get("assetId")
    status, current = call(args.base, "GET", f"/projects/{args.project}")
    doc = current.get("project") or current
    asset = next((item for item in doc.get("assets") or [] if item.get("id") == asset_id), None)
    if asset is None:
        print(json.dumps({"error": "asset no encontrado en el proyecto", "assetId": asset_id}))
        return 1

    applied = args.use
    revision = current.get("revision")
    if args.use == "scene":
        status, result = call(args.base, "POST", f"/projects/{args.project}/media", {"path": asset["path"]})
        if status not in (200, 201):
            print(json.dumps(result, ensure_ascii=False)); return 1
        revision = result.get("revision")
    elif args.use == "music":
        doc["music"] = {
            "assetId": asset_id,
            "volume": args.volume,
            "fadeIn": 1.0,
            "fadeOut": 1.5,
            "loop": True,
            "ducking": True,
        }
        status, result = call(args.base, "PUT", f"/projects/{args.project}", {"revision": revision, "draft": doc})
        if status != 200:
            print(json.dumps(result, ensure_ascii=False)); return 1
        revision = result.get("revision")
    elif args.use == "logo":
        doc["logo"] = {
            "assetId": asset_id,
            "position": args.position,
            "opacity": args.opacity,
            "scale": args.scale,
        }
        status, result = call(args.base, "PUT", f"/projects/{args.project}", {"revision": revision, "draft": doc})
        if status != 200:
            print(json.dumps(result, ensure_ascii=False)); return 1
        revision = result.get("revision")
    elif args.use == "sfx":
        events = list(doc.get("audioEvents") or [])
        events.append({"id": "ae_" + secrets.token_hex(3), "assetId": asset_id, "at": args.at, "volume": args.volume})
        doc["audioEvents"] = events
        status, result = call(args.base, "PUT", f"/projects/{args.project}", {"revision": revision, "draft": doc})
        if status != 200:
            print(json.dumps(result, ensure_ascii=False)); return 1
        revision = result.get("revision")

    print(json.dumps({
        "jobId": generated["jobId"],
        "assetId": asset_id,
        "kind": args.kind,
        "path": asset["path"],
        "applied": applied,
        "revision": revision,
        "url": args.base.rstrip("/") + (job.get("assetUrl") or ""),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
