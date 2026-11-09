#!/usr/bin/env python3
"""editor-video-spike — servicio local de render FFmpeg para el spike F1.

Contrato:
  GET  /health                    estado del servicio (usado por el botón del pane)
  POST /jobs                      encola un render {kind, label?, preset?, crf?, width?, height?, loops?, dedupe_key?}
  GET  /jobs                      últimos jobs
  GET  /jobs/{id}                 estado + progreso + métricas + eventos
  POST /jobs/{id}/cancel          cancela (kill-tree Windows: taskkill /T /F)
  GET  /out/{file}                sirve el MP4 con soporte Range (preview <video>)
  POST /probe                     evidencia enviada por el pane (CSP/CORS/fetch)
  GET  /probe                     lee esa evidencia

Garantías:
  - 1 solo job concurrente (un worker, una cola).
  - Journal SQLite (jobs + job_events + plugin_probes), sobrevive caídas.
  - Staging en out/.staging/<id>/ y rename atómico (os.replace) a out/<id>.mp4.
  - Reaper al arrancar: jobs 'running' huérfanos se matan por PID y se marcan 'interrupted'.
  - Métricas por job: wall_s, cpu_s, rss_peak_kb, fps, speed, exit_code.

Solo stdlib. Python 3.11+ (probado con 3.11.15).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"
OUT = ROOT / "out"
STAGING = OUT / ".staging"
LOGS = ROOT / "logs"
WORK = ROOT / "work"
ASSETS_JSON = ROOT / "assets.json"
DB_PATH = ROOT / "jobs.sqlite3"
VERSION = "0.1.1"
PORT = int(os.environ.get("SPIKE_PORT", "8765"))
HOST = "127.0.0.1"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".mts", ".m2ts"}

FONT_BOLD = "C\\:/Windows/Fonts/arialbd.ttf"
FONT_REG = "C\\:/Windows/Fonts/arial.ttf"


# ---------------------------------------------------------------- registro de assets

def _assets() -> dict:
    try:
        return json.loads(ASSETS_JSON.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return {}


def _save_assets(d: dict) -> None:
    ASSETS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_file(path: Path, limit: int = 512 * 1024 * 1024) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def register_asset(folder: str, rel: str) -> dict:
    """Registra un archivo del disco (ruta absoluta = folder + rel) para servir por HTTP."""
    base = Path(folder).resolve()
    target = (base / rel).resolve() if not Path(rel).is_absolute() else Path(rel).resolve()
    # contención: el archivo tiene que estar dentro de la carpeta declarada
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError("ruta fuera de la carpeta concedida") from None
    if not target.is_file():
        raise FileNotFoundError(f"no es un archivo: {target}")
    if target.suffix.lower() not in VIDEO_EXT:
        raise ValueError(f"extensión no soportada: {target.suffix}")
    size = target.stat().st_size
    digest = sha256_file(target)
    aid = "a" + digest[:10]
    d = _assets()
    d[aid] = {
        "id": aid,
        "name": target.name,
        "path": str(target),
        "folder": str(base),
        "rel": rel,
        "size": size,
        "sha256": digest,
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _save_assets(d)
    return d[aid]

# ---------------------------------------------------------------- SQLite journal

_db_lock = threading.RLock()
_db: sqlite3.Connection | None = None


def db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA synchronous=NORMAL")
        _db.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              label TEXT,
              dedupe_key TEXT,
              state TEXT NOT NULL,
              created_at REAL NOT NULL,
              started_at REAL,
              finished_at REAL,
              progress REAL DEFAULT 0,
              stage TEXT,
              pid INTEGER,
              exit_code INTEGER,
              wall_s REAL,
              cpu_s REAL,
              rss_peak_kb INTEGER,
              ffmpeg_maxrss_kb INTEGER,
              fps REAL,
              speed REAL,
              out_path TEXT,
              out_bytes INTEGER,
              error TEXT,
              cmd TEXT,
              cancel_requested INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS job_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id TEXT NOT NULL,
              ts REAL NOT NULL,
              kind TEXT NOT NULL,
              detail TEXT
            );
            CREATE TABLE IF NOT EXISTS plugin_probes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts REAL NOT NULL,
              stage TEXT,
              detail TEXT,
              origin TEXT,
              user_agent TEXT,
              referer TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state, created_at);
            """
        )
        _db.commit()
    return _db


