"""Project document tests: schema, validation, migration, atomic save, revisions."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import _support
import project


class SchemaFileTests(unittest.TestCase):
    def test_schema_is_valid_json_and_matches_version(self):
        schema = json.loads((_support.CORE / "schema" / "project.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], project.SCHEMA_VERSION)
        self.assertIn("scene", schema["$defs"])
        self.assertIn("asset", schema["$defs"])

    def test_example_document_satisfies_its_own_schema_contract(self):
        schema = json.loads((_support.CORE / "schema" / "project.schema.json").read_text(encoding="utf-8"))
        example = _support.example_document()
        self.assertTrue(set(schema["required"]).issubset(example))
        for name in schema["$defs"]["scene"]["required"]:
            self.assertIn(name, example["scenes"][0])
        for name in schema["$defs"]["asset"]["required"]:
            self.assertIn(name, example["assets"][0])
        self.assertEqual(project.validate(example), [])

    def test_example_validates_with_jsonschema_when_available(self):
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest("jsonschema not installed (optional cross-check)")
        schema = json.loads((_support.CORE / "schema" / "project.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(_support.example_document(), schema)


class ValidationTests(unittest.TestCase):
    def base(self) -> dict:
        return _support.small_document(2)

    def assert_invalid(self, doc: dict, needle: str):
        errors = project.validate(doc)
        self.assertTrue(errors, "document unexpectedly valid")
        joined = " | ".join(errors)
        self.assertIn(needle, joined, f"expected {needle!r} in: {joined}")
        with self.assertRaises(project.ValidationError):
            project.check(doc)

    def test_example_document_is_valid(self):
        self.assertEqual(project.validate(_support.example_document()), [])

    def test_rejects_bad_project_id(self):
        doc = self.base()
        doc["projectId"] = "../escape"
        self.assert_invalid(doc, "projectId")

    def test_rejects_negative_revision(self):
        doc = self.base()
        doc["revision"] = -1
        self.assert_invalid(doc, "revision")

    def test_rejects_base_revision_ahead_of_revision(self):
        doc = self.base()
        doc["baseRevision"] = doc["revision"] + 1
        self.assert_invalid(doc, "baseRevision")

    def test_rejects_bad_engine_tag(self):
        doc = self.base()
        doc["engineTag"] = "FFmpeg 9.0.1"
        self.assert_invalid(doc, "engineTag")

    def test_rejects_odd_dimension(self):
        doc = self.base()
        doc["width"] = 1281
        self.assert_invalid(doc, "width")

    def test_rejects_zero_fps_denominator(self):
        doc = self.base()
        doc["fps"] = {"num": 30, "den": 0}
        self.assert_invalid(doc, "fps.den")

    def test_rejects_media_path_traversal(self):
        doc = self.base()
        doc["scenes"][0]["source"]["path"] = "../../etc/passwd"
        doc["assets"][0]["path"] = "../../etc/passwd"
        self.assert_invalid(doc, "must not contain '..'")

    def test_rejects_unnormalized_media_path(self):
        doc = self.base()
        doc["scenes"][0]["source"]["path"] = "./media/clip1.mp4"
        self.assert_invalid(doc, "normalized")

    def test_rejects_null_source_without_relink_flag(self):
        doc = self.base()
        doc["scenes"][0]["source"]["path"] = None
        doc["scenes"][0]["needsRelink"] = False
        self.assert_invalid(doc, "needsRelink")

    def test_accepts_null_source_with_relink_flag(self):
        doc = self.base()
        doc["scenes"][0]["source"] = {
            "assetId": None,
            "path": None,
            "sha256": None,
            "kind": "video",
        }
        doc["scenes"][0]["needsRelink"] = True
        self.assertEqual(project.validate(doc), [])

    def test_rejects_unknown_asset_reference(self):
        doc = self.base()
        doc["scenes"][0]["source"]["assetId"] = "md_missing"
        self.assert_invalid(doc, "unknown asset")

    def test_rejects_source_hash_mismatch_with_asset(self):
        doc = self.base()
        doc["scenes"][0]["source"]["sha256"] = "f" * 64
        self.assert_invalid(doc, "does not match the referenced asset")

    def test_rejects_scene_shorter_than_minimum(self):
        doc = self.base()
        doc["scenes"][0]["out"] = doc["scenes"][0]["in"] + 0.1
        self.assert_invalid(doc, "at least")

    def test_rejects_out_before_in(self):
        doc = self.base()
        doc["scenes"][0]["out"] = 0.0
        self.assert_invalid(doc, "greater than 'in'")

    def test_rejects_unknown_transition(self):
        doc = self.base()
        doc["scenes"][0]["transition"] = "crossfade"
        self.assert_invalid(doc, "transition")

    def test_rejects_fade_longer_than_scene(self):
        doc = self.base()
        doc["scenes"][0]["transition"] = "fade-2.0"
        self.assert_invalid(doc, "longer than the scene")

    def test_rejects_fade_outside_allowed_range(self):
        doc = self.base()
        doc["scenes"][0]["transition"] = "fade-0.05"
        self.assert_invalid(doc, "between 0.1 and 2.0")

    def test_rejects_text_beyond_scene_end(self):
        doc = self.base()
        doc["scenes"][0]["text"] = [{"content": "hola", "at": 0.0, "until": 5.0, "position": "bottom"}]
        self.assert_invalid(doc, "must not exceed the scene duration")

    def test_rejects_volume_out_of_range(self):
        doc = self.base()
        doc["scenes"][0]["audio"]["volume"] = 140
        self.assert_invalid(doc, "volume")

    def test_rejects_audio_fades_longer_than_scene(self):
        doc = self.base()
        doc["scenes"][0]["audio"] = {"volume": 100, "fadeIn": 0.8, "fadeOut": 0.8}
        self.assert_invalid(doc, "fadeIn + fadeOut")

    def test_rejects_duplicate_scene_ids(self):
        doc = self.base()
        doc["scenes"][1]["id"] = doc["scenes"][0]["id"]
        self.assert_invalid(doc, "duplicate scene id")

    def test_rejects_bad_sha256(self):
        doc = self.base()
        doc["assets"][0]["sha256"] = "ZZZ"
        self.assert_invalid(doc, "sha256")

    def test_rejects_bad_rights_status(self):
        doc = self.base()
        doc["assets"][0]["rights"]["status"] = "borrowed"
        self.assert_invalid(doc, "rights.status")

    def test_rejects_bad_timestamp(self):
        doc = self.base()
        doc["updatedAt"] = "ayer"
        self.assert_invalid(doc, "updatedAt")

    def test_unknown_properties_warn_but_do_not_block(self):
        doc = self.base()
        doc["futureFeature"] = {"x": 1}
        errors, warnings = project.inspect(doc)
        self.assertEqual(errors, [])
        self.assertTrue(any("futureFeature" in w for w in warnings))

    def test_non_dict_document_is_rejected(self):
        self.assertTrue(project.validate([]))


class ExportValidationTests(unittest.TestCase):
    def test_rejects_empty_project(self):
        doc = _support.small_document(0)
        self.assertIn("at least one scene", " ".join(project.validate_for_export(doc)))

    def test_rejects_unrelinked_media(self):
        doc = _support.small_document(1)
        doc["scenes"][0]["source"] = {"assetId": None, "path": None, "sha256": None, "kind": "video"}
        doc["scenes"][0]["needsRelink"] = True
        self.assertIn("not relinked", " ".join(project.validate_for_export(doc)))

    def test_rejects_resolution_above_mvp_scope(self):
        doc = _support.small_document(1, width=3840, height=2160)
        self.assertIn("capped", " ".join(project.validate_for_export(doc)))

    def test_accepts_portrait_at_the_same_pixel_budget(self):
        doc = _support.small_document(1, width=720, height=1280)
        self.assertEqual(project.validate_for_export(doc), [])
        doc = _support.small_document(1, width=1080, height=1920)
        self.assertEqual(project.validate_for_export(doc), [])

    def test_rejects_portrait_beyond_the_pixel_budget(self):
        doc = _support.small_document(1, width=1440, height=2560)
        self.assertIn("capped", " ".join(project.validate_for_export(doc)))

    def test_rejects_fps_above_mvp_scope(self):
        doc = _support.small_document(1)
        doc["fps"] = {"num": 120, "den": 1}
        self.assertIn("capped", " ".join(project.validate_for_export(doc)))

    def test_rejects_assets_above_size_limit(self):
        doc = _support.small_document(1)
        doc["assets"][0]["bytes"] = 3 * 1024**3
        self.assertIn("bytes", " ".join(project.validate_for_export(doc)))

    def test_valid_project_exports_cleanly(self):
        self.assertEqual(project.validate_for_export(_support.example_document()), [])


class MigrationTests(unittest.TestCase):
    def test_ui_draft_is_migrated_without_losing_data(self):
        draft = _support.ui_draft_document()
        original = copy.deepcopy(draft)
        migrated, applied = project.migrate(draft)

        self.assertEqual(draft, original, "migration must not mutate its input")
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["from"], 0)
        self.assertEqual(applied[0]["to"], 1)
        self.assertEqual(migrated["schemaVersion"], 1)
        self.assertEqual(migrated["projectId"], "prj_ui")
        self.assertEqual(migrated["sessionId"], "sess_4f2a")
        self.assertEqual(migrated["audio"]["masterVolume"], 80)
        self.assertEqual(migrated["width"], 1280)
        self.assertEqual(migrated["height"], 720)
        self.assertEqual(migrated["scenes"][0]["source"]["path"], "media/intro.mp4")
        self.assertEqual(migrated["assets"][0]["id"], "md_01")
        self.assertEqual(migrated["scenes"][0]["text"][0]["content"], "Exporta en 720p y vuelve al chat con el MP4 listo.")
        self.assertEqual(migrated["scenes"][0]["audio"]["volume"], 80)
        self.assertFalse(migrated["scenes"][0]["needsRelink"])
        # Scene 2 pointed at media that the draft never described.
        self.assertTrue(migrated["scenes"][1]["needsRelink"])
        self.assertIsNone(migrated["scenes"][1]["source"]["path"])
        # Legacy keys survive the migration.
        self.assertEqual(migrated["project_id"], "prj_ui")
        self.assertEqual(migrated["updated_at"], "2026-11-08T18:42:10Z")
        self.assertEqual(project.validate(migrated), [])

    def test_migrated_document_exports_only_after_relink(self):
        migrated, _ = project.migrate(_support.ui_draft_document())
        errors = project.validate_for_export(migrated)
        self.assertTrue(any("not relinked" in error for error in errors))

    def test_unversioned_canonical_document_is_stamped_not_remapped(self):
        doc = _support.small_document(2)
        del doc["schemaVersion"]
        migrated, applied = project.migrate(doc)
        self.assertEqual(len(applied), 1)
        self.assertEqual(migrated["scenes"][0]["source"]["path"], "media/clip1.mp4")
        self.assertEqual(project.validate(migrated), [])

    def test_future_version_is_refused(self):
        doc = _support.small_document(1)
        doc["schemaVersion"] = 99
        with self.assertRaises(project.UnsupportedSchemaVersion):
            project.migrate(doc)

    def test_migration_log_accumulates(self):
        migrated, _ = project.migrate(_support.ui_draft_document())
        migrated_again, applied = project.migrate(migrated)
        self.assertEqual(applied, [])
        self.assertEqual(len(migrated_again["migrationLog"]), 1)


class SerializationTests(unittest.TestCase):
    def test_dumps_is_byte_identical_regardless_of_key_order(self):
        doc = _support.example_document()
        reordered = json.loads(json.dumps(doc))
        reordered = {key: reordered[key] for key in reversed(list(reordered))}
        self.assertEqual(project.dumps(doc), project.dumps(reordered))
        self.assertEqual(project.document_hash(doc), project.document_hash(reordered))

    def test_floats_are_fixed_precision(self):
        doc = _support.small_document(1)
        doc["scenes"][0]["out"] = 0.30000000000000004
        doc["scenes"][0]["in"] = -0.0
        text = project.dumps(doc)
        self.assertIn('"out": 0.3', text)
        self.assertIn('"in": 0.0', text)

    def test_nan_is_rejected_instead_of_written(self):
        doc = _support.small_document(1)
        doc["scenes"][0]["out"] = float("nan")
        with self.assertRaises(ValueError):
            project.dumps(doc)

    def test_unicode_survives_round_trip(self):
        doc = _support.small_document(1)
        doc["title"] = "Añó — 日本語"
        reloaded = json.loads(project.dumps(doc))
        self.assertEqual(reloaded["title"], "Añó — 日本語")

    def test_dedupe_key_is_stable_and_sensitive(self):
        doc = _support.small_document(2)
        same = copy.deepcopy(doc)
        same = {key: same[key] for key in reversed(list(same))}
        key = project.dedupe_key(doc, "mp4-720p30")
        self.assertEqual(key, project.dedupe_key(same, "mp4-720p30"))
        self.assertNotEqual(key, project.dedupe_key(doc, "mp4-1080p30"))
        self.assertNotEqual(key, project.dedupe_key(doc, "mp4-720p30", captions=False))
        changed = copy.deepcopy(doc)
        changed["scenes"][0]["out"] = 0.9
        self.assertNotEqual(key, project.dedupe_key(changed, "mp4-720p30"))


class AtomicSaveTests(_support.TempDirTestCase):
    def test_save_and_load_round_trip(self):
        doc = _support.example_document()
        target = self.write("project.json", doc)
        loaded = project.load(target)
        self.assertEqual(project.dumps(loaded), project.dumps(project.normalize(doc)))

    def test_save_keeps_previous_version_as_backup(self):
        doc = _support.small_document(2)
        target = self.write("project.json", doc)
        changed = copy.deepcopy(doc)
        changed["title"] = "Renombrado"
        project.save_atomic(target, changed)
        self.assertTrue(Path(str(target) + ".bak").exists())
        backup = json.loads(Path(str(target) + ".bak").read_text(encoding="utf-8"))
        self.assertEqual(backup["title"], "Proyecto de prueba")
        self.assertEqual(project.load(target)["title"], "Renombrado")

    def test_no_temporary_files_left_behind(self):
        doc = _support.small_document(1)
        target = self.tmp / "nested" / "project.json"
        project.save_atomic(target, doc)
        leftovers = [p.name for p in target.parent.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_load_rejects_corrupt_json(self):
        target = self.tmp / "broken.json"
        target.write_text("{not json", encoding="utf-8")
        with self.assertRaises(project.ValidationError):
            project.load(target)

    def test_load_does_not_rewrite_the_file(self):
        doc = _support.small_document(1)
        target = self.write("project.json", doc)
        before = target.read_bytes()
        project.load(target)
        self.assertEqual(target.read_bytes(), before)


class RevisionTests(unittest.TestCase):
    def test_conflict_reports_both_revisions(self):
        doc = _support.small_document(1)
        with self.assertRaises(project.RevisionConflict) as caught:
            project.bump_revision(doc, doc["revision"] - 1)
        self.assertEqual(caught.exception.expected, doc["revision"] - 1)
        self.assertEqual(caught.exception.current, doc["revision"])

    def test_bump_increments_and_records_base(self):
        doc = _support.small_document(1)
        next_doc = project.bump_revision(doc, doc["revision"])
        self.assertEqual(next_doc["revision"], doc["revision"] + 1)
        self.assertEqual(next_doc["baseRevision"], doc["revision"])
        self.assertNotEqual(next_doc["updatedAt"], doc["updatedAt"])
        self.assertEqual(doc["revision"], 3, "input document must not be mutated")

    def test_bump_requires_integer_base(self):
        doc = _support.small_document(1)
        for value in ("3", None, 3.0, True):
            with self.subTest(value=value):
                with self.assertRaises(project.ValidationError):
                    project.bump_revision(doc, value)


class UiAdapterTests(unittest.TestCase):
    def test_ui_projection_matches_pane_contract(self):
        ui = project.to_ui_document(_support.example_document())
        self.assertEqual(ui["project_id"], "prj_lanzamiento_q4")
        self.assertEqual(ui["revision"], 7)
        self.assertEqual(ui["audio"], {"master_volume": 80})
        scene = ui["scenes"][0]
        self.assertEqual(scene["media_id"], "md_01")
        self.assertEqual(scene["transition"], "none")
        self.assertTrue(scene["caption"].startswith("Exporta en 720p"))
        self.assertEqual(scene["volume"], 80)
        self.assertFalse(scene["muted"])
        self.assertTrue(ui["media"][0]["path"] == "media/intro.mp4")

    def test_ui_round_trip_keeps_scenes_and_media(self):
        original = _support.example_document()
        ui = project.to_ui_document(original)
        back = project.from_ui_document(ui)
        self.assertEqual(len(back["scenes"]), len(original["scenes"]))
        self.assertEqual(back["assets"][0]["path"], original["assets"][0]["path"])
        self.assertEqual(back["width"], original["width"])
        self.assertEqual(project.validate(back), [])

    def test_normalize_incoming_accepts_both_shapes(self):
        canonical = project.normalize_incoming(_support.example_document())
        draft = project.normalize_incoming(_support.ui_draft_document())
        self.assertEqual(canonical["projectId"], "prj_lanzamiento_q4")
        self.assertEqual(draft["projectId"], "prj_ui")

    def test_normalize_incoming_rejects_garbage(self):
        with self.assertRaises(project.ValidationError):
            project.normalize_incoming({"project_id": "..."})

    def test_new_project_is_valid(self):
        doc = project.new_project("prj_nuevo", "Nuevo proyecto")
        self.assertEqual(doc["revision"], 0)
        self.assertEqual(doc["scenes"], [])
        self.assertEqual(project.validate(doc), [])


class CloneDocumentTests(unittest.TestCase):
    """Duplicating a project must never alias ids with the original."""

    def test_clone_is_a_valid_revision_zero_copy(self):
        original = _support.small_document(scenes=2)
        clone = project.clone_document(original, "prj_copia")
        self.assertEqual(clone["projectId"], "prj_copia")
        self.assertEqual(clone["revision"], 0)
        self.assertEqual(clone["baseRevision"], 0)
        self.assertEqual(clone["title"], "Proyecto de prueba (copia)")
        self.assertEqual(project.validate(clone), [])
        self.assertEqual(original["projectId"], "prj_test")  # never mutated

    def test_clone_regenerates_asset_and_scene_ids(self):
        original = _support.small_document(scenes=2)
        clone = project.clone_document(original, "prj_copia")
        original_assets = {asset["id"] for asset in original["assets"]}
        clone_assets = {asset["id"] for asset in clone["assets"]}
        self.assertEqual(len(clone_assets), len(original_assets))
        self.assertFalse(original_assets & clone_assets)
        self.assertFalse(
            {scene["id"] for scene in original["scenes"]} & {scene["id"] for scene in clone["scenes"]}
        )
        # paths are the same files; ids are not
        self.assertEqual(
            [a["path"] for a in clone["assets"]], [a["path"] for a in original["assets"]]
        )

    def test_clone_remaps_scene_sources(self):
        clone = project.clone_document(_support.small_document(scenes=2), "prj_copia")
        asset_ids = {asset["id"] for asset in clone["assets"]}
        for scene in clone["scenes"]:
            self.assertIn(scene["source"]["assetId"], asset_ids)
        self.assertEqual(project.validate(clone), [])

    def test_clone_caps_a_long_title(self):
        doc = _support.small_document(scenes=1)
        doc["title"] = "x" * 200
        clone = project.clone_document(doc, "prj_copia")
        self.assertLessEqual(len(clone["title"]), 200)
        self.assertTrue(clone["title"].endswith("(copia)"))


class RemoveAssetTests(unittest.TestCase):
    def test_removes_asset_and_only_its_scenes(self):
        doc = _support.small_document(scenes=2)
        trimmed, removed = project.remove_asset(doc, "md_01")
        self.assertEqual([asset["id"] for asset in trimmed["assets"]], ["md_02"])
        self.assertEqual([scene["id"] for scene in trimmed["scenes"]], ["sc_02"])
        self.assertEqual(removed, ["sc_01"])
        self.assertEqual(project.validate(trimmed), [])
        self.assertEqual(len(doc["assets"]), 2)  # input untouched

    def test_unknown_asset_is_a_no_op(self):
        doc = _support.small_document(scenes=1)
        trimmed, removed = project.remove_asset(doc, "md_nope")
        self.assertEqual(removed, [])
        self.assertEqual(len(trimmed["assets"]), len(doc["assets"]))
        self.assertEqual(len(trimmed["scenes"]), len(doc["scenes"]))


if __name__ == "__main__":
    unittest.main()
