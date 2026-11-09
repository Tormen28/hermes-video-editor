"""v3 backend surface: project library, media removal, thumbnails, waveform, exports.

These run against the real server (ephemeral port, real ffmpeg) on top of the
harness in ``test_service.py``: the point is to prove the new endpoints behave
over HTTP, with optimistic revisions and on-disk caches, not just in-process.
"""

from __future__ import annotations

import json
import subprocess
import unittest
import urllib.parse
from pathlib import Path

import _support
from test_service import ServiceTestCase


class LibraryTestCase(ServiceTestCase):
    def project(self, project_id: str) -> dict:
        status, body = self.call("GET", f"/projects/{project_id}")
        self.assertEqual(status, 200, body)
        return body["project"]


class DeleteProjectTests(LibraryTestCase):
    def test_delete_requires_confirmation(self):
        created = self.new_project("Borrable")
        status, body = self.call("DELETE", f"/projects/{created['projectId']}")
        self.assertEqual(status, 400, body)
        self.assertIn("confirm", body["error"])
        self.assertEqual(self.call("GET", f"/projects/{created['projectId']}")[0], 200)

    def test_delete_removes_project_jobs_and_cache(self):
        created = self.new_project("Borrable")
        project_id = created["projectId"]
        media = self.add_clip(project_id, "borrable.mp4")
        asset_id = media["media"][0]["id"]

        status, body = self.call("POST", f"/projects/{project_id}/export", {})
        self.assertEqual(status, 202, body)
        job_id = body["jobId"]
        self.assertEqual(self.wait_terminal(job_id)["state"], "succeeded")

        # populate both caches so the purge has something to prove
        self.assertEqual(self.fetch(f"/thumbnails/{project_id}/{asset_id}?t=0.5")[0], 200)
        self.assertEqual(self.call("GET", f"/waveform/{project_id}/{asset_id}")[0], 200)
        thumbs = list((self.data_dir / "cache" / "thumbs").glob("*.jpg"))
        waves = list((self.data_dir / "cache" / "wave").glob("*.json"))
        self.assertEqual(len(thumbs), 1)
        self.assertEqual(len(waves), 1)

        status, body = self.call("DELETE", f"/projects/{project_id}?confirm=1")
        self.assertEqual(status, 200, body)
        self.assertTrue(body["deleted"])
        self.assertEqual(body["projectId"], project_id)
        self.assertGreaterEqual(body["jobsDeleted"], 1)
        self.assertTrue(body["filesPurged"])

        self.assertEqual(self.call("GET", f"/projects/{project_id}")[0], 404)
        self.assertEqual(self.call("GET", f"/jobs/{job_id}")[0], 404)
        self.assertEqual(self.call("GET", f"/exports?project={project_id}")[0], 404)
        self.assertFalse((self.data_dir / "jobs" / job_id).exists())
        self.assertFalse((self.data_dir / "out" / job_id).exists())
        self.assertEqual(list((self.data_dir / "cache" / "thumbs").glob("*.jpg")), [])
        self.assertEqual(list((self.data_dir / "cache" / "wave").glob("*.json")), [])

        listed = self.call("GET", "/projects")[1]["projects"]
        self.assertNotIn(project_id, [item["projectId"] for item in listed])

    def test_delete_accepts_confirmation_in_the_body(self):
        created = self.new_project("Borrable en cuerpo")
        project_id = created["projectId"]
        status, body = self.call("DELETE", f"/projects/{project_id}", {"confirm": True})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.call("GET", f"/projects/{project_id}")[0], 404)

    def test_delete_unknown_project_is_404(self):
        status, body = self.call("DELETE", "/projects/prj_no_existe?confirm=1")
        self.assertEqual(status, 404, body)


class DuplicateProjectTests(LibraryTestCase):
    def test_duplicate_copies_document_and_assets_under_a_new_id(self):
        created = self.new_project("Lanzamiento Q4")
        original_id = created["projectId"]
        self.add_clip(original_id, "dup1.mp4")
        self.add_clip(original_id, "dup2.mp4", seconds=1.0)
        original = self.project(original_id)

        status, body = self.call("POST", f"/projects/{original_id}/duplicate")
        self.assertEqual(status, 201, body)
        copy_id = body["projectId"]
        self.assertNotEqual(copy_id, original_id)
        self.assertEqual(body["revision"], 0)
        self.assertEqual(body["project"]["title"], "Lanzamiento Q4 (copia)")

        copy = body["project"]
        self.assertEqual(len(copy["assets"]), len(original["assets"]))
        self.assertEqual(len(copy["scenes"]), len(original["scenes"]))
        self.assertEqual(
            [asset["path"] for asset in copy["assets"]], [asset["path"] for asset in original["assets"]]
        )
        self.assertEqual(
            [asset["sha256"] for asset in copy["assets"]], [asset["sha256"] for asset in original["assets"]]
        )
        self.assertFalse({a["id"] for a in copy["assets"]} & {a["id"] for a in original["assets"]})
        self.assertFalse({s["id"] for s in copy["scenes"]} & {s["id"] for s in original["scenes"]})
        asset_ids = {asset["id"] for asset in copy["assets"]}
        for scene in copy["scenes"]:
            self.assertIn(scene["source"]["assetId"], asset_ids)

        # the original is untouched and both are listed
        self.assertEqual(self.project(original_id)["revision"], original["revision"])
        listed = [item["projectId"] for item in self.call("GET", "/projects")[1]["projects"]]
        self.assertIn(original_id, listed)
        self.assertIn(copy_id, listed)

    def test_duplicate_unknown_project_is_404(self):
        status, body = self.call("POST", "/projects/prj_no_existe/duplicate")
        self.assertEqual(status, 404, body)


