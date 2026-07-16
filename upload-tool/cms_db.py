"""SQLite persistence and frontend export for the local photography CMS."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 2

VALID_CATEGORIES = {"portrait", "landscape", "street", "performance", "official"}
VALID_COMMERCIAL_CATEGORIES = {"公務攝影", "演出攝影", "體育攝影", "空間攝影", "廣告", "視頻", "電商"}

REORDER_SCOPES = {
    "photo_groups": None,
    "photo_items": "group_id",
    "videos": None,
    "commercial_projects": None,
    "commercial_items": "project_id",
}

BATCH_DELETE_SCOPES = {"photo_items", "commercial_items", "videos"}

SCHEMA_STATEMENTS = (
    """
    create table if not exists photo_groups (
        id integer primary key autoincrement,
        category text not null default 'portrait',
        title text not null default '',
        description text not null default '',
        date text not null default '',
        cols integer not null default 3,
        sort_order integer not null default 0
    )
    """,
    """
    create table if not exists photo_items (
        id integer primary key autoincrement,
        group_id integer not null references photo_groups(id) on delete cascade,
        src text not null,
        title text not null default '',
        description text not null default '',
        sort_order integer not null default 0
    )
    """,
    """
    create table if not exists videos (
        id integer primary key autoincrement,
        title text not null default '',
        description text not null default '',
        url text not null,
        platform text not null default '',
        source text not null default '',
        sort_order integer not null default 0
    )
    """,
    """
    create table if not exists commercial_projects (
        id text primary key,
        client text not null default '',
        title text not null default '',
        description text not null default '',
        cover text not null default '',
        year integer not null default 2026,
        category text not null default '',
        sort_order integer not null default 0
    )
    """,
    """
    create table if not exists commercial_items (
        id integer primary key autoincrement,
        project_id text not null references commercial_projects(id) on delete cascade,
        type text not null default 'image',
        src text not null,
        title text not null default '',
        poster text not null default '',
        sort_order integer not null default 0
    )
    """,
    """
    create table if not exists idempotency_records (
        operation_key text primary key,
        operation text not null,
        response_status integer not null,
        response_payload text not null,
        created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
)


class DatabaseError(Exception):
    """Base exception for expected database-layer errors."""


class ValidationError(DatabaseError):
    """Raised when a CMS record or operation is invalid."""


class NotFoundError(DatabaseError):
    """Raised when a requested CMS record does not exist."""


class IdempotencyConflict(DatabaseError):
    """Raised when an operation key was already used for another operation."""


