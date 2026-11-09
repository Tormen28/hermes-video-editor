#!/usr/bin/env python3
"""Test 1: render demo real + métricas + p95 del gateway antes/durante/después.

Método p95: se reutiliza UNA conexión keep-alive a http://127.0.0.1:55860 y se mide
el tiempo de ida y vuelta de GET /api/health (el listener HTTP del gateway, el mismo
que consulta la app). No mide latencia de turnos LLM; mide si el render degrada el
event loop del gateway. Puerto leído de los rendezvous records, no hardcodeado a ciegas.
"""
from __future__ import annotations

import http.client
import json
import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import call, submit  # noqa: E402

GW_HOST, GW_PORT = "127.0.0.1", 55860
SAMPLES = 60


def p95(values: list[float]) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[idx]


def gw_latencies(n: int, stop: threading.Event | None = None) -> list[float]:
    out: list[float] = []
    conn = http.client.HTTPConnection(GW_HOST, GW_PORT, timeout=10)
    for _ in range(n):
        if stop is not None and stop.is_set():
            break
        t0 = time.perf_counter()
        try:
            conn.request("GET", "/api/health")
            r = conn.getresponse()
            r.read()
            out.append((time.perf_counter() - t0) * 1000.0)
            if r.status != 200:
                break
        except Exception:  # noqa: BLE001
            try:
                conn.close()
                conn = http.client.HTTPConnection(GW_HOST, GW_PORT, timeout=10)
            except Exception:  # noqa: BLE001
                break
        time.sleep(0.05)
    conn.close()
    return out


def summarize(name: str, vals: list[float]) -> dict:
    if not vals:
        return {"phase": name, "n": 0}
    return {
        "phase": name,
        "n": len(vals),
        "p50_ms": round(statistics.median(vals), 2),
        "p95_ms": round(p95(vals), 2),
        "max_ms": round(max(vals), 2),
    }


def main() -> int:
    result: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    before = gw_latencies(SAMPLES)
    result["gateway_before"] = summarize("before", before)
    print("gateway before:", result["gateway_before"], flush=True)

    sub = submit("demo", preset="veryfast", crf=23, label="demo p95")
    jid = sub["id"]
    result["job_id"] = jid
    print("submitted:", sub, flush=True)

    during: list[float] = []
    stop = threading.Event()
    sample_state: dict = {"progress": 0, "fps": 0, "speed": 0}

    def gw_during() -> None:
        conn = http.client.HTTPConnection(GW_HOST, GW_PORT, timeout=10)
        while not stop.is_set():
            t0 = time.perf_counter()
            try:
                conn.request("GET", "/api/health")
                r = conn.getresponse()
                r.read()
                during.append((time.perf_counter() - t0) * 1000.0)
            except Exception:  # noqa: BLE001
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
                conn = http.client.HTTPConnection(GW_HOST, GW_PORT, timeout=10)
            time.sleep(0.05)
        conn.close()

    t = threading.Thread(target=gw_during, daemon=True)
    t.start()

    t0 = time.time()
    last = -1
    timeline: list[dict] = []
    while True:
        job = call(f"/jobs/{jid}")
        sample_state = {"progress": job.get("progress"), "fps": job.get("fps"), "speed": job.get("speed")}
        if int(job.get("progress") or 0) != last:
            last = int(job.get("progress") or 0)
            timeline.append({"t": round(time.time() - t0, 2), "pct": last, "fps": job.get("fps"), "speed": job.get("speed")})
        if job["state"] in ("succeeded", "failed", "cancelled", "interrupted"):
            break
        time.sleep(0.15)
    stop.set()
    t.join(timeout=5)
    result["gateway_during"] = summarize("during", during)
    print("gateway during:", result["gateway_during"], flush=True)

    time.sleep(1.0)
    after = gw_latencies(SAMPLES)
    result["gateway_after"] = summarize("after", after)
    print("gateway after:", result["gateway_after"], flush=True)

    result["job"] = job
    result["progress_timeline"] = timeline
    result["observed_wall_s"] = round(time.time() - t0, 2)

    # verificación del artefacto
    out = job.get("out_path")
    if out:
        import subprocess

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate",
             "-show_entries", "stream=codec_name,width,height,avg_frame_rate", "-of", "json", out],
            capture_output=True, text=True,
        )
        result["ffprobe"] = json.loads(probe.stdout or "{}")
        h = subprocess.run(["sha256sum", out], capture_output=True, text=True)
        result["sha256"] = h.stdout.strip()
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "test_demo.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print("wrote", path)
    print("job_id:", result["job_id"])
    print("state:", job["state"], "wall_s:", job.get("wall_s"), "cpu_s:", job.get("cpu_s"),
          "rss_peak_kb:", job.get("rss_peak_kb"), "ffmpeg_maxrss_kb:", job.get("ffmpeg_maxrss_kb"),
          "fps:", job.get("fps"), "speed:", job.get("speed"), "out_bytes:", job.get("out_bytes"))
    return 0 if job["state"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