class ProjectQueryTests(LibraryTestCase):
    def test_query_filters_by_title_case_insensitively(self):
        alpha = self.new_project("Campaña Alpha")["projectId"]
        beta = self.new_project("Campaña Beta")["projectId"]
        self.new_project("Otro asunto")

        status, body = self.call("GET", "/projects?query=beta")
        self.assertEqual(status, 200, body)
        self.assertEqual([item["projectId"] for item in body["projects"]], [beta])

        status, body = self.call("GET", "/projects?query=" + urllib.parse.quote("CAMPAÑA"))
        self.assertEqual(status, 200, body)
        self.assertEqual({item["projectId"] for item in body["projects"]}, {alpha, beta})

        status, body = self.call("GET", "/projects?query=zzz")
        self.assertEqual(body["projects"], [])


class RemoveMediaTests(LibraryTestCase):
    def test_remove_media_drops_asset_and_its_scenes(self):
        created = self.new_project("Con dos medios")
        project_id = created["projectId"]
        first = self.add_clip(project_id, "quitar.mp4")
        self.add_clip(project_id, "quedarse.mp4", seconds=1.0)
        asset_id = first["media"][0]["id"]
        before = self.project(project_id)
        self.assertEqual(len(before["assets"]), 2)
        self.assertEqual(len(before["scenes"]), 2)
        doomed_scene = next(s["id"] for s in before["scenes"] if s["source"]["assetId"] == asset_id)

        status, body = self.call("DELETE", f"/projects/{project_id}/media/{asset_id}")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["removedAsset"]["id"], asset_id)
        self.assertEqual(body["removedScenes"], [doomed_scene])
        self.assertEqual(body["revision"], before["revision"] + 1)

        after = self.project(project_id)
        self.assertEqual(len(after["assets"]), 1)
        self.assertEqual(len(after["scenes"]), 1)
        self.assertNotIn(asset_id, [a["id"] for a in after["assets"]])
        self.assertNotIn(doomed_scene, [s["id"] for s in after["scenes"]])
        self.assertEqual(after["revision"], before["revision"] + 1)

        # the asset is gone for good
        self.assertEqual(self.call("DELETE", f"/projects/{project_id}/media/{asset_id}")[0], 404)
        self.assertEqual(self.call("GET", f"/thumbnails/{project_id}/{asset_id}")[0], 404)

    def test_remove_media_rejects_a_stale_revision(self):
        created = self.new_project("Conflicto")
        project_id = created["projectId"]
        media = self.add_clip(project_id, "conflicto.mp4")
        asset_id = media["media"][0]["id"]
        before = self.project(project_id)

        status, body = self.call(
            "DELETE", f"/projects/{project_id}/media/{asset_id}?revision={before['revision'] - 1}"
        )
        self.assertEqual(status, 409, body)
        self.assertEqual(body["current_revision"], before["revision"])
        self.assertEqual(len(self.project(project_id)["assets"]), 1)

    def test_remove_unknown_asset_is_404(self):
        created = self.new_project("Sin ese medio")
        status, body = self.call("DELETE", f"/projects/{created['projectId']}/media/md_inexistente")
        self.assertEqual(status, 404, body)