def q(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with _db_lock:
        return db().execute(sql, args).fetchall()


def x(sql: str, args: tuple = ()) -> None:
    with _db_lock:
        con = db()
        con.execute(sql, args)
        con.commit()


def event(job_id: str, kind: str, detail: str = "") -> None:
    x("INSERT INTO job_events(job_id, ts, kind, detail) VALUES (?,?,?,?)", (job_id, time.time(), kind, detail))


def job_row(job_id: str) -> dict | None:
    rows = q("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not rows:
        return None
    d = dict(rows[0])
    d["events"] = [dict(r) for r in q("SELECT ts, kind, detail FROM job_events WHERE job_id=? ORDER BY id", (job_id,))]
    return d


# ---------------------------------------------------------------- Windows metrics

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_kernel32.OpenProcess.restype = wt.HANDLE
_kernel32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
_kernel32.CloseHandle.argtypes = (wt.HANDLE,)
_psapi.GetProcessMemoryInfo.argtypes = (wt.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wt.DWORD)
_kernel32.GetProcessTimes.argtypes = (
    wt.HANDLE,
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010


def _ft_to_s(ft: FILETIME) -> float:
    return ((ft.dwHighDateTime << 32) | ft.dwLowDateTime) / 1e7


def sample_proc(pid: int) -> tuple[int, float] | None:
    """(working_set_bytes, cpu_seconds) del proceso, o None si ya no existe."""
    h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return None
    try:
        pmc = PROCESS_MEMORY_COUNTERS_EX()
        pmc.cb = ctypes.sizeof(pmc)
        if not _psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return None
        c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        cpu = 0.0
        if _kernel32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            cpu = _ft_to_s(k) + _ft_to_s(u)
        return int(pmc.WorkingSetSize), cpu
    finally:
        _kernel32.CloseHandle(h)


def kill_tree(pid: int) -> str:
    """Mata el árbol de procesos (Windows). Devuelve la salida de taskkill."""
    try:
        cp = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return (cp.stdout or "").strip() + (" " + (cp.stderr or "").strip() if cp.stderr else "")
    except Exception as exc:  # noqa: BLE001
        return f"taskkill failed: {exc!r}"


def ffmpeg_available() -> str:
    try:
        cp = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, errors="replace", timeout=15)
        first = (cp.stdout or "").splitlines()[0] if cp.stdout else ""
        return first.strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc!r}"


# ---------------------------------------------------------------- job planning

def ensure_final_texts() -> tuple[str, str]:
    """Escribe el rótulo (drawtext) y los subtítulos .ass con acentos; devuelve rutas con ':' escapado."""
    WORK.mkdir(parents=True, exist_ok=True)
    title = WORK / "titulo_acentos.txt"
    title.write_text("Escena áéíóúüñ ÁÉÍÓÚÑ ¿¡qué pasa?\n", encoding="utf-8")
    subs = WORK / "subs_acentos.ass"
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1280",
        "PlayResY: 720",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Base,Arial,40,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,20,20,40,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        "Dialogue: 0,0:00:00.50,0:00:03.50,Base,,0,0,0,,Subtítulo con acentos: á é í ó ú ü ñ",
        "Dialogue: 0,0:00:05.00,0:00:08.50,Base,,0,0,0,,Grafía española: ¿¡Mañana!",
    ]
    subs.write_text("\n".join(lines) + "\n", encoding="utf-8")
    esc = lambda p: str(p).replace("\\", "/").replace(":", "\\:")  # noqa: E731
    return esc(title), esc(subs)


