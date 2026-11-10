"""Baseline generation (no keys, no network): local image, music and voice."""

from __future__ import annotations

import json
import subprocess
import time
import unittest

import _support
from service import generate
from test_service import ServiceTestCase


class LocalGeneration(ServiceTestCase):
    def run_gen(self, pid, body):
        status, job = self.call("POST", f"/projects/{pid}/generate", body)
        self.assertEqual(status, 202, job)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            status, cur = self.call("GET", f"/jobs/{job['jobId']}")
            if cur["state"] in ("succeeded", "failed"):
                return cur
            time.sleep(0.2)
        self.fail("generation did not finish")

    def probe(self, relative):
        out = subprocess.run(
            [str(_support.FFPROBE), "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
             "-of", "json", str(self.media_dir / relative)], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def asset_path(self, pid):
        return self.call("GET", f"/projects/{pid}")[1]["project"]["assets"][-1]["path"]

    def test_local_image_defaults_to_cinematic_and_respects_aspect(self):
        self.assertEqual(generate._pick_style("cualquier cosa", {}), "cinematic")
        pid = self.new_project()["projectId"]
        job = self.run_gen(pid, {"kind": "image", "provider": "local", "prompt": "montaÃƒÂ±a al amanecer", "options": {"aspect": "9:16"}})
        self.assertEqual(job["state"], "succeeded", job)
        stream = self.probe(self.asset_path(pid))["streams"][0]
        self.assertLess(stream["width"], stream["height"])

    def test_local_music_has_the_requested_length(self):
        pid = self.new_project()["projectId"]
        job = self.run_gen(pid, {"kind": "music", "provider": "local", "prompt": "ÃƒÂ©pica", "duration": 4, "options": {"mood": "epic"}})
        self.assertEqual(job["state"], "succeeded", job)
        self.assertAlmostEqual(float(self.probe(self.asset_path(pid))["format"]["duration"]), 4.0, delta=0.6)

    @unittest.skipUnless(generate.voice_status().get("local"), "no local Windows voice on this machine")
    def test_local_voice_keeps_the_whole_sentence(self):
        """Regression: silence trimming used to cut the speech at its first pause."""
        pid = self.new_project()["projectId"]
        text = "Hola. Este es el editor de vÃƒÂ­deo. Ahora hacemos una pausa, y seguimos hablando un poco mÃƒÂ¡s."
        job = self.run_gen(pid, {"kind": "voice", "provider": "local", "prompt": text})
        self.assertEqual(job["state"], "succeeded", job)
        info = self.probe(self.asset_path(pid))
        self.assertEqual(info["streams"][0]["codec_type"], "audio")
        self.assertGreater(float(info["format"]["duration"]), 3.0)

    def test_voice_prompt_over_the_limit_is_refused(self):
        pid = self.new_project()["projectId"]
        status, body = self.call("POST", f"/projects/{pid}/generate", {"kind": "voice", "provider": "local", "prompt": "x" * (generate.VOICE_TEXT_MAX + 1)})
        self.assertEqual(status, 400, body)

    def test_http_provider_without_url_is_a_clear_400_and_the_base_keeps_working(self):
        pid = self.new_project()["projectId"]
        status, body = self.call("POST", f"/projects/{pid}/generate", {"kind": "voice", "provider": "http", "prompt": "hola"})
        self.assertEqual(status, 400, body)
        self.assertIn("VE_PROVIDER_VOICE_URL", body["error"])
        self.assertNotIn("Bearer", json.dumps(body))
        # absence of Plus never blocks the baseline
        self.assertEqual(self.run_gen(pid, {"kind": "image", "provider": "local", "prompt": "ok"})["state"], "succeeded")


if __name__ == "__main__":
    unittest.main()