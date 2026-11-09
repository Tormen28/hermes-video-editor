#!/usr/bin/env python3
"""Test 2: cancelación a mitad, sin huérfanos; dedupe; crash + reaper.

Evidencia:
  - tasklist ffmpeg antes / durante / después
  - taskkill output
  - staging eliminado, sin MP4 parcial
  - dedupe_key: dos POST iguales -> mismo id
  - crash: se mata el servicio con un job corriendo -> queda ffmpeg huérfano;
    al relanzar, el reaper mata el huérfano y marca el job 'interrupted'
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from client import call, submit  # noqa: E402

SERVICE = os.path.join(HERE, "service.py")
LOG = os.path.join(HERE, "logs", "service.stdout.log")


def ffmpeg_pids() -> list[int]:
    cp = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ffmpeg.exe", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True)
    pids = []
    for line in (cp.stdout or "").splitlines():
        if "ffmpeg.exe" in line.lower():
            parts = [p.strip('"') for p in line.split('","')]
            try:
                pids.append(int(parts[1]))
            except (IndexError, ValueError):
                pass
    return pids


def wait_health(port: int = 8765, timeout: float = 25) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    return False


def main() -> int:
    res: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    res["ffmpeg_before"] = ffmpeg_pids()

    # ---- A) cancelación a mitad
    sub = submit("long", preset="medium", crf=21, width=1920, height=1080, loops=8, label="cancel test")
    jid = sub["id"]
    res["job_id"] = jid
    print("submitted long:", sub, flush=True)

    t0 = time.time()
    progress = 0
    while time.time() - t0 < 120:
        job = call(f"/jobs/{jid}")
        progress = job.get("progress") or 0
        if progress >= 8 or time.time() - t0 > 25:
            break
        time.sleep(0.4)
    res["progress_at_cancel"] = progress
    res["seconds_before_cancel"] = round(time.time() - t0, 2)
    res["ffmpeg_during"] = ffmpeg_pids()
    res["pid_reported"] = job.get("pid")
    print("progress:", progress, "ffmpeg during:", res["ffmpeg_during"], flush=True)

    t1 = time.time()
    cancel = call(f"/jobs/{jid}/cancel", "POST", {})
    res["cancel_response"] = cancel
    print("cancel:", cancel, flush=True)

    final = {}
    while time.time() - t1 < 40:
        final = call(f"/jobs/{jid}")
        if final["state"] in ("cancelled", "failed", "succeeded", "interrupted"):
            break
        time.sleep(0.3)
    res["cancel_latency_s"] = round(time.time() - t1, 2)
    res["final_state"] = final.get("state")
    res["final_exit_code"] = final.get("exit_code")
    res["final_progress"] = final.get("progress")
    time.sleep(1.5)
    res["ffmpeg_after_cancel"] = ffmpeg_pids()
    staging = os.path.join(HERE, "out", ".staging", jid)
    res["staging_exists"] = os.path.exists(staging)
    res["partial_out_exists"] = os.path.exists(os.path.join(HERE, "out", f"{jid}.mp4"))
    print("final:", final.get("state"), "after tasklist:", res["ffmpeg_after_cancel"],
          "staging_exists:", res["staging_exists"], flush=True)

    # ---- B) dedupe (relanzar sin duplicados)
    d1 = submit("long", preset="ultrafast", width=640, height=360, loops=16, dedupe_key="kanban-42")
    d2 = submit("long", preset="ultrafast", width=640, height=360, loops=16, dedupe_key="kanban-42")
    res["dedupe_first"] = d1
    res["dedupe_second"] = d2
    res["dedupe_same_id"] = d1.get("id") == d2.get("id")
    print("dedupe:", d1, d2, flush=True)
    call(f"/jobs/{d1['id']}/cancel", "POST", {})
    time.sleep(1.0)

    # ---- C) crash del servicio con job corriendo -> huérfano -> reaper al relanzar
    crash_job = submit("long", preset="medium", width=1920, height=1080, loops=8, label="crash test")
    cjid = crash_job["id"]
    res["crash_job_id"] = cjid
    t0 = time.time()
    while time.time() - t0 < 40:
        j = call(f"/jobs/{cjid}")
        if (j.get("progress") or 0) > 3:
            break
        time.sleep(0.3)
    res["crash_progress"] = j.get("progress")
    res["ffmpeg_before_crash"] = ffmpeg_pids()

    svc_pid = call("/health")["pid"]
    killed = subprocess.run(["taskkill", "/PID", str(svc_pid), "/F"], capture_output=True, text=True)
    res["service_kill"] = (killed.stdout or killed.stderr).strip()
    time.sleep(1.5)
    res["ffmpeg_after_service_kill"] = ffmpeg_pids()
    print("service killed:", svc_pid, "orphans:", res["ffmpeg_after_service_kill"], flush=True)

    # relanzar (proceso independiente, mismo puerto y DB)
    env = dict(os.environ)
    proc = subprocess.Popen(
        [sys.executable, SERVICE, "--port", "8765"],
        cwd=HERE,
        stdout=open(LOG, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        env=env,
    )
    res["relaunched_pid"] = proc.pid
    res["relaunched_healthy"] = wait_health()
    time.sleep(1.5)
    res["ffmpeg_after_reaper"] = ffmpeg_pids()
    after = call(f"/jobs/{cjid}")
    res["crash_job_state_after_restart"] = after.get("state")
    res["crash_job_error"] = after.get("error")
    res["service_health_after"] = call("/health")
    res["ffmpeg_final"] = ffmpeg_pids()
    res["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(os.path.join(HERE, "logs", "test_cancel.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    print(json.dumps({k: res[k] for k in (
        "progress_at_cancel", "ffmpeg_during", "ffmpeg_after_cancel", "staging_exists",
        "final_state", "dedupe_same_id", "ffmpeg_before_crash", "ffmpeg_after_service_kill",
        "ffmpeg_after_reaper", "crash_job_state_after_restart", "ffmpeg_final")}, indent=2))
    ok = (
        res["final_state"] in ("cancelled",)
        and not res["ffmpeg_after_cancel"]
        and not res["staging_exists"]
        and not res["partial_out_exists"]
        and res["dedupe_same_id"]
        and res["ffmpeg_after_service_kill"]  # huérfano real, si no el test no prueba nada
        and not res["ffmpeg_after_reaper"]
        and res["crash_job_state_after_restart"] == "interrupted"
        and not res["ffmpeg_final"]
    )
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
