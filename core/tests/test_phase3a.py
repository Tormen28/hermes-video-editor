"""Fase 3A: eventos de sonido (audioEvents) y plan de entradas."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import project
from service import worker

CORE = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((CORE / "schema" / "project.example.json").read_text(encoding="utf-8"))


def doc_with_sfx() -> dict:
    doc = copy.deepcopy(EXAMPLE)
    doc["assets"].append(
        {
            "id": "md_sfx",
            "path": "media/sfx.wav",
            "sha256": "d" * 64,
            "kind": "audio",
            "bytes": 2048,
            "rights": {"status": "generated", "license": "", "notes": "local"},
            "addedAt": "2026-11-09T07:00:00Z",
        }
    )
    doc["audioEvents"] = [
        {"id": "ae_1", "assetId": "md_sfx", "at": 1.5, "volume": 80, "fadeIn": 0.1, "fadeOut": 0.2}
    ]
    return doc


def errors_for(doc: dict) -> list[str]:
    errors, _warnings = project.inspect(doc)
    return errors


class AudioEventValidationTest(unittest.TestCase):
    def test_valid_event_passes(self) -> None:
        self.assertEqual(errors_for(doc_with_sfx()), [])

    def test_unknown_asset_rejected(self) -> None:
        doc = doc_with_sfx()
        doc["audioEvents"][0]["assetId"] = "md_nope"
        self.assertTrue(any("unknown asset" in e for e in errors_for(doc)))

    def test_non_audio_asset_rejected(self) -> None:
        doc = doc_with_sfx()
        doc["audioEvents"][0]["assetId"] = "md_01"
        self.assertTrue(any("must reference an audio asset" in e for e in errors_for(doc)))

    def test_negative_at_rejected(self) -> None:
        doc = doc_with_sfx()
        doc["audioEvents"][0]["at"] = -1
        self.assertTrue(any("at" in e for e in errors_for(doc)))

    def test_volume_range(self) -> None:
        doc = doc_with_sfx()
        doc["audioEvents"][0]["volume"] = 101
        self.assertTrue(any("volume" in e for e in errors_for(doc)))

    def test_duplicate_id_rejected(self) -> None:
        doc = doc_with_sfx()
        doc["audioEvents"].append(dict(doc["audioEvents"][0]))
        self.assertTrue(any("duplicate" in e for e in errors_for(doc)))

    def test_asset_kind_generated_is_valid(self) -> None:
        doc = doc_with_sfx()
        self.assertEqual(doc["assets"][-1]["rights"]["status"], "generated")
        self.assertEqual(errors_for(doc), [])


class AudioEventPlanTest(unittest.TestCase):
    def test_event_indexes_after_scenes(self) -> None:
        doc = doc_with_sfx()
        self.assertEqual(worker.audio_event_indexes(doc), [len(doc["scenes"])])

    def test_event_indexes_count_music_and_logo(self) -> None:
        doc = doc_with_sfx()
        doc["music"] = {"assetId": "md_sfx", "volume": 30}
        doc["assets"].append(
            {
                "id": "md_logo", "path": "media/logo.png", "sha256": "e" * 64, "kind": "image",
                "bytes": 512, "rights": {"status": "owned"}, "addedAt": "2026-11-09T07:00:00Z",
            }
        )
        doc["logo"] = {"assetId": "md_logo", "position": "bottom-right", "opacity": 0.8, "scale": 0.15}
        self.assertEqual(worker.audio_event_indexes(doc), [len(doc["scenes"]) + 2])

    def test_graph_contains_adelay_and_sfx_mix(self) -> None:
        doc = doc_with_sfx()
        cache = {
            "media/intro.mp4": {"has_video": True, "duration": 5.0, "width": 1280, "height": 720},
            "media/cierre.png": {"has_video": True, "duration": 5.0, "width": 1280, "height": 720},
            "media/sfx.wav": {"has_video": False, "duration": 2.0},
        }
        with tempfile.TemporaryDirectory() as tmp:
            graph = worker.build_filter_graph(
                doc, job_dir=Path(tmp), probe_cache=cache, captions=False, font_file=None
            )
        self.assertIn("adelay=", graph)
        self.assertIn("[asfx]", graph)

    def test_graph_without_events_is_unchanged(self) -> None:
        doc = copy.deepcopy(EXAMPLE)
        cache = {
            "media/intro.mp4": {"has_video": True, "duration": 5.0, "width": 1280, "height": 720},
            "media/cierre.png": {"has_video": True, "duration": 5.0, "width": 1280, "height": 720},
        }
        with tempfile.TemporaryDirectory() as tmp:
            graph = worker.build_filter_graph(
                doc, job_dir=Path(tmp), probe_cache=cache, captions=False, font_file=None
            )
        self.assertNotIn("adelay=", graph)


if __name__ == "__main__":
    unittest.main()
