"""Path isolation tests: traversal, absolute paths, device names, symlinks."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

import _support  # noqa: F401  (sys.path bootstrap)
import paths


class NormalizeRelativeTests(unittest.TestCase):
    def test_accepts_plain_nested_path(self):
        self.assertEqual(paths.normalize_relative("media/clip 01.mp4"), "media/clip 01.mp4")

    def test_collapses_dot_and_duplicate_separators(self):
        self.assertEqual(paths.normalize_relative("media/./sub//clip.mp4"), "media/sub/clip.mp4")

    def test_rejects_parent_traversal(self):
        for value in ("../secret.mp4", "media/../../x.mp4", "..", "media/.."):
            with self.subTest(value=value):
                with self.assertRaises(paths.PathError):
                    paths.normalize_relative(value)

    def test_rejects_absolute_and_drive_paths(self):
        for value in ("/etc/passwd", "C:/Windows/win.ini", "C:relative.mp4", "\\\\server\\share\\x.mp4"):
            with self.subTest(value=value):
                with self.assertRaises(paths.PathError):
                    paths.normalize_relative(value)

    def test_rejects_backslashes(self):
        with self.assertRaises(paths.PathError):
            paths.normalize_relative("media\\clip.mp4")

    def test_rejects_alternate_data_stream(self):
        with self.assertRaises(paths.PathError):
            paths.normalize_relative("media/clip.mp4:hidden")

    def test_rejects_reserved_device_names(self):
        for value in ("CON", "media/nul.mp4", "com1.txt", "LPT9"):
            with self.subTest(value=value):
                with self.assertRaises(paths.PathError):
                    paths.normalize_relative(value)

    def test_rejects_trailing_dot_or_space(self):
        for value in ("media/clip.mp4.", "media/clip.mp4 "):
            with self.subTest(value=value):
                with self.assertRaises(paths.PathError):
                    paths.normalize_relative(value)

    def test_rejects_control_characters_and_empty(self):
        for value in ("", "   ", "media/\x00clip.mp4", "media/\nclip.mp4"):
            with self.subTest(value=value):
                with self.assertRaises(paths.PathError):
                    paths.normalize_relative(value)

    def test_rejects_overlong_segment(self):
        with self.assertRaises(paths.PathError):
            paths.normalize_relative("media/" + "a" * (paths.MAX_SEGMENT + 1) + ".mp4")


class ResolveWithinTests(_support.TempDirTestCase):
    def test_resolves_inside_root(self):
        root = self.tmp / "root"
        (root / "media").mkdir(parents=True)
        (root / "media" / "clip.mp4").write_bytes(b"x")
        resolved = paths.resolve_within(root, "media/clip.mp4", must_exist=True)
        self.assertEqual(resolved, Path(os.path.realpath(root / "media" / "clip.mp4")))

    def test_missing_file_flagged_only_when_required(self):
        root = self.tmp / "root"
        root.mkdir()
        paths.resolve_within(root, "media/none.mp4")
        with self.assertRaises(paths.PathError):
            paths.resolve_within(root, "media/none.mp4", must_exist=True)

    def test_prefix_sibling_directory_is_not_inside(self):
        root = self.tmp / "root"
        sibling = self.tmp / "root_evil"
        root.mkdir()
        sibling.mkdir()
        (sibling / "x.mp4").write_bytes(b"x")
        self.assertFalse(paths.is_within(sibling / "x.mp4", root))

    def test_symlink_escape_is_rejected(self):
        root = self.tmp / "root"
        outside = self.tmp / "outside"
        root.mkdir()
        outside.mkdir()
        (outside / "secret.mp4").write_bytes(b"secret")
        link = root / "link"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:  # pragma: no cover - privilege dependent
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaises(paths.PathError):
            paths.resolve_within(root, "link/secret.mp4", must_exist=True)


class JobArtifactTests(unittest.TestCase):
    ALLOWED = {"output.mp4", "poster.jpg"}

    def test_accepts_published_artifact(self):
        self.assertEqual(paths.safe_job_artifact("output.mp4", allowed=self.ALLOWED), "output.mp4")

    def test_rejects_unknown_artifact(self):
        with self.assertRaises(paths.PathError):
            paths.safe_job_artifact("passwd", allowed=self.ALLOWED)

    def test_rejects_traversal_and_separators(self):
        for value in ("../output.mp4", "sub/output.mp4", "sub\\output.mp4", "C:output.mp4"):
            with self.subTest(value=value):
                with self.assertRaises(paths.PathError):
                    paths.safe_job_artifact(value, allowed=self.ALLOWED)

    def test_rejects_hidden_and_reserved(self):
        for value in (".output.mp4", "CON", ""):
            with self.subTest(value=value):
                with self.assertRaises(paths.PathError):
                    paths.safe_job_artifact(value, allowed={value})


if __name__ == "__main__":
    unittest.main()
