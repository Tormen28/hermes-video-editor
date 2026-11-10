"""Smoke de punta a punta contra un servicio YA en marcha (con token): negativos + montar + editar por tiempo + exportar + ffprobe.

  python scripts/e2e_smoke.py --base http://127.0.0.1:8770 --media-root <carpeta de medios> --clip a.mp4 --clip b.mp4 [--voice]

Crea un proyecto nuevo de prueba (no toca los existentes). Sale con código 1 si algo falla.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import ve_client as vc

FAILS: list[str] = []


def ck(name: str, ok: bool, extra: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
    if not ok:
        FAILS.append(name)


def raw(base: str, method: str, path: str, headers: dict, body: bytes | None = None):
    req = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=vc.DEFAULT_BASE)
    ap.add_argument("--clip", action="append", required=True, help="ruta relativa a la carpeta de medios (≥2)")
    ap.add_argument("--voice", action="store_true", help="genera y coloca una voz local")
    ap.add_argument("--ffprobe", default=None)
    a = ap.parse_args()
    base = a.base

    # --- negativos de seguridad
    s, _ = raw(base, "GET", "/projects", {})
    ck("sin token -> 401", s == 401, str(s))
    s, _ = raw(base, "GET", "/projects", {"X-VE-Token": "mal"})
    ck("token malo -> 403", s == 403, str(s))
    s, h = raw(base, "POST", "/projects", {"Origin": "null", "Content-Type": "application/json"}, b'{"title":"x"}')
    ck("Origin null sin token -> 401 y sin ACAO", s == 401 and "Access-Control-Allow-Origin" not in h, str(s))
    tok = vc.auth.read_token() or ""
    s, _ = raw(base, "POST", "/projects", {"Origin": "https://evil.example", "X-VE-Token": tok, "Content-Type": "application/json"}, b'{"title":"x"}')
    ck("origen ajeno (con token) -> 403", s == 403, str(s))
    s, h = raw(base, "GET", "/health", {"Origin": "null"})
    ck("health sin token no filtra CORS ni *", h.get("Access-Control-Allow-Origin") not in ("*", "null"), str(h.get("Access-Control-Allow-Origin")))

    # --- flujo
    s, p = vc.call(base, "POST", "/projects", {"title": "Smoke e2e"}); ck("crear proyecto", s == 201, str(s)); pid = p["projectId"]
    for clip in a.clip:
        s, _ = vc.call(base, "POST", f"/projects/{pid}/media", {"path": clip}); ck(f"importar {clip}", s == 201, str(s))
    if a.voice:
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("ve_generate.py")), "--base", base, "--project", pid,
                            "--kind", "voice", "--prompt", "Hola. Esta es una prueba de la voz local del editor.", "--use", "voice", "--at", "1"],
                           capture_output=True, text=True)
        ck("voz local generada y colocada", r.returncode == 0, (r.stdout + r.stderr)[-160:].replace("\n", " "))
    s, tl = vc.call(base, "GET", f"/projects/{pid}/timeline"); ck("timeline", s == 200 and len(tl["scenes"]) >= 2, f"dura {tl.get('durationTc')}")
    t_mid = tl["scenes"][1]["start"] + 0.5
    s, res = vc.call(base, "POST", f"/projects/{pid}/edit", {"ops": [
        {"op": "set_text", "time": t_mid, "content": "Editado por tiempo"},
        {"op": "set_volume", "scene": 1, "volume": 40},
        {"op": "trim", "scene": 1, "duration": 1.5},
    ]})
    ck("edición por tiempo", s == 200, "; ".join(res.get("applied", [])) if s == 200 else str(res))
    s, tl2 = vc.call(base, "GET", f"/projects/{pid}/timeline")
    expected = tl["duration"] - (tl["scenes"][0]["duration"] - 1.5)
    ck("duración recalculada", abs(tl2["duration"] - expected) < 0.2, f"{tl['duration']} -> {tl2['duration']}")
    s, ex = vc.call(base, "POST", f"/projects/{pid}/export", {"preset": "mp4-720p30"}); ck("export 202", s == 202, str(s))
    job = vc.wait_job(base, ex.get("jobId") or ex.get("id"), 300, quiet=True)
    ck("export terminado", job.get("state") == "succeeded", job.get("state", ""))
    out = job.get("outputPath") or job.get("output", {}).get("path") or ""
    if out and Path(out).is_file():
        probe = a.ffprobe or "ffprobe"
        info = json.loads(subprocess.run([probe, "-v", "error", "-show_entries", "stream=codec_name,codec_type,width,height:format=duration", "-of", "json", out], capture_output=True, text=True).stdout)
        kinds = {x["codec_type"]: x for x in info["streams"]}
        ck("ffprobe: h264 + aac", kinds.get("video", {}).get("codec_name") == "h264" and kinds.get("audio", {}).get("codec_name") == "aac")
        ck("ffprobe: 1280x720", (kinds["video"]["width"], kinds["video"]["height"]) == (1280, 720))
        ck("ffprobe: duración = línea de tiempo", abs(float(info["format"]["duration"]) - tl2["duration"]) < 0.3, f"{info['format']['duration']} vs {tl2['duration']}")
    else:
        ck("ruta de salida disponible", False, str(job)[:200])
    print("RESULTADO:", "OK" if not FAILS else f"FALLOS {FAILS}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())