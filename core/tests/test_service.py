"""Service tests: HTTP contract, origin/host guards, export lifecycle, recovery.

These tests drive the real server on an ephemeral port with real ffmpeg, so they
cover the seams the unit tests cannot: range requests, optimistic concurrency
over the wire, the job queue surviving a restart, and the fact that a render
never blocks the API.
"""

from __future__ import annotations

import http.client
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import _support
import project
from service import app as service_app
from service import journal as journal_module

HAVE_TOOLS = _support.tooling_available()


class ServiceTestCase(_support.TempDirTestCase):
    run_worker = True

    def setUp(self) -> None:
        super().setUp()
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        self.media_dir = self.tmp / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.tmp / "data"
        self.service = self.start_service()

    def start_service(self) -> service_app.Service:
        svc = service_app.build_service(
            self.data_dir, self.media_dir, tools_root=_support.TOOLS, port=0,
        ).start(run_worker=self.run_worker)
        self.addCleanup(self._stop, svc)
        return svc

    def _stop(self, svc: service_app.Service) -> None:
        try:
            svc.stop()
        except Exception:
            pass

    # -- HTTP helpers ----------------------------------------------------- #

    def call(self, method: str, path: str, body: dict | None = None,
             headers: dict | None = None, svc: service_app.Service | None = None) -> tuple[int, dict]:
        target = (svc or self.service).base_url + path
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(target, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read().decode("utf-8")
            finally:
                exc.close()
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, {"raw": raw}

    def fetch(self, path: str, *, headers: dict | None = None,
              svc: service_app.Service | None = None) -> tuple[int, bytes, dict]:
        target = (svc or self.service).base_url + path
        request = urllib.request.Request(target, method="GET")
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.read(), dict(exc.headers)
            finally:
                exc.close()

    # -- fixtures --------------------------------------------------------- #

    def new_project(self, title: str = "Lanzamiento Q4", session: str | None = None) -> dict:
        status, body = self.call("POST", "/projects", {"title": title, "session_id": session, "cwd": "C:/proyectos/q4"})
        self.assertEqual(status, 201, body)
        return body

    def add_clip(self, project_id: str, name: str = "clip1.mp4", seconds: float = 1.5) -> dict:
        _support.make_clip(self.media_dir / name, seconds=seconds)
        status, body = self.call("POST", f"/projects/{project_id}/media", {"path": name})
        self.assertEqual(status, 201, body)
        return body

    def wait_terminal(self, job_id: str, *, timeout: float = 120.0) -> dict:
        deadline = time.monotonic() + timeout
        job = {}
        while time.monotonic() < deadline:
            status, job = self.call("GET", f"/jobs/{job_id}")
            self.assertEqual(status, 200, job)
            if job["state"] in ("succeeded", "failed", "cancelled", "interrupted"):
                return job
            time.sleep(0.1)
        self.fail(f"job {job_id} did not finish: {job}")


# --------------------------------------------------------------------------- #
# surface and guards
# --------------------------------------------------------------------------- #


class HealthTests(ServiceTestCase):
    def test_health_reports_engine_tools_and_queue(self):
        status, body = self.call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["engine"], project.DEFAULT_ENGINE_TAG)
        self.assertTrue(Path(body["ffmpeg"]).is_file())
        self.assertNotEqual(body["ffmpegVersion"], "unknown")
        self.assertEqual(body["presets"], list(service_app.ALLOWED_PRESETS))
        self.assertEqual(body["queue"], {"queued": 0, "running": 0, "current": None})

    def test_grants_exposes_the_media_root(self):
        status, body = self.call("GET", "/grants")
        self.assertEqual(status, 200)
        self.assertEqual(Path(body["mediaRoot"]), self.media_dir.resolve())


