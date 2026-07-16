#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local visual CMS for the photography site.

Run from the repository root:
    python upload-tool/cms_server.py
"""

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi
import re
import json
import os
import shutil
import sqlite3
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = Path(__file__).resolve().parent
DB_PATH = TOOL_DIR / "site_content.sqlite"
MEDIA_DIR = TOOL_DIR / "media"
PORT = 8090

try:
    from PIL import Image
except Exception:
    Image = None


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript(
            """
            create table if not exists photo_groups (
                id integer primary key autoincrement,
                category text not null default 'portrait',
                title text not null default '',
                description text not null default '',
                date text not null default '',
                cols integer not null default 3,
                sort_order integer not null default 0
            );
            create table if not exists photo_items (
                id integer primary key autoincrement,
                group_id integer not null references photo_groups(id) on delete cascade,
                src text not null,
                title text not null default '',
                description text not null default '',
                sort_order integer not null default 0
            );
            create table if not exists videos (
                id integer primary key autoincrement,
                title text not null default '',
                description text not null default '',
                url text not null,
                platform text not null default '',
                source text not null default '',
                sort_order integer not null default 0
            );
            create table if not exists commercial_projects (
                id text primary key,
                client text not null default '',
                title text not null default '',
                description text not null default '',
                cover text not null default '',
                year integer not null default 2026,
                category text not null default '',
                sort_order integer not null default 0
            );
            create table if not exists commercial_items (
                id integer primary key autoincrement,
                project_id text not null references commercial_projects(id) on delete cascade,
                type text not null default 'image',
                src text not null,
                title text not null default '',
                poster text not null default '',
                sort_order integer not null default 0
            );
            """
        )
        count = db.execute("select count(*) from photo_groups").fetchone()[0]
        project_count = db.execute("select count(*) from commercial_projects").fetchone()[0]
    if count == 0 and project_count == 0:
        seed_from_current_js()


def node_json(script):
    out = subprocess.check_output(["node", "-e", script], cwd=ROOT, text=True, encoding="utf-8")
    return json.loads(out)


def seed_from_current_js():
    data_script = r"""
const fs=require('fs'), vm=require('vm');
const ctx={}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync('data.js','utf8') + '\n;globalThis.__out={photos,photoGroups,videos};', ctx);
console.log(JSON.stringify(ctx.__out));
"""
    commercial_script = r"""