def build_job(kind: str, params: dict) -> tuple[list[str], float, str]:
    """Devuelve (argv, duración_esperada_s, filtro usado)."""
    a = str(FIXTURES / "clipA.mp4").replace("\\", "/")
    b = str(FIXTURES / "clipB.mp4").replace("\\", "/")
    logo = str(FIXTURES / "logo.png").replace("\\", "/")

    preset = str(params.get("preset", "veryfast"))
    crf = int(params.get("crf", 23))
    w = int(params.get("width", 1280))
    h = int(params.get("height", 720))

    if kind == "demo":
        # 8s + 8s con xfade 1s = 15s. Dos escenas, rótulos, logo, crossfade de audio.
        filt = (
            f"[0:v]scale={w}:{h},setsar=1,format=yuv420p,"
            f"drawtext=fontfile='{FONT_BOLD}':text='ESCENA A':x=60:y=60:fontsize=42:fontcolor=white:"
            f"box=1:boxcolor=black@0.5:boxborderw=12[va];"
            f"[1:v]scale={w}:{h},setsar=1,format=yuv420p,"
            f"drawtext=fontfile='{FONT_REG}':text='ESCENA B':x=60:y=60:fontsize=42:fontcolor=white:"
            f"box=1:boxcolor=black@0.5:boxborderw=12[vb];"
            f"[va][vb]xfade=transition=fade:duration=1:offset=7[xf];"
            f"[xf][2:v]overlay=W-w-40:40[vout];"
            f"[0:a][1:a]acrossfade=d=1:c1=tri:c2=tri[aout]"
        )
        duration = 15.0
    elif kind == "long":
        # Job pesado (1080p, preset lento, N loops de clipA) para probar cancelación a mitad.
        loops = int(params.get("loops", 8))
        duration = 8.0 * loops
        filt = (
            f"[0:v]scale={w}:{h},setsar=1,format=yuv420p,"
            f"drawtext=fontfile='{FONT_BOLD}':text='RENDER LARGO %{{n}}':x=60:y=60:fontsize=48:"
            f"fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=12[vout];"
            f"[0:a]anull[aout]"
        )
    elif kind == "final":
        # 3 escenas de 4 s con dos xfade de 1 s (fade + slideleft) = 10 s,
        # rótulos drawtext con acentos (vía textfile UTF-8) y subtítulos .ass con acentos.
        title, subs = ensure_final_texts()
        scene = lambda idx, label: (  # noqa: E731
            f"[{idx}:v]trim=start=0:end=4,setpts=PTS-STARTPTS,scale={w}:{h},setsar=1,format=yuv420p,"
            f"drawtext=fontfile='{FONT_BOLD}':textfile='{title}':x=60:y=60:fontsize=46:fontcolor=white:"
            f"box=1:boxcolor=black@0.65:boxborderw=14[v{idx}];"
            f"[{idx}:a]atrim=start=0:end=4,asetpts=PTS-STARTPTS[a{idx}];"
        )
        filt = (
            scene(0, "1") + scene(1, "2") + scene(2, "3")
            + "[v0][v1]xfade=transition=fade:duration=1:offset=3[x1];"
            + "[x1][v2]xfade=transition=slideleft:duration=1:offset=6[x2];"
            + f"[x2]subtitles=filename='{subs}'[vout];"
            + "[a0][a1]acrossfade=d=1:c1=tri:c2=tri[aa1];"
            + "[aa1][a2]acrossfade=d=1:c1=tri:c2=tri[aout]"
        )
        duration = 10.0
    else:
        raise ValueError(f"kind desconocido: {kind!r}")

    argv = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-benchmark", "-progress", "pipe:1", "-loglevel", "info"]
    if kind == "long":
        loops = int(params.get("loops", 8))
        argv += ["-stream_loop", str(loops - 1)]
    argv += ["-i", a]
    if kind == "demo":
        argv += ["-i", b, "-i", logo]
    elif kind == "final":
        argv += ["-i", b, "-i", a]
    argv += [
        "-filter_complex", filt,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        "{OUT}",
    ]
    return argv, duration, filt


# ---------------------------------------------------------------- worker (1 job concurrente)