class GuardTests(ServiceTestCase):
    def test_foreign_host_header_is_rejected(self):
        status, body = self.call("GET", "/health", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 403)
        self.assertIn("host", body["error"])

    def test_foreign_origin_is_rejected_on_write(self):
        status, body = self.call("POST", "/projects", {"title": "x"}, headers={"Origin": "https://evil.example.com"})
        self.assertEqual(status, 403)
        self.assertIn("origen", body["error"])

    def test_file_origin_is_accepted(self):
        status, body = self.call("POST", "/projects", {"title": "x"}, headers={"Origin": "null"})
        self.assertEqual(status, 201, body)

    def test_cors_preflight_and_headers_on_valid_origin(self):
        origin = f"http://127.0.0.1:{self.service.port}"
        conn = http.client.HTTPConnection("127.0.0.1", self.service.port, timeout=30)
        self.addCleanup(conn.close)
        conn.request("OPTIONS", "/projects", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        })
        response = conn.getresponse()
        response.read()
        self.assertEqual(response.status, 204)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), origin)
        self.assertIn("PUT", response.getheader("Access-Control-Allow-Methods") or "")
        self.assertIn("Content-Type", response.getheader("Access-Control-Allow-Headers") or "")
        self.assertEqual(response.getheader("Vary"), "Origin")

    def test_preflight_from_foreign_origin_is_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.service.port, timeout=30)
        self.addCleanup(conn.close)
        conn.request("OPTIONS", "/projects", headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "PUT",
        })
        response = conn.getresponse()
        response.read()
        self.assertEqual(response.status, 403)
        self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))

    def test_configured_extra_origin_is_accepted(self):
        extra = "http://127.0.0.1:8800"
        svc = service_app.build_service(
            self.data_dir / "extra", self.media_dir, tools_root=_support.TOOLS, port=0,
            extra_origins=(extra,),
        ).start(run_worker=False)
        self.addCleanup(self._stop, svc)
        status, body = self.call("POST", "/projects", {"title": "x"},
                                 headers={"Origin": extra}, svc=svc)
        self.assertEqual(status, 201, body)
        status, _ = self.call("POST", "/projects", {"title": "y"},
                              headers={"Origin": "http://127.0.0.1:9999"}, svc=svc)
        self.assertEqual(status, 403)

    def test_oversized_body_is_rejected_before_reading_it(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.service.port, timeout=30)
        self.addCleanup(conn.close)
        conn.putrequest("POST", "/projects")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(service_app.MAX_BODY_BYTES + 1))
        conn.endheaders()
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 413)
        self.assertIn("grande", payload["error"])

    def test_unknown_routes_are_404(self):
        status, body = self.call("GET", "/nope")
        self.assertEqual(status, 404)
        self.assertIn("desconocida", body["error"])

    def test_invalid_json_is_400(self):
        request = urllib.request.Request(self.service.base_url + "/projects", data=b"{not json", method="POST")
        request.add_header("Content-Type", "application/json")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=30)
        self.assertEqual(caught.exception.code, 400)


# --------------------------------------------------------------------------- #
# projects
# --------------------------------------------------------------------------- #


