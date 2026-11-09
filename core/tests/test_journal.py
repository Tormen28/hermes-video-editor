"""Journal tests: revisions, dedupe, cancel, reaper, events, durability."""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

import _support
import project
from service import journal


class JournalTestCase(_support.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.journal = journal.Journal(self.tmp / "journal.sqlite3")
        self.addCleanup(self.journal.close)

    def add_project(self, scenes: int = 2) -> dict:
        doc = project.normalize(_support.small_document(scenes))
        return self.journal.create_project(doc)

    def add_job(self, *, job_id: str = "j1", dedupe: str = "k1", project_id: str = "prj_test",
                revision: int = 0) -> tuple[dict, bool]:
        return self.journal.create_job(
            job_id=job_id,
            project_id=project_id,
            project_revision=revision,
            engine_tag=project.DEFAULT_ENGINE_TAG,
            preset="mp4-720p30",
            captions=True,
            dedupe_key=dedupe,
            snapshot_path=str(self.tmp / "snapshot.json"),
            source="test",
        )


class SchemaTests(JournalTestCase):
    def test_schema_version_is_set(self):
        self.assertEqual(self.journal.schema_version(), journal.SCHEMA_VERSION)

    def test_reopening_does_not_rerun_migrations(self):
        self.journal.close()
        again = journal.Journal(self.tmp / "journal.sqlite3")
        self.addCleanup(again.close)
        self.assertEqual(again.schema_version(), journal.SCHEMA_VERSION)
        self.assertEqual(again.list_jobs(), [])

    def test_newer_schema_is_refused(self):
        db = self.journal.db
        db.execute(f"PRAGMA user_version={journal.SCHEMA_VERSION + 5}")
        db.commit()
        self.journal.close()
        with self.assertRaises(journal.JournalError):
            journal.Journal(self.tmp / "journal.sqlite3")

    def test_wal_mode_is_enabled(self):
        mode = self.journal.db.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")


class ProjectStorageTests(JournalTestCase):
    def test_create_and_get_round_trip(self):
        created = self.add_project()
        self.assertEqual(created["revision"], 3)
        stored = self.journal.get_project("prj_test")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["revision"], 3)
        self.assertEqual(stored["docHash"], project.document_hash(stored["document"]))
        self.assertEqual(stored["document"]["title"], "Proyecto de prueba")

    def test_duplicate_create_is_rejected(self):
        self.add_project()
        with self.assertRaises(journal.JournalError):
            self.add_project()

    def test_unknown_project_is_not_found(self):
        self.assertIsNone(self.journal.get_project("prj_missing"))
        with self.assertRaises(journal.NotFound):
            self.journal.save_project("prj_missing", _support.small_document(1), 0)

    def test_save_bumps_revision_and_keeps_created_at(self):
        created = self.add_project()
        draft = _support.small_document(2)
        draft["title"] = "Editado"
        saved = self.journal.save_project("prj_test", draft, created["revision"])
        self.assertEqual(saved["revision"], created["revision"] + 1)
        self.assertEqual(saved["document"]["baseRevision"], created["revision"])
        self.assertEqual(saved["document"]["title"], "Editado")
        self.assertEqual(saved["createdAt"], created["createdAt"])

    def test_stale_base_revision_conflicts(self):
        created = self.add_project()
        with self.assertRaises(project.RevisionConflict) as caught:
            self.journal.save_project("prj_test", _support.small_document(2), created["revision"] - 1)
        self.assertEqual(caught.exception.current, created["revision"])

    def test_client_cannot_choose_its_revision(self):
        created = self.add_project()
        draft = _support.small_document(1)
        draft["revision"] = 999
        draft["baseRevision"] = 999
        saved = self.journal.save_project("prj_test", draft, created["revision"])
        self.assertEqual(saved["revision"], created["revision"] + 1)
        self.assertEqual(saved["document"]["revision"], created["revision"] + 1)

    def test_only_one_of_two_racing_saves_wins(self):
        created = self.add_project()
        base = created["revision"]
        self.journal.save_project("prj_test", _support.small_document(1), base)
        with self.assertRaises(project.RevisionConflict):
            self.journal.save_project("prj_test", _support.small_document(1), base)

    def test_invalid_document_is_not_stored(self):
        created = self.add_project()
        bad = _support.small_document(1)
        bad["scenes"][0]["out"] = -5
        with self.assertRaises(project.ValidationError):
            self.journal.save_project("prj_test", bad, created["revision"])
        self.assertEqual(self.journal.get_project("prj_test")["revision"], created["revision"])

    def test_list_projects_reports_latest_revision(self):
        self.add_project()
        saved = self.journal.save_project("prj_test", _support.small_document(1), 3)
        listed = {item["projectId"]: item for item in self.journal.list_projects()}
        self.assertEqual(listed["prj_test"]["revision"], saved["revision"])


