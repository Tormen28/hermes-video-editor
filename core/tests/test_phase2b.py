"""Fase 2B: transiciones reales (xfade) entre escenas consecutivas.

Cubre las cuatro capas del cambio:

1. modelo: catálogo de estilos, duración 0.1–2.0 y compatibilidad con documentos
   que sólo conocían ``fade-<seconds>`` (``project.transition_seconds``);
2. timeline: solapes, arranque absoluto de cada escena y duración final;
3. grafo de ffmpeg: ``xfade`` con ``offset`` acumulado, cadena que termina en
   ``[vcat]``, drawtext con tiempos absolutos y el camino sin transiciones
   byte-idéntico al de antes de 2B;
4. export real con ffmpeg: 2 escenas + slideleft + música + texto + logo.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import _support
import project
import service.worker as worker

HAVE_TOOLS = _support.tooling_available()


def tools() -> worker.Tools:
    return worker.resolve_tools(_support.TOOLS)


def document(scenes: int = 2, **kwargs) -> dict:
    return _support.small_document(scenes, **kwargs)


def errors_for(doc: dict) -> list[str]:
    return project.validate(doc)


def with_music(doc: dict) -> dict:
    doc["assets"].append(
        {
            "id": "md_music",
            "path": "media/music.mp3",
            "sha256": "c" * 64,
            "kind": "audio",
            "bytes": 4096,
            "rights": {"status": "licensed", "license": "CC0-1.0", "notes": ""},
            "addedAt": "2026-11-08T18:45:00Z",
        }
    )
    doc["music"] = {"assetId": "md_music", "volume": 30, "fadeIn": 0.2, "fadeOut": 0.2, "loop": True}
    return doc


def with_logo(doc: dict) -> dict:
    doc["assets"].append(
        {
            "id": "md_logo",
            "path": "media/logo.png",
            "sha256": "d" * 64,
            "kind": "image",
            "bytes": 2048,
            "rights": {"status": "owned", "license": "propio", "notes": ""},
            "addedAt": "2026-11-08T18:45:00Z",
        }
    )
    doc["logo"] = {"assetId": "md_logo", "position": "bottom-right", "opacity": 0.7, "scale": 0.15}
    return doc


def graph_for(doc: dict, job_dir: Path) -> str:
    job_dir.mkdir(parents=True, exist_ok=True)
    return worker.build_filter_graph(doc, job_dir=job_dir, probe_cache={})


# --------------------------------------------------------------------------- #
# 1. modelo: catálogo y validación
# --------------------------------------------------------------------------- #


class TransitionCatalogueTest(unittest.TestCase):
    def test_catalogue_matches_the_public_list(self) -> None:
        self.assertEqual(
            list(project.TRANSITION_STYLES),
            ["fade", "slideleft", "slideright", "wipeleft", "wiperight", "circleopen", "zoomin"],
        )

    def test_every_style_is_accepted_with_a_valid_duration(self) -> None:
        for style in project.TRANSITION_STYLES:
            with self.subTest(style=style):
                doc = document(2)
                doc["scenes"][1]["transition"] = f"{style}-0.5"
                self.assertEqual(errors_for(doc), [])
                self.assertEqual(project.transition_style(f"{style}-0.5"), style)
                self.assertEqual(project.transition_seconds(f"{style}-0.5"), 0.5)

    def test_none_is_a_cut(self) -> None:
        doc = document(2)
        doc["scenes"][1]["transition"] = "none"
        self.assertEqual(errors_for(doc), [])
        self.assertEqual(project.transition_style("none"), "none")
        self.assertEqual(project.transition_seconds("none"), 0.0)

    def test_missing_transition_behaves_like_none(self) -> None:
        # documento viejo: normalize lo rellena y el cálculo no explota
        doc = document(2)
        del doc["scenes"][1]["transition"]
        normalized = project.normalize(doc)
        self.assertEqual(normalized["scenes"][1]["transition"], "none")
        self.assertEqual(project.transition_seconds(normalized["scenes"][1]["transition"]), 0.0)
        self.assertEqual(errors_for(normalized), [])

    def test_unknown_style_is_rejected(self) -> None:
        for value in ("crossfade-0.3", "fade", "slide-0.3", "zoomout-0.5", "zoom-0.5", "none-0.3"):
            with self.subTest(value=value):
                doc = document(2)
                doc["scenes"][1]["transition"] = value
                self.assertTrue(
                    any(".transition" in error for error in errors_for(doc)),
                    f"{value} debería rechazarse",
                )

    def test_duration_outside_the_range_is_rejected(self) -> None:
        for value in ("fade-0.05", "fade-0", "wipeleft-2.5", "circleopen-3.0"):
            with self.subTest(value=value):
                doc = document(2)
                doc["scenes"][1]["transition"] = value
                errors = errors_for(doc)
                self.assertTrue(
                    any("between 0.1 and 2.0" in error for error in errors),
                    f"{value} debería rechazarse por duración: {errors}",
                )

    def test_duration_bounds_are_inclusive(self) -> None:
        for value in ("fade-0.1", "fade-2.0"):
            with self.subTest(value=value):
                doc = document(2)
                doc["scenes"][0]["out"] = doc["scenes"][0]["in"] + 2.0
                doc["scenes"][1]["out"] = doc["scenes"][1]["in"] + 2.0
                doc["scenes"][1]["transition"] = value
                self.assertEqual(errors_for(doc), [])

    def test_transition_longer_than_its_own_scene_is_rejected(self) -> None:
        doc = document(2)
        doc["scenes"][1]["transition"] = "fade-2.0"
        doc["scenes"][1]["out"] = doc["scenes"][1]["in"] + 1.0
        self.assertTrue(any("longer than the scene" in e for e in errors_for(doc)))

    def test_transition_longer_than_the_previous_scene_is_rejected(self) -> None:
        doc = document(2)
        doc["scenes"][0]["out"] = doc["scenes"][0]["in"] + 0.4
        doc["scenes"][1]["out"] = doc["scenes"][1]["in"] + 1.5
        doc["scenes"][1]["transition"] = "slideleft-0.5"
        self.assertTrue(any("longer than the previous scene" in e for e in errors_for(doc)))

    def test_transition_must_be_a_string(self) -> None:
        doc = document(2)
        doc["scenes"][1]["transition"] = 0.3
        self.assertTrue(any(".transition" in e for e in errors_for(doc)))


# --------------------------------------------------------------------------- #
# 2. timeline: solapes, arranques y duración final
# --------------------------------------------------------------------------- #


class TimelineMathTest(unittest.TestCase):
    def test_two_scenes_with_one_crossfade(self) -> None:
        doc = document(2)
        doc["scenes"][1]["transition"] = "slideleft-0.5"
        self.assertEqual(project.transition_overlaps(doc), [0.0, 0.5])
        self.assertEqual(project.scene_starts(doc), [0.0, 0.5])
        self.assertAlmostEqual(project.timeline_duration(doc), 1.5, places=3)
        self.assertAlmostEqual(project.total_duration(doc), 2.0, places=3)
        self.assertTrue(project.has_crossfade(doc))

    def test_three_scenes_with_two_crossfades(self) -> None:
        doc = document(3)
        doc["scenes"][1]["transition"] = "fade-0.5"
        doc["scenes"][2]["transition"] = "circleopen-0.3"
        self.assertEqual(project.transition_overlaps(doc), [0.0, 0.5, 0.3])
        self.assertEqual(project.scene_starts(doc), [0.0, 0.5, 1.2])
        self.assertAlmostEqual(project.timeline_duration(doc), 2.2, places=3)

    def test_first_scene_never_overlaps(self) -> None:
        doc = document(2)
        doc["scenes"][0]["transition"] = "fade-0.4"
        self.assertEqual(project.transition_overlaps(doc), [0.0, 0.0])
        self.assertFalse(project.has_crossfade(doc))
        self.assertEqual(project.scene_starts(doc), [0.0, 1.0])
        self.assertAlmostEqual(project.timeline_duration(doc), 2.0, places=3)

    def test_no_transition_keeps_the_raw_sum(self) -> None:
        doc = document(3)
        self.assertFalse(project.has_crossfade(doc))
        self.assertEqual(project.timeline_duration(doc), project.total_duration(doc))
        self.assertEqual(project.scene_starts(doc), [0.0, 1.0, 2.0])

    def test_overlap_is_clamped_to_the_shortest_neighbour(self) -> None:
        # documento sin validar: el render no puede recibir un offset negativo
        doc = document(2)
        doc["scenes"][0]["out"] = doc["scenes"][0]["in"] + 0.3
        doc["scenes"][1]["transition"] = "zoomin-2.0"
        # sin validar, el solape se recorta a la escena corta (0.3 s), nunca 2.0
        self.assertEqual(project.transition_overlaps(doc), [0.0, 0.3])
        self.assertAlmostEqual(project.timeline_duration(doc), 1.0, places=3)


# --------------------------------------------------------------------------- #
# 3. grafo de ffmpeg
# --------------------------------------------------------------------------- #


class CrossfadeGraphTest(_support.TempDirTestCase):
    def graph(self, doc: dict) -> str:
        return graph_for(doc, self.tmp / "job")

    def test_two_scenes_emit_one_xfade_with_accumulated_offset(self) -> None:
        doc = document(2)
        doc["scenes"][1]["transition"] = "slideleft-0.5"
        graph = self.graph(doc)
        self.assertIn("[v0][v1]xfade=transition=slideleft:duration=0.500:offset=0.500[vcat]", graph)
        self.assertNotIn("concat=n=2:v=1:a=1", graph)
        # el audio sigue siendo un concat plano (la transición es visual)
        self.assertIn("[a0][a1]concat=n=2:v=0:a=1[acat]", graph)
        self.assertIn("trim=duration=1.500,setpts=PTS-STARTPTS,format=yuv420p[vout]", graph)
        self.assertIn("atrim=duration=1.500", graph)

    def test_three_scenes_chain_two_xfades(self) -> None:
        doc = document(3)
        doc["scenes"][1]["transition"] = "wipeleft-0.5"
        doc["scenes"][2]["transition"] = "zoomin-0.3"
        graph = self.graph(doc)
        self.assertIn("[v0][v1]xfade=transition=wipeleft:duration=0.500:offset=0.500[vx1]", graph)
        self.assertIn("[vx1][v2]xfade=transition=zoomin:duration=0.300:offset=1.200[vcat]", graph)
        self.assertIn("trim=duration=2.200", graph)

    def test_cut_between_crossfades_uses_concat_for_that_pair(self) -> None:
        doc = document(3)
        doc["scenes"][1]["transition"] = "slideright-0.4"
        doc["scenes"][2]["transition"] = "none"
        graph = self.graph(doc)
        self.assertIn("[v0][v1]xfade=transition=slideright:duration=0.400:offset=0.600[vx1]", graph)
        self.assertIn("[vx1][v2]concat=n=2:v=1:a=0[vcat]", graph)
        self.assertIn("trim=duration=2.600", graph)

    def test_drawtext_uses_absolute_times_on_the_final_line(self) -> None:
        doc = document(2)
        doc["scenes"][1]["transition"] = "fade-0.5"
        doc["scenes"][1]["text"] = [
            {"content": "segunda", "at": 0.1, "until": 0.6, "position": "center"}
        ]
        graph = self.graph(doc)
        # la escena 2 arranca en 0.5 s: 0.5+0.1 = 0.600 y 0.5+0.6 = 1.100
        self.assertIn("between(t,0.600,1.100)", graph)

    def test_graph_without_transitions_is_the_legacy_one(self) -> None:
        doc = document(3)
        graph = self.graph(doc)
        self.assertNotIn("xfade", graph)
        self.assertIn("[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[vcat][acat]", graph)
        self.assertIn("fps=30/1,format=yuv420p[v0]", graph)
        self.assertIn("trim=duration=3.000,setpts=PTS-STARTPTS,format=yuv420p[vout]", graph)

    def test_legacy_path_is_reached_only_when_nothing_overlaps(self) -> None:
        doc = document(3)
        original = project.has_crossfade
        try:
            project.has_crossfade = lambda _doc: False  # type: ignore[assignment]
            forced = self.graph(doc)
        finally:
            project.has_crossfade = original  # type: ignore[assignment]
        self.assertEqual(forced, self.graph(doc))

    def test_audio_chain_never_uses_acrossfade(self) -> None:
        doc = document(3)
        doc["scenes"][1]["transition"] = "fade-0.5"
        doc["scenes"][2]["transition"] = "fade-0.5"
        graph = self.graph(doc)
        self.assertNotIn("acrossfade", graph)
        self.assertIn("[a0][a1][a2]concat=n=3:v=0:a=1[acat]", graph)


# --------------------------------------------------------------------------- #
# 4. export real
# --------------------------------------------------------------------------- #


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_mp3(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = _support.run_ffmpeg([
        "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:a", "libmp3lame", "-b:a", "128k", str(path),
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:600])
    return path


def make_png(path: Path, size: str = "240x120") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = _support.run_ffmpeg([
        "-y", "-f", "lavfi", "-i", f"color=c=red@0.9:s={size}:d=1",
        "-frames:v", "1", str(path),
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:600])
    return path


class CrossfadeExportTest(_support.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data_root = self.tmp / "data"
        self.media_root = self.tmp / "media"
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.layout = worker.Layout(self.data_root, self.media_root).ensure()

    def test_two_scenes_slideleft_music_text_and_logo(self) -> None:
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        clip1 = _support.make_clip(self.media_root / "media/clip1.mp4", seconds=1.0, size="640x360")
        clip2 = _support.make_clip(self.media_root / "media/clip2.mp4", seconds=1.0, size="640x360")
        music = make_mp3(self.media_root / "media/music.mp3", 2.0)
        logo = make_png(self.media_root / "media/logo.png")

        doc = with_logo(with_music(document(2, width=1280, height=720)))
        doc["projectId"] = "prj_phase2b"
        for index, clip in enumerate((clip1, clip2)):
            doc["assets"][index]["sha256"] = sha256(clip)
            doc["assets"][index]["bytes"] = clip.stat().st_size
            doc["scenes"][index]["source"]["sha256"] = sha256(clip)
        doc["assets"][-2]["sha256"] = sha256(music)  # md_music
        doc["assets"][-1]["sha256"] = sha256(logo)   # md_logo

        doc["scenes"][1]["transition"] = "slideleft-0.5"
        doc["scenes"][0]["text"] = [
            {"content": "Fase 2B", "at": 0.1, "until": 0.8, "position": "center", "size": 64}
        ]
        doc["scenes"][1]["text"] = [
            {"content": "Transición real", "at": 0.1, "until": 0.6, "position": "bottom"}
        ]

        self.assertEqual(project.validate_for_export(doc), [])
        expected = project.timeline_duration(doc)
        self.assertAlmostEqual(expected, 1.5, places=3)

        result = worker.run_job(doc, job_id="je2b0001", layout=self.layout, tools=tools())
        self.assertEqual(result.state, "succeeded", result.error)
        output = Path(result.output_path)
        self.assertTrue(output.is_file())

        info = worker.probe_media(output, tools())
        self.assertEqual((info["width"], info["height"]), (1280, 720))
        self.assertEqual(info["video_codec"], "h264")
        self.assertEqual(info["audio_codec"], "aac")
        self.assertTrue(info["has_audio"])
        self.assertAlmostEqual(float(info["duration"]), expected, delta=0.15)
        self.assertLess(float(info["duration"]), 2.0)  # el solape acortó el vídeo

    def test_crossfade_keeps_30fps(self) -> None:
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        import subprocess

        clip1 = _support.make_clip(self.media_root / "media/clip1.mp4", seconds=1.0, size="320x240")
        clip2 = _support.make_clip(self.media_root / "media/clip2.mp4", seconds=1.0, size="320x240")
        doc = document(2, width=1280, height=720)
        for index, clip in enumerate((clip1, clip2)):
            digest = sha256(clip)
            doc["assets"][index]["sha256"] = digest
            doc["assets"][index]["bytes"] = clip.stat().st_size
            doc["scenes"][index]["source"]["sha256"] = digest
        doc["scenes"][1]["transition"] = "circleopen-0.4"

        result = worker.run_job(doc, job_id="je2b0002", layout=self.layout, tools=tools())
        self.assertEqual(result.state, "succeeded", result.error)
        raw = subprocess.run(
            [str(_support.FFPROBE), "-hide_banner", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate", "-of", "json", result.output_path],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(json.loads(raw.stdout)["streams"][0]["r_frame_rate"], "30/1")


if __name__ == "__main__":
    unittest.main()
