"""Own SQLite journal: project revisions, job queue, events.

Separate from Hermes' databases by design (PLAN 2.4): the video service must
survive a gateway restart and must never read or write another component's
tables. The schema carries its own version (``PRAGMA user_version``) and an
ordered migration list.

States:  queued -> running -> succeeded | failed | cancelled | interrupted
Stages:  queued -> probing -> rendering -> validating -> promoting -> done
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

if __package__ in (None, ""):  # allow `python service/journal.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import project  # noqa: E402

SCHEMA_VERSION = 2

TERMINAL_STATES = ("succeeded", "failed", "cancelled", "interrupted")
ACTIVE_STATES = ("queued", "running")
STAGES = ("queued", "probing", "rendering", "validating", "promoting", "done")

_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE projects (
            project_id  TEXT PRIMARY KEY,
            revision    INTEGER NOT NULL,
            document    TEXT NOT NULL,
            doc_hash    TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE jobs (
            job_id           TEXT PRIMARY KEY,
            project_id       TEXT NOT NULL,
            project_revision INTEGER NOT NULL,
            engine_tag       TEXT NOT NULL,
            preset           TEXT NOT NULL,
            captions         INTEGER NOT NULL DEFAULT 1,
            dedupe_key       TEXT UNIQUE,
            state            TEXT NOT NULL,
            stage            TEXT NOT NULL,
            progress         REAL NOT NULL DEFAULT 0,
            eta_s            REAL,
            message          TEXT NOT NULL DEFAULT '',
            error            TEXT,
            exit_code        INTEGER,
            output_name      TEXT,
            artifacts        TEXT NOT NULL DEFAULT '[]',
            snapshot_path    TEXT,
            worker_pid       INTEGER,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            source           TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL,
            started_at       TEXT,
            finished_at      TEXT,
            updated_at       TEXT NOT NULL
        );

        CREATE INDEX jobs_state_idx ON jobs (state, created_at);
        CREATE INDEX jobs_project_idx ON jobs (project_id, created_at DESC);

        CREATE TABLE events (
            seq      INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id   TEXT,
            ts       TEXT NOT NULL,
            state    TEXT,
            stage    TEXT,
            progress REAL,
            message  TEXT
        );

        CREATE INDEX events_job_idx ON events (job_id, seq);
        """,
    ),
    (
        2,
        # Phase 3A: jobs also carry *generation* work. One table keeps
        # GET /jobs/<id>, cancel and the event stream identical for both kinds;
        # job_type is what stops the render runner from claiming a generation
        # job (and vice versa). payload holds the request plus its result.
        """
        ALTER TABLE jobs ADD COLUMN job_type TEXT NOT NULL DEFAULT 'render';
        ALTER TABLE jobs ADD COLUMN payload TEXT NOT NULL DEFAULT '{}';

        CREATE INDEX jobs_type_state_idx ON jobs (job_type, state, created_at);
        """,
    )
]


class JournalError(RuntimeError):
    pass


