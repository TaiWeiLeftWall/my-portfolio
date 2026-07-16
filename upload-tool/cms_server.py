#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local visual CMS for the photography site.

Run from the repository root:
    python upload-tool/cms_server.py
"""

from datetime import date as calendar_date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
import cgi
import json
import os
import socket
import sqlite3
import time

from cms_db import Database, NotFoundError, ValidationError
from r2_client import CmsConfig, R2Client, R2Error


ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = Path(__file__).resolve().parent
DB_PATH = TOOL_DIR / "site_content.sqlite"
MEDIA_DIR = TOOL_DIR / "media"
CONFIG_PATH = TOOL_DIR / "cms_config.json"
PORT = 8090
MAX_JSON_BODY_SIZE = 1024 * 1024
ACCEPTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

try:
    from PIL import Image
except Exception:
    Image = None


def public_path(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def save_upload(field, area):
    if not field or not getattr(field, "filename", ""):
        return ""
    safe_name = Path(field.filename).name.replace(" ", "-")
    folder = MEDIA_DIR / area / time.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{int(time.time() * 1000)}-{safe_name}"
    raw = field.file.read()
    if Image and field.type and field.type.startswith("image/"):
        try:
            from io import BytesIO

            img = Image.open(BytesIO(raw))
            img.thumbnail((2400, 2400))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            target = target.with_suffix(".jpg")
            img.save(target, "JPEG", quality=82, optimize=True)
            return public_path(target)
        except Exception:
            pass
    with open(target, "wb") as file:
        file.write(raw)
    return public_path(target)


def r2_key_from_src(src):
    if not isinstance(src, str) or not src:
        return None
    parsed = urlparse(src)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    decoded_path = unquote(parsed.path)
    marker = "/images/"
    marker_index = decoded_path.find(marker)
    if marker_index < 0:
        return None
    key = decoded_path[marker_index + 1 :]
    parts = key.split("/")
    if (
        len(parts) < 2
        or parts[0] != "images"
        or any(part in ("", ".", "..") for part in parts)
        or "\\" in key
    ):
        return None
    return key


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class Handler(SimpleHTTPRequestHandler):
    database: Database
    config = CmsConfig()
    r2_client = None
    JSON_BODY_READ_TIMEOUT = 10.0

    def guess_type(self, path):
        content_type = super().guess_type(path)
        if content_type == "text/html":
            content_type = "text/html; charset=utf-8"
        return content_type

    def translate_path(self, path):
        if "?" in path:
            path = path.split("?")[0]
        if path == "/" or path.startswith("/cms"):
            return str(TOOL_DIR / "cms.html")
        if path.startswith("/upload-tool/"):
            return str(ROOT / path.lstrip("/"))
        return str(ROOT / path.lstrip("/"))

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_response(self, code, message=None):
        self._response_started = True
        super().send_response(code, message)

    def read_json(self):
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise ApiError(
                400, "invalid_content_length", "Content-Length header is required"
            )
        try:
            size = int(content_length)
        except (TypeError, ValueError) as exc:
            raise ApiError(
                400, "invalid_content_length", "Content-Length must be an integer"
            ) from exc
        if size < 0:
            raise ApiError(
                400, "invalid_content_length", "Content-Length must not be negative"
            )
        if size > MAX_JSON_BODY_SIZE:
            raise ApiError(
                413,
                "payload_too_large",
                "JSON request body exceeds the 1 MiB limit",
            )

        previous_timeout = self.connection.gettimeout()
        self.connection.settimeout(self.JSON_BODY_READ_TIMEOUT)
        try:
            try:
                raw = self.rfile.read(size)
            except socket.timeout as exc:
                raise ApiError(
                    408,
                    "request_timeout",
                    "timed out while reading the JSON request body",
                ) from exc
        finally:
            self.connection.settimeout(previous_timeout)
        if len(raw) != size:
            raise ApiError(
                400, "truncated_body", "request body is shorter than Content-Length"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ApiError(
                400, "invalid_utf8", "JSON request body must use UTF-8"
            ) from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ApiError(
                400, "invalid_json", "request body must contain valid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise ApiError(
                400, "invalid_json_body", "JSON request body must be an object"
            )
        return data

    def _dispatch(self, action):
        self._response_started = False
        try:
            action()
        except Exception as exc:
            if self._response_started:
                self.close_connection = True
                self.log_error(
                    "Exception after response started for %s: %s", self.path, exc
                )
            elif isinstance(exc, ApiError):
                self.send_json(
                    {"ok": False, "code": exc.code, "message": exc.message},
                    exc.status,
                )
            elif isinstance(exc, NotFoundError):
                self.send_json(
                    {"ok": False, "code": "not_found", "message": str(exc)}, 404
                )
            elif isinstance(exc, ValidationError):
                self.send_json(
                    {"ok": False, "code": "validation_error", "message": str(exc)},
                    400,
                )
            elif isinstance(exc, json.JSONDecodeError):
                self.send_json(
                    {
                        "ok": False,
                        "code": "invalid_json",
                        "message": "request body must contain valid JSON",
                    },
                    400,
                )
            elif isinstance(exc, sqlite3.IntegrityError):
                self.send_json(
                    {
                        "ok": False,
                        "code": "conflict",
                        "message": "database integrity constraint failed",
                    },
                    409,
                )
            else:
                self.log_error("Unhandled exception for %s: %s", self.path, exc)
                self.send_json(
                    {
                        "ok": False,
                        "code": "internal_error",
                        "message": "an internal server error occurred",
                    },
                    500,
                )

    def do_GET(self):
        self._dispatch(self._do_GET)

    def _do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_json(self.database.state())
            return
        if parsed.path == "/api/health":
            database_health = self.database.health()
            configured = self.config.configured
            reachable = False
            if configured and self.r2_client is not None:
                try:
                    self.r2_client.health()
                except R2Error:
                    pass
                else:
                    reachable = True
            database_ok = bool(database_health["ok"])
            self.send_json(
                {
                    "ok": database_ok and (not configured or reachable),
                    "database": database_ok,
                    "r2": {"configured": configured, "reachable": reachable},
                    "schema_version": database_health["schema_version"],
                    "orphan_photo_items": database_health["orphan_photo_items"],
                    "orphan_commercial_items": database_health[
                        "orphan_commercial_items"
                    ],
                }
            )
            return
        if parsed.path == "/api" or parsed.path.startswith("/api/"):
            raise ApiError(404, "not_found", "API route not found")
        super().do_GET()

    def do_POST(self):
        self._dispatch(self._do_POST)

    def _do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/export":
            self.database.export_frontend()
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/photo-groups":
            record = self.database.create_photo_group(self.read_json())
            self.send_json({"ok": True, "id": record["id"]})
            return
        if parsed.path == "/api/videos":
            record = self.database.create_video(self.read_json())
            self.send_json({"ok": True, "id": record["id"]})
            return
        if parsed.path == "/api/commercial-projects":
            record = self.database.create_commercial_project(self.read_json())
            self.send_json({"ok": True, "id": record["id"]})
            return
        if parsed.path == "/api/photo-items/upload":
            self._upload_photo_item()
            return
        if parsed.path == "/api/upload":
            self._upload()
            return
        if parsed.path == "/api/reorder":
            data = self.read_json()
            result = self.database.reorder(
                data.get("table", ""), data.get("order", []), data.get("parent_id")
            )
            self.send_json({"ok": True, **result})
            return
        if parsed.path == "/api/batch-delete":
            data = self.read_json()
            result = self.database.batch_delete(data.get("table", ""), data.get("ids", []))
            self.send_json({"ok": True, **result})
            return
        if parsed.path == "/api/bulk-import":
            data = self.read_json()
            created = self.database.bulk_import(data.get("groups", []))
            self.send_json({"ok": True, "groups": created})
            return
        raise ApiError(404, "not_found", "API route not found")

    def _multipart_form(self):
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise ApiError(
                400, "invalid_content_length", "Content-Length header is required"
            )
        try:
            size = int(content_length)
        except (TypeError, ValueError) as exc:
            raise ApiError(
                400, "invalid_content_length", "Content-Length must be an integer"
            ) from exc
        if size < 0:
            raise ApiError(
                400, "invalid_content_length", "Content-Length must not be negative"
            )
        if size > self.config.max_upload_bytes:
            raise ApiError(
                413,
                "payload_too_large",
                "multipart request body exceeds the configured upload limit",
            )

        content_type = self.headers.get("Content-Type", "")
        media_type, parameters = cgi.parse_header(content_type)
        if media_type.lower() != "multipart/form-data" or not parameters.get(
            "boundary"
        ):
            raise ApiError(
                400,
                "invalid_multipart",
                "Content-Type must be multipart/form-data with a boundary",
            )

        previous_timeout = self.connection.gettimeout()
        self.connection.settimeout(self.JSON_BODY_READ_TIMEOUT)
        try:
            try:
                return cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": content_type,
                        "CONTENT_LENGTH": str(size),
                    },
                    keep_blank_values=True,
                )
            except socket.timeout as exc:
                raise ApiError(
                    408,
                    "request_timeout",
                    "timed out while reading the multipart request body",
                ) from exc
        finally:
            self.connection.settimeout(previous_timeout)

    @staticmethod
    def _validate_upload_date(value):
        if not isinstance(value, str):
            raise ApiError(400, "invalid_date", "date must use YYYY-MM-DD")
        try:
            parsed = calendar_date.fromisoformat(value)
        except ValueError as exc:
            raise ApiError(400, "invalid_date", "date must use YYYY-MM-DD") from exc
        if parsed.isoformat() != value:
            raise ApiError(400, "invalid_date", "date must use YYYY-MM-DD")
        return value

    def _require_r2(self):
        if not self.config.configured or self.r2_client is None:
            raise ApiError(503, "r2_not_configured", "R2 storage is not configured")
        return self.r2_client

    def _upload_photo_item(self):
        form = self._multipart_form()
        r2_client = self._require_r2()
        file_fields = [
            field
            for field in (form.list or [])
            if getattr(field, "filename", None) is not None
        ]
        if len(file_fields) != 1 or file_fields[0].name != "image":
            raise ApiError(
                400, "invalid_image_count", "exactly one image field is required"
            )
        image = file_fields[0]
        content_type = (image.type or "").lower()
        if content_type not in ACCEPTED_IMAGE_TYPES:
            raise ApiError(
                400, "invalid_image_type", "image must be JPEG, PNG, or WebP"
            )

        group_id = form.getfirst("group_id", "")
        if not str(group_id).strip():
            raise ApiError(400, "missing_group", "group_id is required")
        group = self.database.get_photo_group(group_id)
        if group is None:
            raise ApiError(400, "missing_group", "photo group does not exist")
        category = form.getfirst("category", "")
        if category != group["category"]:
            raise ApiError(
                400,
                "category_mismatch",
                "category does not match the selected photo group",
            )
        upload_date = self._validate_upload_date(form.getfirst("date", ""))
        filename = Path(image.filename or "").name
        if not filename:
            raise ApiError(400, "invalid_image", "image filename is required")
        content = image.file.read()

        try:
            uploaded = r2_client.upload(
                content, content_type, category, upload_date, filename
            )
        except R2Error:
            raise ApiError(
                502, "r2_upload_failed", "R2 image upload failed"
            ) from None

        try:
            record = self.database.create_photo_item(
                {"group_id": group["id"], "src": uploaded.url}
            )
        except Exception:
            rollback_succeeded = False
            try:
                r2_client.delete(uploaded.key)
            except Exception:
                pass
            else:
                rollback_succeeded = True
            self.send_json(
                {
                    "ok": False,
                    "code": "database_write_failed",
                    "message": "database write failed after R2 upload",
                    "r2_rollback_succeeded": rollback_succeeded,
                },
                500,
            )
            return
        self.send_json({"ok": True, "id": record["id"], "src": uploaded.url})

    def _upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            record = self.database.create_photo_item(self.read_json())
            self.send_json({"ok": True, "id": record["id"]})
            return

        form = cgi.FieldStorage(
            fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"}
        )
        area = form.getfirst("area", "gallery")
        src = save_upload(form["file"], area) if "file" in form else form.getfirst("src", "")
        if area == "commercial":
            project_id = form.getfirst("project_id", "")
            record = self.database.create_commercial_item_with_cover(
                {
                    "project_id": project_id,
                    "type": form.getfirst("type", "image"),
                    "src": src,
                    "title": form.getfirst("title", ""),
                    "poster": form.getfirst("poster", ""),
                },
                set_cover=form.getfirst("set_cover") == "1",
            )
        else:
            record = self.database.create_photo_item(
                {
                    "group_id": form.getfirst("group_id", "0"),
                    "src": src,
                    "title": form.getfirst("title", ""),
                    "description": form.getfirst("description", ""),
                }
            )
        self.send_json({"ok": True, "id": record["id"], "src": src})

    def do_PUT(self):
        self._dispatch(self._do_PUT)

    def _do_PUT(self):
        parsed = urlparse(self.path)
        item_id = parsed.path.rsplit("/", 1)[-1]
        if parsed.path.startswith("/api/photo-groups/"):
            data = self.read_json()
            self.database.update_photo_group(item_id, data)
        elif parsed.path.startswith("/api/videos/"):
            data = self.read_json()
            self.database.update_video(item_id, data)
        elif parsed.path.startswith("/api/commercial-projects/"):
            data = self.read_json()
            self.database.update_commercial_project(item_id, data)
        elif parsed.path.startswith("/api/photo-items/"):
            data = self.read_json()
            self.database.update_photo_item(item_id, data)
        elif parsed.path.startswith("/api/commercial-items/"):
            data = self.read_json()
            self.database.update_commercial_item(item_id, data)
        else:
            raise ApiError(404, "not_found", "API route not found")
        self.send_json({"ok": True})

    def do_DELETE(self):
        self._dispatch(self._do_DELETE)

    def _do_DELETE(self):
        parsed = urlparse(self.path)
        item_id = parsed.path.rsplit("/", 1)[-1]
        if parsed.path.startswith("/api/photo-groups/"):
            plan = self.database.get_photo_group_with_items(item_id)
            self._delete_r2_keys(
                [r2_key_from_src(item.get("src")) for item in plan["items"]]
            )
            self.database.delete_photo_group(item_id)
        elif parsed.path.startswith("/api/photo-items/"):
            item = self.database.get_photo_item(item_id)
            if item is None:
                raise NotFoundError("photo item {} not found".format(item_id))
            self._delete_r2_keys([r2_key_from_src(item.get("src"))])
            self.database.delete_photo_item(item_id)
        elif parsed.path.startswith("/api/videos/"):
            self.database.delete_video(item_id)
        elif parsed.path.startswith("/api/commercial-projects/"):
            self.database.delete_commercial_project(item_id)
        elif parsed.path.startswith("/api/commercial-items/"):
            self.database.delete_commercial_item(item_id)
        else:
            raise ApiError(404, "not_found", "API route not found")
        self.send_json({"ok": True})

    def _delete_r2_keys(self, keys):
        unique_keys = []
        for key in keys:
            if key and key not in unique_keys:
                unique_keys.append(key)
        if not unique_keys:
            return
        r2_client = self._require_r2()
        for key in unique_keys:
            try:
                r2_client.delete(key)
            except R2Error:
                raise ApiError(
                    502, "r2_delete_failed", "R2 image deletion failed"
                ) from None


def main():
    database = Database(DB_PATH, ROOT, MEDIA_DIR)
    database.initialize(seed=True)
    config = CmsConfig.load(CONFIG_PATH, os.environ)
    Handler.database = database
    Handler.config = config
    Handler.r2_client = R2Client(config) if config.configured else None
    os.chdir(ROOT)
    print(f"CMS running at http://127.0.0.1:{PORT}")
    print(f"Database: {DB_PATH}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
