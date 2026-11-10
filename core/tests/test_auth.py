"""Token + origin guard: the fix for the file:// / Origin: null local-CSRF hole."""

from __future__ import annotations

import http.client
import json
import os
import stat
import sys
import unittest
from pathlib import Path

import _support
from service import app as service_app
from service import auth

TOKEN = "t" * 43


class AuthTests(_support.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        if not _support.tooling_available():
            self.skipTest("ffmpeg tools not installed")
        media = self.tmp / "media"
        media.mkdir()
        self.svc = service_app.build_service(
            self.tmp / "data", media, tools_root=_support.TOOLS, port=0, token=TOKEN
        ).start(run_worker=False)
        self.addCleanup(self.svc.stop)

    def req(self, method, path, *, headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.svc.port, timeout=20)
        h = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body)
            h.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        try:
            parsed = json.loads(raw) if raw else {}
        except ValueError:
            parsed = {"raw": raw[:80]}
        return r.status, parsed, {k.lower(): v for k, v in r.getheaders()}

    def test_missing_token_is_401_even_for_reads(self):
        for path in ("/projects", "/grants", "/library"):
            status, body, _ = self.req("GET", path)
            self.assertEqual(status, 401, (path, body))

    def test_wrong_token_is_403(self):
        status, _, _ = self.req("GET", "/projects", headers={"X-VE-Token": "nope"})
        self.assertEqual(status, 403)

    def test_right_token_works_and_null_origin_is_the_pane(self):
        status, _, h = self.req("GET", "/projects", headers={"X-VE-Token": TOKEN, "Origin": "null"})
        self.assertEqual(status, 200)
        self.assertEqual(h.get("access-control-allow-origin"), "null")

    def test_null_origin_without_token_cannot_write(self):
        """A sandboxed page also sends Origin: null -- it has no token, so it is stopped."""
        status, _, h = self.req("POST", "/projects", headers={"Origin": "null"}, body={"title": "x"})
        self.assertEqual(status, 401)
        self.assertNotIn("access-control-allow-origin", h)

    def test_foreign_origin_is_403_even_with_the_token(self):
        status, _, _ = self.req("POST", "/projects", headers={"Origin": "https://evil.example", "X-VE-Token": TOKEN}, body={"title": "x"})
        self.assertEqual(status, 403)

    def test_no_wildcard_cors_anywhere(self):
        for headers in ({}, {"Origin": "null"}, {"X-VE-Token": TOKEN, "Origin": "null"}):
            _, _, h = self.req("GET", "/health", headers=headers)
            self.assertNotEqual(h.get("access-control-allow-origin"), "*")

    def test_health_is_minimal_without_token(self):
        status, body, _ = self.req("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"ok", "service", "authRequired"})
        self.assertTrue(body["authRequired"])
        status, full, _ = self.req("GET", "/health", headers={"X-VE-Token": TOKEN})
        self.assertIn("ffmpeg", full)

    def test_preflight_is_allowed_and_names_the_token_header(self):
        status, _, h = self.req("OPTIONS", "/projects", headers={
            "Origin": "null", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-ve-token"})
        self.assertEqual(status, 204)
        self.assertIn("x-ve-token", h["access-control-allow-headers"].lower())

    def test_admin_stop_needs_the_token(self):
        status, _, _ = self.req("POST", "/admin/stop", body={})
        self.assertEqual(status, 401)
        status, _, _ = self.req("GET", "/health", headers={"X-VE-Token": TOKEN})
        self.assertEqual(status, 200)  # still alive

    def test_passive_media_get_needs_no_token_but_is_never_cors_readable(self):
        status, _, h = self.req("GET", "/media/prj_x/md_x", headers={"Origin": "null"})
        self.assertEqual(status, 404)  # reached the handler (not 401)
        self.assertNotIn("access-control-allow-origin", h)

    def test_token_never_echoed(self):
        _, body, h = self.req("GET", "/health", headers={"X-VE-Token": TOKEN})
        self.assertNotIn(TOKEN, json.dumps(body))
        self.assertNotIn(TOKEN, json.dumps(h))

    def test_foreign_host_header_is_still_rejected(self):
        status, _, _ = self.req("GET", "/health", headers={"Host": "evil.example", "X-VE-Token": TOKEN})
        self.assertEqual(status, 403)


class TokenFileTests(_support.TempDirTestCase):
    def test_create_then_reuse(self):
        path = self.tmp / "sub" / "service.token"
        first = auth.load_or_create_token(path)
        self.assertGreaterEqual(len(first), 32)
        self.assertEqual(auth.load_or_create_token(path), first)
        self.assertEqual(auth.read_token(path), first)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_read_does_not_create(self):
        self.assertIsNone(auth.read_token(self.tmp / "missing.token"))

    def test_matches_is_exact(self):
        self.assertTrue(auth.matches("abc", "abc"))
        for bad in ("", None, "abd", "abcd"):
            self.assertFalse(auth.matches("abc", bad))


if __name__ == "__main__":
    unittest.main()