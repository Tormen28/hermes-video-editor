"""Worker tests: tool allowlist, path isolation, command compilation, limits, render.

The worker is the only component that executes something, so every guarantee in
its threat model (C7) gets a test here:

* no program outside ``ffmpeg``/``ffprobe`` inside the tools directory,
* no media reference that escapes the project media root,
* no flag outside the allowlist, no filter syntax from user text,
* a child environment without secrets,
* a Job Object that really kills the tree it owns,
* a partial MP4 that is never promoted as a success.

Most cases run without ffmpeg. The ``TestRunJob`` / ``TestRunTool`` groups need
the real binary and skip when it is missing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import _support
import project
import service.worker as worker


HAVE_TOOLS = _support.tooling_available()


def tools() -> worker.Tools:
    return worker.resolve_tools(_support.TOOLS)


def junction(link: Path, target: Path) -> bool:
    """Create a Windows directory junction; False when the OS refuses."""
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, check=False,
    )
    return result.returncode == 0 and link.exists()


class WorkerTestCase(_support.TempDirTestCase):
    """Scratch layout: <tmp>/data (jobs+out) and <tmp>/media (read-only root)."""

    def setUp(self) -> None:
        super().setUp()
        self.data_root = self.tmp / "data"
        self.media_root = self.tmp / "media"
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.layout = worker.Layout(self.data_root, self.media_root).ensure()

    def document(self, scenes: int = 2, **kwargs) -> dict:
        return _support.small_document(scenes, **kwargs)

    def media_files(self, doc: dict) -> dict[str, Path]:
        return {
            scene["source"]["path"]: self.media_root / scene["source"]["path"]
            for scene in doc["scenes"]
        }

    def graph(self, doc: dict, *, captions: bool = True, probe_cache: dict | None = None) -> str:
        job_dir = self.layout.job_dir("jtest0001")
        job_dir.mkdir(parents=True, exist_ok=True)
        return worker.build_filter_graph(
            doc, job_dir=job_dir, probe_cache=probe_cache or {}, captions=captions,
        )


# --------------------------------------------------------------------------- #
# tools
# --------------------------------------------------------------------------- #


class ResolveToolsTests(WorkerTestCase):
    def test_missing_directory_is_rejected(self):
        with self.assertRaises(worker.ToolRejected):
            worker.resolve_tools(self.tmp / "no-such-tools")

    def test_directory_without_ffprobe_is_rejected(self):
        fake = self.tmp / "fake-tools"
        fake.mkdir()
        (fake / "ffmpeg.exe").write_bytes(b"MZ")
        with self.assertRaises(worker.ToolRejected):
            worker.resolve_tools(fake)

    def test_directory_instead_of_executable_is_rejected(self):
        fake = self.tmp / "fake-tools"
        (fake / "ffmpeg.exe").mkdir(parents=True)
        (fake / "ffprobe.exe").write_bytes(b"MZ")
        with self.assertRaises(worker.ToolRejected):
            worker.resolve_tools(fake)

    def test_junction_escaping_the_tools_root_is_rejected(self):
        real = self.tmp / "outside"
        real.mkdir()
        (real / "ffmpeg.exe").write_bytes(b"MZ")
        fake = self.tmp / "fake-tools"
        fake.mkdir()
        if not junction(fake / "ffmpeg.exe", real / "ffmpeg.exe"):
            self.skipTest("junction creation not permitted on this host")
        (fake / "ffprobe.exe").write_bytes(b"MZ")
        with self.assertRaises(worker.ToolRejected):
            worker.resolve_tools(fake)

    def test_real_tools_resolve_to_absolute_paths(self):
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        resolved = tools()
        self.assertTrue(resolved.ffmpeg.is_file())
        self.assertTrue(resolved.ffprobe.is_file())
        self.assertTrue(resolved.ffmpeg.is_absolute())

    def test_tool_version_reads_the_real_binary(self):
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        self.assertNotEqual(worker.tool_version(tools()), "unknown")


# --------------------------------------------------------------------------- #
# media references
# --------------------------------------------------------------------------- #


class VerifyMediaTests(WorkerTestCase):
    def make(self, relative: str, payload: bytes = b"x" * 64) -> Path:
        target = self.media_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return target

    def test_executable_extension_is_rejected_even_when_the_file_exists(self):
        self.make("media/dropper.exe")
        with self.assertRaises(worker.MediaRejected):
            worker.verify_media_file(self.media_root, "media/dropper.exe")

    def test_script_extensions_are_rejected(self):
        for name in ("run.bat", "run.ps1", "run.cmd", "run.js", "run.py"):
            with self.subTest(name=name):
                self.make(f"media/{name}")
                with self.assertRaises(worker.MediaRejected):
                    worker.verify_media_file(self.media_root, f"media/{name}")

    def test_unlisted_extension_is_rejected(self):
        self.make("media/notes.docx")
        with self.assertRaises(worker.MediaRejected):
            worker.verify_media_file(self.media_root, "media/notes.docx")

    def test_missing_extension_is_rejected(self):
        self.make("media/noext")
        with self.assertRaises(worker.MediaRejected):
            worker.verify_media_file(self.media_root, "media/noext")

    def test_empty_file_is_rejected(self):
        self.make("media/empty.mp4", b"")
        with self.assertRaises(worker.MediaRejected):
            worker.verify_media_file(self.media_root, "media/empty.mp4")

    def test_oversized_file_is_rejected_before_reading_it(self):
        self.make("media/big.mp4", b"x" * 4096)
        with self.assertRaises(worker.MediaRejected):
            worker.verify_media_file(self.media_root, "media/big.mp4", max_bytes=1024)

    def test_parent_traversal_is_rejected(self):
        for value in ("../escape.mp4", "media/../../escape.mp4", "media/.."):
            with self.subTest(value=value):
                with self.assertRaises(worker.MediaRejected):
                    worker.verify_media_file(self.media_root, value)

    def test_absolute_path_is_rejected(self):
        target = self.make("media/clip.mp4")
        with self.assertRaises(worker.MediaRejected):
            worker.verify_media_file(self.media_root, str(target))

    def test_junction_escaping_the_media_root_is_rejected(self):
        outside = self.tmp / "outside-media"
        outside.mkdir()
        (outside / "secret.mp4").write_bytes(b"x" * 64)
        if not junction(self.media_root / "linked", outside):
            self.skipTest("junction creation not permitted on this host")
        with self.assertRaises(worker.MediaRejected):
            worker.verify_media_file(self.media_root, "linked/secret.mp4")

    def test_valid_relative_path_resolves_inside_the_root(self):
        target = self.make("media/clip.mp4")
        resolved = worker.verify_media_file(self.media_root, "media/clip.mp4")
        self.assertEqual(resolved, target.resolve())

    def test_uppercase_extension_is_accepted(self):
        self.make("media/CLIP.MP4")
        resolved = worker.verify_media_file(self.media_root, "media/CLIP.MP4")
        self.assertTrue(str(resolved).endswith("CLIP.MP4"))


# --------------------------------------------------------------------------- #
# child environment
# --------------------------------------------------------------------------- #


class FilteredEnvTests(WorkerTestCase):
    def test_no_secret_variable_survives(self):
        with mock.patch.dict(os.environ, {
            "MESHY_API_KEY": "sk-should-not-leak",
            "GITHUB_TOKEN": "ghp-should-not-leak",
            "OPENAI_API_KEY": "sk-should-not-leak",
            "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        }, clear=False):
            env = worker.filtered_env(self.tmp)
        for name in env:
            self.assertNotIn("KEY", name.upper())
            self.assertNotIn("TOKEN", name.upper())
        self.assertNotIn("MESHY_API_KEY", env)
        self.assertNotIn("sk-should-not-leak", str(env.values()))

    def test_path_is_not_inherited(self):
        with mock.patch.dict(os.environ, {"PATH": r"C:\Windows\System32"}, clear=False):
            env = worker.filtered_env(self.tmp)
        self.assertNotIn("PATH", env)

    def test_temp_points_inside_the_job_directory(self):
        env = worker.filtered_env(self.tmp / "job")
        self.assertEqual(Path(env["TEMP"]), (self.tmp / "job" / "tmp").resolve())
        self.assertEqual(env["TMP"], env["TEMP"])
        self.assertTrue((self.tmp / "job" / "tmp").is_dir())

    def test_extra_variable_with_secret_marker_is_refused(self):
        with self.assertRaises(worker.WorkerError):
            worker.filtered_env(self.tmp, extra={"SERVICE_TOKEN": "abc"})

    def test_harmless_extra_variable_is_passed(self):
        env = worker.filtered_env(self.tmp, extra={"FFREPORT": "level=32"})
        self.assertEqual(env["FFREPORT"], "level=32")


# --------------------------------------------------------------------------- #
# argument allowlist
# --------------------------------------------------------------------------- #


class ArgAllowlistTests(WorkerTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.roots = [self.media_root, self.data_root]

    def test_program_outside_the_allowlist_is_rejected(self):
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed(
                ["C:/Windows/System32/cmd.exe", "-c", "echo"],
                roots=self.roots, allow_program=_support.FFMPEG,
            )

    def test_unknown_flag_is_rejected(self):
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed(
                [str(_support.FFMPEG), "-i", str(self.media_root / "a.mp4"), "-vn", "x.mp4"],
                roots=self.roots, allow_program=_support.FFMPEG,
            )

    def test_forbidden_filter_flags_are_rejected(self):
        for flag in ("-vf", "-filter_complex", "-lavfi", "-safe", "-hwaccel"):
            with self.subTest(flag=flag):
                with self.assertRaises(worker.WorkerError):
                    worker.assert_args_allowed(
                        [str(_support.FFMPEG), flag, "scale=1:1"],
                        roots=self.roots, allow_program=_support.FFMPEG,
                    )

    def test_media_outside_the_allowed_roots_is_rejected(self):
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed(
                [str(_support.FFMPEG), "-i", str(self.tmp / "elsewhere.mp4")],
                roots=self.roots, allow_program=_support.FFMPEG,
            )

    def test_executable_argument_is_rejected(self):
        target = self.media_root / "dropper.exe"
        target.write_bytes(b"MZ")
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed(
                [str(_support.FFMPEG), "-i", str(target)],
                roots=self.roots, allow_program=_support.FFMPEG,
            )

    def test_relative_media_argument_is_rejected(self):
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed(
                [str(_support.FFMPEG), "-i", "media/clip.mp4"],
                roots=self.roots, allow_program=_support.FFMPEG,
            )

    def test_control_characters_are_rejected(self):
        for value in ("line\nbreak", "null\x00byte", "carriage\rreturn"):
            with self.subTest(value=value):
                with self.assertRaises(worker.WorkerError):
                    worker.assert_args_allowed(
                        [str(_support.FFMPEG), "-loglevel", value],
                        roots=self.roots, allow_program=_support.FFMPEG,
                    )

    def test_empty_command_line_is_rejected(self):
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed([], roots=self.roots)

    def test_filter_script_must_be_absolute_and_inside_the_job(self):
        job_dir = self.layout.job_dir("jtest0001")
        job_dir.mkdir(parents=True, exist_ok=True)
        inside = job_dir / "filters.txt"
        inside.write_text("[0:v]null[vout]\n", encoding="utf-8")
        outside = self.tmp / "elsewhere.txt"
        outside.write_text("x", encoding="utf-8")

        worker.assert_args_allowed(  # absolute + inside: accepted
            [str(_support.FFMPEG), "-filter_complex_script", str(inside)],
            roots=[job_dir], allow_program=_support.FFMPEG,
        )
        with self.assertRaises(worker.WorkerError):  # relative: rejected
            worker.assert_args_allowed(
                [str(_support.FFMPEG), "-filter_complex_script", "filters.txt"],
                roots=[job_dir], allow_program=_support.FFMPEG,
            )
        with self.assertRaises(worker.WorkerError):  # outside: rejected
            worker.assert_args_allowed(
                [str(_support.FFMPEG), "-filter_complex_script", str(outside)],
                roots=[job_dir], allow_program=_support.FFMPEG,
            )

    def test_the_compiled_render_command_passes_the_allowlist(self):
        doc = self.document()
        graph = worker.inline_graph(self.graph(doc))
        command = worker.build_render_command(
            doc,
            tools=worker.Tools(ffmpeg=_support.FFMPEG, ffprobe=_support.FFPROBE, root=_support.TOOLS),
            media_files=self.media_files(doc),
            filter_graph=graph,
            output=self.data_root / "jobs" / "jtest0001" / "staging" / "output.mp4",
        )
        worker.assert_args_allowed(
            command,
            roots=[self.media_root, self.data_root / "jobs" / "jtest0001"],
            allow_program=_support.FFMPEG,
            allow_graph=graph,
        )

    def test_a_tampered_graph_is_rejected(self):
        doc = self.document()
        graph = worker.inline_graph(self.graph(doc))
        command = worker.build_render_command(
            doc,
            tools=worker.Tools(ffmpeg=_support.FFMPEG, ffprobe=_support.FFPROBE, root=_support.TOOLS),
            media_files=self.media_files(doc),
            filter_graph=graph,
            output=self.data_root / "jobs" / "jtest0001" / "staging" / "output.mp4",
        )
        index = command.index("-filter_complex")
        command[index + 1] = graph + ";movie=secret.png[evil]"
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed(
                command, roots=[self.media_root, self.data_root / "jobs" / "jtest0001"],
                allow_program=_support.FFMPEG, allow_graph=graph,
            )

    def test_an_inline_graph_without_a_compiled_match_is_forbidden(self):
        with self.assertRaises(worker.WorkerError):
            worker.assert_args_allowed(
                [str(_support.FFMPEG), "-filter_complex", "movie=x.png[out]"],
                roots=[self.media_root], allow_program=_support.FFMPEG,
            )


# --------------------------------------------------------------------------- #
# command compilation
# --------------------------------------------------------------------------- #


class CommandCompilationTests(WorkerTestCase):
    def test_unknown_preset_is_rejected(self):
        doc = self.document()
        with self.assertRaises(worker.WorkerError):
            worker.build_render_command(
                doc, tools=worker.Tools(_support.FFMPEG, _support.FFPROBE, _support.TOOLS),
                media_files=self.media_files(doc), filter_graph="[0:v]null[vout]",
                output=self.tmp / "o.mp4", preset="mp4-1080p60",
            )

    def test_empty_or_multiline_graph_is_rejected(self):
        doc = self.document()
        for graph in ("", "[0:v]null[vout];\n[0:a]anull[aout]\n"):
            with self.subTest(graph=graph):
                with self.assertRaises(worker.WorkerError):
                    worker.build_render_command(
                        doc, tools=worker.Tools(_support.FFMPEG, _support.FFPROBE, _support.TOOLS),
                        media_files=self.media_files(doc), filter_graph=graph,
                        output=self.tmp / "o.mp4",
                    )

    def test_oversized_graph_is_rejected_instead_of_truncated(self):
        doc = self.document()
        huge = "x" * (worker.MAX_FILTER_GRAPH_CHARS + 1)
        with self.assertRaises(worker.WorkerError) as caught:
            worker.build_render_command(
                doc, tools=worker.Tools(_support.FFMPEG, _support.FFPROBE, _support.TOOLS),
                media_files=self.media_files(doc), filter_graph=huge,
                output=self.tmp / "o.mp4",
            )
        self.assertIn("render fewer scenes", str(caught.exception))

    def test_image_scene_is_looped_for_its_duration(self):
        doc = self.document(1)
        doc["scenes"][0]["source"]["kind"] = "image"
        doc["scenes"][0]["source"]["path"] = "media/still.png"
        args, labels = worker.build_inputs(doc, {"media/still.png": self.media_root / "still.png"})
        self.assertEqual(labels, ["0"])
        self.assertEqual(args[:2], ["-loop", "1"])
        self.assertIn("-framerate", args)
        self.assertIn("30", args)

    def test_video_scene_is_trimmed_with_seek_and_duration(self):
        doc = self.document(1)
        doc["scenes"][0]["in"] = 0.5
        doc["scenes"][0]["out"] = 1.5
        args, _ = worker.build_inputs(doc, {"media/clip1.mp4": self.media_root / "clip1.mp4"})
        self.assertEqual(args[:2], ["-ss", "0.500"])
        self.assertIn("-t", args)
        self.assertIn("1.000", args)
        self.assertNotIn("-loop", args)

    def test_render_command_inlines_one_graph_and_no_script_file(self):
        doc = self.document()
        graph = worker.inline_graph(self.graph(doc))
        command = worker.build_render_command(
            doc, tools=worker.Tools(_support.FFMPEG, _support.FFPROBE, _support.TOOLS),
            media_files=self.media_files(doc), filter_graph=graph,
            output=self.tmp / "out.mp4",
        )
        for flag in ("-vf", "-filter_complex_script", "-lavfi", "-filter_script"):
            self.assertNotIn(flag, command)
        self.assertEqual(command.count("-filter_complex"), 1)
        self.assertEqual(command[command.index("-filter_complex") + 1], graph)
        self.assertNotIn("\n", graph)
        self.assertEqual(command.count("-map"), 2)

    def test_filter_path_uses_quotes_and_escapes_colons(self):
        self.assertEqual(worker._filter_path(Path("C:/tmp/a b.mp4")), "'C\\:/tmp/a b.mp4'")
        self.assertEqual(worker._filter_path(Path("C:/tmp/Juan's.mp4")), "'C\\:/tmp/Juan'\\''s.mp4'")
        self.assertEqual(worker._filter_path(Path(r"C:\tmp\x.png")), "'C\\:/tmp/x.png'")

    def test_user_text_never_reaches_the_filter_graph(self):
        payload = "Hola [x]drawtext=text='pwn':x=0\n:y=0,"
        doc = self.document(1)
        doc["scenes"][0]["text"] = [
            {"at": 0.0, "until": 0.8, "content": payload, "position": "bottom"},
        ]
        graph = self.graph(doc)
        self.assertNotIn("pwn", graph)
        self.assertNotIn("[x]", graph)
        text_file = self.layout.job_dir("jtest0001") / "text_0.txt"
        self.assertEqual(text_file.read_text(encoding="utf-8"), payload)
        self.assertIn("textfile=", graph)
        self.assertIn("expansion=none", graph)

    def test_accented_caption_is_written_as_utf8(self):
        caption = "Canción, año, ¿ñandú? — áéíóúüñ"
        doc = self.document(1)
        doc["scenes"][0]["text"] = [
            {"at": 0.0, "until": 0.9, "content": caption, "position": "top"},
        ]
        self.graph(doc)
        raw = (self.layout.job_dir("jtest0001") / "text_0.txt").read_bytes()
        self.assertEqual(raw.decode("utf-8"), caption)

    def test_caption_timing_is_offset_by_previous_scenes(self):
        doc = self.document(2)
        doc["scenes"][1]["text"] = [
            {"at": 0.25, "until": 0.75, "content": "segunda", "position": "center"},
        ]
        graph = self.graph(doc)
        self.assertIn("between(t,1.250,1.750)", graph)

    def test_transition_is_a_real_xfade_between_neighbours(self):
        doc = self.document(2)
        doc["scenes"][1]["transition"] = "fade-0.3"
        graph = self.graph(doc)
        # offset = duración acumulada (1.0 s) - solape (0.3 s); sin fades sueltos
        self.assertIn("[v0][v1]xfade=transition=fade:duration=0.300:offset=0.700[vcat]", graph)
        self.assertNotIn("fade=t=out", graph)
        self.assertNotIn("fade=t=in", graph)

    def test_no_transition_keeps_the_concat_cut(self):
        graph = self.graph(self.document(2))
        self.assertIn("[v0][a0][v1][a1]concat=n=2:v=1:a=1[vcat][acat]", graph)
        self.assertNotIn("xfade", graph)

    def test_master_volume_multiplies_scene_volume(self):
        doc = self.document(1)
        doc["audio"]["masterVolume"] = 80
        doc["scenes"][0]["audio"]["volume"] = 100
        graph = self.graph(doc, probe_cache={"media/clip1.mp4": {"has_audio": True}})
        self.assertIn("volume=0.8000", graph)

    def test_volume_is_clamped_to_double_gain(self):
        doc = self.document(1)
        doc["audio"]["masterVolume"] = 200
        doc["scenes"][0]["audio"]["volume"] = 200
        graph = self.graph(doc, probe_cache={"media/clip1.mp4": {"has_audio": True}})
        self.assertIn("volume=2.0000", graph)

    def test_scene_without_audio_gets_silence(self):
        doc = self.document(1)
        graph = self.graph(doc, probe_cache={})
        self.assertIn("anullsrc=channel_layout=stereo:sample_rate=48000", graph)

    def test_scene_with_audio_gets_resample_and_pad(self):
        doc = self.document(1)
        graph = self.graph(doc, probe_cache={"media/clip1.mp4": {"has_audio": True}})
        self.assertIn("aresample=48000", graph)
        self.assertIn("aformat=channel_layouts=stereo", graph)
        self.assertIn("apad", graph)
        self.assertNotIn("anullsrc", graph)

    def test_graph_is_balanced_and_ends_with_outputs(self):
        doc = self.document(3)
        graph = self.graph(doc)
        self.assertTrue(graph.endswith("\n"))
        self.assertIn("concat=n=3:v=1:a=1", graph)
        self.assertIn("[vout]", graph)
        self.assertIn("[aout]", graph)
        stripped = graph.replace(";\n", "\n")
        opened = stripped.count("[") - stripped.count("[vout]") - stripped.count("[aout]")
        closed = stripped.count("]") - stripped.count("[vout]") - stripped.count("[aout]")
        self.assertEqual(opened, closed)

    def test_total_duration_limits_both_outputs(self):
        doc = self.document(2)
        total = project.total_duration(doc)
        graph = self.graph(doc)
        self.assertIn(f"trim=duration={total:.3f},setpts=PTS-STARTPTS,format=yuv420p[vout]", graph)


# --------------------------------------------------------------------------- #
# layout and job ids
# --------------------------------------------------------------------------- #


class LayoutTests(WorkerTestCase):
    def test_created_directories_exist(self):
        self.assertTrue((self.data_root / "jobs").is_dir())
        self.assertTrue((self.data_root / "out").is_dir())

    def test_paths_stay_below_the_data_root(self):
        job_dir = self.layout.job_dir("jabc1234")
        self.assertEqual(job_dir.parent, self.data_root / "jobs")
        self.assertEqual(self.layout.output_path("jabc1234").parent, self.data_root / "out" / "jabc1234")

    def test_invalid_job_ids_are_rejected(self):
        for value in ("", "../escape", "ABC123", "j-1234", "a", "a" * 33, "j/1234", "j 1234"):
            with self.subTest(value=value):
                with self.assertRaises(worker.WorkerError):
                    self.layout.job_dir(value)

    def test_valid_job_ids_are_accepted(self):
        for value in ("jabc1234", "j0123456789abcdef", "a1b2"):
            with self.subTest(value=value):
                self.assertEqual(self.layout.check_job_id(value), value)


# --------------------------------------------------------------------------- #
# progress parser
# --------------------------------------------------------------------------- #


class ProgressParsingTests(unittest.TestCase):
    def test_frame_line(self):
        self.assertEqual(worker._progress_from_line("frame=120\n"), (120, None))

    def test_out_time_line(self):
        self.assertEqual(worker._progress_from_line("out_time_us=1500000\n"), (None, 1500000))

    def test_unknown_and_malformed_lines_are_ignored(self):
        for line in ("", "progress=continue", "frame=\n", "out_time_us=abc", "bits/s=0.0kbits/s"):
            with self.subTest(line=line):
                self.assertEqual(worker._progress_from_line(line), (None, None))


# --------------------------------------------------------------------------- #
# process control
# --------------------------------------------------------------------------- #


class RunToolTests(WorkerTestCase):
    def python_sleep(self, seconds: float) -> list[str]:
        return [sys.executable, "-c", f"import time; time.sleep({seconds})"]

    def test_timeout_stops_a_long_process(self):
        limit = worker.ProcessLimit(memory_limit_mb=512)
        limit.create()
        try:
            run = worker.run_tool(
                self.python_sleep(5), cwd=self.tmp, env=worker.filtered_env(self.tmp),
                limit=limit, timeout_s=1.0,
            )
        finally:
            limit.close()
        self.assertTrue(run.timed_out)
        self.assertFalse(run.cancelled)
        self.assertLess(run.wall_s, 4.0)

    def test_cancel_callback_stops_the_process(self):
        flag = {"stop": False}

        def should_cancel() -> bool:
            return flag["stop"]

        timer = threading.Timer(0.3, lambda: flag.__setitem__("stop", True))
        timer.start()
        self.addCleanup(timer.cancel)
        limit = worker.ProcessLimit(memory_limit_mb=512)
        limit.create()
        try:
            run = worker.run_tool(
                self.python_sleep(5), cwd=self.tmp, env=worker.filtered_env(self.tmp),
                limit=limit, timeout_s=30, should_cancel=should_cancel,
            )
        finally:
            limit.close()
        self.assertTrue(run.cancelled)
        self.assertFalse(run.timed_out)

    def test_cancel_event_stops_the_process(self):
        event = threading.Event()
        threading.Timer(0.3, event.set).start()
        limit = worker.ProcessLimit(memory_limit_mb=512)
        limit.create()
        try:
            run = worker.run_tool(
                self.python_sleep(5), cwd=self.tmp, env=worker.filtered_env(self.tmp),
                limit=limit, timeout_s=30, cancel_event=event,
            )
        finally:
            limit.close()
        self.assertTrue(run.cancelled)

    def test_stdout_lines_reach_the_callback(self):
        collected: list[str] = []
        limit = worker.ProcessLimit(memory_limit_mb=512)
        limit.create()
        try:
            run = worker.run_tool(
                [sys.executable, "-c", "print('frame=12'); print('frame=24')"],
                cwd=self.tmp, env=worker.filtered_env(self.tmp), limit=limit,
                timeout_s=20, on_line=collected.append,
            )
        finally:
            limit.close()
        self.assertEqual(run.exit_code, 0)
        self.assertEqual([line.strip() for line in collected], ["frame=12", "frame=24"])

    def test_a_raising_callback_never_kills_the_run(self):
        def boom(_line: str) -> None:
            raise RuntimeError("callback bug")

        limit = worker.ProcessLimit(memory_limit_mb=512)
        limit.create()
        try:
            run = worker.run_tool(
                [sys.executable, "-c", "print('frame=1')"],
                cwd=self.tmp, env=worker.filtered_env(self.tmp), limit=limit,
                timeout_s=20, on_line=boom,
            )
        finally:
            limit.close()
        self.assertEqual(run.exit_code, 0)

    def test_terminate_pid_tree_refuses_a_pid_that_is_not_ffmpeg(self):
        self.assertFalse(worker.terminate_pid_tree(os.getpid(), tools_root=_support.TOOLS))


class ProcessLimitTests(WorkerTestCase):
    def test_create_and_close_toggle_enforcement(self):
        limit = worker.ProcessLimit(memory_limit_mb=256)
        enforced = limit.create()
        self.addCleanup(limit.close)
        if os.name != "nt":
            self.assertFalse(enforced)
            self.skipTest("Job Objects are Windows-only")
        self.assertTrue(enforced)
        self.assertTrue(limit.enforced)
        limit.close()
        self.assertFalse(limit.enforced)
        self.assertIsNone(limit.handle)

    def test_kill_on_close_terminates_the_assigned_tree(self):
        if os.name != "nt":
            self.skipTest("Job Objects are Windows-only")
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(proc.kill)
        limit = worker.ProcessLimit(memory_limit_mb=256)
        if not limit.create():
            self.skipTest(f"Job Object unavailable: {limit.fallback}")
        self.assertTrue(limit.assign(proc.pid))
        limit.close()  # KILL_ON_JOB_CLOSE: the child must die with the handle
        proc.wait(timeout=10)
        self.assertIsNotNone(proc.returncode)


# --------------------------------------------------------------------------- #
# real render
# --------------------------------------------------------------------------- #


class RunJobTests(WorkerTestCase):
    def setUp(self) -> None:
        super().setUp()
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        self.tool = tools()

    def real_document(self, scenes: int = 2, *, duration: float = 1.0) -> dict:
        doc = self.document(scenes, width=320, height=240)
        for index, scene in enumerate(doc["scenes"]):
            clip = self.media_root / scene["source"]["path"]
            _support.make_clip(clip, seconds=1.5)
            digest = worker.sha256_file(clip)
            doc["assets"][index]["sha256"] = digest
            doc["assets"][index]["bytes"] = clip.stat().st_size
            scene["source"]["sha256"] = digest
            scene["in"] = 0.0
            scene["out"] = duration
        return doc

    def run_doc(self, doc: dict, job_id: str = "jtest0001", **kwargs) -> worker.JobResult:
        return worker.run_job(
            doc, job_id=job_id, layout=self.layout, tools=self.tool,
            preset="mp4-720p30", **kwargs,
        )

    def test_successful_render_produces_a_valid_mp4_and_cleans_derivatives(self):
        doc = self.real_document(2)
        result = self.run_doc(doc)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.state, "succeeded")
        self.assertEqual(result.stage, "done")
        self.assertEqual(result.progress, 100.0)
        self.assertEqual(result.artifacts, ["output.mp4"])

        final = Path(result.output_path)
        self.assertTrue(final.is_file())
        self.assertEqual(final, self.layout.output_path("jtest0001"))
        probe = worker.probe_media(final, self.tool)
        self.assertEqual(probe["video_codec"], "h264")
        self.assertEqual(probe["audio_codec"], "aac")
        # El preset mp4-720p30 manda el tamaño de salida; el proyecto define el lienzo de origen.
        self.assertEqual((probe["width"], probe["height"]), (1280, 720))
        self.assertAlmostEqual(probe["duration"], 2.0, delta=0.4)

        job_dir = self.layout.job_dir("jtest0001")
        self.assertFalse((job_dir / "staging" / "output.mp4").exists())
        self.assertFalse((job_dir / "filters.txt").exists())
        self.assertFalse(list(job_dir.glob("text_*.txt")))
        self.assertTrue(result.wall_s > 0)
        self.assertGreater(result.peak_memory_bytes or 0, 0)

        log = job_dir / "ffmpeg.log"
        self.assertTrue(log.is_file())
        body = log.read_text(encoding="utf-8")
        self.assertIn("[command]", body)
        self.assertNotIn(str(Path.home()), body)

    def test_caption_with_accents_renders_and_stays_out_of_the_command_line(self):
        doc = self.real_document(1)
        caption = "Añó — ñandú 日本語 & 100%"
        doc["scenes"][0]["text"] = [
            {"at": 0.0, "until": 0.9, "content": caption, "position": "bottom"},
        ]
        result = self.run_doc(doc)
        self.assertTrue(result.ok, result.error)
        log = (self.layout.job_dir("jtest0001") / "ffmpeg.log").read_text(encoding="utf-8")
        self.assertIn("textfile=", log)
        self.assertNotIn("ñandú", log)
        self.assertNotIn("日本語", log)

    def test_media_path_with_spaces_and_a_quote_renders(self):
        doc = self.real_document(1)
        original = self.media_root / doc["scenes"][0]["source"]["path"]
        renamed = self.media_root / "media" / "Juan's clip final.mp4"
        original.rename(renamed)
        digest = worker.sha256_file(renamed)
        doc["scenes"][0]["source"]["path"] = "media/Juan's clip final.mp4"
        doc["scenes"][0]["source"]["sha256"] = digest
        doc["assets"][0]["path"] = "media/Juan's clip final.mp4"
        doc["assets"][0]["sha256"] = digest
        doc["assets"][0]["bytes"] = renamed.stat().st_size

        result = self.run_doc(doc)
        self.assertTrue(result.ok, result.error)
        self.assertTrue(Path(result.output_path).is_file())

    def test_sha256_mismatch_fails_and_publishes_nothing(self):
        doc = self.real_document(1)
        doc["assets"][0]["sha256"] = "0" * 64
        result = self.run_doc(doc)
        self.assertEqual(result.state, "failed")
        self.assertIn("sha256", (result.error or "").lower())
        self.assertFalse(self.layout.output_path("jtest0001").exists())
        staging = self.layout.staging_dir("jtest0001")
        self.assertFalse(staging.exists() and any(staging.iterdir()))

    def test_missing_media_fails_without_publishing(self):
        doc = self.document(1)
        doc["scenes"][0]["source"]["path"] = "media/never-created.mp4"
        doc["assets"][0]["path"] = "media/never-created.mp4"
        result = self.run_doc(doc, verify_hash=False)
        self.assertEqual(result.state, "failed")
        self.assertTrue(result.error)
        self.assertFalse(self.layout.output_path("jtest0001").exists())

    def test_cancel_before_render_returns_cancelled(self):
        doc = self.real_document(1)
        event = threading.Event()
        event.set()
        result = self.run_doc(doc, cancel_event=event)
        self.assertEqual(result.state, "cancelled")
        self.assertFalse(self.layout.output_path("jtest0001").exists())

    def test_invalid_document_fails_before_touching_media(self):
        doc = self.document(0)
        result = self.run_doc(doc)
        self.assertEqual(result.state, "failed")
        self.assertFalse(self.layout.output_path("jtest0001").exists())

    def test_image_scene_renders_for_its_full_duration(self):
        doc = self.document(1, width=320, height=240)
        png = self.media_root / "media" / "still.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        result = _support.run_ffmpeg([
            "-y", "-f", "lavfi", "-i", "color=c=navy:s=320x240:d=1",
            "-frames:v", "1", str(png),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        doc["scenes"][0]["source"].update({"kind": "image", "path": "media/still.png"})
        doc["assets"][0].update({"kind": "image", "path": "media/still.png"})
        doc["scenes"][0]["out"] = 1.0

        rendered = self.run_doc(doc, verify_hash=False)
        self.assertTrue(rendered.ok, rendered.error)
        probe = worker.probe_media(Path(rendered.output_path), self.tool)
        self.assertAlmostEqual(probe["duration"], 1.0, delta=0.4)
        self.assertTrue(probe["has_audio"])

    def test_render_reports_progress_monotonically(self):
        doc = self.real_document(2)
        seen: list[tuple[str, float]] = []

        def progress(stage: str, pct: float, eta: float | None) -> None:
            seen.append((stage, pct))

        result = self.run_doc(doc, progress_cb=progress)
        self.assertTrue(result.ok, result.error)
        stages = [stage for stage, _ in seen]
        self.assertEqual(stages[0], "probing")
        self.assertIn("rendering", stages)
        self.assertEqual(stages[-1], "done")
        values = [pct for _, pct in seen]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[-1], 100.0)


# --------------------------------------------------------------------------- #
# job log
# --------------------------------------------------------------------------- #


class JobLogTests(WorkerTestCase):
    def run_record(self, stderr: str) -> worker.ToolRun:
        return worker.ToolRun(
            exit_code=1, cancelled=False, timed_out=False, wall_s=0.5,
            stderr_tail=stderr, stdout_tail="", peak_memory_bytes=0, limits_enforced=True,
        )

    def test_log_redacts_home_directory_and_account(self):
        user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        noise = f"open {Path.home()}\\media\\clip.mp4 as {user}"
        log = worker.write_job_log(self.tmp, ["ffmpeg", str(Path.home())], self.run_record(noise))
        body = log.read_text(encoding="utf-8")
        self.assertIn("<home>", body)
        self.assertNotIn(str(Path.home()), body)
        if len(user) >= 3:
            self.assertNotIn(user, body)

    def test_log_keeps_the_terminal_state_for_diagnosis(self):
        log = worker.write_job_log(self.tmp, ["ffmpeg", "-x"], self.run_record("boom"))
        body = log.read_text(encoding="utf-8")
        self.assertIn("[exit] 1", body)
        self.assertIn("boom", body)


# --------------------------------------------------------------------------- #
# staged output validation
# --------------------------------------------------------------------------- #


class ValidateStagedOutputTests(WorkerTestCase):
    def setUp(self) -> None:
        super().setUp()
        if not HAVE_TOOLS:
            self.skipTest("ffmpeg tools not installed")
        self.tool = tools()

    def test_missing_file_is_rejected(self):
        with self.assertRaises(worker.WorkerError):
            worker.validate_staged_output(self.tmp / "nope.mp4", self.document(1), self.tool)

    def test_empty_file_is_rejected(self):
        empty = self.tmp / "empty.mp4"
        empty.write_bytes(b"")
        with self.assertRaises(worker.WorkerError):
            worker.validate_staged_output(empty, self.document(1), self.tool)

    def test_non_video_payload_is_rejected(self):
        junk = self.tmp / "junk.mp4"
        junk.write_bytes(b"not a video at all" * 100)
        with self.assertRaises(worker.MediaRejected):
            worker.validate_staged_output(junk, self.document(1), self.tool)

    def test_wrong_resolution_is_rejected(self):
        doc = self.document(1, width=320, height=240)
        clip = self.media_root / "media" / "clip1.mp4"
        _support.make_clip(clip, seconds=1.0)
        staged = self.tmp / "staged.mp4"
        result = _support.run_ffmpeg([
            "-y", "-i", str(clip), "-t", "1.0",
            "-vf", "scale=160:120", "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", str(staged),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.assertRaises(worker.WorkerError) as caught:
            worker.validate_staged_output(staged, doc, self.tool)
        self.assertIn("resolution", str(caught.exception))

    def test_valid_render_is_accepted(self):
        doc = self.document(1, width=320, height=240)
        clip = self.media_root / "media" / "clip1.mp4"
        _support.make_clip(clip, seconds=1.0)
        staged = self.tmp / "staged.mp4"
        result = _support.run_ffmpeg([
            "-y", "-i", str(clip), "-t", "1.0",
            "-vf", "scale=320:240", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", str(staged),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        info = worker.validate_staged_output(staged, doc, self.tool, expected_duration=1.0)
        self.assertEqual(info["video_codec"], "h264")
        self.assertEqual(info["width"], 320)
        self.assertGreater(info["bytes"], 0)


if __name__ == "__main__":
    unittest.main()
