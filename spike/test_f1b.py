#!/usr/bin/env python3
"""F1-b: VFR real (P3), render final con acentos+xfade (P4) y baseline de latencia (P6).

Escribe logs/f1b/{vfr,final,latency}.json. Solo stdlib. No toca config ni gateway.
"""
from __future__ import annotations

import glob
import http.client
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "fixtures"
LOGS = ROOT / "logs" / "f1b"
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT))
from client import call, submit  # noqa: E402

LOGS.mkdir(parents=True, exist_ok=True)
VIDEO = ROOT / "work"


def run(argv: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=timeout)


def ffprobe_json(path: Path, entries: str) -> dict:
    cp = run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", str(path)])
    return json.loads(cp.stdout or "{}")


# ---------------------------------------------------------------- P3 · VFR

def build_vfr() -> dict:
    res: dict = {"steps": []}
    mix = FIX / "vfr_mix.mp4"
    clip24 = VIDEO / "clip_24fps.mp4"
    cp = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-f", "lavfi",
              "-i", "testsrc2=size=1280x720:rate=24:duration=4",
              "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(clip24)])
    res["steps"].append({"make_24fps": cp.returncode, "err": cp.stderr[-300:]})

    lst = VIDEO / "concat_vfr.txt"
    lst.write_text(
        "file '" + str(FIX / "clipA.mp4").replace("\\", "/") + "'\n"
        "file '" + str(clip24).replace("\\", "/") + "'\n",
        encoding="utf-8",
    )
    cp = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-f", "concat", "-safe", "0",
              "-i", str(lst), "-c", "copy", str(mix)])
    res["steps"].append({"concat_copy": cp.returncode, "err": cp.stderr[-400:]})

    info = ffprobe_json(mix, "stream=index,codec_type,avg_frame_rate,r_frame_rate,nb_frames,duration")
    st = [s for s in info.get("streams", []) if s.get("codec_type") == "video"][0]
    res["stream"] = st
    res["avg_ne_r"] = st.get("avg_frame_rate") != st.get("r_frame_rate")
    fmt = ffprobe_json(mix, "format=duration,size")["format"]
    res["format"] = fmt

    # irregularidad real de los timestamps (deltas de pts entre frames)
    cp = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
              "frame=pts_time", "-of", "csv=p=0", str(mix)])
    pts = [float(x.strip().strip(",")) for x in cp.stdout.splitlines() if x.strip().strip(",")]
    deltas = [round(b - a, 4) for a, b in zip(pts, pts[1:])]
    uniq = sorted(set(deltas))
    res["n_frames_probed"] = len(pts)
    res["delta_unique"] = uniq[:10]
    res["delta_min"] = min(deltas) if deltas else None
    res["delta_max"] = max(deltas) if deltas else None
    res["is_vfr_by_deltas"] = bool(deltas) and (max(deltas) - min(deltas)) > 0.005

    # corte 1: -ss antes del -i con -c copy (rápido, ata a keyframe)
    cut_copy = VIDEO / "cut_copy.mp4"
    cp = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-ss", "2", "-i", str(mix),
              "-t", "3", "-c", "copy", str(cut_copy)])
    res["cut_copy"] = {
        "rc": cp.returncode,
        "duration": ffprobe_json(cut_copy, "format=duration").get("format", {}).get("duration"),
        "start_time": ffprobe_json(cut_copy, "format=start_time").get("format", {}).get("start_time"),
    }
    # corte 2: re-encode (preciso)
    cut_re = VIDEO / "cut_reencode.mp4"
    cp = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-ss", "2", "-i", str(mix),
              "-t", "3", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", str(cut_re)])
    res["cut_reencode"] = {
        "rc": cp.returncode,
        "duration": ffprobe_json(cut_re, "format=duration").get("format", {}).get("duration"),
        "frames": ffprobe_json(cut_re, "stream=codec_type,nb_frames").get("streams", [{}])[0].get("nb_frames"),
    }

    # proxy CFR 30 con mapeo temporal
    proxy = VIDEO / "proxy_cfr30.mp4"
    cp = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(mix),
              "-vf", "fps=30,setpts=N/30/TB", "-fps_mode", "cfr",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-an", str(proxy)])
    pinfo = ffprobe_json(proxy, "stream=avg_frame_rate,r_frame_rate,nb_frames,duration")
    res["proxy"] = {"rc": cp.returncode, **pinfo.get("streams", [{}])[0],
                    "format_duration": ffprobe_json(proxy, "format=duration").get("format", {}).get("duration")}

    # mapeo: mismo instante t=2 en origen VFR y en proxy CFR -> SSIM alto
    cp = run(["ffmpeg", "-hide_banner", "-v", "error", "-ss", "2", "-i", str(mix), "-t", "2",
              "-ss", "2", "-i", str(proxy), "-t", "2",
              "-lavfi", "[0:v]scale=640:360,setpts=PTS-STARTPTS[a];[1:v]scale=640:360,setpts=PTS-STARTPTS[b];[a][b]ssim",
              "-f", "null", "-"])
    res["ssim_cut_mapping"] = ((cp.stderr or "") + (cp.stdout or "")).strip().splitlines()[-1][:200] if (cp.stderr or cp.stdout) else None
    return res