class Worker(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True, name="render-worker")
        self.stop_flag = False
        self.current: str | None = None

    # -- cola
    def claim(self) -> dict | None:
        with _db_lock:
            con = db()
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                con.commit()
                return None
            con.execute(
                "UPDATE jobs SET state='running', started_at=?, progress=0, stage='starting' WHERE id=?",
                (time.time(), row["id"]),
            )
            con.commit()
        d = dict(row)
        d["state"] = "running"
        return d

    def run(self) -> None:
        while not self.stop_flag:
            job = self.claim()
            if not job:
                time.sleep(0.2)
                continue
            self.current = job["id"]
            try:
                self.execute(job)
            except Exception as exc:  # noqa: BLE001
                x(
                    "UPDATE jobs SET state='failed', finished_at=?, error=? WHERE id=?",
                    (time.time(), f"worker crash: {exc!r}", job["id"]),
                )
                event(job["id"], "worker_crash", traceback.format_exc()[-2000:])
            finally:
                self.current = None

    # -- ejecución
    def execute(self, job: dict) -> None:
        jid = job["id"]
        row = q("SELECT * FROM jobs WHERE id=?", (jid,))[0]
        full = dict(row)
        # los parámetros reales viven en cmd como JSON hasta que se construye el argv
        try:
            params = json.loads(full.get("cmd") or "{}")
        except Exception:  # noqa: BLE001
            params = {}
        kind = full["kind"]

        staging_dir = STAGING / jid
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)
        out_tmp = staging_dir / "out.mp4"

        argv, duration, _ = build_job(kind, params)
        argv = [a.replace("{OUT}", str(out_tmp).replace("\\", "/")) for a in argv]
        x("UPDATE jobs SET cmd=?, stage='launching' WHERE id=?", (" ".join(argv), jid))
        event(jid, "launch", " ".join(argv))

        # ¿cancelado antes de arrancar?
        if q("SELECT cancel_requested FROM jobs WHERE id=?", (jid,))[0][0]:
            x("UPDATE jobs SET state='cancelled', finished_at=? WHERE id=?", (time.time(), jid))
            event(jid, "cancelled_before_start")
            shutil.rmtree(staging_dir, ignore_errors=True)
            return

        stderr_path = LOGS / f"{jid}.ffmpeg.log"
        started = time.monotonic()
        with open(stderr_path, "wb") as errf:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=errf,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            )
        x("UPDATE jobs SET pid=?, stage='encoding' WHERE id=?", (proc.pid, jid))
        event(jid, "pid", str(proc.pid))

        # lector de -progress pipe:1
        progress_state = {"pct": 0.0, "fps": 0.0, "speed": 0.0, "last_write": 0.0}

        def read_progress() -> None:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k == "out_time_us" and v.isdigit():
                    pct = min(99.9, (int(v) / 1e6) / duration * 100.0) if duration else 0.0
                    progress_state["pct"] = pct
                elif k == "fps":
                    try:
                        progress_state["fps"] = float(v)
                    except ValueError:
                        pass
                elif k == "speed":
                    try:
                        progress_state["speed"] = float(v.rstrip("x"))
                    except ValueError:
                        pass
                now = time.time()
                if now - progress_state["last_write"] > 0.25:
                    progress_state["last_write"] = now
                    x(
                        "UPDATE jobs SET progress=?, fps=?, speed=? WHERE id=?",
                        (progress_state["pct"], progress_state["fps"], progress_state["speed"], jid),
                    )
                if k == "progress" and v == "end":
                    break

        # muestreo RSS / CPU (100 ms)
        sample_state = {"peak_kb": 0, "cpu": 0.0}

        def sampler() -> None:
            while proc.poll() is None:
                s = sample_proc(proc.pid)
                if s:
                    ws, cpu = s
                    if ws // 1024 > sample_state["peak_kb"]:
                        sample_state["peak_kb"] = ws // 1024
                    sample_state["cpu"] = cpu
                time.sleep(0.1)

        t_prog = threading.Thread(target=read_progress, daemon=True)
        t_samp = threading.Thread(target=sampler, daemon=True)
        t_prog.start()
        t_samp.start()

        # cancelación asíncrona: el endpoint mata el árbol; aquí solo esperamos
        while proc.poll() is None:
            req = q("SELECT cancel_requested FROM jobs WHERE id=?", (jid,))[0][0]
            if req:
                x("UPDATE jobs SET stage='cancelling' WHERE id=?", (jid,))
                event(jid, "cancel_requested")
                kill_tree(proc.pid)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    event(jid, "cancel_wait_timeout")
                break
            time.sleep(0.15)

        exit_code = proc.wait()
        wall = time.monotonic() - started
        t_prog.join(timeout=2)
        t_samp.join(timeout=2)

        err_txt = ""
        try:
            err_txt = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        except OSError:
            pass
        bench = re.findall(r"bench: utime=([\d.]+)s stime=([\d.]+)s", err_txt)
        maxrss = re.findall(r"bench: maxrss=(\d+)KiB", err_txt)
        cpu_from_bench = (float(bench[-1][0]) + float(bench[-1][1])) if bench else None
        cpu = cpu_from_bench if cpu_from_bench is not None else sample_state["cpu"]

        cancelled = bool(q("SELECT cancel_requested FROM jobs WHERE id=?", (jid,))[0][0])
        state = "cancelled" if cancelled else ("succeeded" if exit_code == 0 else "failed")
        out_path = None
        out_bytes = None

        if state == "succeeded":
            # verificación real del artefacto antes del rename atómico
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                 "-show_entries", "stream=codec_name", "-of", "json", str(out_tmp)],
                capture_output=True, text=True,
            )
            ok = False
            info = {}
            try:
                info = json.loads(probe.stdout or "{}")
                ok = float(info.get("format", {}).get("duration", 0)) > 0.5 and len(info.get("streams", [])) >= 2
            except Exception:  # noqa: BLE001
                ok = False
            if ok and out_tmp.exists():
                final = OUT / f"{jid}.mp4"
                os.replace(out_tmp, final)  # atómico en el mismo volumen
                out_path = str(final)
                out_bytes = final.stat().st_size
                event(jid, "artifact", f"{out_path} bytes={out_bytes} probe={json.dumps(info)[:300]}")
            else:
                state = "failed"
                event(jid, "verify_failed", (probe.stdout or probe.stderr or "")[:1500])

        if state != "succeeded":
            shutil.rmtree(staging_dir, ignore_errors=True)
            event(jid, "staging_removed", str(staging_dir))

        x(
            """UPDATE jobs SET state=?, finished_at=?, wall_s=?, cpu_s=?, rss_peak_kb=?,
               ffmpeg_maxrss_kb=?, exit_code=?, out_path=?, out_bytes=?, error=?, stage='done',
               progress=CASE WHEN ?='succeeded' THEN 100 ELSE progress END
               WHERE id=?""",
            (
                state,
                time.time(),
                wall,
                cpu,
                sample_state["peak_kb"],
                int(maxrss[-1]) if maxrss else None,
                exit_code,
                out_path,
                out_bytes,
                None if state == "succeeded" else (err_txt[-1500:] if not cancelled else "cancelled"),
                state,
                jid,
            ),
        )
        event(jid, "finished", f"state={state} exit={exit_code} wall={wall:.2f}s cpu={cpu:.2f}s peak_rss={sample_state['peak_kb']}KiB")