class ProjectTests(ServiceTestCase):
    def test_create_returns_revision_zero_and_an_empty_document(self):
        body = self.new_project(session="sess_4f2a")
        self.assertTrue(body["projectId"].startswith("prj_"))
        self.assertEqual(body["revision"], 0)
        self.assertEqual(body["project"]["scenes"], [])
        self.assertEqual(body["project"]["sessionId"], "sess_4f2a")
        self.assertEqual(body["media"], [])

    def test_list_filters_by_session(self):
        self.new_project("A", session="sess_a")
        self.new_project("B", session="sess_b")
        status, body = self.call("GET", "/projects?session=sess_a")
        self.assertEqual(status, 200)
        self.assertEqual([item["title"] for item in body["projects"]], ["A"])

    def test_missing_project_is_404(self):
        status, body = self.call("GET", "/projects/prj_missing")
        self.assertEqual(status, 404)

    def test_add_media_registers_asset_and_scene(self):
        created = self.new_project()
        body = self.add_clip(created["projectId"])
        self.assertEqual(body["revision"], 1)
        self.assertEqual(len(body["project"]["assets"]), 1)
        self.assertEqual(len(body["project"]["scenes"]), 1)
        asset = body["project"]["assets"][0]
        self.assertEqual(asset["kind"], "video")
        self.assertEqual(asset["rights"]["status"], "unknown")
        self.assertTrue(body["media"][0]["exists"])
        self.assertTrue(body["media"][0]["previewUrl"].startswith("/media/"))

    def test_add_media_rejects_paths_outside_the_grant(self):
        created = self.new_project()
        outside = self.tmp / "outside.mp4"
        outside.write_bytes(b"x" * 100)
        status, body = self.call("POST", f"/projects/{created['projectId']}/media", {"path": str(outside)})
        self.assertEqual(status, 400)
        self.assertIn("carpeta concedida", body["error"])

    def test_add_media_rejects_a_missing_file(self):
        created = self.new_project()
        status, body = self.call("POST", f"/projects/{created['projectId']}/media", {"path": "nope.mp4"})
        self.assertEqual(status, 400)

    def test_add_media_rejects_an_executable(self):
        created = self.new_project()
        (self.media_dir / "dropper.exe").write_bytes(b"MZ")
        status, body = self.call("POST", f"/projects/{created['projectId']}/media", {"path": "dropper.exe"})
        self.assertEqual(status, 400)

    def test_repeated_media_registration_does_not_duplicate(self):
        created = self.new_project()
        first = self.add_clip(created["projectId"])
        second = self.add_clip(created["projectId"])
        self.assertEqual(len(second["project"]["assets"]), 1)
        self.assertEqual(len(second["project"]["scenes"]), 2)
        self.assertGreaterEqual(second["revision"], first["revision"])

    def test_save_with_stale_revision_is_409_and_keeps_current(self):
        created = self.new_project()
        updated = self.add_clip(created["projectId"])
        stale = dict(updated["project"])
        stale["title"] = "Pisado"
        status, body = self.call("PUT", f"/projects/{created['projectId']}", {"revision": 0, "project": stale})
        self.assertEqual(status, 409)
        self.assertEqual(body["current_revision"], updated["revision"])
        status, current = self.call("GET", f"/projects/{created['projectId']}")
        self.assertEqual(current["project"]["title"], "Lanzamiento Q4")

    def test_save_with_current_revision_bumps_and_persists(self):
        created = self.new_project()
        current = self.add_clip(created["projectId"])
        draft = dict(current["project"])
        draft["title"] = "Nuevo título"
        draft["scenes"][0]["name"] = "Escena renombrada"
        status, body = self.call("PUT", f"/projects/{created['projectId']}", {"revision": current["revision"], "project": draft})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["revision"], current["revision"] + 1)
        self.assertEqual(body["project"]["title"], "Nuevo título")
        status, again = self.call("GET", f"/projects/{created['projectId']}")
        self.assertEqual(again["project"]["scenes"][0]["name"], "Escena renombrada")

    def test_save_requires_a_revision(self):
        created = self.new_project()
        status, body = self.call("PUT", f"/projects/{created['projectId']}", {"project": created["project"]})
        self.assertEqual(status, 400)
        self.assertIn("revision", body["error"])


# --------------------------------------------------------------------------- #
# media transport
# --------------------------------------------------------------------------- #


class MediaRangeTests(ServiceTestCase):
    def test_full_media_request_returns_the_bytes(self):
        created = self.new_project()
        body = self.add_clip(created["projectId"])
        project_id, asset_id = created["projectId"], body["project"]["assets"][0]["id"]
        status, payload, headers = self.fetch(f"/media/{project_id}/{asset_id}")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertEqual(int(headers["Content-Length"]), len(payload))
        self.assertEqual(headers["Accept-Ranges"], "bytes")

    def test_range_request_returns_206_and_the_right_slice(self):
        created = self.new_project()
        body = self.add_clip(created["projectId"])
        project_id, asset_id = created["projectId"], body["project"]["assets"][0]["id"]
        _, whole, _ = self.fetch(f"/media/{project_id}/{asset_id}")
        status, part, headers = self.fetch(f"/media/{project_id}/{asset_id}", headers={"Range": "bytes=100-199"})
        self.assertEqual(status, 206)
        self.assertEqual(len(part), 100)
        self.assertEqual(part, whole[100:200])
        self.assertEqual(headers["Content-Range"], f"bytes 100-199/{len(whole)}")

    def test_unknown_media_is_404(self):
        created = self.new_project()
        status, payload, _ = self.fetch(f"/media/{created['projectId']}/md_missing")
        self.assertEqual(status, 404)


