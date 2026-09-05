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

import cms_db  # noqa: E402
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

    def test_schema_v3_persists_idempotency_and_photo_collection_fields(self):
        conn = self.db.connect()
        try:
            self.assertEqual(conn.execute("pragma user_version").fetchone()[0], 3)
            columns = {
                row[1]: row[2]
                for row in conn.execute(
                    "pragma table_info(idempotency_records)"
                ).fetchall()
            }
            group_columns = {
                row[1]: row[2]
                for row in conn.execute("pragma table_info(photo_groups)").fetchall()
            }
        finally:
            conn.close()

        self.assertEqual(
            columns,
            {
                "operation_key": "TEXT",
                "operation": "TEXT",
                "response_status": "INTEGER",
                "response_payload": "TEXT",
                "created_at": "TEXT",
            },
        )
        self.assertEqual(group_columns["collection"], "TEXT")

    def test_photo_group_collection_round_trips_through_create_update_and_state(self):
        group = self.db.create_photo_group(
            {
                "category": "portrait",
                "title": "Graduation",
                "date": "2025-06-24",
                "collection": "graduation",
            }
        )

        self.assertEqual(group["collection"], "graduation")
        self.assertEqual(
            self.db.state()["photoGroups"][0]["collection"], "graduation"
        )

        updated = self.db.update_photo_group(group["id"], {"title": "Updated"})

        self.assertEqual(updated["collection"], "graduation")

    def test_photo_group_collection_defaults_to_empty_string(self):
        group = self.db.create_photo_group({"category": "portrait"})

        self.assertEqual(group["collection"], "")

    def test_bulk_import_and_frontend_export_preserve_collection(self):
        self.db.bulk_import(
            [
                {
                    "category": "portrait",
                    "title": "Graduation",
                    "date": "2025-06-24",
                    "collection": "graduation",
                    "images": [],
                }
            ]
        )

        data_js, _commercial_js = self.db._frontend_strings()

        self.assertIn('"collection": "graduation"', data_js)

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
                "collection": "graduation",
                "sort_order": 73,
            }
        )

        updated = self.db.update_photo_group(group["id"], {"title": "After"})

        self.assertEqual(updated["title"], "After")
        self.assertEqual(updated["sort_order"], 73)
        self.assertEqual(updated["category"], "landscape")
        self.assertEqual(updated["cols"], 4)
        self.assertEqual(updated["collection"], "graduation")

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

    def test_real_v1_schema_migrates_to_v3_and_preserves_existing_rows(self):
        legacy_path = self.root / "legacy-v1.sqlite"
        conn = sqlite3.connect(legacy_path)
        try:
            for statement in cms_db.SCHEMA_STATEMENTS[:-1]:
                conn.execute(statement)
            conn.execute(
                """insert into photo_groups
                (category,title,description,date,cols,sort_order)
                values(?,?,?,?,?,?)""",
                ("portrait", "legacy row", "", "2026-07", 3, 9),
            )
            conn.execute("pragma user_version = 1")
            conn.commit()
            tables = {
                row[0]
                for row in conn.execute(
                    "select name from sqlite_master where type='table'"
                )
            }
            self.assertNotIn("idempotency_records", tables)
        finally:
            conn.close()

        legacy = Database(legacy_path, self.root, self.root / "legacy-media")
        legacy.initialize(seed=False)

        backup_path = legacy_path.with_name("legacy-v1.sqlite.bak-v1")
        self.assertTrue(backup_path.exists())
        backup = sqlite3.connect(backup_path)
        try:
            self.assertEqual(backup.execute("pragma user_version").fetchone()[0], 1)
            backup_tables = {
                row[0]
                for row in backup.execute(
                    "select name from sqlite_master where type='table'"
                )
            }
            self.assertNotIn("idempotency_records", backup_tables)
        finally:
            backup.close()
        migrated = legacy.connect()
        try:
            self.assertEqual(migrated.execute("pragma user_version").fetchone()[0], 3)
            self.assertIsNotNone(
                migrated.execute(
                    "select 1 from sqlite_master where type='table' and name='idempotency_records'"
                ).fetchone()
            )
            row = migrated.execute(
                "select title,collection,sort_order from photo_groups"
            ).fetchone()
            self.assertEqual(
                dict(row),
                {"title": "legacy row", "collection": "", "sort_order": 9},
            )
        finally:
            migrated.close()

    def test_real_v2_schema_migrates_to_v3_and_preserves_existing_rows(self):
        legacy_path = self.root / "legacy-v2.sqlite"
        conn = sqlite3.connect(legacy_path)
        try:
            conn.execute(
                """create table photo_groups (
                id integer primary key autoincrement,
                category text not null default 'portrait',
                title text not null default '',
                description text not null default '',
                date text not null default '',
                cols integer not null default 3,
                sort_order integer not null default 0
                )"""
            )
            conn.execute(
                """insert into photo_groups
                (category,title,description,date,cols,sort_order)
                values(?,?,?,?,?,?)""",
                ("portrait", "v2 row", "", "2025-06-24", 3, 11),
            )
            conn.execute("pragma user_version = 2")
            conn.commit()
        finally:
            conn.close()

        legacy = Database(legacy_path, self.root, self.root / "legacy-v2-media")
        legacy.initialize(seed=False)

        migrated = legacy.connect()
        try:
            self.assertEqual(migrated.execute("pragma user_version").fetchone()[0], 3)
            row = migrated.execute(
                "select title,collection,sort_order from photo_groups"
            ).fetchone()
            self.assertEqual(
                dict(row),
                {"title": "v2 row", "collection": "", "sort_order": 11},
            )
        finally:
            migrated.close()

    def test_mid_migration_failure_rolls_back_schema_and_version(self):
        failed_path = self.root / "failed-migration.sqlite"
        database = Database(failed_path, self.root, self.root / "failed-media")
        injected_statements = (
            cms_db.SCHEMA_STATEMENTS[0],
            "create table this is invalid sql",
            *cms_db.SCHEMA_STATEMENTS[1:],
        )

        with mock.patch.object(cms_db, "SCHEMA_STATEMENTS", injected_statements):
            with self.assertRaises(sqlite3.OperationalError):
                database.initialize(seed=False)

        conn = sqlite3.connect(failed_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "select name from sqlite_master where type='table'"
                ).fetchall()
            }
            self.assertNotIn("photo_groups", tables)
            self.assertEqual(conn.execute("pragma user_version").fetchone()[0], 0)
        finally:
            conn.close()

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

    def test_photo_item_post_insert_read_failure_rolls_back_insert(self):
        group = self.db.create_photo_group({"category": "portrait"})

        with mock.patch.object(
            self.db,
            "_get_on",
            side_effect=RuntimeError("injected post-insert read failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.db.create_photo_item(
                    {
                        "group_id": group["id"],
                        "src": "https://cdn.example.test/images/a.jpg",
                    }
                )

        self.assertEqual(self.db.state()["photoGroups"][0]["images"], [])

    def test_each_update_uses_one_immediate_transaction_connection(self):
        group = self.db.create_photo_group({"category": "portrait"})
        photo = self.db.create_photo_item(
            {"group_id": group["id"], "src": "https://example.test/photo.jpg"}
        )
        video = self.db.create_video({"url": "https://example.test/video"})
        project = self.db.create_commercial_project({"id": "snapshot-project"})
        commercial = self.db.create_commercial_item(
            {"project_id": project["id"], "src": "https://example.test/item.jpg"}
        )
        cases = (
            (self.db.update_photo_group, group["id"]),
            (self.db.update_photo_item, photo["id"]),
            (self.db.update_video, video["id"]),
            (self.db.update_commercial_project, project["id"]),
            (self.db.update_commercial_item, commercial["id"]),
        )

        for update, record_id in cases:
            with self.subTest(update=update.__name__):
                statements = []
                real_connect = self.db.connect

                def traced_connect():
                    connection = real_connect()
                    connection.set_trace_callback(statements.append)
                    return connection

                with mock.patch.object(self.db, "connect", side_effect=traced_connect) as connect:
                    update(record_id, {"title": update.__name__})

                self.assertEqual(connect.call_count, 1)
                self.assertIn("BEGIN IMMEDIATE", [sql.upper() for sql in statements])

    def test_state_uses_one_explicit_snapshot_connection(self):
        group = self.db.create_photo_group({"category": "portrait"})
        self.db.create_photo_item(
            {"group_id": group["id"], "src": "https://example.test/photo.jpg"}
        )
        project = self.db.create_commercial_project({"id": "state-project"})
        self.db.create_commercial_item(
            {"project_id": project["id"], "src": "https://example.test/item.jpg"}
        )
        statements = []
        real_connect = self.db.connect

        def traced_connect():
            connection = real_connect()
            connection.set_trace_callback(statements.append)
            return connection

        with mock.patch.object(self.db, "connect", side_effect=traced_connect) as connect:
            state = self.db.state()

        self.assertEqual(connect.call_count, 1)
        self.assertEqual(len(state["photoGroups"][0]["images"]), 1)
        self.assertEqual(len(state["commercialProjects"][0]["items"]), 1)
        self.assertIn("BEGIN", [sql.upper() for sql in statements])

    def test_commercial_item_and_cover_roll_back_together_when_cover_update_fails(self):
        project = self.db.create_commercial_project(
            {"id": "atomic-cover", "cover": "old-cover.jpg"}
        )
        conn = self.db.connect()
        try:
            with conn:
                conn.execute(
                    """create trigger reject_cover_update before update of cover
                    on commercial_projects begin
                    select raise(abort, 'cover update rejected');
                    end"""
                )
        finally:
            conn.close()

        with self.assertRaises(ValidationError):
            self.db.create_commercial_item_with_cover(
                {
                    "project_id": project["id"],
                    "src": "https://example.test/new-item.jpg",
                },
                set_cover=True,
            )

        state = self.db.state()
        self.assertEqual(state["commercialProjects"][0]["cover"], "old-cover.jpg")
        self.assertEqual(state["commercialProjects"][0]["items"], [])

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

        result = self.db.batch_delete(
            "videos", [first["id"], first["id"], second["id"]]
        )

        self.assertEqual(result["deleted"], 2)
        self.assertEqual(self.db.state()["videos"], [])
        with self.assertRaises(ValidationError):
            self.db.batch_delete("photo_groups", [1])
        with self.assertRaises(ValidationError):
            self.db.batch_delete("videos", [])

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

    def test_target_specific_replace_failure_uses_atomic_rollback_file(self):
        data_target = self.root / "data.js"
        commercial_target = self.root / "commercial.js"
        data_target.write_text("old data", encoding="utf-8")
        commercial_target.write_text("old commercial", encoding="utf-8")
        real_replace = os.replace
        replacements = []

        def reject_new_commercial(source, target):
            source = Path(source)
            target = Path(target)
            source_content = source.read_text(encoding="utf-8")
            replacements.append((target, source_content))
            if target == commercial_target and source_content != "old commercial":
                raise OSError("commercial target unavailable")
            return real_replace(source, target)

        with mock.patch("cms_db.os.replace", side_effect=reject_new_commercial):
            with self.assertRaises(OSError):
                self.db.export_frontend()

        data_replacements = [content for target, content in replacements if target == data_target]
        self.assertEqual(data_replacements[-1], "old data")
        self.assertGreaterEqual(len(data_replacements), 2)
        self.assertEqual(data_target.read_text(encoding="utf-8"), "old data")
        self.assertEqual(commercial_target.read_text(encoding="utf-8"), "old commercial")

    def test_export_fsyncs_new_and_rollback_files_before_replacing(self):
        (self.root / "data.js").write_text("old data", encoding="utf-8")
        (self.root / "commercial.js").write_text("old commercial", encoding="utf-8")

        with mock.patch("cms_db.os.fsync", wraps=os.fsync) as fsync:
            self.db.export_frontend()

        self.assertEqual(fsync.call_count, 4)


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

    def test_upload_handler_uses_compound_commercial_item_cover_method(self):
        tree = ast.parse(SERVER.read_text(encoding="utf-8-sig"))
        handler = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "Handler"
        )
        upload = next(
            node
            for node in handler.body
            if isinstance(node, ast.FunctionDef) and node.name == "_upload"
        )
        source = ast.unparse(upload)
        self.assertIn("create_commercial_item_with_cover", source)
        self.assertNotIn("update_commercial_project", source)

    def test_server_has_no_duplicate_database_validation_definitions(self):
        tree = ast.parse(SERVER.read_text(encoding="utf-8-sig"))
        names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        assignments = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        self.assertNotIn("validate_date", names)
        self.assertNotIn("validate_enum", names)
        self.assertNotIn("VALID_CATEGORIES", assignments)
        self.assertNotIn("VALID_COMMERCIAL_CATEGORIES", assignments)


if __name__ == "__main__":
    unittest.main()