class JobQueueTests(JournalTestCase):
    def test_job_starts_queued(self):
        job, created = self.add_job()
        self.assertTrue(created)
        self.assertEqual(job["state"], "queued")
        self.assertEqual(job["stage"], "queued")
        self.assertEqual(job["progress"], 0)
        self.assertEqual(job["artifacts"], [])

    def test_dedupe_returns_the_original_job(self):
        first, created_first = self.add_job(job_id="j1", dedupe="same")
        second, created_second = self.add_job(job_id="j2", dedupe="same")
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first["jobId"], second["jobId"])
        self.assertEqual(len(self.journal.list_jobs()), 1)

    def test_claim_is_exclusive(self):
        self.add_job()
        self.assertTrue(self.journal.claim_job("j1"))
        self.assertFalse(self.journal.claim_job("j1"))
        job = self.journal.get_job("j1")
        self.assertEqual(job["state"], "running")
        self.assertIsNotNone(job["startedAt"])

    def test_next_queued_is_fifo(self):
        self.add_job(job_id="j1", dedupe="k1")
        self.add_job(job_id="j2", dedupe="k2")
        first = self.journal.next_queued_job()
        self.assertEqual(first["jobId"], "j1")
        self.journal.claim_job("j1")
        self.assertEqual(self.journal.next_queued_job()["jobId"], "j2")

    def test_progress_updates_and_events(self):
        self.add_job()
        self.journal.claim_job("j1")
        self.journal.update_progress("j1", stage="rendering", progress=42.5, eta_s=12.0, message="mitad")
        job = self.journal.get_job("j1")
        self.assertEqual(job["stage"], "rendering")
        self.assertEqual(job["progress"], 42.5)
        self.assertEqual(job["eta_s"], 12.0)
        messages = [event["message"] for event in self.journal.events_since(0)]
        self.assertIn("mitad", messages)

    def test_progress_is_clamped(self):
        self.add_job()
        self.journal.update_progress("j1", progress=250)
        self.assertEqual(self.journal.get_job("j1")["progress"], 100.0)

    def test_finish_success_records_output_and_artifacts(self):
        self.add_job()
        self.journal.claim_job("j1")
        job = self.journal.finish_job(
            "j1", "succeeded", exit_code=0, output_name="output.mp4",
            artifacts=["output.mp4", "poster.jpg"], message="listo",
        )
        self.assertEqual(job["state"], "succeeded")
        self.assertEqual(job["progress"], 100.0)
        self.assertEqual(job["outputName"], "output.mp4")
        self.assertEqual(job["artifacts"], ["output.mp4", "poster.jpg"])
        self.assertIsNotNone(job["finishedAt"])

    def test_finish_failure_discards_artifacts(self):
        self.add_job()
        self.journal.claim_job("j1")
        job = self.journal.finish_job("j1", "failed", exit_code=1, error="boom", artifacts=["output.mp4"])
        self.assertEqual(job["state"], "failed")
        self.assertEqual(job["artifacts"], [])
        self.assertIsNone(job["outputName"])
        self.assertEqual(job["error"], "boom")

    def test_invalid_terminal_state_is_rejected(self):
        self.add_job()
        with self.assertRaises(journal.JournalError):
            self.journal.finish_job("j1", "running")


class CancelTests(JournalTestCase):
    def test_cancelling_a_queued_job_finishes_it_immediately(self):
        self.add_job()
        job = self.journal.request_cancel("j1")
        self.assertEqual(job["state"], "cancelled")
        self.assertIsNone(self.journal.next_queued_job())

    def test_cancelling_a_running_job_sets_the_flag(self):
        self.add_job()
        self.journal.claim_job("j1")
        job = self.journal.request_cancel("j1")
        self.assertEqual(job["state"], "running")
        self.assertTrue(self.journal.cancel_requested("j1"))
        self.assertTrue(job["cancelRequested"])

    def test_cancelling_a_finished_job_is_a_noop(self):
        self.add_job()
        self.journal.claim_job("j1")
        self.journal.finish_job("j1", "succeeded", exit_code=0, output_name="output.mp4")
        job = self.journal.request_cancel("j1")
        self.assertEqual(job["state"], "succeeded")

    def test_unknown_job_cancel_returns_none(self):
        self.assertIsNone(self.journal.request_cancel("nope"))