# ---------------------------------------------------------------- P4 · render final

def render_final() -> dict:
    jid = submit("final", preset="veryfast", crf="23")["id"]
    t0 = time.time()
    last = None
    while time.time() - t0 < 240:
        job = call(f"/jobs/{jid}")
        if job["state"] in ("succeeded", "failed", "cancelled", "interrupted"):
            break
        p = job.get("progress")
        if p != last:
            print(f"  [final] {job['state']} {p:.0f}% stage={job.get('stage')}", flush=True)
            last = p
        time.sleep(0.4)
    job = call(f"/jobs/{jid}")
    out = OUT / f"{jid}.mp4"
    res = {"id": jid, "state": job["state"], "wall_s": job.get("wall_s"), "out": str(out),
           "bytes": job.get("out_bytes"), "error": (job.get("error") or "")[:600]}
    if out.exists():
        res["probe"] = ffprobe_json(out, "format=duration,size:stream=codec_name,width,height,avg_frame_rate,nb_frames")
        res["cmd"] = (job.get("cmd") or "")[:1200]
    return res


# ---------------------------------------------------------------- P6 · latencia gateway

def gw_port() -> int:
    """Puerto del listener HTTP del gateway: el record puede venir sin 'port',
    así que se prueba /api/health en los puertos LISTENING de ese PID."""
    cand: list[int] = []
    pid = None
    for p in glob.glob(os.path.expanduser("~/.local/state/hermes/gateway-locks/host-*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if d.get("role") == "gateway":
            pid = d.get("pid")
            if d.get("port"):
                cand.append(int(d["port"]))
    if pid:
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, errors="replace").stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[-1] == str(pid) and "LISTENING" in line:
                    cand.append(int(parts[1].rsplit(":", 1)[1]))
        except Exception:
            pass
    cand += [55860, 63621]
    for port in cand:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            conn.request("GET", "/api/health")
            r = conn.getresponse()
            r.read()
            conn.close()
            if r.status == 200:
                return port
        except Exception:
            continue
    raise RuntimeError(f"no gateway http port among {cand}")


def p95(vals: list[float]) -> float:
    if not vals:
        return float("nan")
    o = sorted(vals)
    return o[min(len(o) - 1, int(round(0.95 * (len(o) - 1))))]


def summarize(name: str, vals: list[float]) -> dict:
    if not vals:
        return {"phase": name, "n": 0}
    return {"phase": name, "n": len(vals), "p50_ms": round(statistics.median(vals), 2),
            "p95_ms": round(p95(vals), 2), "max_ms": round(max(vals), 2)}


def latencies(port: int, n: int, interval: float = 0.02, stop: threading.Event | None = None) -> list[float]:
    out: list[float] = []
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    for _ in range(n):
        if stop is not None and stop.is_set():
            break
        t0 = time.perf_counter()
        try:
            conn.request("GET", "/api/health")
            r = conn.getresponse()
            r.read()
            out.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            try:
                conn.close()
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            except Exception:
                break
        time.sleep(interval)
    conn.close()
    return out


def latency_runs(runs: int = 3, n: int = 200) -> dict:
    port = gw_port()
    report = {"gateway_port": port, "n_per_window": n, "runs": []}
    for i in range(runs):
        before = latencies(port, n)
        jid = submit("final", preset="veryfast")["id"]
        stop = threading.Event()
        during: list[float] = []
        th = threading.Thread(target=lambda: during.extend(latencies(port, 600, 0.02, stop)), daemon=True)
        th.start()
        t0 = time.time()
        while time.time() - t0 < 120:
            job = call(f"/jobs/{jid}")
            if job["state"] in ("succeeded", "failed", "cancelled", "interrupted"):
                break
            time.sleep(0.2)
        stop.set()
        th.join(timeout=20)
        after = latencies(port, n)
        r = {"run": i + 1, "job": jid,
             "before": summarize("before", before), "during": summarize("during", during),
             "after": summarize("after", after),
             "during_has_200": len(during) >= n}
        r["p95_delta_pct"] = (round((r["during"]["p95_ms"] / r["before"]["p95_ms"] - 1) * 100, 1)
                              if r["before"].get("p95_ms") else None)
        report["runs"].append(r)
        print(f"  [latency run {i+1}] {r['before']} -> {r['during']} (Δp95 {r['p95_delta_pct']}%)", flush=True)
    return report


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "vfr"):
        print("[P3] VFR…", flush=True)
        v = build_vfr()
        (LOGS / "vfr.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v[k] for k in ("avg_ne_r", "is_vfr_by_deltas", "delta_unique", "proxy") if k in v}, ensure_ascii=False))
    if which in ("all", "final"):
        print("[P4] render final…", flush=True)
        f = render_final()
        (LOGS / "final.json").write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: f.get(k) for k in ("id", "state", "wall_s", "bytes")}, ensure_ascii=False))
    if which in ("all", "latency"):
        print("[P6] latencia…", flush=True)
        g = latency_runs()
        (LOGS / "latency.json").write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
