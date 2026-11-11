"""Timeline-by-time API: read the timeline, find items at T, edit by timestamp."""

from __future__ import annotations

import threading
import unittest

import _support
import project
from service import timeline_ops as ops
from test_service import ServiceTestCase


def doc3() -> dict:
    d = _support.small_document(3)
    d["scenes"][0]["out"] = 2.0   # 0.0-2.0
    d["scenes"][1]["out"] = 3.0   # 2.0-5.0
    d["scenes"][2]["out"] = 1.5   # 5.0-6.5
    d["scenes"][1]["text"] = [{"content": "hola", "at": 0.5, "until": 2.0}]
    d["assets"].append({"id": "md_au", "path": "media/voz.wav", "sha256": "f" * 64, "kind": "audio",
                        "bytes": 10, "rights": {"status": "owned", "license": "", "notes": ""}, "addedAt": "2026-11-08T18:40:00Z"})
    return d


class TimeParsing(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(ops.parse_time(83.5), 83.5)
        self.assertEqual(ops.parse_time("1:23.5"), 83.5)
        self.assertEqual(ops.parse_time("01:23,500"), 83.5)
        self.assertEqual(ops.parse_time("1:02:03"), 3723)
        self.assertEqual(ops.fmt(193.0), "03:13.000")

    def test_rejects_junk(self):
        for bad in ("", "abc", "-1", -1, True, "1:2:3:4"):
            with self.assertRaises(ops.OpError):
                ops.parse_time(bad)


class DescribeAndAt(unittest.TestCase):
    def test_describe_has_absolute_times(self):
        t = ops.describe(doc3())
        self.assertEqual([(s["start"], s["end"]) for s in t["scenes"]], [(0, 2), (2, 5), (5, 6.5)])
        self.assertEqual(t["duration"], 6.5)
        self.assertEqual(t["scenes"][1]["text"][0]["from"], 2.5)
        self.assertEqual(t["scenes"][1]["text"][0]["to"], 4.0)

    def test_at_finds_scene_and_text(self):
        d = doc3()
        hit = ops.items_at(d, 3.0)
        self.assertEqual([s["number"] for s in hit["scenes"]], [2])
        self.assertEqual(hit["text"][0]["content"], "hola")
        self.assertEqual(ops.items_at(d, 2.1)["text"], [])
        self.assertTrue(ops.items_at(d, 6.5)["inRange"])
        self.assertFalse(ops.items_at(d, 99)["inRange"])

    def test_transition_overlap_uses_final_timeline(self):
        d = doc3()
        d["scenes"][1]["transition"] = "fade-0.5"
        t = ops.describe(d)
        self.assertEqual(t["scenes"][1]["start"], 1.5)
        self.assertEqual(t["duration"], 6.0)


class Edits(unittest.TestCase):
    def apply(self, *op_list, doc=None):
        new, summary = ops.apply_ops(doc or doc3(), list(op_list))
        project.check({**new, "projectId": "prj_test"})  # still a valid project
        return new, summary

    def test_set_text_by_time_and_by_scene(self):
        new, _ = self.apply({"op": "set_text", "time": 3.0, "content": "adiós"})
        self.assertEqual(new["scenes"][1]["text"][0]["content"], "adiós")
        new, _ = self.apply({"op": "set_text", "scene": 1, "content": "nuevo", "from": 0.5, "to": 1.5})
        self.assertEqual(new["scenes"][0]["text"][0]["at"], 0.5)
        self.assertEqual(new["scenes"][0]["text"][0]["until"], 1.5)

    def test_time_edit_replaces_the_caption_on_screen_or_adds_a_new_one(self):
        # scene 2 has "hola" on screen 2.5-4.0
        new, _ = self.apply({"op": "set_text", "time": 3.0, "content": "cambiado"})
        self.assertEqual([x["content"] for x in new["scenes"][1]["text"]], ["cambiado"])
        # 4.5 s is in scene 2 but after the caption ended -> a second caption from 4.5
        new, _ = self.apply({"op": "set_text", "time": 4.5, "content": "otro"})
        texts = new["scenes"][1]["text"]
        self.assertEqual([x["content"] for x in texts], ["hola", "otro"])
        self.assertEqual(texts[1]["at"], 2.5)

    def test_empty_text_removes_it(self):
        new, _ = self.apply({"op": "set_text", "scene": 2, "content": ""})
        self.assertEqual(new["scenes"][1]["text"], [])

    def test_trim_shifts_everything_after(self):
        new, _ = self.apply({"op": "trim", "scene": 2, "duration": 1.0})
        self.assertEqual(ops.describe(new)["scenes"][2]["start"], 3.0)
        # the caption (0.5-2.0) no longer fits in 1.0 s: clamped, not dropped
        self.assertEqual(new["scenes"][1]["text"][0]["until"], 1.0)

    def test_trim_drops_caption_that_falls_outside_and_says_so(self):
        new, summary = self.apply({"op": "trim", "scene": 2, "duration": 0.5})
        self.assertEqual(new["scenes"][1]["text"], [])
        self.assertTrue(any("quitó" in line for line in summary))

    def test_split_and_delete(self):
        new, _ = self.apply({"op": "split", "time": 3.5})
        self.assertEqual(len(new["scenes"]), 4)
        t = ops.describe(new)
        self.assertEqual([(s["start"], s["end"]) for s in t["scenes"]][1:3], [(2, 3.5), (3.5, 5)])
        new, _ = self.apply({"op": "delete_scene", "time": 3.0}, doc=new)
        self.assertEqual(len(new["scenes"]), 3)

    def test_split_too_close_to_edge_is_refused(self):
        with self.assertRaises(ops.OpError):
            ops.apply_ops(doc3(), [{"op": "split", "time": 2.02}])

    def test_move_scene(self):
        new, _ = self.apply({"op": "move_scene", "scene": 3, "to_index": 1})
        self.assertEqual([s["id"] for s in new["scenes"]], ["sc_03", "sc_01", "sc_02"])
        new, _ = self.apply({"op": "move_scene", "scene": "sc_01", "to_time": 5.0})
        self.assertEqual(new["scenes"][-1]["id"], "sc_01")

    def test_move_scene_to_first_clears_the_entry_transition(self):
        # A fade moved to the first position has nothing to blend with and makes
        # ffmpeg fail (libx264 -22) on export: the op must normalize it.
        doc = doc3()
        doc["scenes"][2]["transition"] = "fade-0.4"
        new, summary = ops.apply_ops(doc, [{"op": "move_scene", "scene": 3, "to_index": 1}])
        self.assertEqual(new["scenes"][0]["id"], "sc_03")
        self.assertEqual(new["scenes"][0]["transition"], "none")
        self.assertIn("normalizada", summary[0])
        # Moving the current first away promotes a faded scene: also normalized.
        doc = doc3()
        doc["scenes"][1]["transition"] = "fade-0.4"
        new, _ = ops.apply_ops(doc, [{"op": "move_scene", "scene": 1, "to_index": 3}])
        self.assertEqual(new["scenes"][0]["id"], "sc_02")
        self.assertEqual(new["scenes"][0]["transition"], "none")

    def test_volume_targets_and_mute(self):
        new, _ = self.apply({"op": "set_volume", "scene": 1, "volume": 30})
        self.assertEqual(new["scenes"][0]["audio"]["volume"], 30)
        new, _ = self.apply({"op": "set_volume", "scene": 1, "mute": True})
        self.assertEqual(new["scenes"][0]["audio"]["volume"], 0)
        new, _ = self.apply({"op": "set_volume", "target": "master", "volume": 70})
        self.assertEqual(new["audio"]["masterVolume"], 70)
        with self.assertRaises(ops.OpError):
            ops.apply_ops(doc3(), [{"op": "set_volume", "scene": 1, "volume": 300}])
        with self.assertRaises(ops.OpError):
            ops.apply_ops(doc3(), [{"op": "set_volume", "target": "music", "volume": 10}])

    def test_audio_events_add_move_volume_remove(self):
        new, _ = self.apply({"op": "add_audio", "assetId": "md_au", "at": "0:03.5", "volume": 90})
        event = new["audioEvents"][0]
        self.assertEqual((event["at"], event["volume"]), (3.5, 90))
        new, _ = self.apply({"op": "move_audio", "id": event["id"], "at": 1.0},
                            {"op": "set_volume", "target": "event", "id": event["id"], "volume": 20}, doc=new)
        self.assertEqual((new["audioEvents"][0]["at"], new["audioEvents"][0]["volume"]), (1.0, 20))
        new, _ = self.apply({"op": "remove_audio", "id": event["id"]}, doc=new)
        self.assertNotIn("audioEvents", new)
        with self.assertRaises(ops.OpError):
            ops.apply_ops(doc3(), [{"op": "add_audio", "assetId": "md_01", "at": 0}])  # a video, not audio

    def test_transition_and_speed(self):
        new, _ = self.apply({"op": "set_transition", "scene": 2, "value": "fade-0.5"},
                            {"op": "set_speed", "scene": 3, "speed": 2})
        self.assertEqual(new["scenes"][1]["transition"], "fade-0.5")
        self.assertEqual(ops.describe(new)["scenes"][2]["duration"], 0.75)
        with self.assertRaises(ops.OpError):
            ops.apply_ops(doc3(), [{"op": "set_speed", "scene": 1, "speed": 9}])

    def test_errors_are_plain_and_name_the_operation(self):
        for bad in ({"op": "nope"}, {"op": "trim"}, {"op": "set_text", "time": 99, "content": "x"},
                    {"op": "delete_scene", "scene": 9}, "x"):
            with self.assertRaises(ops.OpError):
                ops.apply_ops(doc3(), [bad])
        with self.assertRaises(ops.OpError) as ctx:
            ops.apply_ops(doc3(), [{"op": "set_title", "title": "ok"}, {"op": "nope"}])
        self.assertIn("operación 2", str(ctx.exception))

    def test_failed_batch_changes_nothing(self):
        d = doc3()
        before = project.dumps(d)
        with self.assertRaises(ops.OpError):
            ops.apply_ops(d, [{"op": "set_title", "title": "x"}, {"op": "nope"}])
        self.assertEqual(project.dumps(d), before)


class OverHttp(ServiceTestCase):
    def build(self):
        pid = self.new_project()["projectId"]
        self.add_clip(pid, "a.mp4", 2.0)
        self.add_clip(pid, "b.mp4", 3.0)
        return pid

    def test_timeline_at_and_edit_roundtrip(self):
        pid = self.build()
        status, tl = self.call("GET", f"/projects/{pid}/timeline")
        self.assertEqual(status, 200, tl)
        self.assertEqual(len(tl["scenes"]), 2)
        self.assertAlmostEqual(tl["duration"], 5.0, places=1)
        status, hit = self.call("GET", f"/projects/{pid}/at?t=0:03.000")
        self.assertEqual(status, 200, hit)
        self.assertEqual(hit["scenes"][0]["number"], 2)
        status, res = self.call("POST", f"/projects/{pid}/edit", {"ops": [
            {"op": "set_text", "time": 3, "content": "A las 3 s"},
            {"op": "trim", "scene": 1, "duration": 1.0},
        ]})
        self.assertEqual(status, 200, res)
        self.assertEqual(res["revision"], res["baseRevision"] + 1)
        self.assertAlmostEqual(res["timeline"]["duration"], 4.0, places=1)
        self.assertEqual(res["timeline"]["scenes"][1]["text"][0]["content"], "A las 3 s")
        # the pane sees it through the normal project endpoint (same document)
        status, body = self.call("GET", f"/projects/{pid}")
        self.assertEqual(body["revision"], res["revision"])

    def test_bad_ops_are_400_and_change_nothing(self):
        pid = self.build()
        before = self.call("GET", f"/projects/{pid}")[1]["revision"]
        status, body = self.call("POST", f"/projects/{pid}/edit", {"ops": [{"op": "trim", "scene": 9, "out": 1}]})
        self.assertEqual(status, 400, body)
        self.assertIn("operación 1", body["error"])
        status, body = self.call("POST", f"/projects/{pid}/edit", {"ops": []})
        self.assertEqual(status, 400)
        self.assertEqual(self.call("GET", f"/projects/{pid}")[1]["revision"], before)
        self.assertEqual(self.call("GET", "/projects/prj_nope/timeline")[0], 404)
        self.assertEqual(self.call("GET", f"/projects/{pid}/at?t=zzz")[0], 400)

    def test_edit_rebases_on_manual_saves_instead_of_clobbering(self):
        pid = self.build()
        # the "pane" saves a manual change first (title)...
        payload = self.call("GET", f"/projects/{pid}")[1]
        draft = payload["project"]
        draft["title"] = "Título manual"
        status, saved = self.call("PUT", f"/projects/{pid}", {"revision": payload["revision"], "draft": draft})
        self.assertEqual(status, 200, saved)
        # ...then chat edits using a STALE revision: it must apply on top, keeping the title.
        status, res = self.call("POST", f"/projects/{pid}/edit", {
            "revision": payload["revision"], "ops": [{"op": "set_text", "scene": 1, "content": "chat"}]})
        self.assertEqual(status, 200, res)
        current = self.call("GET", f"/projects/{pid}")[1]["project"]
        self.assertEqual(current["title"], "Título manual")
        self.assertEqual(current["scenes"][0]["text"][0]["content"], "chat")

    def test_strict_mode_returns_409(self):
        pid = self.build()
        rev = self.call("GET", f"/projects/{pid}")[1]["revision"]
        status, body = self.call("POST", f"/projects/{pid}/edit",
                                 {"strict": True, "revision": rev - 1, "ops": [{"op": "set_title", "title": "x"}]})
        self.assertEqual(status, 409, body)
        self.assertEqual(body["current_revision"], rev)

    def test_parallel_edits_all_land(self):
        pid = self.build()
        results = []

        def go(n):
            results.append(self.call("POST", f"/projects/{pid}/edit",
                                     {"ops": [{"op": "set_text", "scene": 1, "content": f"t{n}", "add": True}]})[0])

        threads = [threading.Thread(target=go, args=(n,)) for n in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(results, [200] * 4)
        text = self.call("GET", f"/projects/{pid}")[1]["project"]["scenes"][0]["text"]
        self.assertEqual(len(text), 4)

    def test_insert_media_at_a_time(self):
        pid = self.build()
        _support.make_clip(self.media_dir / "c.mp4", seconds=1.0)
        status, res = self.call("POST", f"/projects/{pid}/edit",
                                {"ops": [{"op": "insert_media", "path": "c.mp4", "at": 0}]})
        self.assertEqual(status, 200, res)
        self.assertEqual(res["timeline"]["scenes"][0]["path"], "c.mp4")
        self.assertEqual(len(res["timeline"]["scenes"]), 3)


if __name__ == "__main__":
    unittest.main()