WORKER = Worker()


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = f"editor-video-spike/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # log a archivo, no a stderr
        try:
            with open(LOGS / "service.access.log", "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.address_string()} {fmt % args}\n")
        except OSError:
            pass

    # -- CORS (file:// -> Origin: null)
    def _cors(self) -> None:
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            return {}

    # -- rutas
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/health":
                running = q("SELECT id FROM jobs WHERE state='running'")
                queued = q("SELECT id FROM jobs WHERE state='queued'")
                return self._json(200, {
                    "ok": True,
                    "service": "editor-video-spike",
                    "version": VERSION,
                    "pid": os.getpid(),
                    "ffmpeg": ffmpeg_available(),
                    "db": str(DB_PATH),
                    "worker": {"running": running[0]["id"] if running else None, "queued": len(queued)},
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                })
            if path == "/jobs":
                rows = [dict(r) for r in q("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 25")]
                return self._json(200, {"jobs": rows})
            if path.startswith("/jobs/"):
                jid = path.split("/")[2]
                row = job_row(jid)
                if not row:
                    return self._json(404, {"error": "job not found", "id": jid})
                return self._json(200, row)
            if path == "/probe":
                rows = [dict(r) for r in q("SELECT * FROM plugin_probes ORDER BY id")]
                return self._json(200, {"probes": rows})
            if path.startswith("/out/"):
                return self._serve_file(unquote(path[len("/out/"):]))
            if path.startswith("/media/"):
                return self._serve_media(unquote(path[len("/media/"):]))
            if path == "/assets":
                return self._json(200, {"assets": list(_assets().values())})
            return self._json(404, {"error": "not found", "path": path})
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"error": repr(exc), "trace": traceback.format_exc()[-1200:]})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/probe":
                data = self._read_json()
                x(
                    "INSERT INTO plugin_probes(ts, stage, detail, origin, user_agent, referer) VALUES (?,?,?,?,?,?)",
                    (
                        time.time(),
                        str(data.get("stage", ""))[:200],
                        json.dumps({k: v for k, v in data.items() if k != "stage"}, ensure_ascii=False)[:4000],
                        self.headers.get("Origin"),
                        (self.headers.get("User-Agent") or "")[:400],
                        (self.headers.get("Referer") or "")[:400],
                    ),
                )
                return self._json(200, {"ok": True, "recorded": len(q("SELECT id FROM plugin_probes"))})
            if path == "/assets":
                data = self._read_json()
                folder = str(data.get("folder") or "").strip()
                rel = str(data.get("rel") or "").strip()
                if not folder or not rel:
                    return self._json(400, {"error": "faltan 'folder' y 'rel'"})
                try:
                    asset = register_asset(folder, rel)
                except PermissionError as exc:
                    return self._json(403, {"error": "outside-folder", "message": str(exc)})
                except FileNotFoundError as exc:
                    return self._json(404, {"error": "not-found", "message": str(exc)})
                except ValueError as exc:
                    return self._json(400, {"error": "invalid-path", "message": str(exc)})
                return self._json(201, {
                    "ok": True,
                    "asset": asset,
                    "url": f"/media/{asset['id']}",
                })
            if path == "/jobs":
                data = self._read_json()
                kind = str(data.get("kind", "demo"))
                if kind not in ("demo", "long", "final"):
                    return self._json(400, {"error": f"kind inválido: {kind}"})
                params = {k: data[k] for k in ("preset", "crf", "width", "height", "loops") if k in data}
                dedupe = data.get("dedupe_key")
                if dedupe:
                    existing = q(
                        "SELECT id, state FROM jobs WHERE dedupe_key=? AND state IN ('queued','running')",
                        (str(dedupe),),
                    )
                    if existing:
                        return self._json(200, {
                            "id": existing[0]["id"],
                            "state": existing[0]["state"],
                            "deduplicated": True,
                        })
                jid = "j" + uuid.uuid4().hex[:10]
                x(
                    """INSERT INTO jobs(id, kind, label, dedupe_key, state, created_at, progress, cmd, stage)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        jid,
                        kind,
                        str(data.get("label", ""))[:200],
                        str(dedupe) if dedupe else None,
                        "queued",
                        time.time(),
                        0.0,
                        json.dumps(params),
                        "queued",
                    ),
                )
                event(jid, "queued", f"kind={kind} params={params}")
                pos = len(q("SELECT id FROM jobs WHERE state='queued'"))
                return self._json(202, {"id": jid, "state": "queued", "position": pos})
            if path.startswith("/jobs/") and path.endswith("/cancel"):
                jid = path.split("/")[2]
                row = q("SELECT * FROM jobs WHERE id=?", (jid,))
                if not row:
                    return self._json(404, {"error": "job not found", "id": jid})
                row = row[0]
                if row["state"] in ("succeeded", "failed", "cancelled", "interrupted"):
                    return self._json(409, {"error": f"job ya terminó: {row['state']}", "job": job_row(jid)})
                x("UPDATE jobs SET cancel_requested=1 WHERE id=?", (jid,))
                event(jid, "cancel_endpoint")
                killed = ""
                if row["pid"]:
                    killed = kill_tree(int(row["pid"]))
                    event(jid, "kill_tree", killed)
                return self._json(202, {"id": jid, "cancel_requested": True, "pid": row["pid"], "taskkill": killed})
            return self._json(404, {"error": "not found", "path": path})
        except Exception as exc:  # noqa: BLE001
            return self._json(500, {"error": repr(exc), "trace": traceback.format_exc()[-1200:]})

    # -- archivos con Range
    def _serve_file(self, name: str) -> None:
        safe = os.path.basename(name)
        path = OUT / safe
        if not path.exists() or not path.is_file():
            return self._json(404, {"error": "file not found", "name": safe})
        return self._serve_path(path, "video/mp4")

    def _serve_media(self, token: str) -> None:
        """Sirve un asset registrado, un fixture o un MP4 de out/ con soporte Range."""
        safe = os.path.basename(token)
        asset = _assets().get(safe)
        candidates: list[Path] = []
        if asset:
            candidates.append(Path(asset["path"]))
        candidates.append(FIXTURES / safe)
        candidates.append(OUT / f"{safe}.mp4")
        candidates.append(OUT / safe)
        for p in candidates:
            if p.exists() and p.is_file():
                ctype = "video/mp4" if p.suffix.lower() in (".mp4", ".m4v") else "application/octet-stream"
                return self._serve_path(p, ctype)
        return self._json(404, {"error": "media not found", "token": safe})

    def _serve_path(self, path: Path, ctype: str = "application/octet-stream") -> None:
        size = path.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng and rng.startswith("bytes="):
            spec = rng[len("bytes="):].split(",")[0]
            a, _, b = spec.partition("-")
            if a.isdigit():
                start = int(a)
            if b.isdigit():
                end = int(b)
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self._cors()
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self._cors()
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(262144, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


# ---------------------------------------------------------------- arranque / reaper

def reaper() -> list[str]:
    """Mata huérfanos de una ejecución anterior y marca jobs interrumpidos."""
    notes = []
    rows = q("SELECT id, pid FROM jobs WHERE state='running'")
    for r in rows:
        if r["pid"]:
            msg = kill_tree(int(r["pid"]))
            notes.append(f"killed orphan pid={r['pid']} job={r['id']}: {msg}")
        x(
            "UPDATE jobs SET state='interrupted', finished_at=?, error='service restarted while running', stage='done' WHERE id=?",
            (time.time(), r["id"]),
        )
        event(r["id"], "interrupted_on_startup")
    for r in q("SELECT id FROM jobs WHERE state='queued'"):
        x("UPDATE jobs SET state='interrupted', finished_at=?, error='queued at restart' WHERE id=?", (time.time(), r["id"]))
        event(r["id"], "queued_dropped_on_startup")
    if rows:
        with open(LOGS / "service.reaper.log", "a", encoding="utf-8") as fh:
            for n in notes:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {n}\n")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-worker", action="store_true", help="solo HTTP (no procesa cola)")
    args = ap.parse_args()

    for d in (FIXTURES, OUT, STAGING, LOGS, WORK):
        d.mkdir(parents=True, exist_ok=True)

    db()
    notes = reaper()
    if notes:
        print("[reaper]", *notes, sep="\n  ")

    if not args.no_worker:
        WORKER.start()

    httpd = ThreadingHTTPServer((HOST, args.port), Handler)
    httpd.daemon_threads = True
    print(f"[editor-video-spike] listening on http://{HOST}:{args.port} pid={os.getpid()} db={DB_PATH}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[editor-video-spike] closing")
    finally:
        WORKER.stop_flag = True
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