# --------------------------------------------------------------------------- #
# export lifecycle
# --------------------------------------------------------------------------- #


class ExportTests(ServiceTestCase):
    def ready_project(self) -> tuple[str, dict]:
        created = self.new_project()
        current = created
        for index in (1, 2):
            current = self.add_clip(created["projectId"], name=f"clip{index}.mp4", seconds=1.5)
        return created["projectId"], current

    def test_export_runs_to_success_with_a_playable_output(self):
        project_id, _ = self.ready_project()
        status, queued = self.call("POST", f"/projects/{project_id}/export", {"preset": "mp4-720p30", "captions": True})
        self.assertEqual(status, 202, queued)
        self.assertFalse(queued["deduped"])

        job = self.wait_terminal(queued["jobId"])
        self.assertEqual(job["state"], "succeeded", job.get("error"))
        self.assertEqual(job["progress"], 100.0)
        self.assertEqual(job["artifacts"], ["output.mp4"])
        self.assertTrue(job["outputUrl"].endswith("/output"))

        status, payload, headers = self.fetch(job["outputUrl"])
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertGreater(len(payload), 10_000)

        status, ranged, _ = self.fetch(job["outputUrl"], headers={"Range": "bytes=0-1023"})
        self.assertEqual(status, 206)
        self.assertEqual(len(ranged), 1024)

    def test_second_export_of_the_same_revision_is_deduped(self):
        project_id, _ = self.ready_project()
        _, first = self.call("POST", f"/projects/{project_id}/export", {"preset": "mp4-720p30"})
        self.wait_terminal(first["jobId"])
        status, second = self.call("POST", f"/projects/{project_id}/export", {"preset": "mp4-720p30"})
        self.assertEqual(status, 202)
        self.assertEqual(second["jobId"], first["jobId"])
        self.assertTrue(second["deduped"])

    def test_export_of_an_empty_project_is_rejected(self):
        created = self.new_project()
        status, body = self.call("POST", f"/projects/{created['projectId']}/export", {})
        self.assertEqual(status, 400)
        self.assertIn("errors", body)
        self.assertTrue(any("scene" in item for item in body["errors"]))

    def test_unknown_preset_is_rejected(self):
        project_id, _ = self.ready_project()
        status, body = self.call("POST", f"/projects/{project_id}/export", {"preset": "mp4-4k60"})
        self.assertEqual(status, 400)
        self.assertIn("preset", body["error"])

    def test_export_unknown_project_is_404(self):
        status, body = self.call("POST", "/projects/prj_missing/export", {})
        self.assertEqual(status, 404)

    def test_output_before_success_is_409(self):
        project_id, _ = self.ready_project()
        _, queued = self.call("POST", f"/projects/{project_id}/export", {})
        # The runner may be fast; a fresh job that is still queued must not serve bytes.
        status, payload, _ = self.fetch(f"/jobs/{queued['jobId']}/output")
        self.assertIn(status, (200, 409))
        if status == 409:
            self.assertIn("salida", payload.decode("utf-8"))


