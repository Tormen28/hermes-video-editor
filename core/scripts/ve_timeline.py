"""Hermes-side tool: read and edit a video project BY TIME, in the same document the pane shows.

  ve_timeline.py ensure                              # arranca el servicio si no responde
  ve_timeline.py projects                            # lista de proyectos
  ve_timeline.py show  <project> [--json]            # línea de tiempo con tiempos absolutos
  ve_timeline.py at    <project> 3:13                # qué hay en ese instante
  ve_timeline.py edit  <project> --ops '[{"op":"set_text","time":"3:13","content":"Hola"}]'
  ve_timeline.py edit  <project> --ops-file ops.json
  ve_timeline.py text  <project> 3:13 "Nuevo texto"  # atajo de set_text por tiempo
  ve_timeline.py mute  <project> 3:13                # silencia la escena en ese instante
  ve_timeline.py volume <project> 3:13 40            # volumen de la escena (0-100)
  ve_timeline.py export <project> [--preset mp4-720p30]

Ops (ver core/CONTRATO.md §9): set_text, trim, split, delete_scene, move_scene, set_transition,
set_speed, set_volume, add_audio, move_audio, set_audio, remove_audio, set_music, remove_music,
insert_media, set_title. Tiempos: 83.5 | 1:23.5 | 01:23.500.

La edición se aplica sobre la revisión ACTUAL (si el usuario guardó a mano mientras tanto, se
respeta). El pane abierto la recoge sola en ~1 s. Nunca imprime el token.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import ve_client as vc

CORE = Path(__file__).resolve().parent.parent


def fail(message: str, code: int = 1) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return code


def need(status: int, body: dict) -> dict | None:
    if status >= 400:
        print(f"ERROR {status}: {body.get('error') or body}", file=sys.stderr)
        if status in (401, 403):
            print("  (token: ejecuta instalar.py / activar-editor.cmd y reintenta)", file=sys.stderr)
        return None
    return body


def render(tl: dict) -> str:
    out = [f"{tl.get('title')}  ·  rev {tl.get('revision')}  ·  dura {tl.get('durationTc')}  ·  {tl.get('width')}x{tl.get('height')}"]
    for s in tl["scenes"]:
        out.append(
            f"  [{s['number']}] {s['startTc']} → {s['endTc']}  {s.get('name') or s['id']}"
            f"  ({s.get('kind')}, vol {s.get('volume')}%, trans {s.get('transition')}, vel {s.get('speed')}x)  id={s['id']}"
        )
        for t in s["text"]:
            out.append(f"        texto[{t['index']}] «{t['content']}»  {vc_tc(t['from'])} → {vc_tc(t['to'])}")
    for e in tl["audioEvents"]:
        out.append(f"  ♪ {e['atTc']}  {e['id']}  vol {e['volume']}%  {e.get('path')}")
    if tl.get("music"):
        out.append(f"  ♫ música {tl['music']}")
    out.append(f"  volumen general {tl.get('masterVolume')}%")
    return "\n".join(out)


def vc_tc(seconds: float) -> str:
    total = int(round(seconds * 1000))
    return f"{total // 60000:02d}:{(total % 60000) // 1000:02d}.{total % 1000:03d}"


def run_ops(base: str, project: str, ops: list) -> int:
    body = need(*vc.call(base, "POST", f"/projects/{project}/edit", {"ops": ops}))
    if body is None:
        return 1
    for line in body["applied"]:
        print("✓", line)
    print(f"revisión {body['baseRevision']} → {body['revision']}  ·  dura {body['timeline']['durationTc']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=vc.DEFAULT_BASE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ensure")
    sub.add_parser("projects")
    p = sub.add_parser("show"); p.add_argument("project"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("at"); p.add_argument("project"); p.add_argument("time")
    p = sub.add_parser("edit"); p.add_argument("project"); p.add_argument("--ops"); p.add_argument("--ops-file")
    p = sub.add_parser("text"); p.add_argument("project"); p.add_argument("time"); p.add_argument("content")
    p = sub.add_parser("mute"); p.add_argument("project"); p.add_argument("time")
    p = sub.add_parser("volume"); p.add_argument("project"); p.add_argument("time"); p.add_argument("volume", type=int)
    p = sub.add_parser("export"); p.add_argument("project"); p.add_argument("--preset", default="mp4-720p30"); p.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()

    if a.cmd == "ensure":
        port = a.base.rsplit(":", 1)[-1].strip("/")
        cmd = [sys.executable, str(CORE / "start_service.py"), "--ensure", "--port", port]
        config = Path.home() / "AppData" / "Local" / "hermes" / "video-editor" / "config.json"
        if config.is_file():
            cmd = [sys.executable, str(CORE / "start_service.py"), "--ensure", "--config", str(config)]
        return subprocess.run(cmd).returncode

    if a.cmd == "projects":
        body = need(*vc.call(a.base, "GET", "/projects"))
        if body is None:
            return 1
        for item in body.get("projects", body if isinstance(body, list) else []):
            print(item.get("projectId") or item.get("project_id"), "·", item.get("title"), "· rev", item.get("revision"))
        return 0

    if a.cmd == "show":
        body = need(*vc.call(a.base, "GET", f"/projects/{a.project}/timeline"))
        if body is None:
            return 1
        print(json.dumps(body, ensure_ascii=False, indent=2) if a.json else render(body))
        return 0

    if a.cmd == "at":
        body = need(*vc.call(a.base, "GET", f"/projects/{a.project}/at?t={a.time}"))
        if body is None:
            return 1
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0

    if a.cmd == "edit":
        raw = a.ops
        if a.ops_file:
            raw = Path(a.ops_file).read_text(encoding="utf-8")
        if not raw:
            return fail("falta --ops o --ops-file")
        try:
            ops = json.loads(raw)
        except ValueError as exc:
            return fail(f"JSON inválido: {exc}")
        return run_ops(a.base, a.project, ops if isinstance(ops, list) else [ops])

    if a.cmd == "text":
        return run_ops(a.base, a.project, [{"op": "set_text", "time": a.time, "content": a.content}])
    if a.cmd == "mute":
        return run_ops(a.base, a.project, [{"op": "set_volume", "target": "scene", "time": a.time, "mute": True}])
    if a.cmd == "volume":
        return run_ops(a.base, a.project, [{"op": "set_volume", "target": "scene", "time": a.time, "volume": a.volume}])

    if a.cmd == "export":
        body = need(*vc.call(a.base, "POST", f"/projects/{a.project}/export", {"preset": a.preset}))
        if body is None:
            return 1
        job_id = body.get("jobId") or body.get("job", {}).get("jobId") or body.get("id")
        job = vc.wait_job(a.base, job_id, a.timeout)
        print(json.dumps(job, ensure_ascii=False, indent=2))
        return 0 if job.get("state") == "succeeded" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())