const fs=require('fs'), vm=require('vm');
const ctx={}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync('commercial.js','utf8') + '\n;globalThis.__out={commercialProjects};', ctx);
console.log(JSON.stringify(ctx.__out));
"""
    try:
        data = node_json(data_script)
        commercial = node_json(commercial_script)
    except Exception as exc:
        print("Skipping JS import:", exc)
        return

    with connect() as db:
        for group_index, group in enumerate(data.get("photoGroups", [])):
            cur = db.execute(
                "insert into photo_groups(category,title,description,date,cols,sort_order) values(?,?,?,?,?,?)",
                (
                    group.get("category", "portrait"),
                    group.get("title", ""),
                    group.get("description", ""),
                    group.get("date", ""),
                    int(group.get("cols", 3) or 3),
                    group_index,
                ),
            )
            group_id = cur.lastrowid
            for item_index, item in enumerate(group.get("images", [])):
                db.execute(
                    "insert into photo_items(group_id,src,title,description,sort_order) values(?,?,?,?,?)",
                    (group_id, item.get("src", ""), item.get("title", ""), item.get("description", ""), item_index),
                )
        for index, video in enumerate(data.get("videos", [])):
            db.execute(
                "insert into videos(title,description,url,platform,source,sort_order) values(?,?,?,?,?,?)",
                (video.get("title", ""), video.get("description", ""), video.get("url", ""), video.get("platform", ""), video.get("source", ""), index),
            )
        for index, project in enumerate(commercial.get("commercialProjects", [])):
            db.execute(
                "insert into commercial_projects(id,client,title,description,cover,year,category,sort_order) values(?,?,?,?,?,?,?,?)",
                (
                    project.get("id", f"project-{index}"),
                    project.get("client", ""),
                    project.get("title", ""),
                    project.get("description", ""),
                    project.get("cover", ""),
                    int(project.get("year", 2026) or 2026),
                    project.get("category", ""),
                    index,
                ),
            )
            for item_index, item in enumerate(project.get("items", [])):
                db.execute(
                    "insert into commercial_items(project_id,type,src,title,poster,sort_order) values(?,?,?,?,?,?)",
                    (
                        project.get("id", f"project-{index}"),
                        item.get("type", "image"),
                        item.get("src", ""),
                        item.get("title", ""),
                        item.get("poster", ""),
                        item_index,
                    ),
                )


def rows(sql, args=()):
    with connect() as db:
        return [dict(row) for row in db.execute(sql, args).fetchall()]


def state():
    groups = rows("select * from photo_groups order by sort_order,id")
    for group in groups:
        group["images"] = rows("select * from photo_items where group_id=? order by sort_order,id", (group["id"],))
    projects = rows("select * from commercial_projects order by sort_order,id")
    for project in projects:
        project["items"] = rows("select * from commercial_items where project_id=? order by sort_order,id", (project["id"],))
    return {
        "photoGroups": groups,
        "videos": rows("select * from videos order by sort_order,id"),
        "commercialProjects": projects,
    }


def migrate_videos(db):
    import sqlite3 as _sql
    for col in ('platform', 'source'):
        try:
            db.execute(f"alter table videos add column {col} text not null default '")
        except _sql.OperationalError:
            pass


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
    with open(target, "wb") as f:
        f.write(raw)
    return public_path(target)


def export_frontend():
    content = state()
    data_js = (
        "// ==========================================\n"
        "// 摄影作品集数据文件 - 由 upload-tool/cms_server.py 导出\n"
        "// ==========================================\n\n"
        'const photographerName = "摄影师名称";\n\n'
        "const photos = [];\n\n"
        "const photoGroups = "
        + json.dumps(
            [
                {
                    "category": g["category"],
                    "title": g["title"],
                    "description": g["description"],
                    "date": g["date"],
                    "cols": g["cols"],
                    "images": [
                        {"src": i["src"], "title": i["title"], "description": i["description"]}
                        for i in g["images"]
                    ],
                }
                for g in content["photoGroups"]
            ],
            ensure_ascii=False,
            indent=4,
        )
        + ";\n\n"
        "const videos = "
        + json.dumps(
            [
                {"title": v["title"], "description": v["description"], "url": v["url"], "platform": v["platform"], "source": v["source"]}
                for v in content["videos"]
            ],
            ensure_ascii=False,
            indent=4,
        )
        + ";\n"
    )
    commercial_js = (
        "// ==========================================\n"
        "// 商业项目数据 - 由 upload-tool/cms_server.py 导出\n"
        "// ==========================================\n\n"
        "const commercialProjects = "
        + json.dumps(
            [
                {
                    "id": p["id"],
                    "client": p["client"],
                    "title": p["title"],
                    "description": p["description"],
                    "cover": p["cover"],
                    "year": p["year"],
                    "category": p["category"],
                    "items": [
                        {
                            "type": i["type"],
                            "src": i["src"],
                            "title": i["title"],
                            **({"poster": i["poster"]} if i["poster"] else {}),
                        }
                        for i in p["items"]
                    ],
                }
                for p in content["commercialProjects"]
            ],
            ensure_ascii=False,
            indent=4,
        )
        + ";\n\n"
        "function getProjectById(id) {\n"
        "    return commercialProjects.find(p => p.id === id) || null;\n"
        "}\n\n"
        "function getCommercialYears() {\n"
        "    const years = new Set(commercialProjects.map(p => p.year));\n"
        "    return Array.from(years).sort().reverse();\n"
        "}\n\n"
        "function getCommercialCategories() {\n"
        "    const categories = new Set(commercialProjects.map(p => p.category));\n"
        "    return Array.from(categories).sort();\n"
        "}\n"
    )
    (ROOT / "data.js").write_text(data_js, encoding="utf-8")
    (ROOT / "commercial.js").write_text(commercial_js, encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        ctype = super().guess_type(path)
        if ctype == 'text/html':
            ctype = 'text/html; charset=utf-8'
        return ctype

    def translate_path(self, path):
        # Strip query string for static file serving
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
            self.send_json(state())
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/export":
            export_frontend()
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/photo-groups":
            data = self.read_json()
            cat = validate_enum(data.get("category", "portrait"), VALID_CATEGORIES, "portrait")
            d = validate_date(data.get("date", ""))
            with connect() as db:
                cur = db.execute(
                    "insert into photo_groups(category,title,description,date,cols,sort_order) values(?,?,?,?,?,?)",
                    (cat, data.get("title", ""), data.get("description", ""), d, int(data.get("cols", 3)), int(time.time())),
                )
            self.send_json({"ok": True, "id": cur.lastrowid})
            return
        if parsed.path == "/api/videos":
            data = self.read_json()
            with connect() as db:
                db.execute(
                    "insert into videos(title,description,url,platform,source,sort_order) values(?,?,?,?,?,?)",
                    (data.get("title", ""), data.get("description", ""), data.get("url", ""), data.get("platform", ""), data.get("source", ""), int(time.time())),
                )
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/commercial-projects":
            data = self.read_json()
            project_id = data.get("id") or f"commercial-{int(time.time())}"
            cat = validate_enum(data.get("category", ""), VALID_COMMERCIAL_CATEGORIES, "")
            with connect() as db:
                db.execute(
                    "insert or replace into commercial_projects(id,client,title,description,cover,year,category,sort_order) values(?,?,?,?,?,?,?,?)",
                    (project_id, data.get("client", ""), data.get("title", ""), data.get("description", ""), data.get("cover", ""), int(data.get("year", 2026)), cat, int(time.time())),
                )
            self.send_json({"ok": True, "id": project_id})
            return
        if parsed.path == "/api/upload":
            # Keep existing upload endpoint but also support JSON-based item creation
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                data = self.read_json()
                with connect() as db:
                    db.execute(
                        "insert into photo_items(group_id,src,title,description,sort_order) values(?,?,?,?,?)",
                        (int(data.get("group_id", 0)), data.get("src", ""), data.get("title", ""), data.get("description", ""), int(time.time())),
                    )
                self.send_json({"ok": True})
                return
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"})
            area = form.getfirst("area", "gallery")
            src = save_upload(form["file"], area) if "file" in form else form.getfirst("src", "")
            with connect() as db:
                if area == "commercial":
                    project_id = form.getfirst("project_id", "")
                    db.execute(
                        "insert into commercial_items(project_id,type,src,title,poster,sort_order) values(?,?,?,?,?,?)",
                        (project_id, form.getfirst("type", "image"), src, form.getfirst("title", ""), form.getfirst("poster", ""), int(time.time())),
                    )
                    if form.getfirst("set_cover") == "1":
                        db.execute("update commercial_projects set cover=? where id=?", (src, project_id))
                else:
                    db.execute(
                        "insert into photo_items(group_id,src,title,description,sort_order) values(?,?,?,?,?)",
                        (int(form.getfirst("group_id", "0")), src, form.getfirst("title", ""), form.getfirst("description", ""), int(time.time())),
                    )
            self.send_json({"ok": True, "src": src})
            return
        if parsed.path == "/api/reorder":
            data = self.read_json()
            table = data.get("table", "")
            parent_col = data.get("parent_col", "")
            parent_id = data.get("parent_id")
            order = data.get("order", [])
            if table not in ("photo_groups", "photo_items", "videos", "commercial_projects", "commercial_items"):
                self.send_json({"error": "invalid table"}, 400)
                return
            with connect() as db:
                for idx, item_id in enumerate(order):
                    if parent_col and parent_id is not None:
                        db.execute(
                            f"update {table} set sort_order=? where id=? and {parent_col}=?",
                            (idx, item_id, parent_id),
                        )
                    else:
                        db.execute(
                            f"update {table} set sort_order=? where id=?",
                            (idx, item_id),
                        )
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/batch-delete":
            data = self.read_json()
            table = data.get("table", "")
            ids = data.get("ids", [])
            if table not in ("photo_items", "commercial_items", "videos"):
                self.send_json({"error": "invalid table"}, 400)
                return
            if not ids:
                self.send_json({"error": "no ids provided"}, 400)
                return
            with connect() as db:
                db.execute(f"delete from {table} where id in ({','.join('?' * len(ids))})", ids)
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/bulk-import":
            data = self.read_json()
            groups = data.get("groups", [])
            created = []
            with connect() as db:
                for g in groups:
                    cat = validate_enum(g.get("category", "portrait"), VALID_CATEGORIES, "portrait")
                    d = validate_date(g.get("date", ""))
                    cur = db.execute(
                        "insert into photo_groups(category,title,description,date,cols,sort_order) values(?,?,?,?,?,?)",
                        (cat, g.get("title", ""), g.get("description", ""), d, int(g.get("cols", 3)), int(time.time())),
                    )
                    gid = cur.lastrowid
                    for idx, img in enumerate(g.get("images", [])):
                        db.execute(
                            "insert into photo_items(group_id,src,title,description,sort_order) values(?,?,?,?,?)",
                            (gid, img.get("src", ""), img.get("title", ""), img.get("description", ""), idx),
                        )
                    created.append({"id": gid, "date": d, "category": cat, "count": len(g.get("images", []))})
            self.send_json({"ok": True, "groups": created})
            return
        if parsed.path == "/api/bulk-import-form":
            qs = parse_qs(parsed.query)
            data_str = qs.get("d", ["{}"])[0]
            data = json.loads(data_str)
            groups = data.get("groups", [])
            with connect() as db:
                for g in groups:
                    cat = validate_enum(g.get("category", "portrait"), VALID_CATEGORIES, "portrait")
                    d = validate_date(g.get("date", ""))
                    cur = db.execute(
                        "insert into photo_groups(category,title,description,date,cols,sort_order) values(?,?,?,?,?,?)",
                        (cat, g.get("title", ""), g.get("description", ""), d, int(g.get("cols", 3)), int(time.time())),
                    )
                    gid = cur.lastrowid
                    for idx, img in enumerate(g.get("images", [])):
                        db.execute(
                            "insert into photo_items(group_id,src,title,description,sort_order) values(?,?,?,?,?)",
                            (gid, img.get("src", ""), img.get("title", ""), img.get("description", ""), idx),
                        )
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        self.send_json({"error": "not found"}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        data = self.read_json()
        item_id = parsed.path.rsplit("/", 1)[-1]
        with connect() as db:
            if parsed.path.startswith("/api/photo-groups/"):
                cat = validate_enum(data.get("category", ""), VALID_CATEGORIES, "")
                d = validate_date(data.get("date", ""))
                db.execute(
                    "update photo_groups set category=?,title=?,description=?,date=?,cols=?,sort_order=? where id=?",
                    (cat, data.get("title", ""), data.get("description", ""), d, int(data.get("cols", 3)), int(data.get("sort_order", 0)), item_id),
                )
            elif parsed.path.startswith("/api/videos/"):
                db.execute(
                    "update videos set title=?,description=?,url=?,platform=?,source=?,sort_order=? where id=?",
                    (data.get("title", ""), data.get("description", ""), data.get("url", ""), data.get("platform", ""), data.get("source", ""), int(data.get("sort_order", 0)), item_id),
                )
            elif parsed.path.startswith("/api/commercial-projects/"):
                cat = validate_enum(data.get("category", ""), VALID_COMMERCIAL_CATEGORIES, "")
                db.execute(
                    "update commercial_projects set client=?,title=?,description=?,cover=?,year=?,category=?,sort_order=? where id=?",
                    (data.get("client", ""), data.get("title", ""), data.get("description", ""), data.get("cover", ""), int(data.get("year", 2026)), cat, int(data.get("sort_order", 0)), item_id),
                )
            elif parsed.path.startswith("/api/photo-items/"):
                db.execute(
                    "update photo_items set src=?,title=?,description=?,sort_order=? where id=?",
                    (data.get("src", ""), data.get("title", ""), data.get("description", ""), int(data.get("sort_order", 0)), item_id),
                )
            elif parsed.path.startswith("/api/commercial-items/"):
                db.execute(
                    "update commercial_items set type=?,src=?,title=?,poster=?,sort_order=? where id=?",
                    (data.get("type", "image"), data.get("src", ""), data.get("title", ""), data.get("poster", ""), int(data.get("sort_order", 0)), item_id),
                )
            else:
                self.send_json({"error": "not found"}, 404)
                return
        self.send_json({"ok": True})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        item_id = parsed.path.rsplit("/", 1)[-1]
        with connect() as db:
            if parsed.path.startswith("/api/photo-groups/"):
                db.execute("delete from photo_groups where id=?", (item_id,))
            elif parsed.path.startswith("/api/photo-items/"):
                db.execute("delete from photo_items where id=?", (item_id,))
            elif parsed.path.startswith("/api/videos/"):
                db.execute("delete from videos where id=?", (item_id,))
            elif parsed.path.startswith("/api/commercial-projects/"):
                db.execute("delete from commercial_projects where id=?", (item_id,))
            elif parsed.path.startswith("/api/commercial-items/"):
                db.execute("delete from commercial_items where id=?", (item_id,))
            else:
                self.send_json({"error": "not found"}, 404)
                return
        self.send_json({"ok": True})

VALID_CATEGORIES = {"portrait", "landscape", "street", "performance", "official"}
VALID_COMMERCIAL_CATEGORIES = {"公務攝影", "演出攝影", "體育攝影", "空間攝影", "廣告", "視頻", "電商"}


def validate_date(d):
    """Return d if YYYY-MM-DD or YYYY-MM, else empty string."""
    if not d:
        return ""
    if re.match(r"^\d{4}-\d{2}(-\d{2})?$", d):
        return d
    return ""


def validate_enum(value, allowed, default):
    return value if value in allowed else default


if __name__ == "__main__":
    init_db()
    os.chdir(ROOT)
    print(f"CMS running at http://localhost:{PORT}")
    print(f"Database: {DB_PATH}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