class ThumbnailTests(LibraryTestCase):
    def test_thumbnail_is_a_cached_jpeg_at_320px(self):
        created = self.new_project("Miniaturas")
        project_id = created["projectId"]
        media = self.add_clip(project_id, "miniatura.mp4")
        asset_id = media["media"][0]["id"]

        status, raw, headers = self.fetch(f"/thumbnails/{project_id}/{asset_id}?t=0.5")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "image/jpeg")
        self.assertTrue(raw.startswith(b"\xff\xd8"), raw[:8])
        self.assertGreater(len(raw), 1000)

        cache = list((self.data_dir / "cache" / "thumbs").glob("*.jpg"))
        self.assertEqual(len(cache), 1)
        self.assertTrue(cache[0].name.endswith("_0.500.jpg"))
        first_mtime = cache[0].stat().st_mtime_ns
        first_bytes = cache[0].read_bytes()

        # second hit is served from the cache file, not re-encoded
        status, raw_again, _ = self.fetch(f"/thumbnails/{project_id}/{asset_id}?t=0.5")
        self.assertEqual(status, 200)
        self.assertEqual(raw_again, first_bytes)
        self.assertEqual(cache[0].stat().st_mtime_ns, first_mtime)

        probe = subprocess.run(
            [str(_support.FFPROBE), "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(cache[0])],
            capture_output=True, text=True, check=False,
        )
        stream = json.loads(probe.stdout)["streams"][0]
        self.assertEqual(stream["width"], 320)

    def test_thumbnail_of_unknown_asset_is_404(self):
        created = self.new_project("Fantasma")
        status, body = self.call("GET", f"/thumbnails/{created['projectId']}/md_nope")
        self.assertEqual(status, 404, body)

    def test_thumbnail_rejects_a_bad_time(self):
        created = self.new_project("Tiempo raro")
        project_id = created["projectId"]
        asset_id = self.add_clip(project_id, "tiempo.mp4")["media"][0]["id"]
        status, body = self.call("GET", f"/thumbnails/{project_id}/{asset_id}?t=abc")
        self.assertEqual(status, 400, body)


class WaveformTests(LibraryTestCase):
    def test_waveform_has_buckets_duration_and_is_cached(self):
        created = self.new_project("Ondas")
        project_id = created["projectId"]
        media = self.add_clip(project_id, "onda.mp4", seconds=1.5)
        asset_id = media["media"][0]["id"]

        status, body = self.call("GET", f"/waveform/{project_id}/{asset_id}")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["buckets"], 200)
        self.assertEqual(len(body["peaks"]), 200)
        self.assertAlmostEqual(body["duration"], 1.5, delta=0.25)
        self.assertTrue(all(0.0 <= peak <= 1.0 for peak in body["peaks"]))
        self.assertGreater(max(body["peaks"]), 0.05)  # the sine actually reached the buckets

        cached = list((self.data_dir / "cache" / "wave").glob("*.json"))
        self.assertEqual(len(cached), 1)
        on_disk = json.loads(cached[0].read_text(encoding="utf-8"))
        self.assertEqual(on_disk["peaks"], body["peaks"])
        mtime = cached[0].stat().st_mtime_ns

        status, again = self.call("GET", f"/waveform/{project_id}/{asset_id}")
        self.assertEqual(status, 200)
        self.assertEqual(again["peaks"], body["peaks"])
        self.assertEqual(cached[0].stat().st_mtime_ns, mtime)  # cache hit, no ffmpeg run

    def test_waveform_of_unknown_asset_is_404(self):
        created = self.new_project("Sin onda")
        status, body = self.call("GET", f"/waveform/{created['projectId']}/md_nope")
        self.assertEqual(status, 404, body)


class ExportHistoryTests(LibraryTestCase):
    def export(self, project_id: str) -> str:
        status, body = self.call("POST", f"/projects/{project_id}/export", {})
        self.assertEqual(status, 202, body)
        job_id = body["jobId"]
        self.assertEqual(self.wait_terminal(job_id)["state"], "succeeded")
        return job_id

    def test_exports_are_filtered_by_project_newest_first(self):
        alpha = self.new_project("Historial A")["projectId"]
        beta = self.new_project("Historial B")["projectId"]
        self.add_clip(alpha, "hist-a.mp4")
        self.add_clip(beta, "hist-b.mp4")
        alpha_job = self.export(alpha)
        beta_job = self.export(beta)

        status, body = self.call("GET", f"/exports?project={alpha}")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["projectId"], alpha)
        self.assertEqual(body["count"], 1)
        job = body["jobs"][0]
        self.assertEqual(job["jobId"], alpha_job)
        self.assertEqual(job["projectId"], alpha)
        self.assertEqual(job["state"], "succeeded")
        self.assertEqual(job["outputUrl"], f"/jobs/{alpha_job}/output")
        self.assertGreater(job["outputBytes"], 0)
        self.assertIsNone(job["error"])

        status, body = self.call("GET", f"/exports?project={beta}&limit=5")
        self.assertEqual([item["jobId"] for item in body["jobs"]], [beta_job])

        status, body = self.call("GET", "/exports?limit=10")
        self.assertEqual(status, 200)
        ids = [item["jobId"] for item in body["jobs"]]
        self.assertIn(alpha_job, ids)
        self.assertIn(beta_job, ids)
        stamps = [item["createdAt"] for item in body["jobs"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))  # newest first

    def test_exports_of_unknown_project_is_404(self):
        status, body = self.call("GET", "/exports?project=prj_no_existe")
        self.assertEqual(status, 404, body)

    def test_exports_limit_must_be_a_number(self):
        status, body = self.call("GET", "/exports?limit=nope")
        self.assertEqual(status, 400, body)


if __name__ == "__main__":
    unittest.main()
