"""Música de fondo: validación del modelo y entradas del motor."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import project
from service import worker

CORE = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((CORE / "schema" / "project.example.json").read_text(encoding="utf-8"))


def music_document() -> dict:
    doc = copy.deepcopy(EXAMPLE)
    doc["assets"].append(
        {
            "id": "md_music",
            "path": "media/music.mp3",
            "sha256": "c" * 64,
            "kind": "audio",
            "bytes": 1024,
            "rights": {"status": "licensed", "license": "CC0-1.0", "notes": "fixture"},
            "addedAt": "2026-11-08T18:42:00Z",
        }
    )
    doc["music"] = {
        "assetId": "md_music",
        "volume": 35,
        "fadeIn": 0.5,
        "fadeOut": 1.0,
        "loop": True,
        "ducking": True,
    }
    doc["audio"]["normalize"] = True
    return doc


def errors_for(doc: dict) -> list[str]:
    errors, _warnings = project.inspect(doc)
    return errors


class MusicValidationTest(unittest.TestCase):
    def test_valid_music_passes(self) -> None:
        self.assertEqual(errors_for(music_document()), [])

    def test_unknown_asset_is_rejected(self) -> None:
        doc = music_document()
        doc["music"]["assetId"] = "md_nope"
        self.assertTrue(any("unknown asset" in e for e in errors_for(doc)))

    def test_non_audio_asset_is_rejected(self) -> None:
        doc = music_document()
        video_asset = next(a for a in doc["assets"] if a["kind"] == "video")
        doc["music"]["assetId"] = video_asset["id"]
        self.assertTrue(any("must reference an audio asset" in e for e in errors_for(doc)))

    def test_volume_range(self) -> None:
        doc = music_document()
        doc["music"]["volume"] = 101
        self.assertTrue(any("music.volume" in e for e in errors_for(doc)))

    def test_loop_must_be_boolean(self) -> None:
        doc = music_document()
        doc["music"]["loop"] = "yes"
        self.assertTrue(any("music.loop" in e for e in errors_for(doc)))

    def test_normalize_must_be_boolean(self) -> None:
        doc = music_document()
        doc["audio"]["normalize"] = "true"
        self.assertTrue(any("audio.normalize" in e for e in errors_for(doc)))


class MusicInputsTest(unittest.TestCase):
    def test_music_input_is_appended_with_stream_loop(self) -> None:
        doc = music_document()
        media = {"media/intro.mp4": Path("intro.mp4"), "media/cierre.png": Path("cierre.png"), "media/music.mp3": Path("music.mp3")}
        # Sólo se usan las rutas; el motor real resuelve los archivos al ejecutar.
        args, labels = worker.build_inputs(doc, media)
        self.assertEqual(len(labels), len(doc["scenes"]))
        self.assertIn("-stream_loop", args)
        self.assertEqual(args[-1], "music.mp3")

    def test_without_music_input_is_unchanged(self) -> None:
        doc = copy.deepcopy(EXAMPLE)
        media = {"media/intro.mp4": Path("intro.mp4"), "media/cierre.png": Path("cierre.png")}
        args, labels = worker.build_inputs(doc, media)
        self.assertNotIn("-stream_loop", args)
        self.assertEqual(len(labels), len(doc["scenes"]))


if __name__ == "__main__":
    unittest.main()
