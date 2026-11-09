#!/usr/bin/env python3
"""Cliente CLI del spike: health, submit, follow, cancel, get. Solo stdlib."""
from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8765"


def call(path: str, method: str = "GET", body: dict | None = None, timeout: float = 30) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def submit(kind: str = "demo", **kw) -> dict:
    return call("/jobs", "POST", {"kind": kind, **kw})


def follow(jid: str, timeout: float = 300, echo: bool = True) -> dict:
    t0 = time.time()
    last = -1
    while time.time() - t0 < timeout:
        job = call(f"/jobs/{jid}")
        pct = int(job.get("progress") or 0)
        if echo and pct != last:
            print(
                f"  {job['state']:10s} {pct:3d}% fps={job.get('fps')} speed={job.get('speed')} "
                f"stage={job.get('stage')} pid={job.get('pid')}",
                flush=True,
            )
            last = pct
        if job["state"] in ("succeeded", "failed", "cancelled", "interrupted"):
            return job
        time.sleep(0.5)
    return call(f"/jobs/{jid}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "health"
    if cmd == "health":
        print(json.dumps(call("/health"), indent=2, ensure_ascii=False))
    elif cmd == "submit":
        kind = sys.argv[2] if len(sys.argv) > 2 else "demo"
        kw = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(submit(kind, **kw), indent=2))
    elif cmd == "follow":
        print(json.dumps(follow(sys.argv[2]), indent=2, ensure_ascii=False))
    elif cmd == "cancel":
        print(json.dumps(call(f"/jobs/{sys.argv[2]}/cancel", "POST", {}), indent=2))
    elif cmd == "get":
        print(json.dumps(call(f"/jobs/{sys.argv[2]}"), indent=2, ensure_ascii=False))
    elif cmd == "list":
        print(json.dumps(call("/jobs"), indent=2, ensure_ascii=False))
    elif cmd == "probe":
        print(json.dumps(call("/probe"), indent=2, ensure_ascii=False))
    else:
        raise SystemExit(f"comando desconocido: {cmd}")
