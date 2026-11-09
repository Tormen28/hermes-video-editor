"""Fase 2A: estilos/animation de texto, filtros por escena y logo de marca.

Cubre las tres capas: validación del modelo (``project.inspect``), compilación
del grafo de ffmpeg (``worker.build_filter_graph`` / ``build_input_plan``) y un
export real con ffmpeg (2 escenas + música + texto animado + filtro + logo).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest
from pathlib import Path

import _support
import project
import service.worker as worker

HAVE_TOOLS = _support.tooling_available()


def tools() -> worker.Tools:
    return worker.resolve_tools(_support.TOOLS)


def document(scenes: int = 1, **kwargs) -> dict:
    return _support.small_document(scenes, **kwargs)


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


def with_text(doc: dict, index: int = 0, **overrides) -> dict:
    item = {"content": "Hola mundo", "at": 0.0, "until": 0.8, "position": "bottom"}
    item.update(overrides)
    doc["scenes"][index]["text"] = [item]
    return doc


def errors_for(doc: dict) -> list[str]:
    errors, _warnings = project.inspect(doc)
    return errors


# --------------------------------------------------------------------------- #
# 1. modelo: texto con estilo
# --------------------------------------------------------------------------- #


class TextStyleValidationTest(unittest.TestCase):
    def test_full_style_passes(self) -> None:
        doc = with_text(
            document(),
            size=64,
            color="#FFCC00",
            border=4,
            borderColor="#101010",
            shadow=2,
            animation={"in": "fade", "out": "slide-up"},
        )
        self.assertEqual(errors_for(doc), [])

    def test_old_document_without_style_still_passes(self) -> None:
        doc = with_text(document())
        self.assertEqual(errors_for(doc), [])

    def test_size_bounds(self) -> None:
        for value in (project.TEXT_SIZE_MIN, project.TEXT_SIZE_MAX):
            self.assertEqual(errors_for(with_text(document(), size=value)), [])
        for value in (project.TEXT_SIZE_MIN - 1, project.TEXT_SIZE_MAX + 1):
            doc = with_text(document(), size=value)
            self.assertTrue(any(".size" in e for e in errors_for(doc)), value)

    def test_size_must_be_integer(self) -> None:
        doc = with_text(document(), size=42.5)
        self.assertTrue(any(".size" in e for e in errors_for(doc)))

    def test_colour_must_be_hex_rgb(self) -> None:
        for bad in ("red", "#FFF", "#GGGGGG", "0xFF0000", 16711680):
            doc = with_text(document(), color=bad)
            self.assertTrue(any(".color" in e for e in errors_for(doc)), bad)
        self.assertEqual(errors_for(with_text(document(), color="#ff00aa")), [])

    def test_border_and_shadow_ranges(self) -> None:
        self.assertEqual(errors_for(with_text(document(), border=0, shadow=10)), [])
        for key in ("border", "shadow"):
            doc = with_text(document(), **{key: -1})
            self.assertTrue(any(f".{key}" in e for e in errors_for(doc)), key)
            doc = with_text(document(), **{key: 11})
            self.assertTrue(any(f".{key}" in e for e in errors_for(doc)), key)

    def test_border_color_is_validated(self) -> None:
        doc = with_text(document(), borderColor="blue")
        self.assertTrue(any(".borderColor" in e for e in errors_for(doc)))

    def test_animation_enum(self) -> None:
        for value in ("fade", "slide-up", "slide-down", "none"):
            doc = with_text(document(), animation={"in": value, "out": value})
            self.assertEqual(errors_for(doc), [], value)
        doc = with_text(document(), animation={"in": "zoom"})
        self.assertTrue(any(".animation.in" in e for e in errors_for(doc)))
        doc = with_text(document(), animation={"out": "spin"})
        self.assertTrue(any(".animation.out" in e for e in errors_for(doc)))

    def test_animation_must_be_object(self) -> None:
        doc = with_text(document(), animation="fade")
        self.assertTrue(any(".animation" in e for e in errors_for(doc)))

    def test_normalize_fills_defaults_and_uppercases(self) -> None:
        item = project.normalize(with_text(document(), color="#aabbcc"))["scenes"][0]["text"][0]
        self.assertEqual(item["size"], project.TEXT_SIZE_DEFAULT)
        self.assertEqual(item["color"], "#AABBCC")
        self.assertEqual(item["border"], 0)
        self.assertEqual(item["borderColor"], "#000000")
        self.assertEqual(item["shadow"], 0)
        self.assertEqual(item["animation"], {"in": "none", "out": "none"})

    def test_normalize_is_idempotent(self) -> None:
        doc = with_text(document(), size=50, animation={"in": "fade"})
        once = project.normalize(copy.deepcopy(doc))
        twice = project.normalize(copy.deepcopy(once))
        self.assertEqual(once, twice)


# --------------------------------------------------------------------------- #
# 2. modelo: filtros por escena y logo
# --------------------------------------------------------------------------- #


class SceneFiltersValidationTest(unittest.TestCase):
    def test_valid_filters_pass(self) -> None:
        doc = document()
        doc["scenes"][0]["filters"] = {
            "brightness": -0.2, "contrast": 1.4, "saturation": 0.5,
            "grayscale": True, "vignette": True, "blur": 6,
        }
        self.assertEqual(errors_for(doc), [])

    def test_empty_filters_pass(self) -> None:
        doc = document()
        doc["scenes"][0]["filters"] = {}
        self.assertEqual(errors_for(doc), [])

    def test_ranges(self) -> None:
        cases = {
            "brightness": (1.5, -1.5),
            "contrast": (2.5, -0.1),
            "saturation": (3.5, -0.1),
            "blur": (21, -1),
        }
        for key, values in cases.items():
            for value in values:
                doc = document()
                doc["scenes"][0]["filters"] = {key: value}
                self.assertTrue(any(f".filters.{key}" in e for e in errors_for(doc)), (key, value))

    def test_flags_must_be_boolean(self) -> None:
        for key in project.SCENE_FILTER_FLAGS:
            doc = document()
            doc["scenes"][0]["filters"] = {key: "yes"}
            self.assertTrue(any(f".filters.{key}" in e for e in errors_for(doc)), key)

    def test_filters_must_be_object(self) -> None:
        doc = document()
        doc["scenes"][0]["filters"] = [1, 2]
        self.assertTrue(any(".filters" in e for e in errors_for(doc)))


class LogoValidationTest(unittest.TestCase):
    def test_valid_logo_passes(self) -> None:
        self.assertEqual(errors_for(with_logo(document())), [])

    def test_logo_with_defaults_passes(self) -> None:
        doc = with_logo(document())
        doc["logo"] = {"assetId": "md_logo"}
        self.assertEqual(errors_for(doc), [])

    def test_unknown_asset_is_rejected(self) -> None:
        doc = with_logo(document())
        doc["logo"]["assetId"] = "md_nope"
        self.assertTrue(any("logo.assetId" in e for e in errors_for(doc)))

    def test_non_image_asset_is_rejected(self) -> None:
        doc = with_logo(document())
        doc["logo"]["assetId"] = doc["assets"][0]["id"]  # vídeo
        self.assertTrue(any("must reference an image asset" in e for e in errors_for(doc)))

    def test_missing_asset_id_is_rejected(self) -> None:
        doc = with_logo(document())
        del doc["logo"]["assetId"]
        self.assertTrue(any("logo.assetId" in e for e in errors_for(doc)))

    def test_position_enum(self) -> None:
        for position in project.LOGO_POSITIONS:
            doc = with_logo(document())
            doc["logo"]["position"] = position
            self.assertEqual(errors_for(doc), [], position)
        doc = with_logo(document())
        doc["logo"]["position"] = "middle"
        self.assertTrue(any("logo.position" in e for e in errors_for(doc)))

    def test_opacity_and_scale_ranges(self) -> None:
        doc = with_logo(document())
        doc["logo"]["opacity"] = 1.2
        self.assertTrue(any("logo.opacity" in e for e in errors_for(doc)))
        doc = with_logo(document())
        doc["logo"]["scale"] = 0.01
        self.assertTrue(any("logo.scale" in e for e in errors_for(doc)))
        doc = with_logo(document())
        doc["logo"]["scale"] = 0.9
        self.assertTrue(any("logo.scale" in e for e in errors_for(doc)))

    def test_normalize_fills_logo_defaults(self) -> None:
        doc = with_logo(document())
        doc["logo"] = {"assetId": "md_logo"}
        logo = project.normalize(doc)["logo"]
        self.assertEqual(logo["position"], project.LOGO_POSITION_DEFAULT)
        self.assertEqual(logo["opacity"], project.LOGO_OPACITY_DEFAULT)
        self.assertEqual(logo["scale"], project.LOGO_SCALE_DEFAULT)


# --------------------------------------------------------------------------- #
# 3. motor: grafo
# --------------------------------------------------------------------------- #


class GraphTestCase(_support.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.job_dir = self.tmp / "job"
        self.job_dir.mkdir(parents=True)

    def graph(self, doc: dict) -> str:
        return worker.build_filter_graph(doc, job_dir=self.job_dir, probe_cache={}, captions=True)

    def media(self, doc: dict) -> dict[str, Path]:
        files = {scene["source"]["path"]: Path(scene["source"]["path"]) for scene in doc["scenes"]}
        for asset in doc["assets"]:
            files[asset["path"]] = Path(asset["path"])
        return files


class TextGraphTest(GraphTestCase):
    def test_static_text_has_no_animation(self) -> None:
        graph = self.graph(with_text(document(), size=64, color="#FFCC00"))
        self.assertIn("fontsize=64", graph)
        self.assertIn("fontcolor=0xFFCC00", graph)
        self.assertNotIn("alpha=", graph)
        self.assertNotIn("*40", graph)

    def test_border_and_shadow_options(self) -> None:
        doc = with_text(document(), border=4, borderColor="#101010", shadow=3)
        graph = self.graph(doc)
        self.assertIn("borderw=4", graph)
        self.assertIn("bordercolor=0x101010", graph)
        self.assertIn("shadowx=3", graph)
        self.assertIn("shadowy=3", graph)

    def test_border_and_shadow_absent_when_zero(self) -> None:
        graph = self.graph(with_text(document()))
        self.assertNotIn(":borderw=", graph)
        self.assertNotIn("shadowx=", graph)

    def test_fade_animation_adds_alpha(self) -> None:
        doc = with_text(document(), animation={"in": "fade", "out": "fade"})
        graph = self.graph(doc)
        self.assertIn("alpha='", graph)
        self.assertNotIn("*40", graph)

    def test_slide_animation_moves_y(self) -> None:
        for direction in ("slide-up", "slide-down"):
            graph = self.graph(with_text(document(), animation={"in": direction}))
            self.assertIn("y='", graph, direction)
            self.assertIn("*40", graph, direction)
            self.assertNotIn("alpha=", graph, direction)

    def test_slide_out_animation(self) -> None:
        graph = self.graph(with_text(document(), animation={"out": "slide-up"}))
        self.assertIn("y='", graph)
        self.assertIn("*40", graph)


class SceneFiltersGraphTest(GraphTestCase):
    def test_no_filters_keeps_graph_unchanged(self) -> None:
        baseline = self.graph(document())
        with_empty = document()
        with_empty["scenes"][0]["filters"] = {}
        self.assertEqual(self.graph(with_empty), baseline)

    def test_filter_chain_is_compiled_before_scale(self) -> None:
        doc = document()
        doc["scenes"][0]["filters"] = {
            "brightness": 0.1, "contrast": 1.2, "saturation": 0.8,
            "grayscale": True, "vignette": True, "blur": 4,
        }
        graph = self.graph(doc)
        chain = "eq=brightness=0.100:contrast=1.200:saturation=0.800,hue=s=0,vignette,boxblur=4"
        self.assertIn(chain, graph)
        self.assertLess(graph.index("eq=brightness"), graph.index("scale="))
        self.assertLess(graph.index("vignette"), graph.index("scale="))

    def test_only_requested_filters_appear(self) -> None:
        doc = document()
        doc["scenes"][0]["filters"] = {"grayscale": True}
        graph = self.graph(doc)
        self.assertIn("hue=s=0", graph)
        self.assertNotIn("eq=", graph)
        self.assertNotIn("vignette", graph)
        self.assertNotIn("boxblur", graph)

    def test_filters_are_per_scene(self) -> None:
        doc = document(scenes=2)
        doc["scenes"][1]["filters"] = {"vignette": True}
        graph = self.graph(doc)
        first = next(l for l in graph.splitlines() if l.startswith("[0:v]"))
        second = next(l for l in graph.splitlines() if l.startswith("[1:v]"))
        self.assertNotIn("vignette", first)
        self.assertIn("vignette", second)


class LogoGraphTest(GraphTestCase):
    def test_logo_overlay_is_present_and_last_in_video_chain(self) -> None:
        doc = with_logo(document(width=1280, height=720))
        graph = self.graph(doc)
        self.assertIn("[1:v]format=rgba,scale=192:-2,colorchannelmixer=aa=0.700[logo]", graph)
        self.assertIn("[logo]overlay=", graph)
        # el overlay va después del drawtext y antes del trim final [vout]
        self.assertLess(graph.index("overlay="), graph.index("[vout]"))
        self.assertIn("x=W-w-22:y=H-h-22", graph)

    def test_logo_scale_and_position(self) -> None:
        doc = with_logo(document(width=1280, height=720))
        doc["logo"].update({"scale": 0.25, "position": "top-left", "opacity": 1.0})
        graph = self.graph(doc)
        self.assertIn("scale=320:-2", graph)
        self.assertIn("colorchannelmixer=aa=1.000", graph)
        self.assertIn("x=22:y=22", graph)

    def test_center_position(self) -> None:
        doc = with_logo(document(width=1280, height=720))
        doc["logo"]["position"] = "center"
        graph = self.graph(doc)
        self.assertIn("x=(W-w)/2:y=(H-h)/2", graph)

    def test_no_logo_keeps_previous_graph(self) -> None:
        graph = self.graph(document())
        self.assertNotIn("overlay=", graph)
        self.assertNotIn("[logo]", graph)


class InputPlanTest(GraphTestCase):
    def test_scenes_only(self) -> None:
        doc = document(scenes=2)
        plan = worker.build_input_plan(doc, self.media(doc))
        self.assertEqual(plan.scene_labels, ["0", "1"])
        self.assertIsNone(plan.music_index)
        self.assertIsNone(plan.logo_index)

    def test_music_after_scenes(self) -> None:
        doc = with_music(document(scenes=2))
        plan = worker.build_input_plan(doc, self.media(doc))
        self.assertEqual(plan.music_index, 2)
        self.assertIsNone(plan.logo_index)
        self.assertEqual(Path(plan.args[-1]).name, "music.mp3")

    def test_logo_after_scenes_without_music(self) -> None:
        doc = with_logo(document(scenes=2))
        plan = worker.build_input_plan(doc, self.media(doc))
        self.assertIsNone(plan.music_index)
        self.assertEqual(plan.logo_index, 2)
        self.assertEqual(Path(plan.args[-1]).name, "logo.png")
        self.assertIn("-loop", plan.args)

    def test_logo_after_music(self) -> None:
        doc = with_logo(with_music(document(scenes=2)))
        plan = worker.build_input_plan(doc, self.media(doc))
        self.assertEqual(plan.music_index, 2)
        self.assertEqual(plan.logo_index, 3)
        self.assertEqual(Path(plan.args[-1]).name, "logo.png")
        graph = self.graph(doc)
        self.assertIn("[3:v]format=rgba", graph)
        self.assertIn("[2:a]", graph)

    def test_compatibility_tuple_view(self) -> None:
        doc = with_music(document(scenes=2))
        args, labels = worker.build_inputs(doc, self.media(doc))
        self.assertEqual(len(labels), 2)
        self.assertEqual(Path(args[-1]).name, "music.mp3")


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


class BrandedExportTest(_support.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data_root = self.tmp / "data"
        self.media_root = self.tmp / "media"
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.layout = worker.Layout(self.data_root, self.media_root).ensure()

    def test_two_scenes_music_text_filter_and_logo(self) -> None:
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        clip1 = _support.make_clip(self.media_root / "media/clip1.mp4", seconds=1.0, size="640x360")
        clip2 = _support.make_clip(self.media_root / "media/clip2.mp4", seconds=1.0, size="640x360")
        music = make_mp3(self.media_root / "media/music.mp3", 2.0)
        logo = make_png(self.media_root / "media/logo.png")

        doc = with_logo(with_music(document(scenes=2, width=1280, height=720)))
        doc["projectId"] = "prj_phase2a"
        for index, clip in enumerate((clip1, clip2)):
            doc["assets"][index]["sha256"] = sha256(clip)
            doc["scenes"][index]["source"]["sha256"] = sha256(clip)
            doc["assets"][index]["bytes"] = clip.stat().st_size
        doc["assets"][-2]["sha256"] = sha256(music)  # md_music
        doc["assets"][-1]["sha256"] = sha256(logo)   # md_logo

        doc["scenes"][0]["text"] = [{
            "content": "Fase 2A",
            "at": 0.1,
            "until": 0.9,
            "position": "center",
            "size": 64,
            "color": "#FFCC00",
            "border": 4,
            "borderColor": "#101010",
            "shadow": 2,
            "animation": {"in": "fade", "out": "slide-up"},
        }]
        doc["scenes"][1]["filters"] = {
            "grayscale": True, "vignette": True, "brightness": 0.05,
            "contrast": 1.1, "saturation": 0.9,
        }
        doc["scenes"][1]["text"] = [{
            "content": "Logo abajo",
            "at": 0.0,
            "until": 0.6,
            "animation": {"in": "slide-down"},
        }]

        errors = project.validate_for_export(doc)
        self.assertEqual(errors, [])

        result = worker.run_job(doc, job_id="je2a0001", layout=self.layout, tools=tools())
        self.assertEqual(result.state, "succeeded", result.error)
        output = Path(result.output_path)
        self.assertTrue(output.is_file())

        info = worker.probe_media(output, tools())
        self.assertEqual((info["width"], info["height"]), (1280, 720))
        self.assertEqual(info["video_codec"], "h264")
        self.assertEqual(info["audio_codec"], "aac")
        self.assertAlmostEqual(float(info["duration"]), 2.0, delta=0.2)

    def test_stream_rate_is_30fps(self) -> None:
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        import subprocess

        clip = _support.make_clip(self.media_root / "media/clip1.mp4", seconds=1.0, size="320x240")
        doc = document(scenes=1, width=1280, height=720)
        doc["assets"][0]["sha256"] = sha256(clip)
        doc["scenes"][0]["source"]["sha256"] = sha256(clip)
        result = worker.run_job(doc, job_id="je2a0002", layout=self.layout, tools=tools())
        self.assertEqual(result.state, "succeeded", result.error)
        raw = subprocess.run(
            [str(_support.FFPROBE), "-hide_banner", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate", "-of", "json", result.output_path],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(json.loads(raw.stdout)["streams"][0]["r_frame_rate"], "30/1")


if __name__ == "__main__":
    unittest.main()
