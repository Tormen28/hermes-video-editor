"""Tiny HTTP client shared by the chat-side tools (token-aware, stdlib only)."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from service import auth  # noqa: E402

DEFAULT_BASE = os.environ.get("VE_BASE") or "http://127.0.0.1:8770"


def call(base: str, method: str, path: str, body: dict | None = None, timeout: float = 60.0, token: str | None = None):
    """Return ``(status, json)``. The token (if any) travels only in its header."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data else {}
    token = token if token is not None else auth.read_token()
    if token:
        headers[auth.TOKEN_HEADER] = token
    request = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8") or "{}")
        except ValueError:
            return exc.code, {"error": f"HTTP {exc.code}"}


def wait_job(base: str, job_id: str, timeout: float, quiet: bool = False) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        _status, job = call(base, "GET", f"/jobs/{job_id}")
        state = job.get("state")
        if state != last and not quiet:
            progress = job.get("progress")
            if isinstance(progress, (int, float)):
                pct = progress * 100 if progress <= 1 else progress
                print(f"[{state} {round(pct)}%]", file=sys.stderr)
            else:
                print(f"[{state}]", file=sys.stderr)
            last = state
        if state in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(0.4)
    return {"state": "timeout", "jobId": job_id}