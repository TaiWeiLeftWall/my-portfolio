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
from r2_client import CmsConfig, R2Error, R2Object  # noqa: E402


class FakeR2Client:
    def __init__(self):
        self.uploads = []
        self.deletes = []
        self.health_calls = 0
        self.upload_error = None
        self.upload_result = None
        self.delete_error_for = set()
        self.health_error = None

    def health(self):
        self.health_calls += 1
        if self.health_error:
            raise self.health_error
        return {"ok": True}

    def upload(self, content, content_type, category, date, filename):
        self.uploads.append(
            {
                "content": content,
                "content_type": content_type,
                "category": category,
                "date": date,
                "filename": filename,
            }
        )
        if self.upload_error:
            raise self.upload_error
        if self.upload_result is not None:
            return self.upload_result
        return R2Object(
            key="images/{}/{}/uploaded.jpg".format(category, date),
            url="https://cdn.example.test/images/{}/{}/uploaded.jpg".format(
                category, date
            ),
        )

    def delete(self, key):
        self.deletes.append(key)
        if key in self.delete_error_for:
            raise R2Error("service_unavailable", "secret worker detail", True)


def multipart_body(fields, files, *, boundary="cms-test-boundary", close=True):
    chunks = []
    field_items = fields.items() if isinstance(fields, dict) else fields
    for name, value in field_items:
        chunks.extend(
            [
                "--{}\r\n".format(boundary).encode("ascii"),
                'Content-Disposition: form-data; name="{}"\r\n\r\n'.format(
                    name
                ).encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, filename, content_type, content in files:
        chunks.extend(
            [
                "--{}\r\n".format(boundary).encode("ascii"),
                (
                    'Content-Disposition: form-data; name="{}"; filename="{}"\r\n'
                    "Content-Type: {}\r\n\r\n"
                ).format(name, filename, content_type).encode("ascii"),
                content,
                b"\r\n",
            ]
        )
    if close:
        chunks.append("--{}--\r\n".format(boundary).encode("ascii"))
    return b"".join(chunks), "multipart/form-data; boundary={}".format(boundary)


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
        self.r2 = FakeR2Client()
        self.config = CmsConfig(
            r2_worker_url="https://worker.example.test",
            r2_public_base_url="https://cdn.example.test",
            r2_upload_token="test-token",
            max_upload_bytes=1024 * 1024,
        )

        class IsolatedHandler(cms_server.Handler):
            database = self.db
            config = self.config
            r2_client = self.r2
            JSON_BODY_READ_TIMEOUT = 0.1

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
            try:
                raw = response.read()
            except http.client.IncompleteRead as exc:
                raw = exc.partial
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

    def multipart_request(self, path, fields, files, **options):
        body, content_type = multipart_body(fields, files, **options)
        return self.request(
            "POST", path, body=body, headers={"Content-Type": content_type}
        )

    def raw_request(
        self, body, content_length, *, shutdown_write=True, response_timeout=5
    ):
        connection = http.client.HTTPConnection(
            self.host, self.port, timeout=response_timeout
        )
        try:
            connection.putrequest("POST", "/api/photo-groups")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Connection", "close")
            if content_length is not None:
                connection.putheader("Content-Length", content_length)
            connection.endheaders()
            if body:
                connection.send(body)
            if shutdown_write:
                connection.sock.shutdown(socket.SHUT_WR)
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8"))
        finally:
            connection.close()

    def raw_multipart_request(self, body, content_type, content_length):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            connection.putrequest("POST", "/api/photo-items/upload")
            connection.putheader("Content-Type", content_type)
            connection.putheader("Content-Length", str(content_length))
            connection.putheader("Connection", "close")
            connection.endheaders()
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
        self.assertEqual(payload["database"], True)
        self.assertEqual(payload["r2"], {"configured": True, "reachable": True})
        self.assertEqual(payload["orphan_photo_items"], 0)
        self.assertEqual(payload["orphan_commercial_items"], 0)

    def test_health_distinguishes_unconfigured_r2_from_reachability(self):
        self.handler_class.config = CmsConfig()

        status, payload = self.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["database"], True)
        self.assertEqual(payload["r2"], {"configured": False, "reachable": False})
        self.assertEqual(self.r2.health_calls, 0)

    def test_health_reports_configured_but_unreachable_r2(self):
        self.r2.health_error = R2Error("network_error", "secret resolver", True)

        status, payload = self.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["database"], True)
        self.assertEqual(payload["r2"], {"configured": True, "reachable": False})

    def test_photo_upload_stores_r2_url_only_after_cloud_success(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "date": "2026-07-16"}
        )

        status, payload = self.multipart_request(
            "/api/photo-items/upload",
            {
                "group_id": group["id"],
                "category": "portrait",
                "date": "2026-07-16",
            },
            [("image", "portrait.jpg", "image/jpeg", b"fake-jpeg-bytes")],
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(len(self.r2.uploads), 1)
        self.assertEqual(self.r2.uploads[0]["content"], b"fake-jpeg-bytes")
        self.assertEqual(self.r2.uploads[0]["content_type"], "image/jpeg")
        created = self.db.get_photo_item(payload["id"])
        self.assertEqual(created["src"], payload["src"])
        self.assertEqual(
            created["src"],
            "https://cdn.example.test/images/portrait/2026-07-16/uploaded.jpg",
        )
        self.assertEqual(self.r2.deletes, [])
        self.assertEqual(list((self.root / "media").rglob("*")), [])

    def test_r2_upload_failure_does_not_insert_photo_item(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "date": "2026-07-16"}
        )
        self.r2.upload_error = R2Error(
            "service_unavailable", "secret worker detail", True
        )

        status, payload = self.multipart_request(
            "/api/photo-items/upload",
            {
                "group_id": group["id"],
                "category": "portrait",
                "date": "2026-07-16",
            },
            [("image", "portrait.jpg", "image/jpeg", b"fake-jpeg-bytes")],
        )

        self.assert_error(status, payload, 502, "r2_upload_failed")
        self.assertNotIn("secret", payload["message"])
        self.assertEqual(self.db.state()["photoGroups"][0]["images"], [])

    def test_database_failure_rolls_back_exact_uploaded_r2_key(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "date": "2026-07-16"}
        )

        with mock.patch.object(
            self.db,
            "create_photo_item",
            side_effect=RuntimeError("secret sqlite detail"),
        ):
            status, payload = self.multipart_request(
                "/api/photo-items/upload",
                {
                    "group_id": group["id"],
                    "category": "portrait",
                    "date": "2026-07-16",
                },
                [("image", "portrait.jpg", "image/jpeg", b"fake-jpeg-bytes")],
            )

        self.assertEqual(status, 500)
        self.assertEqual(payload["code"], "database_write_failed")
        self.assertIs(payload["r2_rollback_succeeded"], True)
        self.assertNotIn("secret", payload["message"])
        self.assertEqual(
            self.r2.deletes,
            ["images/portrait/2026-07-16/uploaded.jpg"],
        )

    def test_database_failure_reports_failed_r2_rollback_without_details(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "date": "2026-07-16"}
        )
        self.r2.delete_error_for.add("images/portrait/2026-07-16/uploaded.jpg")

        with mock.patch.object(
            self.db,
            "create_photo_item",
            side_effect=RuntimeError("secret sqlite detail"),
        ):
            status, payload = self.multipart_request(
                "/api/photo-items/upload",
                {
                    "group_id": group["id"],
                    "category": "portrait",
                    "date": "2026-07-16",
                },
                [("image", "portrait.jpg", "image/jpeg", b"fake-jpeg-bytes")],
            )

        self.assertEqual(status, 500)
        self.assertEqual(payload["code"], "database_write_failed")
        self.assertIs(payload["r2_rollback_succeeded"], False)
        self.assertNotIn("secret", json.dumps(payload))

    def test_post_insert_read_failure_rolls_back_db_and_compensates_r2_once(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "date": "2026-07-16"}
        )
        original_get_on = self.db._get_on

        def fail_photo_item_read(conn, table, record_id):
            if table == "photo_items":
                raise RuntimeError("injected post-insert read failure")
            return original_get_on(conn, table, record_id)

        with mock.patch.object(self.db, "_get_on", side_effect=fail_photo_item_read):
            status, payload = self.multipart_request(
                "/api/photo-items/upload",
                {
                    "group_id": group["id"],
                    "category": "portrait",
                    "date": "2026-07-16",
                },
                [("image", "portrait.jpg", "image/jpeg", b"fake-jpeg-bytes")],
            )

        self.assertEqual(status, 500)
        self.assertEqual(payload["code"], "database_write_failed")
        self.assertIs(payload["r2_rollback_succeeded"], True)
        self.assertEqual(
            self.r2.deletes, ["images/portrait/2026-07-16/uploaded.jpg"]
        )
        self.assertEqual(self.db.state()["photoGroups"][0]["images"], [])

    def test_photo_delete_r2_failure_preserves_database_row(self):
        group = self.db.create_photo_group({"category": "portrait"})
        item = self.db.create_photo_item(
            {
                "group_id": group["id"],
                "src": "https://cdn.example.test/images/portrait/2026-07-16/a.jpg",
            }
        )
        self.r2.delete_error_for.add("images/portrait/2026-07-16/a.jpg")

        status, payload = self.request(
            "DELETE", "/api/photo-items/{}".format(item["id"])
        )

        self.assert_error(status, payload, 502, "r2_delete_failed")
        self.assertIsNotNone(self.db.get_photo_item(item["id"]))

    def test_photo_delete_removes_database_row_after_r2_success(self):
        group = self.db.create_photo_group({"category": "portrait"})
        item = self.db.create_photo_item(
            {
                "group_id": group["id"],
                "src": "https://cdn.example.test/images/portrait/2026-07-16/a.jpg",
            }
        )

        status, payload = self.request(
            "DELETE", "/api/photo-items/{}".format(item["id"])
        )

        self.assertEqual((status, payload), (200, {"ok": True}))
        self.assertEqual(self.r2.deletes, ["images/portrait/2026-07-16/a.jpg"])
        self.assertIsNone(self.db.get_photo_item(item["id"]))

    def test_group_delete_partial_r2_failure_keeps_group_for_idempotent_retry(self):
        group = self.db.create_photo_group({"category": "portrait"})
        first = "images/portrait/2026-07-16/a.jpg"
        second = "images/portrait/2026-07-16/b.jpg"
        for key in (first, second):
            self.db.create_photo_item(
                {"group_id": group["id"], "src": "https://cdn.example.test/" + key}
            )
        self.r2.delete_error_for.add(second)

        status, payload = self.request(
            "DELETE", "/api/photo-groups/{}".format(group["id"])
        )

        self.assert_error(status, payload, 502, "r2_delete_failed")
        self.assertIsNotNone(self.db.get_photo_group(group["id"]))
        self.assertEqual(len(self.db.state()["photoGroups"][0]["images"]), 2)
        self.assertEqual(self.r2.deletes, [first, second])

        self.r2.delete_error_for.clear()
        status, payload = self.request(
            "DELETE", "/api/photo-groups/{}".format(group["id"])
        )

        self.assertEqual((status, payload), (200, {"ok": True}))
        self.assertEqual(self.r2.deletes, [first, second, first, second])
        self.assertIsNone(self.db.get_photo_group(group["id"]))

    def test_local_media_photo_delete_skips_r2(self):
        group = self.db.create_photo_group({"category": "portrait"})
        item = self.db.create_photo_item(
            {"group_id": group["id"], "src": "upload-tool/media/legacy.jpg"}
        )

        status, payload = self.request(
            "DELETE", "/api/photo-items/{}".format(item["id"])
        )

        self.assertEqual((status, payload), (200, {"ok": True}))
        self.assertEqual(self.r2.deletes, [])

    def test_unrelated_remote_host_photo_delete_skips_r2(self):
        group = self.db.create_photo_group({"category": "portrait"})
        item = self.db.create_photo_item(
            {
                "group_id": group["id"],
                "src": "https://untrusted.example.test/images/portrait/a.jpg",
            }
        )

        status, payload = self.request(
            "DELETE", "/api/photo-items/{}".format(item["id"])
        )

        self.assertEqual((status, payload), (200, {"ok": True}))
        self.assertEqual(self.r2.deletes, [])
        self.assertIsNone(self.db.get_photo_item(item["id"]))

    def test_upload_url_or_key_mismatch_compensates_exact_key_without_db_row(self):
        group = self.db.create_photo_group({"category": "portrait"})
        cases = (
            R2Object(
                key="images/portrait/2026-07-16/a.jpg",
                url="https://untrusted.example.test/images/portrait/2026-07-16/a.jpg",
            ),
            R2Object(
                key="images/portrait/2026-07-16/a.jpg",
                url="https://cdn.example.test/images/portrait/2026-07-16/b.jpg",
            ),
            R2Object(
                key="images/portrait/2026-07-16/a\n.jpg",
                url="https://cdn.example.test/images/portrait/2026-07-16/a%0A.jpg",
            ),
        )

        for uploaded in cases:
            with self.subTest(url=uploaded.url):
                self.r2.upload_result = uploaded
                self.r2.deletes.clear()
                status, payload = self.multipart_request(
                    "/api/photo-items/upload",
                    {
                        "group_id": group["id"],
                        "category": "portrait",
                        "date": "2026-07-16",
                    },
                    [("image", "a.jpg", "image/jpeg", b"image-bytes")],
                )

                self.assert_error(status, payload, 502, "r2_upload_failed")
                self.assertNotIn("untrusted", json.dumps(payload))
                self.assertEqual(self.r2.deletes, [uploaded.key])
                self.assertEqual(
                    self.db.state()["photoGroups"][0]["images"], []
                )

    def test_upload_accepts_exact_canonical_public_base_url_for_key(self):
        group = self.db.create_photo_group({"category": "portrait"})
        self.r2.upload_result = R2Object(
            key="images/portrait/2026-07-16/a b(1).jpg",
            url=(
                "https://cdn.example.test/"
                "images/portrait/2026-07-16/a%20b(1).jpg"
            ),
        )

        status, payload = self.multipart_request(
            "/api/photo-items/upload",
            {
                "group_id": group["id"],
                "category": "portrait",
                "date": "2026-07-16",
            },
            [("image", "a.jpg", "image/jpeg", b"image-bytes")],
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["src"], self.r2.upload_result.url)
        self.assertEqual(self.r2.deletes, [])

    def test_concurrent_photo_mutation_waits_for_coordinated_delete(self):
        group = self.db.create_photo_group({"category": "portrait"})
        item = self.db.create_photo_item(
            {
                "group_id": group["id"],
                "src": "https://cdn.example.test/images/portrait/2026-07-16/a.jpg",
            }
        )
        delete_entered = threading.Event()
        release_delete = threading.Event()
        mutation_entered = threading.Event()
        results = {}
        original_delete = self.r2.delete
        original_create_group = self.db.create_photo_group

        def blocking_delete(key):
            delete_entered.set()
            if not release_delete.wait(5):
                raise RuntimeError("test timed out waiting to release delete")
            return original_delete(key)

        def observed_create_group(data):
            mutation_entered.set()
            return original_create_group(data)

        def run_request(name, method, path, payload=None):
            try:
                if payload is None:
                    results[name] = self.request(method, path)
                else:
                    results[name] = self.json_request(method, path, payload)
            except Exception as exc:
                results[name] = exc

        with mock.patch.object(self.r2, "delete", side_effect=blocking_delete), mock.patch.object(
            self.db, "create_photo_group", side_effect=observed_create_group
        ):
            delete_thread = threading.Thread(
                target=run_request,
                args=("delete", "DELETE", "/api/photo-items/{}".format(item["id"])),
            )
            mutation_thread = threading.Thread(
                target=run_request,
                args=(
                    "mutation",
                    "POST",
                    "/api/photo-groups",
                    {"category": "portrait", "title": "concurrent"},
                ),
            )
            delete_thread.start()
            self.assertTrue(delete_entered.wait(2))
            mutation_thread.start()
            try:
                self.assertFalse(mutation_entered.wait(0.25))
            finally:
                release_delete.set()
                delete_thread.join(timeout=5)
                mutation_thread.join(timeout=5)

        self.assertFalse(delete_thread.is_alive())
        self.assertFalse(mutation_thread.is_alive())
        self.assertEqual(results["delete"], (200, {"ok": True}))
        self.assertEqual(results["mutation"][0], 200)

    def test_get_remains_concurrent_while_coordinated_delete_holds_lock(self):
        group = self.db.create_photo_group({"category": "portrait"})
        item = self.db.create_photo_item(
            {
                "group_id": group["id"],
                "src": "https://cdn.example.test/images/portrait/2026-07-16/a.jpg",
            }
        )
        delete_entered = threading.Event()
        release_delete = threading.Event()
        get_finished = threading.Event()
        results = {}
        original_delete = self.r2.delete

        def blocking_delete(key):
            delete_entered.set()
            if not release_delete.wait(5):
                raise RuntimeError("test timed out waiting to release delete")
            return original_delete(key)

        def run_delete():
            results["delete"] = self.request(
                "DELETE", "/api/photo-items/{}".format(item["id"])
            )

        def run_get():
            results["get"] = self.request("GET", "/api/state")
            get_finished.set()

        with mock.patch.object(self.r2, "delete", side_effect=blocking_delete):
            delete_thread = threading.Thread(target=run_delete)
            get_thread = threading.Thread(target=run_get)
            delete_thread.start()
            self.assertTrue(delete_entered.wait(2))
            get_thread.start()
            try:
                self.assertTrue(get_finished.wait(1))
            finally:
                release_delete.set()
                delete_thread.join(timeout=5)
                get_thread.join(timeout=5)

        self.assertEqual(results["get"][0], 200)
        self.assertEqual(results["delete"], (200, {"ok": True}))

    def test_photo_upload_rejects_oversized_request_before_multipart_parse(self):
        self.handler_class.config = CmsConfig(
            r2_worker_url="https://worker.example.test",
            r2_public_base_url="https://cdn.example.test",
            r2_upload_token="test-token",
            max_upload_bytes=10,
        )

        status, payload = self.request(
            "POST",
            "/api/photo-items/upload",
            body=b"not parsed because too large",
            headers={"Content-Type": "multipart/form-data; boundary=unused"},
        )

        self.assert_error(status, payload, 413, "payload_too_large")
        self.assertEqual(self.r2.uploads, [])

    def test_photo_upload_rejects_duplicate_and_unknown_multipart_fields(self):
        group = self.db.create_photo_group({"category": "portrait"})
        valid_fields = [
            ("group_id", group["id"]),
            ("category", "portrait"),
            ("date", "2026-07-16"),
        ]
        cases = (
            valid_fields + [("group_id", group["id"])],
            valid_fields + [("title", "not accepted")],
        )

        for fields in cases:
            with self.subTest(fields=fields):
                status, payload = self.multipart_request(
                    "/api/photo-items/upload",
                    fields,
                    [("image", "a.jpg", "image/jpeg", b"image-bytes")],
                )
                self.assert_error(
                    status, payload, 400, "invalid_multipart_fields"
                )
        self.assertEqual(self.r2.uploads, [])

    def test_photo_upload_rejects_malformed_boundary_and_missing_close(self):
        group = self.db.create_photo_group({"category": "portrait"})
        fields = {
            "group_id": group["id"],
            "category": "portrait",
            "date": "2026-07-16",
        }
        valid_files = [("image", "a.jpg", "image/jpeg", b"image-bytes")]

        body, _content_type = multipart_body(
            fields, valid_files, boundary="invalid boundary"
        )
        status, payload = self.request(
            "POST",
            "/api/photo-items/upload",
            body=body,
            headers={
                "Content-Type": "multipart/form-data; boundary=invalid boundary"
            },
        )
        self.assert_error(status, payload, 400, "invalid_multipart")

        status, payload = self.multipart_request(
            "/api/photo-items/upload", fields, valid_files, close=False
        )
        self.assert_error(status, payload, 400, "invalid_multipart")
        self.assertEqual(self.r2.uploads, [])

    def test_photo_upload_rejects_truncated_multipart_body(self):
        group = self.db.create_photo_group({"category": "portrait"})
        body, content_type = multipart_body(
            {
                "group_id": group["id"],
                "category": "portrait",
                "date": "2026-07-16",
            },
            [("image", "a.jpg", "image/jpeg", b"image-bytes")],
        )

        status, payload = self.raw_multipart_request(
            body, content_type, len(body) + 10
        )

        self.assert_error(status, payload, 400, "truncated_body")
        self.assertEqual(self.r2.uploads, [])

    def test_photo_upload_rejects_invalid_date_and_zero_byte_image_locally(self):
        group = self.db.create_photo_group({"category": "portrait"})
        cases = (
            (
                {
                    "group_id": group["id"],
                    "category": "portrait",
                    "date": "2026-02-30",
                },
                [("image", "a.jpg", "image/jpeg", b"image-bytes")],
                "invalid_date",
            ),
            (
                {
                    "group_id": group["id"],
                    "category": "portrait",
                    "date": "2026-07-16",
                },
                [("image", "a.jpg", "image/jpeg", b"")],
                "empty_image",
            ),
        )

        for fields, files, code in cases:
            with self.subTest(code=code):
                status, payload = self.multipart_request(
                    "/api/photo-items/upload", fields, files
                )
                self.assert_error(status, payload, 400, code)
        self.assertEqual(self.r2.uploads, [])

    def test_invalid_multipart_is_rejected_before_r2_configuration_check(self):
        group = self.db.create_photo_group({"category": "portrait"})
        self.handler_class.config = CmsConfig()

        status, payload = self.multipart_request(
            "/api/photo-items/upload",
            {
                "group_id": group["id"],
                "category": "portrait",
                "date": "2026-07-16",
            },
            [("image", "a.jpg", "image/jpeg", b"")],
        )

        self.assert_error(status, payload, 400, "empty_image")
        self.assertEqual(self.r2.uploads, [])

    def test_photo_upload_rejects_missing_group_category_mismatch_and_bad_image(self):
        group = self.db.create_photo_group(
            {"category": "portrait", "date": "2026-07-16"}
        )
        cases = [
            (
                {"category": "portrait", "date": "2026-07-16"},
                [("image", "a.jpg", "image/jpeg", b"x")],
            ),
            (
                {
                    "group_id": group["id"],
                    "category": "landscape",
                    "date": "2026-07-16",
                },
                [("image", "a.jpg", "image/jpeg", b"x")],
            ),
            (
                {
                    "group_id": group["id"],
                    "category": "portrait",
                    "date": "2026-07-16",
                },
                [("image", "a.txt", "text/plain", b"x")],
            ),
            (
                {
                    "group_id": group["id"],
                    "category": "portrait",
                    "date": "2026-07-16",
                },
                [
                    ("image", "a.jpg", "image/jpeg", b"x"),
                    ("image", "b.jpg", "image/jpeg", b"y"),
                ],
            ),
        ]

        for fields, files in cases:
            with self.subTest(fields=fields, files=len(files)):
                status, payload = self.multipart_request(
                    "/api/photo-items/upload", fields, files
                )
                self.assertEqual(status, 400)
                self.assertIs(payload["ok"], False)
        self.assertEqual(self.r2.uploads, [])

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

    def test_partial_body_without_client_shutdown_returns_request_timeout(self):
        try:
            status, payload = self.raw_request(
                b"{}", "10", shutdown_write=False, response_timeout=0.75
            )
        except socket.timeout:
            self.fail("server did not return an HTTP timeout before the test deadline")

        self.assert_error(status, payload, 408, "request_timeout")

    def test_unknown_api_route_has_stable_not_found_error(self):
        status, payload = self.request("GET", "/api/not-a-route")

        self.assert_error(status, payload, 404, "not_found")

    def test_api_namespace_root_has_stable_not_found_error(self):
        status, payload = self.request("GET", "/api")

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

    def test_static_failure_after_headers_does_not_append_a_second_response(self):
        partial_body = b"partial-static-body"

        def fail_copy(_source, output):
            output.write(partial_body)
            output.flush()
            raise RuntimeError("static stream failed after headers")

        with mock.patch.object(
            self.handler_class, "copyfile", side_effect=fail_copy
        ), mock.patch.object(self.handler_class, "log_error") as log_error:
            status, payload = self.request("GET", "/")

        self.assertEqual((status, payload), (200, partial_body))
        log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
