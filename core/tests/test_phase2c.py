"""Fase 2C: presets de export, Ken Burns y velocidad de escena."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import project
from service import worker

CORE = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((CORE / "schema" / "project.example.json").read_text(encoding="utf-8"))


def doc() -> dict:
    return copy.deepcopy(EXAMPLE)


def errors_for(doc_: dict) -> list[str]:
    errors, _warnings = project.inspect(doc_)
    return errors


class PresetTest(unittest.TestCase):
    def test_catalog_sizes(self) -> None:
        self.assertEqual((worker.preset_spec("mp4-720p30").width, worker.preset_spec("mp4-720p30").height), (1280, 720))
        self.assertEqual((worker.preset_spec("mp4-1080p30").width, worker.preset_spec("mp4-1080p30").height), (1920, 1080))
        self.assertEqual((worker.preset_spec("mp4-720p30-vertical").width, worker.preset_spec("mp4-720p30-vertical").height), (720, 1280))
        self.assertEqual((worker.preset_spec("mp4-720p30-square").width, worker.preset_spec("mp4-720p30-square").height), (720, 720))
        self.assertTrue(worker.preset_spec("mp4-1080p30").experimental)

    def test_unknown_preset_raises(self) -> None:
        with self.assertRaises(worker.WorkerError):
            worker.preset_spec("mp4-4k60")

    def test_fit_filters_pad_for_native_and_crop_for_target(self) -> None:
        native = " ".join(worker._fit_filters(1280, 720, native=True))
        self.assertIn("pad", native)
        vertical = " ".join(worker._fit_filters(720, 1280, native=False))
        self.assertIn("crop=720:1280", vertical)


class KenBurnsValidationTest(unittest.TestCase):
    def test_image_scene_accepts_ken_burns(self) -> None:
        d = doc()
        image = next(s for s in d["scenes"] if s["source"]["kind"] == "image")
        image["kenBurns"] = {"zoom": 1.2, "pan": "left"}
        self.assertEqual(errors_for(d), [])

    def test_video_scene_rejects_ken_burns(self) -> None:
        d = doc()
        video = next(s for s in d["scenes"] if s["source"]["kind"] == "video")
        video["kenBurns"] = {"zoom": 1.2, "pan": "none"}
        self.assertTrue(any("only applies to image scenes" in e for e in errors_for(d)))

    def test_zoom_range_is_enforced(self) -> None:
        d = doc()
        image = next(s for s in d["scenes"] if s["source"]["kind"] == "image")
        image["kenBurns"] = {"zoom": 1.6, "pan": "none"}
        self.assertTrue(any("kenBurns.zoom" in e for e in errors_for(d)))

    def test_pan_enum_is_enforced(self) -> None:
        d = doc()
        image = next(s for s in d["scenes"] if s["source"]["kind"] == "image")
        image["kenBurns"] = {"zoom": 1.2, "pan": "diagonal"}
        self.assertTrue(any("kenBurns.pan" in e for e in errors_for(d)))


class SpeedTest(unittest.TestCase):
    def test_speed_range(self) -> None:
        d = doc()
        d["scenes"][0]["speed"] = 2.5
        self.assertTrue(any("speed" in e for e in errors_for(d)))

    def test_duration_divides_by_speed(self) -> None:
        d = doc()
        d["scenes"][0]["speed"] = 2.0
        span = float(d["scenes"][0]["out"]) - float(d["scenes"][0]["in"])
        self.assertAlmostEqual(project.scene_duration(d["scenes"][0]), span / 2.0, places=3)

    def test_timeline_uses_adjusted_duration(self) -> None:
        base = project.timeline_duration(doc())
        d = doc()
        d["scenes"][0]["speed"] = 2.0
        span = float(d["scenes"][0]["out"]) - float(d["scenes"][0]["in"])
        self.assertAlmostEqual(project.timeline_duration(d), base - span / 2.0, places=3)

    def test_default_speed_is_one(self) -> None:
        self.assertEqual(project.scene_speed(doc()["scenes"][0]), 1.0)
        self.assertAlmostEqual(project.scene_duration(doc()["scenes"][0]), 3.2, places=3)


if __name__ == "__main__":
    unittest.main()
