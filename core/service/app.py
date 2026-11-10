"""HTTP surface + single-job runner for the video editor service.

Design rules that come straight from the approved plan:

* **Loopback only.** The socket binds 127.0.0.1. ``Host`` and ``Origin`` are
  checked on every request so a random web page cannot drive the service
  (DNS-rebinding / CSRF), which matters because there is no network auth.
* **One render at a time.** The runner thread takes jobs from our own SQLite
  journal; HTTP threads never touch ffmpeg, so the gateway keeps answering.
* **The queue outlives the process.** Jobs live in the journal, not in memory.
  A restart marks in-flight jobs ``interrupted`` instead of losing them, and the
  Windows Job Object guarantees the child ffmpeg dies with the service, so no
  orphan survives a crash.
* **Same document for preview and export.** Export snapshots the stored
  document; it never re-reads a client draft.

Endpoints follow ``docs/ui-spec.md`` §6.3. Errors are JSON with an ``error``
string; 409 carries ``current_revision`` for the conflict dialog.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
from array import array
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

if __package__ in (None, ""):  # allow `python core/service/app.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paths as path_rules  # noqa: E402
import project  # noqa: E402
from service import auth  # noqa: E402
from service import generate as generation  # noqa: E402
from service import journal as journal_module  # noqa: E402
from service import timeline_ops  # noqa: E402
from service import worker  # noqa: E402

SERVICE_VERSION = "0.3.4"
MAX_BODY_BYTES = 4 * 1024 * 1024
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".flac", ".opus"}
ALLOWED_PRESETS = tuple(worker.PRESETS)
EXPERIMENTAL_PRESETS = tuple(name for name, spec in worker.PRESETS.items() if spec.experimental)
DEFAULT_PRESET = worker.DEFAULT_PRESET
DEFAULT_QUEUE_POLL_S = 0.15
CREATE_NO_WINDOW = 0x08000000
THUMB_WIDTH = 320
THUMB_TIMEOUT_S = 60.0
WAVEFORM_BUCKETS = 200
WAVEFORM_RATE = 8000  # Hz, mono s16le: 16 KB per second of audio
WAVEFORM_TIMEOUT_S = 300.0
EXPORT_HISTORY_LIMIT = 20
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TRUTHY = {"1", "true", "yes", "si", "sí", "y", "on"}


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #


class HttpError(Exception):
    """Anything the HTTP layer must turn into a JSON error response."""

    def __init__(self, status: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


def _bad_request(message: str, **extra: Any) -> HttpError:
    return HttpError(400, message, **extra)


def _as_bool(value: Any) -> bool:
    """Accept the shapes a hand-written client actually sends for a flag."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    return False


def _first(query: dict, name: str) -> str | None:
    values = query.get(name) or []
    return values[0] if values else None


def _confirmed(body: dict | None, query: dict | None) -> bool:
    if _as_bool(_first(query or {}, "confirm")):
        return True
    return _as_bool((body or {}).get("confirm"))


