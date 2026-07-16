#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local visual CMS for the photography site.

Run from the repository root:
    python upload-tool/cms_server.py
"""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi
import json
import os
import re
import time

from cms_db import Database, NotFoundError, ValidationError


ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = Path(__file__).resolve().parent
DB_PATH = TOOL_DIR / "site_content.sqlite"
MEDIA_DIR = TOOL_DIR / "media"
PORT = 8090

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


class Handler(SimpleHTTPRequestHandler):
    database: Database

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

    def read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size).decode("utf-8") or "{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_json(self.database.state())
            return
        if parsed.path == "/api/health":
            self.send_json(self.database.health())
            return
        return super().do_GET()

    def do_POST(self):
        try:
            self._do_POST()
        except NotFoundError as exc:
            self.send_json({"error": str(exc)}, 404)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)

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
        if parsed.path in ("/api/bulk-import", "/api/bulk-import-form"):
            if parsed.path == "/api/bulk-import-form":
                query = parse_qs(parsed.query)
                data = json.loads(query.get("d", ["{}"])[0])
            else:
                data = self.read_json()
            created = self.database.bulk_import(data.get("groups", []))
            if parsed.path == "/api/bulk-import-form":
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self.send_json({"ok": True, "groups": created})
            return
        self.send_json({"error": "not found"}, 404)

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
            record = self.database.create_commercial_item(
                {
                    "project_id": project_id,
                    "type": form.getfirst("type", "image"),
                    "src": src,
                    "title": form.getfirst("title", ""),
                    "poster": form.getfirst("poster", ""),
                }
            )
            if form.getfirst("set_cover") == "1":
                self.database.update_commercial_project(project_id, {"cover": src})
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
        try:
            self._do_PUT()
        except NotFoundError as exc:
            self.send_json({"error": str(exc)}, 404)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)

    def _do_PUT(self):
        parsed = urlparse(self.path)
        data = self.read_json()
        item_id = parsed.path.rsplit("/", 1)[-1]
        if parsed.path.startswith("/api/photo-groups/"):
            self.database.update_photo_group(item_id, data)
        elif parsed.path.startswith("/api/videos/"):
            self.database.update_video(item_id, data)
        elif parsed.path.startswith("/api/commercial-projects/"):
            self.database.update_commercial_project(item_id, data)
        elif parsed.path.startswith("/api/photo-items/"):
            self.database.update_photo_item(item_id, data)
        elif parsed.path.startswith("/api/commercial-items/"):
            self.database.update_commercial_item(item_id, data)
        else:
            self.send_json({"error": "not found"}, 404)
            return
        self.send_json({"ok": True})

    def do_DELETE(self):
        try:
            self._do_DELETE()
        except NotFoundError as exc:
            self.send_json({"error": str(exc)}, 404)
        except ValidationError as exc:
            self.send_json({"error": str(exc)}, 400)

    def _do_DELETE(self):
        parsed = urlparse(self.path)
        item_id = parsed.path.rsplit("/", 1)[-1]
        if parsed.path.startswith("/api/photo-groups/"):
            self.database.delete_photo_group(item_id)
        elif parsed.path.startswith("/api/photo-items/"):
            self.database.delete_photo_item(item_id)
        elif parsed.path.startswith("/api/videos/"):
            self.database.delete_video(item_id)
        elif parsed.path.startswith("/api/commercial-projects/"):
            self.database.delete_commercial_project(item_id)
        elif parsed.path.startswith("/api/commercial-items/"):
            self.database.delete_commercial_item(item_id)
        else:
            self.send_json({"error": "not found"}, 404)
            return
        self.send_json({"ok": True})


VALID_CATEGORIES = {"portrait", "landscape", "street", "performance", "official"}
VALID_COMMERCIAL_CATEGORIES = {"公務攝影", "演出攝影", "體育攝影", "空間攝影", "廣告", "視頻", "電商"}


def validate_date(date):
    """Return date if YYYY-MM-DD or YYYY-MM, else an empty string."""
    if not date:
        return ""
    if re.match(r"^\d{4}-\d{2}(-\d{2})?$", date):
        return date
    return ""


def validate_enum(value, allowed, default):
    return value if value in allowed else default


def main():
    database = Database(DB_PATH, ROOT, MEDIA_DIR)
    database.initialize(seed=True)
    Handler.database = database
    os.chdir(ROOT)
    print(f"CMS running at http://127.0.0.1:{PORT}")
    print(f"Database: {DB_PATH}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