class NotFound(JournalError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Journal:
    """Thread-safe wrapper over one SQLite file. WAL, foreign keys, explicit locks."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=10.0)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.execute("PRAGMA busy_timeout=5000")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._migrate()

    # -- schema ---------------------------------------------------------- #

    @property
    def db(self) -> sqlite3.Connection:
        return self._db

    def schema_version(self) -> int:
        with self._lock:
            return int(self._db.execute("PRAGMA user_version").fetchone()[0])

    def _migrate(self) -> None:
        current = int(self._db.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise JournalError(f"journal schema {current} is newer than supported {SCHEMA_VERSION}")
        for version, script in _MIGRATIONS:
            if version <= current:
                continue
            with self._db:
                self._db.executescript(script)
                self._db.execute(f"PRAGMA user_version={version}")
            current = version

    def close(self) -> None:
        with self._lock:
            try:
                self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            self._db.close()

    # -- projects -------------------------------------------------------- #

    def list_projects(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT project_id, revision, updated_at, doc_hash, document FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        items = []
        for row in rows:
            try:
                title = (json.loads(row["document"]) or {}).get("title")
            except (ValueError, AttributeError):  # a corrupt row must not hide the library
                title = None
            items.append(
                {
                    "projectId": row["project_id"],
                    "revision": row["revision"],
                    "updatedAt": row["updated_at"],
                    "docHash": row["doc_hash"],
                    "title": title,
                }
            )
        return items

    def get_project(self, project_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT project_id, revision, document, doc_hash, created_at, updated_at FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "projectId": row["project_id"],
            "revision": row["revision"],
            "document": json.loads(row["document"]),
            "docHash": row["doc_hash"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def create_project(self, document: dict) -> dict:
        project_id = document["projectId"]
        stamp = now_iso()
        document = dict(document)
        document["revision"] = int(document.get("revision") or 0)
        document["baseRevision"] = document["revision"]
        document.setdefault("createdAt", stamp)
        document["updatedAt"] = stamp
        payload = project.dumps(document)
        with self._lock, self._db:
            try:
                self._db.execute(
                    "INSERT INTO projects (project_id, revision, document, doc_hash, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, document["revision"], payload, project.document_hash(document), document["createdAt"], stamp),
                )
            except sqlite3.IntegrityError as exc:
                raise JournalError(f"project {project_id!r} already exists") from exc
        return {"projectId": project_id, "revision": document["revision"], "document": document,
                "docHash": project.document_hash(document), "createdAt": document["createdAt"],
                "updatedAt": stamp}

    def save_project(self, project_id: str, document: dict, base_revision: Any) -> dict:
        """Apply an edit under optimistic concurrency control.

        ``base_revision`` must equal the stored revision; otherwise
        :class:`project.RevisionConflict` bubbles up and the HTTP layer answers
        409 with the current revision. The stored revision always wins.
        """
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT revision, document, created_at FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"unknown project {project_id!r}")
            stored_doc = json.loads(row["document"])
            next_doc_meta = project.bump_revision(stored_doc, base_revision)

            merged = dict(document)
            merged["projectId"] = project_id
            merged["revision"] = next_doc_meta["revision"]
            merged["baseRevision"] = next_doc_meta["baseRevision"]
            merged["updatedAt"] = next_doc_meta["updatedAt"]
            merged["createdAt"] = row["created_at"]

            project.check(merged)
            payload = project.dumps(merged)
            self._db.execute(
                "UPDATE projects SET revision = ?, document = ?, doc_hash = ?, updated_at = ? WHERE project_id = ?",
                (merged["revision"], payload, project.document_hash(merged), merged["updatedAt"], project_id),
            )
        return {
            "projectId": project_id,
            "revision": merged["revision"],
            "document": merged,
            "docHash": project.document_hash(merged),
            "createdAt": merged["createdAt"],
            "updatedAt": merged["updatedAt"],
        }

    # -- jobs ------------------------------------------------------------ #

    def list_jobs_for_project(self, project_id: str, *, limit: int = 20) -> list[dict]:
        """Exports of one project, newest first (the history view)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC, job_id DESC LIMIT ?",
                (project_id, int(limit)),
            ).fetchall()
        return [self._job_row(row) for row in rows]

    def delete_project(self, project_id: str) -> dict | None:
        """Delete a project with its jobs and their events, in one transaction.

        Returns ``{projectId, jobIds}`` or ``None`` when the project is unknown.
        The HTTP layer purges the files on disk afterwards: the journal is the
        source of truth, so a half-deleted filesystem cannot resurrect a row.
        """
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT project_id FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if row is None:
                return None
            job_ids = [
                item["job_id"]
                for item in self._db.execute(
                    "SELECT job_id FROM jobs WHERE project_id = ?", (project_id,)
                ).fetchall()
            ]
            for start in range(0, len(job_ids), 200):
                chunk = job_ids[start : start + 200]
                placeholders = ", ".join("?" for _ in chunk)
                self._db.execute(f"DELETE FROM events WHERE job_id IN ({placeholders})", chunk)
            self._db.execute("DELETE FROM jobs WHERE project_id = ?", (project_id,))
            self._db.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return {"projectId": project_id, "jobIds": job_ids}

    def create_job(
        self,
        *,
        job_id: str,
        project_id: str,
        project_revision: int,
        engine_tag: str,
        preset: str,
        captions: bool,
        dedupe_key: str,
        snapshot_path: str,
        source: str,
    ) -> tuple[dict, bool]:
        """Insert a queued job. Returns ``(job, created)``; dedupes on dedupe_key."""
        stamp = now_iso()
        with self._lock, self._db:
            try:
                self._db.execute(
                    "INSERT INTO jobs (job_id, project_id, project_revision, engine_tag, preset, captions,"
                    " dedupe_key, state, stage, progress, message, snapshot_path, source, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 'queued', 0, '', ?, ?, ?, ?)",
                    (
                        job_id,
                        project_id,
                        int(project_revision),
                        engine_tag,
                        preset,
                        1 if captions else 0,
                        dedupe_key,
                        snapshot_path,
                        source,
                        stamp,
                        stamp,
                    ),
                )
            except sqlite3.IntegrityError:
                existing = self._db.execute("SELECT * FROM jobs WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
                if existing is None:
                    raise
                return self._job_row(existing), False
            self.add_event_tx(job_id, state="queued", stage="queued", progress=0.0, message="trabajo en cola")
            row = self._db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._job_row(row), True

    def create_generation_job(
        self,
        *,
        job_id: str,
        project_id: str,
        project_revision: int,
        kind: str,
        payload: dict,
        source: str,
    ) -> dict:
        """Insert a queued *generation* job (phase 3A).

        Same table as renders so ``GET /jobs/<id>``, cancellation and the event
        stream work unchanged; ``job_type`` keeps it out of the render queue.
        """
        stamp = now_iso()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO jobs (job_id, project_id, project_revision, engine_tag, preset, captions,"
                " dedupe_key, state, stage, progress, message, artifacts, job_type, payload, source,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, 've-generate/3A', ?, 0, NULL, 'queued', 'queued', 0, '', '[]', 'generate',"
                " ?, ?, ?, ?)",
                (
                    job_id,
                    project_id,
                    int(project_revision),
                    kind,
                    json.dumps(payload, ensure_ascii=False),
                    source,
                    stamp,
                    stamp,
                ),
            )
            self.add_event_tx(job_id, state="queued", stage="queued", progress=0.0, message="generación en cola")
            row = self._db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._job_row(row)

    def update_payload(self, job_id: str, changes: dict) -> dict | None:
        """Merge ``changes`` into a job's payload (generation results/progress)."""
        with self._lock, self._db:
            row = self._db.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            payload = json.loads(row["payload"] or "{}")
            payload.update(changes)
            self._db.execute(
                "UPDATE jobs SET payload = ?, updated_at = ? WHERE job_id = ?",
                (json.dumps(payload, ensure_ascii=False), now_iso(), job_id),
            )
            row = self._db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._job_row(row)

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._job_row(row) if row else None

    def find_job_by_dedupe(self, dedupe_key: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
        return self._job_row(row) if row else None

    def list_jobs(self, *, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [self._job_row(row) for row in rows]

    def next_queued_job(self, *, job_type: str = "render") -> dict | None:
        """Oldest queued job of ``job_type``: renders and generations never mix."""
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM jobs WHERE state = 'queued' AND job_type = ?"
                " ORDER BY created_at ASC, job_id ASC LIMIT 1",
                (job_type,),
            ).fetchone()
        return self._job_row(row) if row else None

    def claim_job(self, job_id: str, *, stage: str = "probing") -> bool:
        """Atomically move a queued job to running. False when someone else won."""
        with self._lock, self._db:
            cursor = self._db.execute(
                "UPDATE jobs SET state = 'running', stage = ?, started_at = ?, updated_at = ?"
                " WHERE job_id = ? AND state = 'queued'",
                (stage, now_iso(), now_iso(), job_id),
            )
            return cursor.rowcount == 1

    def set_worker_pid(self, job_id: str, pid: int) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE jobs SET worker_pid = ?, updated_at = ? WHERE job_id = ?", (int(pid), now_iso(), job_id))

    def update_progress(
        self, job_id: str, *, stage: str | None = None, progress: float | None = None,
        eta_s: float | None = None, message: str | None = None,
    ) -> None:
        sets, values = [], []
        if stage is not None:
            sets.append("stage = ?")
            values.append(stage)
        if progress is not None:
            sets.append("progress = ?")
            values.append(max(0.0, min(100.0, float(progress))))
        if eta_s is not None:
            sets.append("eta_s = ?")
            values.append(float(eta_s))
        if message is not None:
            sets.append("message = ?")
            values.append(message)
        if not sets:
            return
        sets.append("updated_at = ?")
        values.append(now_iso())
        values.append(job_id)
        with self._lock, self._db:
            self._db.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", values)
            job = self._db.execute("SELECT state, stage, progress FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if job is not None:
                self.add_event_tx(job_id, state=job["state"], stage=job["stage"], progress=job["progress"], message=message)

    def finish_job(
        self,
        job_id: str,
        state: str,
        *,
        error: str | None = None,
        exit_code: int | None = None,
        output_name: str | None = None,
        artifacts: Iterable[str] = (),
        message: str | None = None,
    ) -> dict:
        if state not in TERMINAL_STATES:
            raise JournalError(f"not a terminal state: {state}")
        artifacts = list(artifacts)
        progress = 100.0 if state == "succeeded" else None
        with self._lock, self._db:
            self._db.execute(
                "UPDATE jobs SET state = ?, stage = ?, progress = COALESCE(?, progress), error = ?, exit_code = ?,"
                " output_name = ?, artifacts = ?, finished_at = ?, updated_at = ?, message = COALESCE(?, message),"
                " eta_s = NULL WHERE job_id = ?",
                (
                    state,
                    "done" if state == "succeeded" else "failed",
                    progress,
                    error,
                    exit_code,
                    output_name if state == "succeeded" else None,
                    json.dumps(sorted(artifacts)) if state == "succeeded" else "[]",
                    now_iso(),
                    now_iso(),
                    message,
                    job_id,
                ),
            )
            self.add_event_tx(job_id, state=state, stage="done" if state == "succeeded" else "failed",
                              progress=progress, message=message or error)
            row = self._db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._job_row(row)

    def request_cancel(self, job_id: str) -> dict | None:
        """Mark a job for cancellation. Returns the job after the update."""
        with self._lock, self._db:
            row = self._db.execute("SELECT state FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            if row["state"] in TERMINAL_STATES:
                return self.get_job(job_id)
            self._db.execute(
                "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE job_id = ?", (now_iso(), job_id)
            )
            if row["state"] == "queued":
                self.finish_job(job_id, "cancelled", message="cancelado antes de empezar")
            self.add_event_tx(job_id, stage="cancelling", message="cancelación solicitada")
        return self.get_job(job_id)

    def cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            row = self._db.execute("SELECT cancel_requested FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return bool(row and row["cancel_requested"])

    def reap_interrupted(self) -> list[dict]:
        """Close jobs left mid-flight by a crash. Returns them (with worker_pid)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM jobs WHERE state = 'running' ORDER BY created_at"
            ).fetchall()
            reaped = []
            for row in rows:
                job = self._job_row(row)
                self._db.execute(
                    "UPDATE jobs SET state = 'interrupted', stage = 'failed', error = ?, finished_at = ?,"
                    " updated_at = ? WHERE job_id = ? AND state = 'running'",
                    ("servicio reiniciado con el trabajo en curso", now_iso(), now_iso(), job["jobId"]),
                )
                self.add_event_tx(job["jobId"], state="interrupted", stage="failed",
                                  progress=job["progress"], message="servicio reiniciado")
                reaped.append(job)
            self._db.commit()
        return reaped

    # -- events ---------------------------------------------------------- #

    def add_event_tx(self, job_id: str | None, *, state: str | None = None, stage: str | None = None,
                     progress: float | None = None, message: str | None = None) -> None:
        """Insert an event. Caller already holds the transaction."""
        self._db.execute(
            "INSERT INTO events (job_id, ts, state, stage, progress, message) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, now_iso(), state, stage, progress, message),
        )

    def add_event(self, job_id: str | None, *, state: str | None = None, stage: str | None = None,
                  progress: float | None = None, message: str | None = None) -> int:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO events (job_id, ts, state, stage, progress, message) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, now_iso(), state, stage, progress, message),
            )
            return int(self._db.execute("SELECT last_insert_rowid()").fetchone()[0])

    def last_event_seq(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()
        return int(row[0])

    def events_since(self, seq: int, *, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM events WHERE seq > ? ORDER BY seq ASC LIMIT ?", (int(seq), int(limit))
            ).fetchall()
        return [
            {
                "seq": row["seq"],
                "jobId": row["job_id"],
                "ts": row["ts"],
                "state": row["state"],
                "stage": row["stage"],
                "progress": row["progress"],
                "message": row["message"],
            }
            for row in rows
        ]

    def wait_events(self, seq: int, *, timeout: float = 20.0, limit: int = 200,
                    poll: float = 0.15) -> list[dict]:
        """Long-poll helper: block until there are events after *seq* or timeout."""
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            events = self.events_since(seq, limit=limit)
            if events or time.monotonic() >= deadline:
                return events
            time.sleep(poll)

    def prune_events(self, *, keep: int = 5000) -> int:
        with self._lock, self._db:
            cursor = self._db.execute(
                "DELETE FROM events WHERE seq <= (SELECT MAX(seq) - ? FROM events)", (int(keep),)
            )
            return cursor.rowcount

    # -- helpers --------------------------------------------------------- #

    def _job_row(self, row: sqlite3.Row) -> dict:
        return {
            "jobId": row["job_id"],
            "projectId": row["project_id"],
            "revision": row["project_revision"],
            "engineTag": row["engine_tag"],
            "preset": row["preset"],
            "captions": bool(row["captions"]),
            "type": row["job_type"] if "job_type" in row.keys() else "render",
            "generation": json.loads((row["payload"] if "payload" in row.keys() else None) or "{}"),
            "dedupeKey": row["dedupe_key"],
            "state": row["state"],
            "stage": row["stage"],
            "progress": row["progress"],
            "eta_s": row["eta_s"],
            "message": row["message"],
            "error": row["error"],
            "exitCode": row["exit_code"],
            "outputName": row["output_name"],
            "artifacts": json.loads(row["artifacts"] or "[]"),
            "snapshotPath": row["snapshot_path"],
            "workerPid": row["worker_pid"],
            "cancelRequested": bool(row["cancel_requested"]),
            "createdAt": row["created_at"],
            "startedAt": row["started_at"],
            "finishedAt": row["finished_at"],
            "updatedAt": row["updated_at"],
        }