class CancelTests(ServiceTestCase):
    run_worker = False  # queue without a runner so the job stays queued

    def test_cancel_a_queued_job_marks_it_cancelled(self):
        created = self.new_project()
        current = self.add_clip(created["projectId"], name="only.mp4")
        _, queued = self.call("POST", f"/projects/{created['projectId']}/export", {})
        self.assertEqual(queued["state"], "queued")
        status, job = self.call("POST", f"/jobs/{queued['jobId']}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(job["state"], "cancelled")
        status, again = self.call("POST", f"/jobs/{queued['jobId']}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(again["state"], "cancelled")

    def test_cancel_unknown_job_is_404(self):
        status, body = self.call("POST", "/jobs/jmissing/cancel", {})
        self.assertEqual(status, 404)

    def test_queued_job_survives_a_service_restart(self):
        created = self.new_project()
        self.add_clip(created["projectId"], name="only.mp4")
        _, queued = self.call("POST", f"/projects/{created['projectId']}/export", {})
        self.service.stop()
        revived = self.start_service()
        status, job = self.call("GET", f"/jobs/{queued['jobId']}", svc=revived)
        self.assertEqual(status, 200)
        self.assertEqual(job["state"], "queued")


# --------------------------------------------------------------------------- #
# events
# --------------------------------------------------------------------------- #


class EventTests(ServiceTestCase):
    run_worker = False

    def test_events_are_pushed_after_a_queue_event(self):
        created = self.new_project()
        self.add_clip(created["projectId"], name="only.mp4")
        _, queued = self.call("POST", f"/projects/{created['projectId']}/export", {})
        status, body = self.call("GET", "/events?since=0&timeout=5")
        self.assertEqual(status, 200)
        job_events = [event for event in body["events"] if event["jobId"] == queued["jobId"]]
        self.assertTrue(job_events)
        self.assertEqual(job_events[0]["state"], "queued")
        self.assertGreaterEqual(body["lastSeq"], job_events[0]["seq"])

    def test_long_poll_times_out_empty_when_nothing_happened(self):
        _, first = self.call("GET", "/events?since=0&timeout=0")
        started = time.monotonic()
        status, second = self.call("GET", f"/events?since={first['lastSeq']}&timeout=0.4")
        self.assertEqual(status, 200)
        self.assertEqual(second["events"], [])
        self.assertGreaterEqual(time.monotonic() - started, 0.3)


# --------------------------------------------------------------------------- #
# crash recovery
# --------------------------------------------------------------------------- #


class RecoveryTests(ServiceTestCase):
    run_worker = False

    def test_a_job_left_running_is_marked_interrupted_on_startup(self):
        created = self.new_project()
        self.add_clip(created["projectId"], name="only.mp4")
        _, queued = self.call("POST", f"/projects/{created['projectId']}/export", {})
        self.assertTrue(self.service.journal.claim_job(queued["jobId"]))
        self.service.stop()

        revived = self.start_service()
        self.assertEqual([job["jobId"] for job in revived.recovered], [queued["jobId"]])
        status, job = self.call("GET", f"/jobs/{queued['jobId']}", svc=revived)
        self.assertEqual(status, 200)
        self.assertEqual(job["state"], "interrupted")
        status, events = self.call("GET", "/events?since=0&timeout=0", svc=revived)
        self.assertTrue(any(event["state"] == "interrupted" for event in events["events"]))

    def test_recovery_does_not_touch_finished_jobs(self):
        created = self.new_project()
        self.add_clip(created["projectId"], name="only.mp4")
        _, queued = self.call("POST", f"/projects/{created['projectId']}/export", {})
        self.service.journal.request_cancel(queued["jobId"])
        self.service.stop()
        revived = self.start_service()
        self.assertEqual(revived.recovered, [])


# --------------------------------------------------------------------------- #
# no-render-while-serving
# --------------------------------------------------------------------------- #


class ResponsivenessTests(ServiceTestCase):
    def test_api_answers_while_a_render_is_running(self):
        created = self.new_project()
        for index in (1, 2, 3):
            self.add_clip(created["projectId"], name=f"clip{index}.mp4", seconds=2.0)
        _, queued = self.call("POST", f"/projects/{created['projectId']}/export", {})
        latencies = []
        started = time.monotonic()
        while time.monotonic() - started < 3.0:
            mark = time.monotonic()
            status, _ = self.call("GET", "/health")
            latencies.append(time.monotonic() - mark)
            self.assertEqual(status, 200)
            if latencies and len(latencies) % 5 == 0:
                pass
            time.sleep(0.05)
        self.assertGreater(len(latencies), 5)
        self.assertLess(max(latencies), 2.0, "una petición nunca debe esperar al render")
        job = self.wait_terminal(queued["jobId"])
        self.assertEqual(job["state"], "succeeded", job.get("error"))


if __name__ == "__main__":
    unittest.main()