class Database:
    def __init__(self, db_path: Path, root: Path, media_dir: Path):
        self.db_path = Path(db_path)
        self.root = Path(root)
        self.media_dir = Path(media_dir)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma busy_timeout = 5000")
        return conn

    def initialize(self, seed: bool = False) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        existed = self.db_path.exists()
        with closing(self.connect()) as conn:
            conn.execute("pragma journal_mode = wal")
            current_version = conn.execute("pragma user_version").fetchone()[0]
            if current_version > SCHEMA_VERSION:
                raise ValidationError(
                    f"database version {current_version} is newer than supported version {SCHEMA_VERSION}"
                )
            if current_version < SCHEMA_VERSION:
                if existed:
                    backup_path = self.db_path.with_name(
                        f"{self.db_path.name}.bak-v{current_version}"
                    )
                    with closing(sqlite3.connect(backup_path)) as backup:
                        conn.backup(backup)
                conn.execute("begin immediate")
                try:
                    for statement in SCHEMA_STATEMENTS:
                        conn.execute(statement)
                    self._ensure_column(conn, "videos", "platform", "text not null default ''")
                    self._ensure_column(conn, "videos", "source", "text not null default ''")
                    conn.execute(f"pragma user_version = {SCHEMA_VERSION}")
                except Exception:
                    conn.rollback()
                    raise
                else:
                    conn.commit()

        if seed and self._is_empty():
            self._seed_from_frontend()

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        columns = {row[1] for row in conn.execute(f"pragma table_info({table})")}
        if column not in columns:
            conn.execute(f"alter table {table} add column {column} {definition}")

    def _is_empty(self) -> bool:
        with closing(self.connect()) as conn:
            photo_count = conn.execute("select count(*) from photo_groups").fetchone()[0]
            project_count = conn.execute(
                "select count(*) from commercial_projects"
            ).fetchone()[0]
        return photo_count == 0 and project_count == 0

    def _node_json(self, script: str) -> dict[str, Any]:
        output = subprocess.check_output(
            ["node", "-e", script], cwd=self.root, text=True, encoding="utf-8"
        )
        return json.loads(output)

    def _seed_from_frontend(self) -> None:
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
            data = self._node_json(data_script)
            commercial = self._node_json(commercial_script)
        except Exception as exc:
            print("Skipping JS import:", exc)
            return

        with self.connect() as conn:
            for group_index, group in enumerate(data.get("photoGroups", [])):
                cursor = conn.execute(
                    """insert into photo_groups
                    (category,title,description,date,cols,sort_order) values(?,?,?,?,?,?)""",
                    (
                        group.get("category", "portrait"),
                        group.get("title", ""),
                        group.get("description", ""),
                        group.get("date", ""),
                        int(group.get("cols", 3) or 3),
                        group_index,
                    ),
                )
                for item_index, item in enumerate(group.get("images", [])):
                    conn.execute(
                        """insert into photo_items
                        (group_id,src,title,description,sort_order) values(?,?,?,?,?)""",
                        (
                            cursor.lastrowid,
                            item.get("src", ""),
                            item.get("title", ""),
                            item.get("description", ""),
                            item_index,
                        ),
                    )
            for index, video in enumerate(data.get("videos", [])):
                conn.execute(
                    """insert into videos
                    (title,description,url,platform,source,sort_order) values(?,?,?,?,?,?)""",
                    (
                        video.get("title", ""),
                        video.get("description", ""),
                        video.get("url", ""),
                        video.get("platform", ""),
                        video.get("source", ""),
                        index,
                    ),
                )
            for index, project in enumerate(commercial.get("commercialProjects", [])):
                project_id = project.get("id", f"project-{index}")
                conn.execute(
                    """insert into commercial_projects
                    (id,client,title,description,cover,year,category,sort_order)
                    values(?,?,?,?,?,?,?,?)""",
                    (
                        project_id,
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
                    conn.execute(
                        """insert into commercial_items
                        (project_id,type,src,title,poster,sort_order) values(?,?,?,?,?,?)""",
                        (
                            project_id,
                            item.get("type", "image"),
                            item.get("src", ""),
                            item.get("title", ""),
                            item.get("poster", ""),
                            item_index,
                        ),
                    )

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def _get_on(
        self, conn: sqlite3.Connection, table: str, record_id: Any
    ) -> dict[str, Any] | None:
        return self._dict(
            conn.execute(f"select * from {table} where id=?", (record_id,)).fetchone()
        )

    def _get(self, table: str, record_id: Any) -> dict[str, Any] | None:
        with closing(self.connect()) as conn:
            return self._get_on(conn, table, record_id)

    @staticmethod
    def _rows_on(
        conn: sqlite3.Connection, sql: str, args: Iterable[Any] = ()
    ) -> list[dict[str, Any]]:
        return [dict(row) for row in conn.execute(sql, tuple(args)).fetchall()]

    def _rows(self, sql: str, args: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with closing(self.connect()) as conn:
            return self._rows_on(conn, sql, args)

    @staticmethod
    def _integer(value: Any, field: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{field} must be an integer") from exc

    @staticmethod
    def _sort_order(data: dict[str, Any]) -> int:
        return Database._integer(data.get("sort_order", int(time.time())), "sort_order")

    @staticmethod
    def _validate_date(value: Any) -> str:
        if value in (None, ""):
            return ""
        if not isinstance(value, str):
            raise ValidationError("date must be a string")
        parts = value.split("-")
        if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
            raise ValidationError("date must use YYYY-MM or YYYY-MM-DD")
        if len(parts[0]) != 4 or any(len(part) != 2 for part in parts[1:]):
            raise ValidationError("date must use YYYY-MM or YYYY-MM-DD")
        return value

    @staticmethod
    def _require_row(record: dict[str, Any] | None, entity: str, record_id: Any) -> dict[str, Any]:
        if record is None:
            raise NotFoundError(f"{entity} {record_id} not found")
        return record

    def state(self) -> dict[str, Any]:
        with closing(self.connect()) as conn:
            conn.execute("begin")
            try:
                groups = self._rows_on(
                    conn, "select * from photo_groups order by sort_order,id"
                )
                for group in groups:
                    group["images"] = self._rows_on(
                        conn,
                        "select * from photo_items where group_id=? order by sort_order,id",
                        (group["id"],),
                    )
                projects = self._rows_on(
                    conn, "select * from commercial_projects order by sort_order,id"
                )
                for project in projects:
                    project["items"] = self._rows_on(
                        conn,
                        "select * from commercial_items where project_id=? order by sort_order,id",
                        (project["id"],),
                    )
                result = {
                    "photoGroups": groups,
                    "videos": self._rows_on(
                        conn, "select * from videos order by sort_order,id"
                    ),
                    "commercialProjects": projects,
                }
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return result

    def health(self) -> dict[str, Any]:
        with self.connect() as conn:
            orphan_photos = conn.execute(
                """select count(*) from photo_items i
                left join photo_groups g on g.id=i.group_id where g.id is null"""
            ).fetchone()[0]
            orphan_commercial = conn.execute(
                """select count(*) from commercial_items i
                left join commercial_projects p on p.id=i.project_id where p.id is null"""
            ).fetchone()[0]
            version = conn.execute("pragma user_version").fetchone()[0]
        return {
            "ok": version == SCHEMA_VERSION,
            "schema_version": version,
            "orphan_photo_items": orphan_photos,
            "orphan_commercial_items": orphan_commercial,
        }

    def get_photo_group(self, group_id: Any) -> dict[str, Any] | None:
        return self._get("photo_groups", group_id)

    @staticmethod
    def _idempotency_response_on(
        conn: sqlite3.Connection, operation_key: str, operation: str
    ) -> tuple[int, dict[str, Any]] | None:
        row = conn.execute(
            """select operation,response_status,response_payload
            from idempotency_records where operation_key=?""",
            (operation_key,),
        ).fetchone()
        if row is None:
            return None
        if row["operation"] != operation:
            raise IdempotencyConflict(
                "idempotency key was already used for another operation"
            )
        payload = json.loads(row["response_payload"])
        if not isinstance(payload, dict):
            raise DatabaseError("stored idempotency response is invalid")
        return int(row["response_status"]), payload

    @staticmethod
    def _store_idempotency_response_on(
        conn: sqlite3.Connection,
        operation_key: str,
        operation: str,
        status: int,
        payload: dict[str, Any],
    ) -> None:
        conn.execute(
            """insert into idempotency_records
            (operation_key,operation,response_status,response_payload)
            values(?,?,?,?)""",
            (
                operation_key,
                operation,
                status,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ),
        )

    def get_idempotency_response(
        self, operation_key: str, operation: str
    ) -> tuple[int, dict[str, Any]] | None:
        with closing(self.connect()) as conn:
            return self._idempotency_response_on(conn, operation_key, operation)

    def get_photo_group_with_items(self, group_id: Any) -> dict[str, Any]:
        with closing(self.connect()) as conn:
            conn.execute("begin")
            try:
                group = self._require_row(
                    self._get_on(conn, "photo_groups", group_id),
                    "photo group",
                    group_id,
                )
                items = self._rows_on(
                    conn,
                    "select * from photo_items where group_id=? order by sort_order,id",
                    (group_id,),
                )
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return {"group": group, "items": items}

    def create_photo_group(self, data: dict[str, Any]) -> dict[str, Any]:
        category = data.get("category", "portrait")
        if category not in VALID_CATEGORIES:
            raise ValidationError("invalid photo category")
        values = (
            category,
            data.get("title", ""),
            data.get("description", ""),
            self._validate_date(data.get("date", "")),
            self._integer(data.get("cols", 3), "cols"),
            self._sort_order(data),
        )
        with self.connect() as conn:
            cursor = conn.execute(
                """insert into photo_groups
                (category,title,description,date,cols,sort_order) values(?,?,?,?,?,?)""",
                values,
            )
            group_id = cursor.lastrowid
        return self._require_row(self.get_photo_group(group_id), "photo group", group_id)

    def create_photo_group_idempotent(
        self, data: dict[str, Any], operation_key: str, operation: str
    ) -> tuple[int, dict[str, Any]]:
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                replay = self._idempotency_response_on(
                    conn, operation_key, operation
                )
                if replay is not None:
                    conn.commit()
                    return replay
                category = data.get("category", "portrait")
                if category not in VALID_CATEGORIES:
                    raise ValidationError("invalid photo category")
                values = (
                    category,
                    data.get("title", ""),
                    data.get("description", ""),
                    self._validate_date(data.get("date", "")),
                    self._integer(data.get("cols", 3), "cols"),
                    self._sort_order(data),
                )
                cursor = conn.execute(
                    """insert into photo_groups
                    (category,title,description,date,cols,sort_order)
                    values(?,?,?,?,?,?)""",
                    values,
                )
                payload = {"ok": True, "id": cursor.lastrowid}
                self._store_idempotency_response_on(
                    conn, operation_key, operation, 200, payload
                )
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return 200, payload

    def update_photo_group(self, group_id: Any, changes: dict[str, Any]) -> dict[str, Any]:
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                current = self._require_row(
                    self._get_on(conn, "photo_groups", group_id), "photo group", group_id
                )
                merged = {**current, **changes}
                category = merged["category"]
                if category not in VALID_CATEGORIES:
                    raise ValidationError("invalid photo category")
                values = (
                    category,
                    merged["title"],
                    merged["description"],
                    self._validate_date(merged["date"]),
                    self._integer(merged["cols"], "cols"),
                    self._integer(merged["sort_order"], "sort_order"),
                    group_id,
                )
                conn.execute(
                    """update photo_groups set
                    category=?,title=?,description=?,date=?,cols=?,sort_order=? where id=?""",
                    values,
                )
                updated = self._require_row(
                    self._get_on(conn, "photo_groups", group_id), "photo group", group_id
                )
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return updated

    def delete_photo_group(self, group_id: Any) -> dict[str, Any]:
        current = self._require_row(self.get_photo_group(group_id), "photo group", group_id)
        with self.connect() as conn:
            conn.execute("delete from photo_groups where id=?", (group_id,))
        return current

    def get_photo_item(self, item_id: Any) -> dict[str, Any] | None:
        return self._get("photo_items", item_id)

    def create_photo_item(self, data: dict[str, Any]) -> dict[str, Any]:
        values = (
            self._integer(data.get("group_id"), "group_id"),
            data.get("src", ""),
            data.get("title", ""),
            data.get("description", ""),
            self._sort_order(data),
        )
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                cursor = conn.execute(
                    """insert into photo_items
                    (group_id,src,title,description,sort_order) values(?,?,?,?,?)""",
                    values,
                )
                item_id = cursor.lastrowid
                created = self._require_row(
                    self._get_on(conn, "photo_items", item_id),
                    "photo item",
                    item_id,
                )
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ValidationError("invalid photo item") from exc
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return created

    def create_photo_item_idempotent(
        self, data: dict[str, Any], operation_key: str, operation: str
    ) -> tuple[int, dict[str, Any]]:
        values = (
            self._integer(data.get("group_id"), "group_id"),
            data.get("src", ""),
            data.get("title", ""),
            data.get("description", ""),
            self._sort_order(data),
        )
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                replay = self._idempotency_response_on(
                    conn, operation_key, operation
                )
                if replay is not None:
                    conn.commit()
                    return replay
                cursor = conn.execute(
                    """insert into photo_items
                    (group_id,src,title,description,sort_order) values(?,?,?,?,?)""",
                    values,
                )
                item_id = cursor.lastrowid
                created = self._require_row(
                    self._get_on(conn, "photo_items", item_id),
                    "photo item",
                    item_id,
                )
                payload = {
                    "ok": True,
                    "id": created["id"],
                    "src": created["src"],
                }
                self._store_idempotency_response_on(
                    conn, operation_key, operation, 200, payload
                )
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ValidationError("invalid photo item") from exc
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return 200, payload

    def update_photo_item(self, item_id: Any, changes: dict[str, Any]) -> dict[str, Any]:
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                current = self._require_row(
                    self._get_on(conn, "photo_items", item_id), "photo item", item_id
                )
                merged = {**current, **changes}
                values = (
                    self._integer(merged["group_id"], "group_id"),
                    merged["src"],
                    merged["title"],
                    merged["description"],
                    self._integer(merged["sort_order"], "sort_order"),
                    item_id,
                )
                conn.execute(
                    """update photo_items set group_id=?,src=?,title=?,description=?,sort_order=?
                    where id=?""",
                    values,
                )
                updated = self._require_row(
                    self._get_on(conn, "photo_items", item_id), "photo item", item_id
                )
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ValidationError("invalid photo item") from exc
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return updated

    def delete_photo_item(self, item_id: Any) -> dict[str, Any]:
        current = self._require_row(self.get_photo_item(item_id), "photo item", item_id)
        with self.connect() as conn:
            conn.execute("delete from photo_items where id=?", (item_id,))
        return current

    def get_video(self, video_id: Any) -> dict[str, Any] | None:
        return self._get("videos", video_id)

    def create_video(self, data: dict[str, Any]) -> dict[str, Any]:
        values = (
            data.get("title", ""),
            data.get("description", ""),
            data.get("url", ""),
            data.get("platform", ""),
            data.get("source", ""),
            self._sort_order(data),
        )
        with self.connect() as conn:
            cursor = conn.execute(
                """insert into videos
                (title,description,url,platform,source,sort_order) values(?,?,?,?,?,?)""",
                values,
            )
            video_id = cursor.lastrowid
        return self._require_row(self.get_video(video_id), "video", video_id)

    def update_video(self, video_id: Any, changes: dict[str, Any]) -> dict[str, Any]:
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                current = self._require_row(
                    self._get_on(conn, "videos", video_id), "video", video_id
                )
                merged = {**current, **changes}
                values = (
                    merged["title"],
                    merged["description"],
                    merged["url"],
                    merged["platform"],
                    merged["source"],
                    self._integer(merged["sort_order"], "sort_order"),
                    video_id,
                )
                conn.execute(
                    """update videos set
                    title=?,description=?,url=?,platform=?,source=?,sort_order=? where id=?""",
                    values,
                )
                updated = self._require_row(
                    self._get_on(conn, "videos", video_id), "video", video_id
                )
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return updated

    def delete_video(self, video_id: Any) -> dict[str, Any]:
        current = self._require_row(self.get_video(video_id), "video", video_id)
        with self.connect() as conn:
            conn.execute("delete from videos where id=?", (video_id,))
        return current

    def get_commercial_project(self, project_id: Any) -> dict[str, Any] | None:
        return self._get("commercial_projects", project_id)

    def create_commercial_project(self, data: dict[str, Any]) -> dict[str, Any]:
        project_id = data.get("id") or f"commercial-{int(time.time())}"
        category = data.get("category", "")
        if category and category not in VALID_COMMERCIAL_CATEGORIES:
            raise ValidationError("invalid commercial category")
        values = (
            project_id,
            data.get("client", ""),
            data.get("title", ""),
            data.get("description", ""),
            data.get("cover", ""),
            self._integer(data.get("year", 2026), "year"),
            category,
            self._sort_order(data),
        )
        try:
            with self.connect() as conn:
                conn.execute(
                    """insert into commercial_projects
                    (id,client,title,description,cover,year,category,sort_order)
                    values(?,?,?,?,?,?,?,?)""",
                    values,
                )
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"commercial project {project_id} already exists") from exc
        return self._require_row(
            self.get_commercial_project(project_id), "commercial project", project_id
        )

    def update_commercial_project(
        self, project_id: Any, changes: dict[str, Any]
    ) -> dict[str, Any]:
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                current = self._require_row(
                    self._get_on(conn, "commercial_projects", project_id),
                    "commercial project",
                    project_id,
                )
                merged = {**current, **changes}
                category = merged["category"]
                if category and category not in VALID_COMMERCIAL_CATEGORIES:
                    raise ValidationError("invalid commercial category")
                values = (
                    merged["client"],
                    merged["title"],
                    merged["description"],
                    merged["cover"],
                    self._integer(merged["year"], "year"),
                    category,
                    self._integer(merged["sort_order"], "sort_order"),
                    project_id,
                )
                conn.execute(
                    """update commercial_projects set
                    client=?,title=?,description=?,cover=?,year=?,category=?,sort_order=?
                    where id=?""",
                    values,
                )
                updated = self._require_row(
                    self._get_on(conn, "commercial_projects", project_id),
                    "commercial project",
                    project_id,
                )
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return updated

    def delete_commercial_project(self, project_id: Any) -> dict[str, Any]:
        current = self._require_row(
            self.get_commercial_project(project_id), "commercial project", project_id
        )
        with self.connect() as conn:
            conn.execute("delete from commercial_projects where id=?", (project_id,))
        return current

    def get_commercial_item(self, item_id: Any) -> dict[str, Any] | None:
        return self._get("commercial_items", item_id)

    def create_commercial_item(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.create_commercial_item_with_cover(data, set_cover=False)

    def create_commercial_item_with_cover(
        self, data: dict[str, Any], set_cover: bool
    ) -> dict[str, Any]:
        item_type = data.get("type", "image")
        if item_type not in {"image", "video"}:
            raise ValidationError("invalid commercial item type")
        values = (
            data.get("project_id", ""),
            item_type,
            data.get("src", ""),
            data.get("title", ""),
            data.get("poster", ""),
            self._sort_order(data),
        )
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                cursor = conn.execute(
                    """insert into commercial_items
                    (project_id,type,src,title,poster,sort_order) values(?,?,?,?,?,?)""",
                    values,
                )
                item_id = cursor.lastrowid
                if set_cover:
                    cursor = conn.execute(
                        "update commercial_projects set cover=? where id=?",
                        (data.get("src", ""), data.get("project_id", "")),
                    )
                    if cursor.rowcount == 0:
                        raise NotFoundError(
                            f"commercial project {data.get('project_id', '')} not found"
                        )
                created = self._require_row(
                    self._get_on(conn, "commercial_items", item_id),
                    "commercial item",
                    item_id,
                )
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ValidationError("invalid commercial item or cover") from exc
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return created

    def update_commercial_item(self, item_id: Any, changes: dict[str, Any]) -> dict[str, Any]:
        with closing(self.connect()) as conn:
            conn.execute("begin immediate")
            try:
                current = self._require_row(
                    self._get_on(conn, "commercial_items", item_id),
                    "commercial item",
                    item_id,
                )
                merged = {**current, **changes}
                if merged["type"] not in {"image", "video"}:
                    raise ValidationError("invalid commercial item type")
                values = (
                    merged["project_id"],
                    merged["type"],
                    merged["src"],
                    merged["title"],
                    merged["poster"],
                    self._integer(merged["sort_order"], "sort_order"),
                    item_id,
                )
                conn.execute(
                    """update commercial_items set
                    project_id=?,type=?,src=?,title=?,poster=?,sort_order=? where id=?""",
                    values,
                )
                updated = self._require_row(
                    self._get_on(conn, "commercial_items", item_id),
                    "commercial item",
                    item_id,
                )
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ValidationError("invalid commercial item") from exc
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
                return updated

    def delete_commercial_item(self, item_id: Any) -> dict[str, Any]:
        current = self._require_row(
            self.get_commercial_item(item_id), "commercial item", item_id
        )
        with self.connect() as conn:
            conn.execute("delete from commercial_items where id=?", (item_id,))
        return current

    def reorder(self, scope: str, order: Iterable[Any], parent_id: Any = None) -> dict[str, Any]:
        if scope not in REORDER_SCOPES:
            raise ValidationError("invalid reorder scope")
        parent_column = REORDER_SCOPES[scope]
        if parent_column and parent_id is None:
            raise ValidationError(f"{scope} reorder requires a parent_id")
        changed = 0
        with self.connect() as conn:
            for index, record_id in enumerate(order):
                if parent_column:
                    cursor = conn.execute(
                        f"update {scope} set sort_order=? where id=? and {parent_column}=?",
                        (index, record_id, parent_id),
                    )
                else:
                    cursor = conn.execute(
                        f"update {scope} set sort_order=? where id=?", (index, record_id)
                    )
                changed += cursor.rowcount
        return {"updated": changed}

    def batch_delete(self, scope: str, ids: Iterable[Any]) -> dict[str, Any]:
        if scope not in BATCH_DELETE_SCOPES:
            raise ValidationError("invalid batch delete scope")
        record_ids = list(ids)
        if not record_ids:
            raise ValidationError("no ids provided")
        placeholders = ",".join("?" for _ in record_ids)
        with self.connect() as conn:
            cursor = conn.execute(
                f"delete from {scope} where id in ({placeholders})", record_ids
            )
        return {"deleted": cursor.rowcount}

    def bulk_import(self, groups: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        with self.connect() as conn:
            for group in groups:
                category = group.get("category", "portrait")
                if category not in VALID_CATEGORIES:
                    raise ValidationError("invalid photo category")
                date = self._validate_date(group.get("date", ""))
                cursor = conn.execute(
                    """insert into photo_groups
                    (category,title,description,date,cols,sort_order) values(?,?,?,?,?,?)""",
                    (
                        category,
                        group.get("title", ""),
                        group.get("description", ""),
                        date,
                        self._integer(group.get("cols", 3), "cols"),
                        self._sort_order(group),
                    ),
                )
                group_id = cursor.lastrowid
                images = group.get("images", [])
                for index, item in enumerate(images):
                    conn.execute(
                        """insert into photo_items
                        (group_id,src,title,description,sort_order) values(?,?,?,?,?)""",
                        (
                            group_id,
                            item.get("src", ""),
                            item.get("title", ""),
                            item.get("description", ""),
                            index,
                        ),
                    )
                created.append(
                    {"id": group_id, "date": date, "category": category, "count": len(images)}
                )
        return created

    def _frontend_strings(self) -> tuple[str, str]:
        content = self.state()
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
                        "category": group["category"],
                        "title": group["title"],
                        "description": group["description"],
                        "date": group["date"],
                        "cols": group["cols"],
                        "images": [
                            {
                                "src": item["src"],
                                "title": item["title"],
                                "description": item["description"],
                            }
                            for item in group["images"]
                        ],
                    }
                    for group in content["photoGroups"]
                ],
                ensure_ascii=False,
                indent=4,
            )
            + ";\n\n"
            "const videos = "
            + json.dumps(
                [
                    {
                        "title": video["title"],
                        "description": video["description"],
                        "url": video["url"],
                        "platform": video["platform"],
                        "source": video["source"],
                    }
                    for video in content["videos"]
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
                        "id": project["id"],
                        "client": project["client"],
                        "title": project["title"],
                        "description": project["description"],
                        "cover": project["cover"],
                        "year": project["year"],
                        "category": project["category"],
                        "items": [
                            {
                                "type": item["type"],
                                "src": item["src"],
                                "title": item["title"],
                                **({"poster": item["poster"]} if item["poster"] else {}),
                            }
                            for item in project["items"]
                        ],
                    }
                    for project in content["commercialProjects"]
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
        return data_js, commercial_js

    @staticmethod
    def _write_temporary(target: Path, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", dir=target.parent, delete=False, encoding="utf-8"
        )
        temporary_path = Path(handle.name)
        try:
            with handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return temporary_path

    @staticmethod
    def _write_temporary_bytes(target: Path, content: bytes) -> Path:
        handle = tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, delete=False)
        temporary_path = Path(handle.name)
        try:
            with handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return temporary_path

    def export_frontend(self) -> dict[str, Path]:
        data_js, commercial_js = self._frontend_strings()
        targets = (self.root / "data.js", self.root / "commercial.js")
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
        temporary_paths: list[Path] = []
        rollback_paths: dict[Path, Path | None] = {}
        replaced_targets: list[Path] = []
        retained_rollbacks: set[Path] = set()
        try:
            temporary_paths.append(self._write_temporary(targets[0], data_js))
            temporary_paths.append(self._write_temporary(targets[1], commercial_js))
            for target in targets:
                rollback_paths[target] = (
                    self._write_temporary_bytes(target, target.read_bytes())
                    if target.exists()
                    else None
                )
            for temporary_path, target in zip(temporary_paths, targets):
                os.replace(temporary_path, target)
                replaced_targets.append(target)
        except Exception as export_error:
            rollback_errors = []
            for target in reversed(replaced_targets):
                rollback_path = rollback_paths[target]
                try:
                    if rollback_path is None:
                        target.unlink(missing_ok=True)
                    else:
                        os.replace(rollback_path, target)
                except Exception as rollback_error:
                    rollback_errors.append(rollback_error)
                    if rollback_path is not None:
                        retained_rollbacks.add(rollback_path)
            if rollback_errors:
                retained = ", ".join(str(path) for path in retained_rollbacks)
                raise OSError(
                    f"export failed and atomic rollback files were retained: {retained}"
                ) from export_error
            raise
        finally:
            for temporary_path in temporary_paths:
                temporary_path.unlink(missing_ok=True)
            for rollback_path in rollback_paths.values():
                if rollback_path is not None and rollback_path not in retained_rollbacks:
                    rollback_path.unlink(missing_ok=True)
        return {"data": targets[0], "commercial": targets[1]}