def _int_param(value: Any, name: str, *, default: int, low: int, high: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise _bad_request(f"{name} debe ser un entero") from exc
    if not low <= parsed <= high:
        raise _bad_request(f"{name} debe estar entre {low} y {high}")
    return parsed


def _float_param(value: Any, name: str, *, default: float, low: float, high: float) -> float:
    if value is None or value == "":
        return default
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise _bad_request(f"{name} debe ser un número") from exc
    if parsed != parsed or not low <= parsed <= high:  # NaN fails both comparisons
        raise _bad_request(f"{name} debe estar entre {low} y {high}")
    return parsed


def _revision_param(body: dict, query: dict, *, default: int) -> int:
    """The revision the client believes it is editing (optimistic concurrency)."""
    for value in (body.get("revision"), _first(query, "revision")):
        if value is None or value == "":
            continue
        try:
            return int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise _bad_request("revision debe ser un entero") from exc
    return int(default)


# --------------------------------------------------------------------------- #
# service
# --------------------------------------------------------------------------- #


@dataclass
class ServiceConfig:
    data_root: Path
    media_root: Path
    tools_root: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8765
    allow_admin: bool = True
    extra_origins: tuple[str, ...] = ()
    #: Shared secret required in ``X-VE-Token``. ``None`` disables the check
    #: (library/tests only: ``main()`` always sets one unless ``--no-token``).
    token: str | None = None


class Service:
    """Owns the journal, the layout and the render loop."""

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        self.data_root = Path(config.data_root).resolve()
        self.media_root = Path(config.media_root).resolve()
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.layout = worker.Layout(self.data_root, self.media_root).ensure()
        #: Derived media lives here (thumbnails, waveforms); safe to wipe at any time.
        self.cache_root = self.data_root / "cache"
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.tools = worker.resolve_tools(config.tools_root) if config.tools_root else worker.resolve_tools(
            _default_tools_root()
        )
        self.journal = journal_module.Journal(self.data_root / "service.sqlite3")
        self.recovered: list[dict] = []
        self._stop = threading.Event()
        self._runner: threading.Thread | None = None
        self._generator: threading.Thread | None = None
        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self.started_at = project.now_iso()
        self.current_job_id: str | None = None
        self._recover()

    # -- lifecycle ------------------------------------------------------- #

    def _recover(self) -> None:
        """Close jobs left mid-flight, then say so in the event stream.

        No PID sweeping is needed: the render child is assigned to a Windows Job
        Object with KILL_ON_JOB_CLOSE, so a dead service cannot leave ffmpeg
        running behind it.
        """
        self.recovered = self.journal.reap_interrupted()
        if self.recovered:
            self.journal.add_event(
                None, state="recovered", message=f"{len(self.recovered)} trabajo(s) interrumpido(s)"
            )

    def start(self, *, run_worker: bool = True) -> "Service":
        if run_worker:
            self._runner = threading.Thread(target=self._loop, name="video-runner", daemon=True)
            self._runner.start()
            self._generator = threading.Thread(target=self._generation_loop, name="video-generator", daemon=True)
            self._generator.start()
        self._httpd = ThreadingHTTPServer((self.config.host, int(self.config.port)), self._handler_factory())
        self._httpd.daemon_threads = True
        self._http_thread = threading.Thread(target=self._httpd.serve_forever, name="video-http", daemon=True)
        self._http_thread.start()
        return self

    @property
    def stopped(self) -> threading.Event:
        """Evento que se activa al llamar a stop(); main() lo espera para salir."""
        return self._stop

    def stop(self) -> None:
        self._stop.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._runner is not None:
            self._runner.join(timeout=15)
            self._runner = None
        if self._generator is not None:
            self._generator.join(timeout=15)
            self._generator = None
        self.journal.close()

    @property
    def port(self) -> int:
        if self._httpd is None:
            return int(self.config.port or 0)
        return int(self._httpd.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{self.config.host}:{self.port}"

    # -- render loop ----------------------------------------------------- #

    def _loop(self) -> None:
        while not self._stop.is_set():
            job = self.journal.next_queued_job()
            if job is None:
                self._stop.wait(DEFAULT_QUEUE_POLL_S)
                continue
            if not self.journal.claim_job(job["jobId"]):
                continue
            self._execute(job)

    def _execute(self, job: dict) -> None:
        job_id = job["jobId"]
        self.current_job_id = job_id
        try:
            snapshot = project.load(job["snapshotPath"])
        except Exception as exc:  # the snapshot is ours; a failure here is a bug, not user input
            self.journal.finish_job(job_id, "failed", error=f"snapshot ilegible: {type(exc).__name__}")
            worker.purge_derivatives(self.layout, job_id)
            self.current_job_id = None
            return

        self.journal.set_worker_pid(job_id, os.getpid())

        def progress(stage: str, pct: float, eta: float | None) -> None:
            self.journal.update_progress(job_id, stage=stage, progress=pct, eta_s=eta)

        try:
            result = worker.run_job(
                snapshot,
                job_id=job_id,
                layout=self.layout,
                tools=self.tools,
                preset=job.get("preset") or DEFAULT_PRESET,
                captions=bool(job.get("captions", True)),
                should_cancel=lambda: self.journal.cancel_requested(job_id),
                progress_cb=progress,
                verify_hash=True,
            )
        except Exception as exc:  # never leave a job running forever
            traceback.print_exc()
            self.journal.finish_job(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
            worker.purge_derivatives(self.layout, job_id)
            self.current_job_id = None
            return

        if result.state != "succeeded":
            worker.purge_derivatives(self.layout, job_id)
        self.journal.finish_job(
            job_id,
            result.state,
            error=result.error,
            exit_code=result.exit_code,
            output_name=result.output_name,
            artifacts=result.artifacts,
            message=None,
        )
        self.current_job_id = None
        try:
            self.journal.prune_events(keep=5000)
        except Exception:
            pass

    def stats(self) -> dict:
        jobs = self.journal.list_jobs(limit=200)
        queued = sum(1 for job in jobs if job["state"] == "queued")
        running = sum(1 for job in jobs if job["state"] == "running")
        return {"queued": queued, "running": running, "current": self.current_job_id}

    # -- domain operations (used by the HTTP layer) ----------------------- #

    def create_project(self, body: dict) -> dict:
        title = _text(body.get("title"), "title", required=False, default="Proyecto sin título", limit=200)
        project_id = "prj_" + secrets.token_hex(8)
        doc = project.new_project(
            project_id,
            title,
            session_id=_optional_text(body.get("session_id"), 120),
            cwd=_optional_text(body.get("cwd"), 500),
        )
        stored = self.journal.create_project(doc)
        return self._project_payload(stored)

    def project_payload(self, project_id: str) -> dict:
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        return self._project_payload(stored)

    def _project_payload(self, stored: dict) -> dict:
        doc = stored["document"]
        return {
            "projectId": doc["projectId"],
            "revision": doc["revision"],
            "docHash": stored.get("docHash"),
            "updatedAt": doc.get("updatedAt"),
            "project": doc,
            "ui": project.to_ui_document(doc),
            "media": [
                {
                    "id": asset["id"],
                    "path": asset["path"],
                    "kind": asset["kind"],
                    "bytes": asset.get("bytes"),
                    "sha256": asset.get("sha256"),
                    "exists": self._asset_exists(asset),
                    "previewUrl": f"/media/{doc['projectId']}/{asset['id']}",
                }
                for asset in doc.get("assets") or []
            ],
        }

    def _asset_exists(self, asset: dict) -> bool:
        try:
            return worker.verify_media_file(self.media_root, asset["path"]).is_file()
        except Exception:
            return False

    def save_project(self, project_id: str, body: dict) -> dict:
        if "draft" not in body and "project" not in body:
            raise _bad_request("falta 'draft' o 'project' en el cuerpo")
        base_revision = body.get("revision", body.get("baseRevision"))
        if base_revision is None:
            raise _bad_request("falta 'revision' (control de concurrencia)")
        draft = body.get("draft", body.get("project"))
        try:
            document = project.from_ui_document(draft) if _looks_like_ui_document(draft) else project.normalize_incoming(draft)
            stored = self.journal.save_project(project_id, document, base_revision)
        except project.RevisionConflict as exc:
            current = self.journal.get_project(project_id)
            raise HttpError(409, "hay una revisión más nueva", current_revision=(current or {}).get("revision")) from exc
        return self._project_payload(stored)

    # -- timeline by time (chat <-> pane) ---------------------------------- #

    _DURATION_CACHE: dict[str, float | None] = {}

    def _asset_seconds(self, asset: dict) -> float | None:
        """Length of an audio/video asset (cached by content hash); None if unknown."""
        key = asset.get("sha256") or asset.get("path")
        if key in self._DURATION_CACHE:
            return self._DURATION_CACHE[key]
        value = None
        try:
            path = worker.verify_media_file(self.media_root, asset["path"])
            value = round(float(worker.probe_media(path, self.tools).get("duration") or 0.0), 3) or None
        except Exception:
            value = None
        self._DURATION_CACHE[key] = value
        return value

    def timeline(self, project_id: str) -> dict:
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        return timeline_ops.describe(stored["document"], self._asset_seconds)

    def items_at(self, project_id: str, time_value: Any) -> dict:
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        try:
            t = timeline_ops.parse_time(time_value)
        except timeline_ops.OpError as exc:
            raise _bad_request(str(exc)) from None
        return timeline_ops.items_at(stored["document"], t, self._asset_seconds)

    def edit(self, project_id: str, body: dict) -> dict:
        """Apply a list of timestamp ops to the CURRENT revision, atomically.

        The write is revision-checked: if the pane saved in between we re-read and
        re-apply (up to 5 times), so neither side overwrites the other. Pass
        ``strict: true`` with ``revision`` to get a 409 instead of a rebase.
        """
        if self.journal.get_project(project_id) is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        ops = list(body.get("ops") or [])
        # insert_media: import the file first (adds it as the last scene), then move it.
        expanded: list[dict] = []
        imported = False
        for op in ops:
            if isinstance(op, dict) and op.get("op") == "insert_media":
                before = len((self.journal.get_project(project_id)["document"]).get("scenes") or [])
                result = self.add_media(project_id, {"path": op.get("path")})
                imported = True
                scenes_now = result["project"]["scenes"]
                if len(scenes_now) == before:  # audio file: no scene, place it as a sound event
                    relative, _resolved = self._resolve_media_reference(op.get("path"))
                    asset = next(a for a in result["project"]["assets"] if a.get("path") == relative)
                    expanded.append({"op": "add_audio", "assetId": asset["id"], "at": op.get("at", 0),
                                     "volume": op.get("volume", 80)})
                    continue
                last = len(scenes_now)
                if op.get("duration") is not None:
                    expanded.append({"op": "trim", "scene": last, "duration": op["duration"]})
                if op.get("at") is not None or op.get("to_index") is not None:
                    move = {"op": "move_scene", "scene": last}
                    if op.get("to_index") is not None:
                        move["to_index"] = op["to_index"]
                    else:
                        move["to_time"] = op["at"]
                    expanded.append(move)
            else:
                expanded.append(op)
        if not expanded:
            if not imported:
                raise _bad_request("'ops' debe ser una lista con al menos una operación")
            return {"revision": self.journal.get_project(project_id)["document"]["revision"],
                    "applied": ["medio importado al final"], "timeline": self.timeline(project_id)}
        for _attempt in range(5):
            stored = self.journal.get_project(project_id)
            doc = stored["document"]
            if body.get("strict") and body.get("revision") not in (None, doc["revision"]):
                raise HttpError(409, "hay una revisión más nueva", current_revision=doc["revision"])
            try:
                new_doc, summary = timeline_ops.apply_ops(doc, expanded)
            except timeline_ops.OpError as exc:
                raise _bad_request(str(exc)) from None
            try:
                document = project.normalize_incoming(new_doc)
                saved = self.journal.save_project(project_id, document, doc["revision"])
            except project.RevisionConflict:
                continue
            return {
                "revision": saved["document"]["revision"],
                "baseRevision": doc["revision"],
                "applied": summary,
                "timeline": timeline_ops.describe(saved["document"], self._asset_seconds),
            }
        raise HttpError(409, "el proyecto cambia sin parar; reintenta", current_revision=None)

    # -- library (v3) ----------------------------------------------------- #

    def delete_project(self, project_id: str, *, confirm: bool) -> dict:
        """Delete a project, its journal rows and everything derived from it."""
        if not confirm:
            raise _bad_request(
                "borrar un proyecto exige confirmación explícita (?confirm=1 o {\"confirm\": true})"
            )
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        jobs = self.journal.list_jobs_for_project(project_id, limit=200)
        if any(job["state"] == "running" for job in jobs):
            raise HttpError(409, "hay un export en curso; cancélalo antes de borrar el proyecto")

        removed = self.journal.delete_project(project_id) or {"projectId": project_id, "jobIds": []}
        purged = self._purge_project_files(stored["document"], removed["jobIds"])
        self.journal.add_event(None, state="deleted", message=f"proyecto borrado: {project_id}")
        return {
            "deleted": True,
            "projectId": project_id,
            "jobsDeleted": len(removed["jobIds"]),
            "filesPurged": purged,
        }

    def duplicate_project(self, project_id: str) -> dict:
        """Copy a project into a brand-new id at revision 0 (assets and scenes copied)."""
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        new_id = ""
        for _ in range(5):
            candidate = "prj_" + secrets.token_hex(8)
            if self.journal.get_project(candidate) is None:
                new_id = candidate
                break
        if not new_id:  # pragma: no cover - 2**64 collisions are not a real scenario
            raise HttpError(500, "no se pudo reservar un identificador para la copia")
        document = project.clone_document(stored["document"], new_id)
        created = self.journal.create_project(document)
        self.journal.add_event(None, state="duplicated", message=f"{project_id} → {new_id}")
        return self._project_payload(created)

    def add_media(self, project_id: str, body: dict) -> dict:
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        doc = stored["document"]

        raw_path = body.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            relative, resolved = self._resolve_media_reference(raw_path)
        else:
            raise _bad_request("falta 'path' (archivo dentro de la carpeta concedida)")

        digest = worker.sha256_file(resolved)
        info = worker.probe_media(resolved, self.tools)
        if not info.get("has_video") and not info.get("has_audio"):
            raise _bad_request(f"{relative}: no contiene vídeo ni audio")
        suffix = resolved.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            kind = "image"
        elif suffix in AUDIO_EXTENSIONS or (info.get("has_audio") and not info.get("has_video")):
            kind = "audio"
        else:
            kind = "video"
        duration = float(info.get("duration") or 0.0)

        existing = next((a for a in doc.get("assets") or [] if a.get("path") == relative), None)
        if existing is None:
            existing = {
                "id": "md_" + secrets.token_hex(4),
                "path": relative,
                "sha256": digest,
                "kind": kind,
                "bytes": resolved.stat().st_size,
                "rights": {"status": "unknown", "license": "", "notes": ""},
                "addedAt": project.now_iso(),
            }
            doc = dict(doc)
            doc["assets"] = list(doc.get("assets") or []) + [existing]
        elif existing.get("sha256") != digest:
            doc = dict(doc)
            doc["assets"] = [
                {**existing, "sha256": digest, "bytes": resolved.stat().st_size} if a.get("id") == existing["id"] else a
                for a in doc["assets"]
            ]
            existing = next(a for a in doc["assets"] if a.get("path") == relative)

        if body.get("scene", kind != "audio"):
            scene = _scene_from_asset(existing, kind, duration, doc)
            doc = dict(doc)
            doc["scenes"] = list(doc.get("scenes") or []) + [scene]

        stored = self.journal.save_project(project_id, doc, doc["revision"])
        return self._project_payload(stored)

    def _resolve_media_reference(self, value: str) -> tuple[str, Path]:
        candidate = Path(value)
        if candidate.is_absolute():
            if not path_rules.is_within(candidate, self.media_root):
                raise _bad_request("la ruta debe estar dentro de la carpeta concedida")
            relative = candidate.resolve().relative_to(self.media_root).as_posix()
        else:
            relative = value
        try:
            resolved = worker.verify_media_file(self.media_root, relative)
        except Exception as exc:
            raise _bad_request(str(exc)) from exc
        return relative, resolved

    def export(self, project_id: str, body: dict) -> dict:
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        doc = stored["document"]
        preset = body.get("preset") or DEFAULT_PRESET
        if preset not in ALLOWED_PRESETS:
            raise _bad_request(
                f"preset no soportado: {preset!r}; disponibles: {', '.join(ALLOWED_PRESETS)}"
            )
        captions = bool(body.get("captions", True))

        errors = project.validate_for_export(doc)
        if errors:
            raise _bad_request("el proyecto no está listo para exportar", errors=errors)

        dedupe = project.dedupe_key(doc, preset, captions=captions)
        found = self.journal.find_job_by_dedupe(dedupe)
        if found is not None and found["state"] in ("queued", "running", "succeeded"):
            return {"jobId": found["jobId"], "deduped": True, "state": found["state"]}

        job_id = "j" + secrets.token_hex(5)
        snapshot_path = self.layout.snapshot_path(job_id)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        project.save_atomic(snapshot_path, doc, backup=False)
        key = dedupe if found is None else f"{dedupe}#{job_id}"
        job, created = self.journal.create_job(
            job_id=job_id,
            project_id=project_id,
            project_revision=doc["revision"],
            engine_tag=doc.get("engineTag") or project.DEFAULT_ENGINE_TAG,
            preset=preset,
            captions=captions,
            dedupe_key=key,
            snapshot_path=str(snapshot_path),
            source="plugin",
        )
        return {"jobId": job["jobId"], "deduped": not created, "state": job["state"]}

    # -- generation loop (phase 3A) -------------------------------------- #

    def _generation_loop(self) -> None:
        """One generation at a time, outside every HTTP thread.

        Separate from :meth:`_loop` on purpose: a 60 s provider call must never
        delay a render, and a render must never block a generation.
        """
        while not self._stop.is_set():
            job = self.journal.next_queued_job(job_type="generate")
            if job is None:
                self._stop.wait(DEFAULT_QUEUE_POLL_S)
                continue
            if not self.journal.claim_job(job["jobId"], stage="generating"):
                continue
            self._execute_generation(job)

    def _execute_generation(self, job: dict) -> None:
        job_id = job["jobId"]
        project_id = job["projectId"]
        request = (job.get("generation") or {}).get("request") or {}
        job_dir = self.layout.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        def progress(stage: str, pct: float, message: str) -> None:
            self.journal.update_progress(job_id, stage=stage, progress=pct)
            self.journal.update_payload(job_id, {"lastMessage": message})

        try:
            if self.journal.cancel_requested(job_id):
                raise worker._Cancelled()
            stored = self.journal.get_project(project_id)
            if stored is None:
                raise generation.GenerationError(f"proyecto desconocido: {project_id}")
            result = generation.run(
                request,
                media_root=self.media_root,
                project_id=project_id,
                tools=self.tools,
                job_dir=job_dir,
                cancel=lambda: self.journal.cancel_requested(job_id),
                progress=progress,
            )
            if self.journal.cancel_requested(job_id):
                raise worker._Cancelled()
            asset = self._register_generated_asset(stored, request, result)
        except worker._Cancelled:
            self.journal.finish_job(job_id, "cancelled", message="generación cancelada")
            shutil.rmtree(job_dir, ignore_errors=True)
            return
        except Exception as exc:
            traceback.print_exc()
            self.journal.finish_job(job_id, "failed", error=f"{type(exc).__name__}: {exc}"[:500])
            shutil.rmtree(job_dir, ignore_errors=True)
            return
        self.journal.update_payload(
            job_id,
            {"assetId": asset["id"], "assetPath": asset["path"], "revision": asset.get("revision"), "result": result},
        )
        self.journal.finish_job(job_id, "succeeded", artifacts=[asset["path"]], message="asset generado")
        shutil.rmtree(job_dir, ignore_errors=True)

    def _register_generated_asset(self, stored: dict, request: dict, result: dict) -> dict:
        """Append the generated file to the project as a normal asset."""
        doc = json.loads(json.dumps(stored["document"]))
        stamp = project.now_iso()
        asset_id = "md_" + secrets.token_hex(4)
        note = (
            f"generado por {result['provider']} ({result['providerNote']}) el {stamp}; "
            f"prompt: {request['prompt']}"
        )[:500]
        asset = {
            "id": asset_id,
            "path": result["path"],
            "sha256": result["sha256"],
            "kind": "image" if request["kind"] == "image" else "audio",
            "bytes": result["bytes"],
            "rights": {"status": "generated", "license": "", "notes": note},
            "addedAt": stamp,
        }
        doc.setdefault("assets", []).append(asset)
        base_revision = int(doc.get("revision") or 0)
        doc["revision"] = base_revision + 1
        doc["updatedAt"] = stamp
        saved = self.journal.save_project(stored["projectId"], doc, base_revision)
        asset["revision"] = saved.get("revision")
        return asset

    def start_generation(self, project_id: str, body: dict) -> dict:
        """Queue a generation job and return at once; the loop does the work."""
        if self.journal.get_project(project_id) is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        try:
            request = generation.normalize_request(body)
        except generation.RequestError as exc:
            raise _bad_request(str(exc)) from None
        job_id = "g" + secrets.token_hex(5)
        job = self.journal.create_generation_job(
            job_id=job_id,
            project_id=project_id,
            project_revision=int(body.get("revision") or 0),
            kind=request["kind"],
            payload={"request": request},
            source="generate",
        )
        return {"jobId": job["jobId"], "type": "generate", "kind": request["kind"], "state": job["state"]}

    def job_payload(self, job_id: str) -> dict:
        job = self.journal.get_job(job_id)
        if job is None:
            raise HttpError(404, f"trabajo desconocido: {job_id}")
        payload = dict(job)
        if job.get("type") == "generate":
            result = payload.get("generation") or {}
            asset_id = result.get("assetId")
            payload["outputUrl"] = None
            payload["outputPath"] = None
            payload["assetId"] = asset_id
            payload["assetUrl"] = f"/media/{job['projectId']}/{asset_id}" if asset_id else None
            payload["assetPath"] = result.get("assetPath")
            return payload
        payload["outputUrl"] = f"/jobs/{job_id}/output" if job["state"] == "succeeded" else None
        payload["outputPath"] = str(self.layout.output_path(job_id, job["outputName"])) if job.get("outputName") else None
        if payload["outputPath"]:
            try:
                payload["outputBytes"] = Path(payload["outputPath"]).stat().st_size
            except OSError:
                payload["outputBytes"] = None
        return payload

    def cancel(self, job_id: str) -> dict:
        job = self.journal.request_cancel(job_id)
        if job is None:
            raise HttpError(404, f"trabajo desconocido: {job_id}")
        return job

    # -- media (v3) ------------------------------------------------------- #

    def _stored_asset(self, project_id: str, asset_id: str) -> tuple[dict, dict]:
        stored = self.journal.get_project(project_id)
        if stored is None:
            raise HttpError(404, f"proyecto desconocido: {project_id}")
        asset = next(
            (item for item in stored["document"].get("assets") or [] if item.get("id") == asset_id), None
        )
        if asset is None:
            raise HttpError(404, f"medio desconocido: {asset_id}")
        return stored, asset

    def _asset_path(self, asset: dict) -> Path:
        try:
            return worker.verify_media_file(self.media_root, asset["path"])
        except Exception:
            raise HttpError(410, f"el archivo ya no está: {asset['path']}")

    def _cache_key(self, asset: dict, path: Path) -> str:
        """Content hash used as the cache file name; never the raw document value."""
        digest = asset.get("sha256")
        if isinstance(digest, str) and _SHA256_RE.match(digest):
            return digest
        return worker.sha256_file(path)

    def _cache_dir(self, name: str) -> Path:
        target = self.cache_root / name
        target.mkdir(parents=True, exist_ok=True)
        return target

    def media_file(self, project_id: str, asset_id: str) -> Path:
        _, asset = self._stored_asset(project_id, asset_id)
        return self._asset_path(asset)

    def remove_media(
        self, project_id: str, asset_id: str, body: dict | None = None, query: dict | None = None
    ) -> dict:
        """Drop an asset and every scene that used it, as a new revision.

        The revision is optimistic like every other mutation: the client may
        send the revision it last saw (``?revision=`` or ``{"revision": n}``)
        and gets a 409 instead of silently deleting on top of a newer edit.
        """
        stored, asset = self._stored_asset(project_id, asset_id)
        document = stored["document"]
        base_revision = _revision_param(body or {}, query or {}, default=document["revision"])

        trimmed, removed_scenes = project.remove_asset(document, asset_id)
        try:
            saved = self.journal.save_project(project_id, trimmed, base_revision)
        except project.RevisionConflict as exc:
            current = self.journal.get_project(project_id)
            raise HttpError(
                409, "hay una revisión más nueva", current_revision=(current or {}).get("revision")
            ) from exc

        payload = self._project_payload(saved)
        payload["removedAsset"] = {"id": asset_id, "path": asset.get("path")}
        payload["removedScenes"] = removed_scenes
        return payload

    # -- derived media (v3): thumbnails and waveforms ---------------------- #

    def thumbnail(self, project_id: str, asset_id: str, at: float = 0.0) -> Path:
        """One JPEG frame at *at* seconds, cached under ``cache/thumbs``."""
        _, asset = self._stored_asset(project_id, asset_id)
        if asset.get("kind") == "audio":
            raise _bad_request("un medio de audio no tiene fotograma")
        source = self._asset_path(asset)
        key = self._cache_key(asset, source)
        target = self._cache_dir("thumbs") / f"{key}_{at:.3f}.jpg"
        if target.is_file() and target.stat().st_size > 0:
            return target

        staging = target.with_name(f"{target.stem}.{secrets.token_hex(4)}.jpg")
        args = [str(self.tools.ffmpeg), "-hide_banner", "-v", "error", "-y"]
        if at > 0 and asset.get("kind") == "video":
            args += ["-ss", f"{at:.3f}"]
        args += [
            "-i", str(source), "-frames:v", "1", "-vf", f"scale={THUMB_WIDTH}:-2",
            "-q:v", "4", str(staging),
        ]
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=THUMB_TIMEOUT_S, check=False,
                cwd=str(staging.parent), env=worker.filtered_env(staging.parent),
                creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            staging.unlink(missing_ok=True)
            raise HttpError(502, f"no se pudo generar la miniatura: {type(exc).__name__}") from exc
        if result.returncode != 0 or not staging.is_file() or staging.stat().st_size == 0:
            staging.unlink(missing_ok=True)
            detail = (result.stderr or "").strip().splitlines()
            raise HttpError(
                502, "no se pudo generar la miniatura", detail=detail[-1][:300] if detail else None
            )
        os.replace(staging, target)
        return target

    def waveform(self, project_id: str, asset_id: str) -> dict:
        """Peaks per bucket (0..1) for the audio track, cached under ``cache/wave``."""
        stored, asset = self._stored_asset(project_id, asset_id)
        source = self._asset_path(asset)
        key = self._cache_key(asset, source)
        cached = self._cache_dir("wave") / f"{key}.json"
        if cached.is_file():
            try:
                payload = json.loads(cached.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                payload = None
            if isinstance(payload, dict) and payload.get("sha256") == key and isinstance(payload.get("peaks"), list):
                return payload

        payload = self._compute_waveform(stored["projectId"], asset, source, key)
        staging = cached.with_name(f"{cached.name}.{secrets.token_hex(4)}.tmp")
        staging.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(staging, cached)
        return payload

    def _compute_waveform(self, project_id: str, asset: dict, source: Path, key: str) -> dict:
        """Decode to mono 8 kHz PCM on stdout and reduce it to bucket peaks in Python."""
        args = [
            str(self.tools.ffmpeg), "-hide_banner", "-v", "error", "-i", str(source),
            "-vn", "-ac", "1", "-ar", str(WAVEFORM_RATE), "-f", "s16le", "pipe:1",
        ]
        try:
            result = subprocess.run(
                args, capture_output=True, timeout=WAVEFORM_TIMEOUT_S, check=False,
                cwd=str(self.cache_root), env=worker.filtered_env(self.cache_root),
                creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise HttpError(502, f"no se pudo analizar el audio: {type(exc).__name__}") from exc
        if result.returncode != 0:
            raise _bad_request(f"{asset['path']}: el medio no tiene pista de audio")

        raw = result.stdout or b""
        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if sys.byteorder != "little":
            samples.byteswap()
        total = len(samples)
        if total == 0:
            raise _bad_request(f"{asset['path']}: el audio decodificado está vacío")

        peaks: list[float] = []
        for slot in range(WAVEFORM_BUCKETS):
            start = slot * total // WAVEFORM_BUCKETS
            end = (slot + 1) * total // WAVEFORM_BUCKETS
            if end <= start:
                peaks.append(0.0)
                continue
            window = samples[start:end]
            peak = max(max(window), -min(window))  # -32768 needs the sign flip, not abs()
            peaks.append(round(min(1.0, peak / 32768.0), 4))

        return {
            "projectId": project_id,
            "assetId": asset["id"],
            "sha256": key,
            "buckets": WAVEFORM_BUCKETS,
            "duration": round(total / WAVEFORM_RATE, 3),
            "peaks": peaks,
        }

    def export_history(self, project_id: str | None, limit: int = EXPORT_HISTORY_LIMIT) -> dict:
        """Newest exports first, with the same fields the job view uses."""
        if project_id:
            if self.journal.get_project(project_id) is None:
                raise HttpError(404, f"proyecto desconocido: {project_id}")
            jobs = self.journal.list_jobs_for_project(project_id, limit=limit)
        else:
            jobs = self.journal.list_jobs(limit=limit)

        items = []
        for job in jobs:
            if job.get("type") == "generate":
                continue
            payload = self.job_payload(job["jobId"])
            items.append({
                "jobId": payload["jobId"],
                "projectId": payload["projectId"],
                "revision": payload["revision"],
                "preset": payload["preset"],
                "state": payload["state"],
                "stage": payload["stage"],
                "progress": payload["progress"],
                "error": payload["error"],
                "outputName": payload["outputName"],
                "outputUrl": payload["outputUrl"],
                "outputBytes": payload.get("outputBytes"),
                "createdAt": payload["createdAt"],
                "finishedAt": payload["finishedAt"],
            })
        return {"projectId": project_id or None, "count": len(items), "jobs": items}

    def _purge_project_files(self, document: dict, job_ids: list[str]) -> list[str]:
        """Best-effort removal of a deleted project's renders and derived media."""
        purged: list[str] = []

        def drop(target: Path) -> None:
            if not target.exists():
                return
            shutil.rmtree(target, ignore_errors=True)
            if not target.exists():
                purged.append(str(target))

        for job_id in job_ids:
            try:
                drop(self.layout.job_dir(job_id))
                drop(self.layout.out_dir(job_id))
            except worker.WorkerError:  # an id we would never have written
                continue

        for asset in document.get("assets") or []:
            digest = asset.get("sha256") if isinstance(asset, dict) else None
            if not isinstance(digest, str) or not _SHA256_RE.match(digest):
                continue
            for thumb in sorted(self._cache_dir("thumbs").glob(f"{digest}_*.jpg")):
                try:
                    thumb.unlink()
                    purged.append(str(thumb))
                except OSError:
                    pass
            wave = self._cache_dir("wave") / f"{digest}.json"
            try:
                if wave.is_file():
                    wave.unlink()
                    purged.append(str(wave))
            except OSError:
                pass
        return purged


    def output_file(self, job_id: str) -> Path:
        job = self.journal.get_job(job_id)
        if job is None:
            raise HttpError(404, f"trabajo desconocido: {job_id}")
        if job["state"] != "succeeded" or not job.get("outputName"):
            raise HttpError(409, "el trabajo todavía no tiene salida")
        path = self.layout.output_path(job_id, job["outputName"])
        if not path.is_file():
            raise HttpError(410, "la salida fue eliminada del disco")
        return path

    # -- HTTP plumbing ---------------------------------------------------- #

    def _handler_factory(self) -> type[BaseHTTPRequestHandler]:
        service = self

        class Handler(_Handler):
            svc = service

        return Handler


def _default_tools_root() -> Path:
    """Locate FFmpeg without hardcoding one machine.

    Order: explicit env var, Hermes tools folder, ``PATH``. Raises a clear
    error instead of failing later inside a render.
    """
    override = os.environ.get("VIDEO_EDITOR_TOOLS")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for candidate in here.parents:
        tools = candidate / "tools"
        if tools.is_dir():
            matches = sorted(p for p in tools.glob("ffmpeg*") if (p / "bin" / "ffmpeg.exe").is_file())
            if matches:
                return matches[-1] / "bin"
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        tools = Path(localappdata) / "hermes" / "tools"
        if tools.is_dir():
            matches = sorted(p for p in tools.glob("ffmpeg*") if (p / "bin" / "ffmpeg.exe").is_file())
            if matches:
                return matches[-1] / "bin"
    found = shutil.which("ffmpeg")
    if found:
        return Path(found).resolve().parent
    raise RuntimeError(
        "FFmpeg no encontrado: instálalo en PATH o define VIDEO_EDITOR_TOOLS con la carpeta que contiene ffmpeg/ffprobe"
    )


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _text(value: Any, name: str, *, required: bool = True, default: str = "", limit: int = 500) -> str:
    if value is None:
        if required:
            raise _bad_request(f"falta '{name}'")
        return default
    if not isinstance(value, str):
        raise _bad_request(f"'{name}' debe ser texto")
    value = value.strip()
    if not value and required:
        raise _bad_request(f"'{name}' no puede estar vacío")
    if len(value) > limit:
        raise _bad_request(f"'{name}' supera {limit} caracteres")
    if any(ord(char) < 32 for char in value):
        raise _bad_request(f"'{name}' contiene caracteres de control")
    return value or default


def _optional_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _bad_request("se esperaba texto")
    value = value.strip()
    if not value:
        return None
    if len(value) > limit:
        raise _bad_request(f"texto supera {limit} caracteres")
    return value


def _looks_like_ui_document(draft: Any) -> bool:
    if not isinstance(draft, dict):
        return False
    return "project_id" in draft or ("scenes" in draft and "schemaVersion" not in draft)


def _scene_from_asset(asset: dict, kind: str, duration: float, doc: dict) -> dict:
    length = round(min(max(duration, 0.4), 10.0) if duration else 3.0, 3)
    return {
        "id": "sc_" + secrets.token_hex(4),
        "name": Path(asset["path"]).stem[:80] or "Escena",
        "source": {"assetId": asset["id"], "path": asset["path"], "sha256": asset["sha256"], "kind": kind},
        "in": 0.0,
        "out": length,
        "transition": "none",
        "text": [],
        "audio": {"volume": 100, "fadeIn": 0.0, "fadeOut": 0.0},
        "needsRelink": False,
    }


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #


class _Handler(BaseHTTPRequestHandler):
    svc: Service
    server_version = f"video-editor/{SERVICE_VERSION}"

    # -- logging: never the raw query string (may carry a path) ----------- #
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {fmt % args}\n")

    # -- entry points ----------------------------------------------------- #

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Preflight CORS: PUT/POST con JSON lo disparan siempre."""
        try:
            self._check_origin()
        except HttpError as exc:
            self._send_json(exc.status, {"error": exc.message, **exc.extra})
            return
        self.send_response(204)
        # Preflights never carry the token (browsers strip custom headers from them);
        # the real request is what gets authenticated.
        self._send_cors(force=True)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", f"Content-Type, {auth.TOKEN_HEADER}")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_cors(self, force: bool = False) -> None:
        """Refleja el Origin solo si está en la allowlist: nunca se refleja uno ajeno.

        Con token configurado, además, solo se reflejan las respuestas a peticiones
        autenticadas (o el preflight): una página ``Origin: null`` ajena no puede
        leer nada porque nunca recibe ``Access-Control-Allow-Origin``.
        """
        origin = (self.headers.get("Origin") or "").strip()
        if not self._origin_allowed(origin):
            return
        if not force and self.svc.config.token and not getattr(self, "_authed", False):
            return
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, Accept-Ranges")

    def _dispatch(self, method: str) -> None:
        self._authed = False
        try:
            self._check_origin()
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            self._check_token(method, path)
            body = self._read_json() if method in ("POST", "PUT", "DELETE") else {}
            status, payload = self._route(method, path, query, body)
            if isinstance(payload, tuple):  # raw file response
                path_obj, content_type = payload[0], payload[1]
                cache_control = payload[2] if len(payload) > 2 else None
                self._send_file(path_obj, content_type, cache_control)
                return
            self._send_json(status, payload)
        except HttpError as exc:
            self._send_json(exc.status, {"error": exc.message, **exc.extra})
        except project.RevisionConflict as exc:
            self._send_json(409, {"error": str(exc)})
        except project.ProjectError as exc:
            self._send_json(400, {"error": str(exc)})
        except journal_module.NotFound as exc:
            self._send_json(404, {"error": str(exc)})
        except journal_module.JournalError as exc:
            self._send_json(400, {"error": str(exc)})
        except worker.WorkerError as exc:
            self._send_json(400, {"error": str(exc)})
        except BrokenPipeError:
            pass
        except Exception as exc:  # pragma: no cover - last resort
            traceback.print_exc()
            self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})

    # -- security --------------------------------------------------------- #

    def _origin_allowed(self, origin: str) -> bool:
        """Allowlist de orígenes; se usa tanto para validar como para emitir CORS."""
        if not origin:
            return False
        port = self.svc.port
        allowed = {
            "null", "file://",
            f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"http://[::1]:{port}",
        }
        allowed.update(item.lower() for item in self.svc.config.extra_origins)
        return origin.strip().lower() in allowed

    #: Read-only byte streams that ``<video>``/``<img>`` fetch without custom
    #: headers. They stay reachable without the token but are never CORS-readable.
    _PASSIVE_GET = ("media", "thumbnails")

    def _is_passive_get(self, method: str, path: str) -> bool:
        if method != "GET":
            return False
        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[0] in self._PASSIVE_GET:
            return True
        return len(parts) == 3 and parts[0] == "jobs" and parts[2] == "output"

    def _check_token(self, method: str, path: str) -> None:
        expected = self.svc.config.token
        if not expected:
            self._authed = True
            return
        supplied = self.headers.get(auth.TOKEN_HEADER)
        if auth.matches(expected, supplied):
            self._authed = True
            return
        if self._is_passive_get(method, path):
            return
        if path == "/health" and method == "GET":
            return
        if supplied:
            raise HttpError(403, "token inválido")
        raise HttpError(401, "falta el token del servicio (cabecera X-VE-Token)")

    def _check_origin(self) -> None:
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.svc.port
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        if not host:
            raise HttpError(403, "falta la cabecera Host")
        if host not in allowed_hosts:
            raise HttpError(403, "host no permitido")
        origin = (self.headers.get("Origin") or "").strip()
        if not origin:
            return
        if not self._origin_allowed(origin):
            raise HttpError(403, "origen no permitido")

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise _bad_request("Content-Length inválido")
        if length > MAX_BODY_BYTES:
            raise HttpError(413, "cuerpo demasiado grande")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _bad_request(f"JSON inválido: {exc}") from exc
        if not isinstance(payload, dict):
            raise _bad_request("se esperaba un objeto JSON")
        return payload

    # -- routing ---------------------------------------------------------- #

    def _route(self, method: str, path: str, query: dict, body: dict):
        svc = self.svc
        parts = [part for part in path.split("/") if part]

        if path == "/health" and method == "GET" and not self._authed:
            return 200, {"ok": True, "service": SERVICE_VERSION, "authRequired": True}

        if path == "/health" and method == "GET":
            return 200, {
                "ok": True,
                "service": SERVICE_VERSION,
                "engine": project.DEFAULT_ENGINE_TAG,
                "ffmpeg": str(svc.tools.ffmpeg),
                "ffmpegVersion": worker.tool_version(svc.tools),
                "dataRoot": str(svc.data_root),
                "mediaRoot": str(svc.media_root),
                "queue": svc.stats(),
                "recovered": [job["jobId"] for job in svc.recovered],
                "presets": list(ALLOWED_PRESETS),
                "presetSizes": {
                    name: [spec.width, spec.height] for name, spec in worker.PRESETS.items()
                },
                "experimentalPresets": list(EXPERIMENTAL_PRESETS),
                "transitions": list(project.TRANSITION_STYLES),
                "providers": generation.provider_status()["providers"],
                "providerModes": generation.provider_status()["providerModes"],
                "startedAt": svc.started_at,
                "authRequired": bool(svc.config.token),
                "voiceModes": generation.voice_status(),
            }

        if path == "/grants" and method == "GET":
            return 200, {"mediaRoot": str(svc.media_root)}

        if path == "/projects" and method == "GET":
            session = (query.get("session") or [None])[0]
            cwd = (query.get("cwd") or [None])[0]
            needle = (_first(query, "query") or "").strip().casefold()
            items = []
            for summary in svc.journal.list_projects():
                stored = svc.journal.get_project(summary["projectId"])
                if stored is None:
                    continue
                doc = stored["document"]
                if session and doc.get("sessionId") != session:
                    continue
                if cwd and doc.get("cwd") != cwd:
                    continue
                title = doc.get("title") or ""
                if needle and needle not in str(title).casefold():
                    continue
                items.append({
                    "projectId": doc["projectId"],
                    "title": doc.get("title"),
                    "revision": doc["revision"],
                    "scenes": len(doc.get("scenes") or []),
                    "assets": len(doc.get("assets") or []),
                    "updatedAt": doc.get("updatedAt"),
                    "sessionId": doc.get("sessionId"),
                    "cwd": doc.get("cwd"),
                })
            return 200, {"projects": items, "mediaRoot": str(svc.media_root), "query": needle}

        if path == "/projects" and method == "POST":
            return 201, svc.create_project(body)

        if len(parts) >= 2 and parts[0] == "projects":
            project_id = parts[1]
            if len(parts) == 2 and method == "GET":
                return 200, svc.project_payload(project_id)
            if len(parts) == 2 and method == "PUT":
                return 200, svc.save_project(project_id, body)
            if len(parts) == 2 and method == "DELETE":
                return 200, svc.delete_project(project_id, confirm=_confirmed(body, query))
            if len(parts) == 3 and parts[2] == "timeline" and method == "GET":
                return 200, svc.timeline(project_id)
            if len(parts) == 3 and parts[2] == "at" and method == "GET":
                return 200, svc.items_at(project_id, _first(query, "t") if _first(query, "t") is not None else "0")
            if len(parts) == 3 and parts[2] == "edit" and method == "POST":
                return 200, svc.edit(project_id, body)
            if len(parts) == 3 and parts[2] == "duplicate" and method == "POST":
                return 201, svc.duplicate_project(project_id)
            if len(parts) == 3 and parts[2] == "media" and method == "POST":
                return 201, svc.add_media(project_id, body)
            if len(parts) == 3 and parts[2] == "export" and method == "POST":
                return 202, svc.export(project_id, body)
            if len(parts) == 3 and parts[2] == "generate" and method == "POST":
                return 202, svc.start_generation(project_id, body)
            if len(parts) == 4 and parts[2] == "media" and method == "DELETE":
                return 200, svc.remove_media(project_id, parts[3], body, query)

        if len(parts) == 3 and parts[0] == "media" and method == "GET":
            return 200, (svc.media_file(parts[1], parts[2]), None)

        if len(parts) == 3 and parts[0] == "thumbnails" and method == "GET":
            at = _float_param(_first(query, "t"), "t", default=0.0, low=0.0, high=86400.0)
            return 200, (svc.thumbnail(parts[1], parts[2], at), "image/jpeg", "public, max-age=300")

        if len(parts) == 3 and parts[0] == "waveform" and method == "GET":
            return 200, svc.waveform(parts[1], parts[2])

        if path == "/exports" and method == "GET":
            project_id = (_first(query, "project") or "").strip()
            limit = _int_param(_first(query, "limit"), "limit", default=EXPORT_HISTORY_LIMIT, low=1, high=200)
            return 200, svc.export_history(project_id, limit)

        if path == "/jobs" and method == "GET":
            limit = int((query.get("limit") or ["50"])[0])
            return 200, {"jobs": svc.journal.list_jobs(limit=max(1, min(limit, 200)))}

        if len(parts) >= 2 and parts[0] == "jobs":
            job_id = parts[1]
            if len(parts) == 2 and method == "GET":
                return 200, svc.job_payload(job_id)
            if len(parts) == 3 and parts[2] == "cancel" and method == "POST":
                return 200, svc.cancel(job_id)
            if len(parts) == 3 and parts[2] == "output" and method == "GET":
                return 200, (svc.output_file(job_id), "video/mp4")

        if path == "/events" and method == "GET":
            since = int((query.get("since") or ["0"])[0])
            timeout = float((query.get("timeout") or ["20"])[0])
            last = svc.journal.last_event_seq()
            events = svc.journal.events_since(since) if timeout <= 0 else svc.journal.wait_events(since, timeout=timeout)
            return 200, {"events": events, "lastSeq": last}

        if path == "/admin/stop" and method == "POST":
            if not svc.config.allow_admin:
                raise HttpError(403, "administración deshabilitada")
            threading.Timer(0.05, svc.stop).start()
            return 200, {"stopping": True}

        raise HttpError(404, f"ruta desconocida: {method} {path}")

    # -- responses -------------------------------------------------------- #

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _send_file(self, path: Path, content_type: str | None, cache_control: str | None = None) -> None:
        content_type = content_type or _content_type(path.name)
        size = path.stat().st_size
        start, end = 0, size - 1
        status = 200
        header = self.headers.get("Range")
        if header and header.startswith("bytes="):
            raw = header[6:].split(",")[0].strip()
            first, _, last = raw.partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                elif last:
                    start = max(0, size - int(last))
                status = 206
            except ValueError:
                raise _bad_request("Range inválido")
            start = max(0, min(start, size - 1))
            end = max(start, min(end, size - 1))
        length = end - start + 1
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache_control or "no-store")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with open(path, "rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


def _content_type(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return {
        ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
        ".mkv": "video/x-matroska", ".webm": "video/webm", ".avi": "video/x-msvideo",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".bmp": "image/bmp",
        ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
    }.get(suffix, "application/octet-stream")


# `project.RevisionConflict`/`ProjectError` are caught directly in `_dispatch`;
# the ordering there (409 before 400) keeps the conflict dialog working.


def build_service(
    data_root: str | os.PathLike[str],
    media_root: str | os.PathLike[str],
    *,
    tools_root: str | os.PathLike[str] | None = None,
    port: int = 8765,
    host: str = "127.0.0.1",
    allow_admin: bool = True,
    extra_origins: tuple[str, ...] = (),
    token: str | None = None,
) -> Service:
    return Service(ServiceConfig(
        data_root=Path(data_root), media_root=Path(media_root),
        tools_root=Path(tools_root) if tools_root else None,
        host=host, port=port, allow_admin=allow_admin, extra_origins=extra_origins,
        token=token,
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Video editor service (loopback)")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--media-root", required=True)
    parser.add_argument("--tools-root", default=None)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-admin", action="store_true")
    parser.add_argument(
        "--allow-origin", action="append", default=[], metavar="ORIGIN",
        help="origen adicional permitido (solo para pruebas locales; repetible)",
    )
    parser.add_argument(
        "--token-file", default=None,
        help="archivo con el token del servicio (por defecto %%LOCALAPPDATA%%/hermes/video-editor/service.token; se crea si falta)",
    )
    parser.add_argument(
        "--no-token", action="store_true",
        help="DESACTIVA la autenticación por token (solo depuración local; no recomendado)",
    )
    args = parser.parse_args(argv)

    token = None if args.no_token else auth.load_or_create_token(args.token_file)
    service = build_service(
        args.data_root, args.media_root, tools_root=args.tools_root,
        port=args.port, allow_admin=not args.no_admin,
        extra_origins=tuple(args.allow_origin), token=token,
    ).start()
    print(json.dumps({
        "service": SERVICE_VERSION,
        "url": service.base_url,
        "dataRoot": str(service.data_root),
        "mediaRoot": str(service.media_root),
        "restartedJobs": [job["jobId"] for job in service.recovered],
        "auth": "token" if token else "DISABLED",
    }, ensure_ascii=False))
    try:
        while not service.stopped.is_set():
            service.stopped.wait(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