class ReaperTests(JournalTestCase):
    def test_running_jobs_are_marked_interrupted_with_their_pid(self):
        self.add_job(job_id="j1", dedupe="k1")
        self.journal.claim_job("j1")
        self.journal.set_worker_pid("j1", 4242)
        self.journal.update_progress("j1", progress=8.2, stage="rendering")
        reaped = self.journal.reap_interrupted()
        self.assertEqual([job["jobId"] for job in reaped], ["j1"])
        self.assertEqual(reaped[0]["workerPid"], 4242)
        job = self.journal.get_job("j1")
        self.assertEqual(job["state"], "interrupted")
        self.assertEqual(job["progress"], 8.2)
        self.assertIn("reiniciado", job["error"])

    def test_queued_jobs_survive_a_restart(self):
        self.add_job(job_id="j1", dedupe="k1")
        self.assertEqual(self.journal.reap_interrupted(), [])
        self.assertEqual(self.journal.get_job("j1")["state"], "queued")
        self.assertIsNotNone(self.journal.next_queued_job())

    def test_reaper_is_idempotent(self):
        self.add_job()
        self.journal.claim_job("j1")
        self.journal.reap_interrupted()
        self.assertEqual(self.journal.reap_interrupted(), [])


class EventStreamTests(JournalTestCase):
    def test_events_are_ordered_and_filtered_by_seq(self):
        self.add_job(job_id="j1", dedupe="k1")
        self.add_job(job_id="j2", dedupe="k2")
        first = self.journal.events_since(0)
        self.assertGreaterEqual(len(first), 2)
        seqs = [event["seq"] for event in first]
        self.assertEqual(seqs, sorted(seqs))
        latest = seqs[-1]
        self.assertEqual(self.journal.events_since(latest), [])

    def test_long_poll_returns_new_events_quickly(self):
        self.add_job()
        start_seq = self.journal.last_event_seq()
        started = time.monotonic()
        self.journal.add_event("j1", stage="rendering", progress=10, message="diez")
        events = self.journal.wait_events(start_seq, timeout=5.0, poll=0.05)
        elapsed = time.monotonic() - started
        self.assertEqual(len(events), 1)
        self.assertLess(elapsed, 2.0)

    def test_long_poll_times_out_empty(self):
        start = time.monotonic()
        events = self.journal.wait_events(self.journal.last_event_seq(), timeout=0.3, poll=0.05)
        self.assertEqual(events, [])
        self.assertGreaterEqual(time.monotonic() - start, 0.25)

    def test_prune_keeps_the_tail(self):
        for index in range(20):
            self.journal.add_event(None, message=f"evento {index}")
        removed = self.journal.prune_events(keep=5)
        self.assertEqual(removed, 15)
        remaining = self.journal.events_since(0)
        self.assertEqual([event["message"] for event in remaining], [f"evento {i}" for i in range(15, 20)])


class DurabilityTests(_support.TempDirTestCase):
    def test_queue_survives_a_restart(self):
        path = self.tmp / "journal.sqlite3"
        first = journal.Journal(path)
        doc = project.normalize(_support.small_document(1))
        first.create_project(doc)
        first.create_job(
            job_id="j1", project_id="prj_test", project_revision=3,
            engine_tag=project.DEFAULT_ENGINE_TAG, preset="mp4-720p30", captions=True,
            dedupe_key="k1", snapshot_path=str(self.tmp / "snap.json"), source="test",
        )
        first.close()

        second = journal.Journal(path)
        self.addCleanup(second.close)
        self.assertEqual(second.get_job("j1")["state"], "queued")
        self.assertEqual(second.get_project("prj_test")["revision"], 3)

    def test_no_pending_transaction_left_open(self):
        path = self.tmp / "journal.sqlite3"
        db = journal.Journal(path)
        self.addCleanup(db.close)
        self.assertTrue(db.db.in_transaction is False)
        db.add_event("j1", message="x")
        self.assertTrue(db.db.in_transaction is False)


if __name__ == "__main__":
    unittest.main()
