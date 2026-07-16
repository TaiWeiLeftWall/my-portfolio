import ast
import http.client
import json
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest import mock


TOOL_DIR = Path(__file__).resolve().parents[1]
SERVER = TOOL_DIR / "cms_server.py"
sys.path.insert(0, str(TOOL_DIR))

import cms_server  # noqa: E402
from cms_db import Database  # noqa: E402


class ServerEntryTests(unittest.TestCase):
    def test_runtime_definitions_precede_main_entry(self):
        tree = ast.parse(SERVER.read_text(encoding="utf-8-sig"))
        main_index = next(
            index
            for index, node in enumerate(tree.body)
            if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test)
        )
        names = {
            node.name: index
            for index, node in enumerate(tree.body)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        self.assertLess(names["public_path"], main_index)
        self.assertLess(names["save_upload"], main_index)
        self.assertLess(names["Handler"], main_index)
        self.assertLess(names["main"], main_index)

    def test_startup_message_uses_loopback_address(self):
        source = SERVER.read_text(encoding="utf-8-sig")
        self.assertIn("PORT = 8090", source)
        self.assertIn('print(f"CMS running at http://127.0.0.1:{PORT}")', source)
        self.assertNotIn("CMS running at http://localhost:", source)


class HttpApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db = Database(
            db_path=self.root / "site.sqlite",
            root=self.root,
            media_dir=self.root / "media",
        )
        self.db.initialize(seed=False)

        class IsolatedHandler(cms_server.Handler):
            database = self.db

            def log_message(self, format, *args):
                pass

        self.handler_class = IsolatedHandler
        self.server = cms_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), self.handler_class
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tempdir.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            raw = response.read()
            content_type = response.getheader("Content-Type", "")
            payload = json.loads(raw.decode("utf-8")) if "application/json" in content_type else raw
            return response.status, payload
        except http.client.RemoteDisconnected:
            self.fail("server closed the connection instead of returning an HTTP response")
        finally:
            connection.close()

    def json_request(self, method, path, payload):
        return self.request(
            method,
            path,
            body=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    def raw_request(self, body, content_length):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            connection.putrequest("POST", "/api/photo-groups")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Connection", "close")
            if content_length is not None:
                connection.putheader("Content-Length", content_length)
            connection.endheaders()
            if body:
                connection.send(body)
            connection.sock.shutdown(socket.SHUT_WR)
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8"))
        finally:
            connection.close()

    def assert_error(self, status, payload, expected_status, expected_code):
        self.assertEqual(status, expected_status)
        self.assertEqual(set(payload), {"ok", "code", "message"})
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["code"], expected_code)
        self.assertIsInstance(payload["message"], str)
        self.assertTrue(payload["message"])

    def test_health_returns_database_health_as_json(self):
        status, payload = self.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["orphan_photo_items"], 0)
        self.assertEqual(payload["orphan_commercial_items"], 0)

    def test_photo_group_post_preserves_success_response_shape(self):
        status, payload = self.json_request(
            "POST",
            "/api/photo-groups",
            {
                "category": "portrait",
                "title": "HTTP group",
                "date": "2026-07-16",
                "sort_order": 17,
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True, "id": payload["id"]})
        created = self.db.get_photo_group(payload["id"])
        self.assertEqual(created["title"], "HTTP group")
        self.assertEqual(created["sort_order"], 17)

    def test_malformed_json_has_stable_error_contract(self):
        status, payload = self.request(
            "POST",
            "/api/photo-groups",
            body=b'{"title":',
            headers={"Content-Type": "application/json"},
        )

        self.assert_error(status, payload, 400, "invalid_json")

    def test_invalid_photo_category_has_stable_validation_error(self):
        status, payload = self.json_request(
            "POST", "/api/photo-groups", {"category": "not-a-category"}
        )

        self.assert_error(status, payload, 400, "validation_error")

    def test_invalid_photo_date_has_stable_validation_error(self):
        status, payload = self.json_request(
            "POST", "/api/photo-groups", {"date": "July 16"}
        )

        self.assert_error(status, payload, 400, "validation_error")

    def test_missing_resource_has_stable_not_found_error(self):
        status, payload = self.json_request(
            "PUT", "/api/photo-groups/999999", {"title": "missing"}
        )

        self.assert_error(status, payload, 404, "not_found")

    def test_missing_content_length_is_rejected(self):
        status, payload = self.raw_request(b"{}", None)

        self.assert_error(status, payload, 400, "invalid_content_length")

    def test_invalid_content_length_is_rejected(self):
        status, payload = self.raw_request(b"{}", "not-an-integer")

        self.assert_error(status, payload, 400, "invalid_content_length")

    def test_json_body_above_one_mebibyte_is_rejected(self):
        status, payload = self.raw_request(b"", str(1024 * 1024 + 1))

        self.assert_error(status, payload, 413, "payload_too_large")

    def test_invalid_utf8_is_rejected(self):
        status, payload = self.request(
            "POST",
            "/api/photo-groups",
            body=b"\xff",
            headers={"Content-Type": "application/json"},
        )

        self.assert_error(status, payload, 400, "invalid_utf8")

    def test_non_object_json_is_rejected(self):
        status, payload = self.json_request("POST", "/api/photo-groups", ["not", "object"])

        self.assert_error(status, payload, 400, "invalid_json_body")

    def test_truncated_json_body_is_rejected(self):
        status, payload = self.raw_request(b"{}", "10")

        self.assert_error(status, payload, 400, "truncated_body")

    def test_unknown_api_route_has_stable_not_found_error(self):
        status, payload = self.request("GET", "/api/not-a-route")

        self.assert_error(status, payload, 404, "not_found")

    def test_bulk_import_form_get_does_not_mutate_database(self):
        before = len(self.db.state()["photoGroups"])
        import_data = quote(
            json.dumps({"groups": [{"title": "must not import", "category": "portrait"}]})
        )

        status, _payload = self.request("GET", f"/api/bulk-import-form?d={import_data}")

        self.assertIn(status, (404, 405))
        self.assertEqual(len(self.db.state()["photoGroups"]), before)

    def test_bulk_import_form_post_is_not_an_api_route(self):
        status, payload = self.request("POST", "/api/bulk-import-form?d=%7B%7D", body=b"")

        self.assert_error(status, payload, 404, "not_found")

    def test_partial_update_preserves_resource_sort_order(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "title": "before", "sort_order": 73}
        )

        status, payload = self.json_request(
            "PUT", f"/api/photo-groups/{group['id']}", {"title": "after"}
        )

        self.assertEqual((status, payload), (200, {"ok": True}))
        self.assertEqual(self.db.get_photo_group(group["id"])["sort_order"], 73)

    def test_sqlite_integrity_errors_are_translated_without_leaking_details(self):
        with mock.patch.object(
            self.db,
            "create_photo_group",
            side_effect=sqlite3.IntegrityError("UNIQUE secret_table.secret_column"),
        ):
            status, payload = self.json_request("POST", "/api/photo-groups", {})

        self.assert_error(status, payload, 409, "conflict")
        self.assertNotIn("secret_table", payload["message"])

    def test_unexpected_errors_are_logged_and_return_generic_json(self):
        with mock.patch.object(
            self.db, "create_photo_group", side_effect=RuntimeError("sensitive traceback")
        ), mock.patch.object(self.handler_class, "log_error") as log_error:
            status, payload = self.json_request("POST", "/api/photo-groups", {})

        self.assert_error(status, payload, 500, "internal_error")
        self.assertNotIn("sensitive", payload["message"])
        log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
