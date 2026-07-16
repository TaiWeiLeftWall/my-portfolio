import ast
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOL_DIR = Path(__file__).resolve().parents[1]
SERVER = TOOL_DIR / "cms_server.py"
sys.path.insert(0, str(TOOL_DIR))

from cms_db import Database, NotFoundError, ValidationError  # noqa: E402


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db_path = self.root / "site.sqlite"
        self.db = Database(
            db_path=self.db_path,
            root=self.root,
            media_dir=self.root / "media",
        )
        self.db.initialize(seed=False)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_connections_enable_foreign_keys_and_group_delete_cascades(self):
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("pragma foreign_keys").fetchone()[0], 1)

        group_id = self.db.create_photo_group(
            {"category": "portrait", "date": "2026-07", "cols": 3}
        )["id"]
        item_id = self.db.create_photo_item(
            {"group_id": group_id, "src": "https://example.test/images/a.jpg"}
        )["id"]

        self.db.delete_photo_group(group_id)

        self.assertIsNone(self.db.get_photo_item(item_id))

    def test_health_reports_orphan_without_deleting_it(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("pragma foreign_keys = off")
            cursor = conn.execute(
                "insert into photo_items(group_id, src) values(?, ?)",
                (9999, "https://example.test/orphan.jpg"),
            )
            orphan_id = cursor.lastrowid

        self.assertEqual(self.db.health()["orphan_photo_items"], 1)
        self.assertIsNotNone(self.db.get_photo_item(orphan_id))

    def test_partial_update_preserves_sort_order(self):
        group = self.db.create_photo_group(
            {
                "category": "landscape",
                "title": "Before",
                "date": "2026-07-16",
                "cols": 4,
                "sort_order": 73,
            }
        )

        updated = self.db.update_photo_group(group["id"], {"title": "After"})

        self.assertEqual(updated["title"], "After")
        self.assertEqual(updated["sort_order"], 73)
        self.assertEqual(updated["category"], "landscape")
        self.assertEqual(updated["cols"], 4)

    def test_version_increase_backs_up_existing_database_and_preserves_orphans(self):
        with self.db.connect() as conn:
            conn.execute("pragma foreign_keys = off")
            conn.execute(
                "insert into photo_items(group_id, src) values(?, ?)",
                (5555, "https://example.test/legacy-orphan.jpg"),
            )
            conn.execute("pragma user_version = 0")

        self.db.initialize(seed=False)

        backup = self.db_path.with_name(f"{self.db_path.name}.bak-v0")
        self.assertTrue(backup.exists())
        with sqlite3.connect(backup) as conn:
            self.assertEqual(conn.execute("pragma user_version").fetchone()[0], 0)
        self.assertEqual(self.db.health()["orphan_photo_items"], 1)

    def test_crud_methods_return_plain_dictionaries_and_missing_updates_raise(self):
        group = self.db.create_photo_group({"category": "portrait", "cols": 3})
        photo = self.db.create_photo_item(
            {"group_id": group["id"], "src": "https://example.test/photo.jpg"}
        )
        video = self.db.create_video(
            {"title": "Clip", "url": "https://example.test/video", "platform": "web"}
        )
        project = self.db.create_commercial_project(
            {"id": "project-one", "title": "Project", "year": 2026, "category": "廣告"}
        )
        commercial_item = self.db.create_commercial_item(
            {
                "project_id": project["id"],
                "type": "image",
                "src": "https://example.test/commercial.jpg",
            }
        )

        for record in (group, photo, video, project, commercial_item):
            self.assertIs(type(record), dict)

        self.assertEqual(self.db.update_photo_item(photo["id"], {"title": "P"})["title"], "P")
        self.assertEqual(self.db.update_video(video["id"], {"title": "V"})["title"], "V")
        self.assertEqual(
            self.db.update_commercial_project(project["id"], {"title": "C"})["title"],
            "C",
        )
        self.assertEqual(
            self.db.update_commercial_item(commercial_item["id"], {"title": "I"})["title"],
            "I",
        )
        with self.assertRaises(NotFoundError):
            self.db.update_video(999999, {"title": "missing"})
        with self.assertRaises(ValidationError):
            self.db.update_photo_group(group["id"], {"category": "not-a-category"})

    def test_reorder_uses_known_scope_and_enforces_parent(self):
        first_group = self.db.create_photo_group({"category": "portrait", "sort_order": 0})
        second_group = self.db.create_photo_group({"category": "portrait", "sort_order": 1})
        first_item = self.db.create_photo_item(
            {"group_id": first_group["id"], "src": "https://example.test/first.jpg"}
        )
        other_item = self.db.create_photo_item(
            {"group_id": second_group["id"], "src": "https://example.test/other.jpg"}
        )

        self.db.reorder(
            "photo_items", [other_item["id"], first_item["id"]], parent_id=first_group["id"]
        )

        self.assertEqual(self.db.get_photo_item(first_item["id"])["sort_order"], 1)
        self.assertNotEqual(self.db.get_photo_item(other_item["id"])["sort_order"], 0)
        with self.assertRaises(ValidationError):
            self.db.reorder("photo_items; drop table photo_groups", [], parent_id=None)

    def test_batch_delete_is_whitelisted(self):
        first = self.db.create_video({"url": "https://example.test/one"})
        second = self.db.create_video({"url": "https://example.test/two"})

        result = self.db.batch_delete("videos", [first["id"], second["id"]])

        self.assertEqual(result["deleted"], 2)
        self.assertEqual(self.db.state()["videos"], [])
        with self.assertRaises(ValidationError):
            self.db.batch_delete("photo_groups", [1])

    def test_export_keeps_frontend_shape_and_omits_database_fields(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "title": "人物", "date": "2026-07", "cols": 3}
        )
        self.db.create_photo_item(
            {"group_id": group["id"], "src": "https://example.test/a.jpg", "title": "A"}
        )
        project = self.db.create_commercial_project(
            {"id": "ad-one", "title": "广告一", "year": 2026, "category": "廣告"}
        )
        self.db.create_commercial_item(
            {"project_id": project["id"], "src": "https://example.test/ad.jpg", "poster": ""}
        )

        result = self.db.export_frontend()
        data_js = (self.root / "data.js").read_text(encoding="utf-8")
        commercial_js = (self.root / "commercial.js").read_text(encoding="utf-8")

        self.assertEqual(result, {"data": self.root / "data.js", "commercial": self.root / "commercial.js"})
        self.assertIn('"category": "portrait"', data_js)
        self.assertNotIn('"group_id"', data_js)
        self.assertNotIn('"sort_order"', data_js)
        self.assertIn("function getProjectById(id)", commercial_js)
        self.assertNotIn('"project_id"', commercial_js)
        self.assertNotIn('"poster": ""', commercial_js)

    def test_second_temporary_write_failure_preserves_both_exports(self):
        data_target = self.root / "data.js"
        commercial_target = self.root / "commercial.js"
        data_target.write_text("old data", encoding="utf-8")
        commercial_target.write_text("old commercial", encoding="utf-8")
        real_named_temporary_file = tempfile.NamedTemporaryFile
        call_count = 0

        def fail_second_write(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            handle = real_named_temporary_file(*args, **kwargs)
            if call_count == 2:
                handle.write = mock.Mock(side_effect=OSError("disk full"))
            return handle

        with mock.patch("cms_db.tempfile.NamedTemporaryFile", side_effect=fail_second_write):
            with self.assertRaises(OSError):
                self.db.export_frontend()

        self.assertEqual(data_target.read_text(encoding="utf-8"), "old data")
        self.assertEqual(commercial_target.read_text(encoding="utf-8"), "old commercial")

    def test_second_replace_failure_restores_both_exports(self):
        data_target = self.root / "data.js"
        commercial_target = self.root / "commercial.js"
        data_target.write_text("old data", encoding="utf-8")
        commercial_target.write_text("old commercial", encoding="utf-8")
        real_replace = os.replace
        call_count = 0

        def fail_second_replace(source, target):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("replace failed")
            return real_replace(source, target)

        with mock.patch("cms_db.os.replace", side_effect=fail_second_replace):
            with self.assertRaises(OSError):
                self.db.export_frontend()

        self.assertEqual(data_target.read_text(encoding="utf-8"), "old data")
        self.assertEqual(commercial_target.read_text(encoding="utf-8"), "old commercial")


class ServerDatabaseWiringTests(unittest.TestCase):
    def test_main_initializes_one_database_and_injects_handler_dependency(self):
        tree = ast.parse(SERVER.read_text(encoding="utf-8-sig"))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("main", functions)
        self.assertNotIn("connect", functions)
        self.assertNotIn("state", functions)
        self.assertNotIn("export_frontend", functions)
        main_source = ast.unparse(functions["main"])
        self.assertIn("database = Database(DB_PATH, ROOT, MEDIA_DIR)", main_source)
        self.assertIn("database.initialize(seed=True)", main_source)
        self.assertIn("Handler.database = database", main_source)

        handler = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "Handler"
        )
        handler_source = ast.unparse(handler)
        self.assertNotIn("connect()", handler_source)
        self.assertIn("self.database.state()", handler_source)


if __name__ == "__main__":
    unittest.main()
