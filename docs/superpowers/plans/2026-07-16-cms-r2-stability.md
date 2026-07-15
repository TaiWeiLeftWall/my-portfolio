# CMS and R2 Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local photography CMS reliable, testable, versioned, and capable of authenticated R2 uploads whose SQLite records cannot silently diverge from cloud objects.

**Architecture:** The browser talks only to the loopback Python CMS. `cms_server.py` handles HTTP, `cms_db.py` owns SQLite and atomic exports, and `r2_client.py` owns authenticated Worker calls. The Worker streams validated image bodies to the `MY_BUCKET` binding, while Python coordinates upload/write and delete/delete operations with explicit compensation.

**Tech Stack:** Python 3.9 standard library, SQLite, static HTML/CSS/JavaScript, Node.js 24 syntax tests, Cloudflare Workers, R2, Wrangler JSONC.

## Global Constraints

- SQLite at `upload-tool/site_content.sqlite` remains the sole CMS data source and must never be deleted or replaced by test data.
- `data.js` and `commercial.js` are generated only through the CMS exporter; no task edits their content manually.
- Tests use temporary directories, temporary SQLite databases, and fake R2 clients; they must not contact the deployed Worker.
- The real CMS is accessed through `http://127.0.0.1:8090`, not `localhost`.
- Existing user changes in `upload-tool/r2-upload.js` are preserved until Task 5 deliberately replaces that file with an authenticated equivalent that retains `/delete` behavior.
- Existing deletions of `DESIGN-claude.md` and `DESIGN-nike.md`, and the untracked `AGENTS.md`, are outside this plan and must not be staged.
- Existing 10 orphaned `photo_items` rows are reported but not deleted.
- Real Worker deployment and real R2 mutation are deferred until the user supplies the R2 bucket name and authorizes the deployment configuration.

## File Map

- Modify `.gitignore`: track sanitized CMS source/tests while excluding state, media, caches, and secrets.
- Modify `upload-tool/cms.html`: remove inline behavior and load the tracked `cms.js`.
- Create `upload-tool/cms.js`: CMS UI state, editing, progress, retry, and API calls.
- Modify `upload-tool/cms_server.py`: loopback HTTP routing, request parsing, dependency wiring, and JSON errors.
- Create `upload-tool/cms_db.py`: SQLite schema, migrations, CRUD, ordering, health data, and atomic export.
- Create `upload-tool/r2_client.py`: configuration loading and authenticated Worker HTTP client.
- Modify `upload-tool/r2-upload.js`: authenticated, validated, streaming R2 Worker.
- Create `upload-tool/cms_config.example.json`: sanitized local configuration contract.
- Create `upload-tool/wrangler.example.jsonc`: sanitized Worker binding/secret contract.
- Create `upload-tool/tests/test_cms_db.py`: isolated database and export tests.
- Create `upload-tool/tests/test_cms_server.py`: isolated HTTP/API and compensation tests.
- Create `upload-tool/tests/test_r2_client.py`: Worker-client request/response tests with a fake opener.
- Create `upload-tool/tests/test_worker.mjs`: Worker tests with a fake R2 binding.
- Create `upload-tool/tests/check_cms_script.mjs`: HTML/JavaScript syntax check.

---

### Task 1: Versioned CMS Baseline and Immediate Startup Fixes

**Files:**
- Modify: `.gitignore:1-15`
- Modify: `upload-tool/cms_server.py:568-582`
- Modify: `upload-tool/cms.html:446`
- Create: `upload-tool/cms_config.example.json`
- Create: `upload-tool/tests/check_cms_script.mjs`
- Create: `upload-tool/tests/test_cms_server.py`

**Interfaces:**
- Produces: a tracked CMS source tree and two baseline regression checks.
- Consumes: no new application interface.

- [ ] **Step 1: Allow only sanitized CMS source and tests through `.gitignore`**

Replace the broad `upload-tool/` rule with explicit allow-list rules:

```gitignore
# Upload tool runtime state is local; sanitized source is versioned.
upload-tool/*
!upload-tool/cms.html
!upload-tool/cms.js
!upload-tool/cms_server.py
!upload-tool/cms_db.py
!upload-tool/r2_client.py
!upload-tool/r2-upload.js
!upload-tool/cms_config.example.json
!upload-tool/wrangler.example.jsonc
!upload-tool/tests/
!upload-tool/tests/**
```

Verify:

```powershell
git check-ignore -v upload-tool/site_content.sqlite upload-tool/media upload-tool/cms_config.json
git check-ignore -v upload-tool/cms_server.py upload-tool/cms.html
```

Expected: state/config paths are ignored; source paths produce no ignore match.

- [ ] **Step 2: Add the failing JavaScript syntax check**

Create `upload-tool/tests/check_cms_script.mjs`:

```javascript
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const tool = path.resolve(here, "..");
const html = fs.readFileSync(path.join(tool, "cms.html"), "utf8");
for (const [index, match] of [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].entries()) {
  new vm.Script(match[1], { filename: `cms-inline-${index}.js` });
}
const external = path.join(tool, "cms.js");
if (fs.existsSync(external)) {
  new vm.Script(fs.readFileSync(external, "utf8"), { filename: "cms.js" });
}
console.log("CMS scripts: OK");
```

Run: `node upload-tool/tests/check_cms_script.mjs`

Expected before the fix: FAIL at current `cms.html:446` with `SyntaxError: Invalid or unexpected token`.

- [ ] **Step 3: Add the failing script-entry regression test**

Create `upload-tool/tests/test_cms_server.py` with an AST check that requires runtime definitions before the blocking main entry:

```python
import ast
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "cms_server.py"


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
        self.assertLess(names["validate_date"], main_index)
        self.assertLess(names["validate_enum"], main_index)


if __name__ == "__main__":
    unittest.main()
```

Run: `python -m unittest upload-tool/tests/test_cms_server.py -v`

Expected before the fix: FAIL because `validate_date` and `validate_enum` follow the main entry.

- [ ] **Step 4: Apply only the two baseline fixes**

Move `VALID_CATEGORIES`, `VALID_COMMERCIAL_CATEGORIES`, `validate_date`, and `validate_enum` above `if __name__ == "__main__":`. Correct `cms.html:446` so the string ends with `</div>';`.

Create `upload-tool/cms_config.example.json`:

```json
{
  "r2_worker_url": "",
  "r2_upload_token": "",
  "request_timeout_seconds": 30,
  "max_upload_bytes": 15728640
}
```

- [ ] **Step 5: Verify the baseline passes without touching the real database**

Run:

```powershell
python -m py_compile upload-tool/cms_server.py
python -m unittest upload-tool/tests/test_cms_server.py -v
node upload-tool/tests/check_cms_script.mjs
```

Expected: Python compile succeeds, 1 unittest passes, and Node prints `CMS scripts: OK`.

- [ ] **Step 6: Commit the baseline**

```powershell
git add .gitignore upload-tool/cms.html upload-tool/cms_server.py upload-tool/cms_config.example.json upload-tool/tests/check_cms_script.mjs upload-tool/tests/test_cms_server.py
git commit -m "fix: restore a versioned CMS startup baseline"
```

### Task 2: SQLite Module, Migrations, and Atomic Export

**Files:**
- Create: `upload-tool/cms_db.py`
- Create: `upload-tool/tests/test_cms_db.py`
- Modify: `upload-tool/cms_server.py:33-317`

**Interfaces:**
- Produces: `Database(db_path, root, media_dir)`, `Database.initialize()`, `Database.state()`, `Database.health()`, `Database.export_frontend()`.
- Produces: CRUD methods returning plain dictionaries and raising `ValidationError` or `NotFoundError`.
- Consumes: existing SQLite schema and existing export shapes.

- [ ] **Step 1: Write isolated connection and cascade tests**

Create `upload-tool/tests/test_cms_db.py` with `tempfile.TemporaryDirectory()` and assertions for:

```python
db = Database(db_path=tmp / "site.sqlite", root=tmp, media_dir=tmp / "media")
db.initialize(seed=False)
with db.connect() as conn:
    self.assertEqual(conn.execute("pragma foreign_keys").fetchone()[0], 1)
group_id = db.create_photo_group({"category": "portrait", "date": "2026-07", "cols": 3})["id"]
item_id = db.create_photo_item({"group_id": group_id, "src": "https://example.test/images/a.jpg"})["id"]
db.delete_photo_group(group_id)
self.assertIsNone(db.get_photo_item(item_id))
```

Add tests that `health()["orphan_photo_items"]` reports but does not delete an inserted orphan, and that editing a title preserves the previous `sort_order`.

Run: `python -m unittest upload-tool/tests/test_cms_db.py -v`

Expected: FAIL because `cms_db.py` does not exist.

- [ ] **Step 2: Implement the database connection and versioned initialization**

Implement `Database.connect()` so every connection runs:

```python
conn = sqlite3.connect(self.db_path, timeout=5)
conn.row_factory = sqlite3.Row
conn.execute("pragma foreign_keys = on")
conn.execute("pragma busy_timeout = 5000")
return conn
```

`initialize(seed=False)` must create schema, set WAL on the initialization connection, inspect `pragma user_version`, back up an existing database before a version increase, apply migrations in one transaction, and set the new version. It must not delete or rewrite orphan rows.

- [ ] **Step 3: Move state and CRUD into `Database`**

Implement explicit methods for photo groups/items, videos, commercial projects/items, reorder, and batch delete. Use a whitelist mapping for reorder identifiers:

```python
REORDER_SCOPES = {
    "photo_groups": None,
    "photo_items": "group_id",
    "videos": None,
    "commercial_projects": None,
    "commercial_items": "project_id",
}
```

Update methods must fetch the current row, merge only provided fields, validate the merged record, execute the update, and return the updated row. A missing row raises `NotFoundError`.

- [ ] **Step 4: Implement atomic export**

Generate both strings in memory first. Write each with `tempfile.NamedTemporaryFile(dir=target.parent, delete=False, encoding="utf-8")`, call `flush()` and `os.fsync()`, then use `os.replace()` only after both temporary writes succeed. On any exception, unlink temporary files and preserve both prior generated files.

Add a test that patches the second temporary write to raise `OSError` and verifies the original contents of both target files are unchanged.

- [ ] **Step 5: Wire `cms_server.py` to one `Database` instance**

At module scope create configuration paths only. In `main()`, instantiate and initialize `Database`, assign it to the handler dependency, then start the loopback server. Keep the `if __name__ == "__main__": main()` block as the final executable statement.

- [ ] **Step 6: Run database and baseline tests**

```powershell
python -m unittest discover -s upload-tool/tests -p "test_*.py" -v
node upload-tool/tests/check_cms_script.mjs
```

Expected: all tests pass and no file under the real `upload-tool/site_content.sqlite*` changes.

- [ ] **Step 7: Commit the database layer**

```powershell
git add upload-tool/cms_db.py upload-tool/cms_server.py upload-tool/tests/test_cms_db.py
git commit -m "refactor: isolate CMS database transactions"
```

### Task 3: Stable HTTP API and Error Contract

**Files:**
- Modify: `upload-tool/cms_server.py`
- Modify: `upload-tool/tests/test_cms_server.py`

**Interfaces:**
- Produces: JSON errors shaped as `{ "ok": false, "code": string, "message": string }`.
- Produces: `GET /api/health`, existing CRUD routes, and no mutating GET route.
- Consumes: `Database` methods from Task 2.

- [ ] **Step 1: Add an isolated HTTP harness**

In `test_cms_server.py`, import the module without running `main()`, bind `ThreadingHTTPServer(("127.0.0.1", 0), Handler)`, inject a temporary `Database`, run `serve_forever()` in a daemon thread, and stop it with `shutdown()` in cleanup.

Add tests for malformed JSON, invalid category/date, missing IDs, a successful photo-group POST, and `/api/health`. Add a test asserting `GET /api/bulk-import-form?...` returns 404 or 405 and does not change row counts.

- [ ] **Step 2: Add typed application errors and one dispatcher wrapper**

Define `ApiError(status, code, message)` and translate `ValidationError`, `NotFoundError`, malformed JSON, `sqlite3.IntegrityError`, and unexpected exceptions into JSON. Unexpected exceptions are logged with `self.log_error()` and return `internal_error` without leaking stack traces.

- [ ] **Step 3: Bound and validate request bodies**

`read_json()` must reject missing/invalid `Content-Length`, lengths above 1 MiB for JSON, invalid UTF-8, non-object JSON, and truncated bodies. Return 400 or 413 with the stable error contract.

- [ ] **Step 4: Remove mutating GET and preserve resource order**

Delete `/api/bulk-import-form`. Route POST/PUT/DELETE through `Database`; do not synthesize default `sort_order=0` on edit.

- [ ] **Step 5: Verify and commit**

```powershell
python -m unittest upload-tool/tests/test_cms_server.py upload-tool/tests/test_cms_db.py -v
git add upload-tool/cms_server.py upload-tool/tests/test_cms_server.py
git commit -m "refactor: stabilize CMS API responses"
```

### Task 4: Authenticated Python R2 Client

**Files:**
- Create: `upload-tool/r2_client.py`
- Create: `upload-tool/tests/test_r2_client.py`
- Modify: `upload-tool/cms_config.example.json`

**Interfaces:**
- Produces: `CmsConfig.load(path, environ) -> CmsConfig`.
- Produces: `R2Client.health()`, `R2Client.upload(content, content_type, category, date, filename) -> R2Object`, `R2Client.delete(key) -> None`.
- Produces: `R2Object(key: str, url: str)` and `R2Error(code, message, retryable)`.

- [ ] **Step 1: Write fake-opener tests**

Inject an opener callable into `R2Client`. Tests must assert exact method, URL, `Authorization: Bearer token`, content type, request body, timeout, decoded response, and error mapping for HTTP 401, HTTP 503, timeout, malformed JSON, and missing `key`/`url`.

- [ ] **Step 2: Implement local configuration precedence**

Load JSON from `cms_config.json`, then override non-empty values with `R2_WORKER_URL`, `R2_UPLOAD_TOKEN`, `R2_REQUEST_TIMEOUT_SECONDS`, and `R2_MAX_UPLOAD_BYTES`. Never log or return the token. Missing URL/token makes `configured` false but does not prevent the CMS from starting.

- [ ] **Step 3: Implement bounded Worker requests**

Use `urllib.request.Request` and the injected opener. Upload sends raw bytes to `/upload` with encoded `category`, `date`, and `filename` query parameters. Delete posts JSON to `/delete`. Parse at most 64 KiB of JSON response and map network/HTTP errors to stable `R2Error` values.

- [ ] **Step 4: Verify and commit**

```powershell
python -m unittest upload-tool/tests/test_r2_client.py -v
git add upload-tool/r2_client.py upload-tool/cms_config.example.json upload-tool/tests/test_r2_client.py
git commit -m "feat: add authenticated R2 client"
```

### Task 5: Secure and Stream the Cloudflare Worker

**Files:**
- Modify: `upload-tool/r2-upload.js`
- Create: `upload-tool/wrangler.example.jsonc`
- Create: `upload-tool/tests/test_worker.mjs`

**Interfaces:**
- Produces: authenticated `GET /health`, `POST /upload`, and `POST /delete`.
- Consumes: `env.MY_BUCKET`, `env.UPLOAD_TOKEN`, and `env.PUBLIC_BASE_URL`.

- [ ] **Step 1: Write Worker tests against a fake R2 binding**

Load the Worker as an ES module using a base64 `data:` URL. The fake bucket records `put(key, body, options)` and `delete(key)`. Test missing/wrong/correct token, invalid MIME, missing body, invalid category/date, upload response, deletion prefix rejection, and successful deletion.

Run: `node --test upload-tool/tests/test_worker.mjs`

Expected before implementation: authentication tests fail.

- [ ] **Step 2: Implement constant-time token verification**

Hash the provided and configured tokens with SHA-256 and compare the fixed-length digests using `crypto.subtle.timingSafeEqual`. A missing configured secret returns 503; missing or invalid client credentials return 401.

- [ ] **Step 3: Implement validated streaming upload**

Accept only `image/jpeg`, `image/png`, and `image/webp`. Validate `Content-Length` against the configured 15 MiB limit when present. Validate category against `portrait`, `landscape`, `street`, `performance`, and `official`; validate date as `YYYY-MM-DD`. Derive extension from MIME, create `images/<category>/<date>/<uuid>.<ext>`, and call:

```javascript
await env.MY_BUCKET.put(key, request.body, {
  httpMetadata: { contentType },
});
```

Build the returned URL from `env.PUBLIC_BASE_URL` and the encoded key; remove the hardcoded R2 public hostname and `Math.random()`.

- [ ] **Step 4: Implement restricted idempotent deletion and structured logs**

Accept `{ "key": "images/..." }`, reject other prefixes, await `env.MY_BUCKET.delete(key)`, and return `{ ok: true, key }`. Log request ID, operation, status, key, and error code as JSON; never log the token.

- [ ] **Step 5: Add a sanitized Wrangler contract**

Create `wrangler.example.jsonc` with empty local deployment values rather than real infrastructure identifiers:

```jsonc
{
  "name": "upload-tool",
  "main": "r2-upload.js",
  "compatibility_date": "2026-07-16",
  "r2_buckets": [{ "binding": "MY_BUCKET", "bucket_name": "" }],
  "vars": { "PUBLIC_BASE_URL": "" },
  "secrets": { "required": ["UPLOAD_TOKEN"] },
  "observability": { "enabled": true }
}
```

- [ ] **Step 6: Verify and commit the deliberate replacement of the user's Worker diff**

```powershell
Get-Content -Raw upload-tool/r2-upload.js | node --input-type=module --check
node --test upload-tool/tests/test_worker.mjs
git diff -- upload-tool/r2-upload.js
git add upload-tool/r2-upload.js upload-tool/wrangler.example.jsonc upload-tool/tests/test_worker.mjs
git commit -m "feat: secure R2 upload worker"
```

Expected: the replacement retains authenticated `/delete` behavior, removes wildcard CORS and hardcoded public URL, and all Worker tests pass.

### Task 6: Compensating Upload and Coordinated Delete API

**Files:**
- Modify: `upload-tool/cms_server.py`
- Modify: `upload-tool/cms_db.py`
- Modify: `upload-tool/tests/test_cms_server.py`

**Interfaces:**
- Produces: `POST /api/photo-items/upload` multipart endpoint.
- Produces: `GET /api/health` fields `database`, `r2.configured`, `r2.reachable`, and orphan counts.
- Consumes: `R2Client` and `Database`.

- [ ] **Step 1: Add compensation tests with a fake R2 client**

Cover: upload success plus DB success; R2 failure with no DB insert; DB failure after upload causing exactly one delete; delete R2 failure preserving the DB row; delete R2 success removing the DB row. Use only temporary SQLite and fake byte content.

- [ ] **Step 2: Implement bounded multipart parsing**

Accept one field named `image` plus `group_id`, `category`, and `date`. Reject requests above the configured byte limit before parsing, non-image MIME, missing group, and mismatched group/category. Do not save the upload to `media/`.

- [ ] **Step 3: Implement the upload compensation sequence**

Call `r2.upload()`, then `db.create_photo_item()`. If the DB call fails, call `r2.delete(uploaded.key)` inside a nested error boundary and return `database_write_failed` with a boolean `r2_rollback_succeeded`. Do not return success unless both operations succeed.

- [ ] **Step 4: Coordinate photo and group deletion**

Read all affected rows before mutation, extract only valid R2 keys, await cloud deletion, then delete in a database transaction. Local media paths skip R2. A cloud error leaves all database rows intact for retry.

- [ ] **Step 5: Verify and commit**

```powershell
python -m unittest upload-tool/tests/test_cms_server.py upload-tool/tests/test_cms_db.py upload-tool/tests/test_r2_client.py -v
git add upload-tool/cms_server.py upload-tool/cms_db.py upload-tool/tests/test_cms_server.py
git commit -m "feat: coordinate CMS and R2 media changes"
```

### Task 7: Split the CMS Script and Replace Direct R2 Calls

**Files:**
- Modify: `upload-tool/cms.html`
- Create: `upload-tool/cms.js`
- Modify: `upload-tool/tests/check_cms_script.mjs`

**Interfaces:**
- Consumes: `/api/state`, `/api/health`, CRUD endpoints, and `/api/photo-items/upload`.
- Produces: explicit edit mode and an upload queue with retryable failed items.

- [ ] **Step 1: Move inline JavaScript verbatim into `cms.js` and keep syntax green**

Replace the inline script with `<script src="/upload-tool/cms.js" defer></script>`. Update the syntax test to assert exactly one external CMS script and compile `cms.js`.

- [ ] **Step 2: Replace the global `savePanel` override**

Represent editor state as `{ mode: "create" | "edit", type, data }`. `savePanel()` selects POST or PUT from that state. `closePanel()` resets it. Add a `saving` guard that disables the save button until the request settles.

- [ ] **Step 3: Replace single upload with the local multipart endpoint**

After compression, always name the blob with `.jpg`, append it as `image`, append group/category/date fields, and call `/api/photo-items/upload`. Remove `R2_UPLOAD_URL`, `R2_BASE_URL`, guessed public URLs, and silent nested catches.

- [ ] **Step 4: Replace batch import with sequential compensated uploads**

Group selected files by `YYYY-MM`, create each group with POST, then upload its files through `/api/photo-items/upload`. Track each item as `pending`, `uploading`, `succeeded`, or `failed`. Remove succeeded items; preserve failed items and their server messages for a retry action. Never navigate to `/api/bulk-import-form`.

- [ ] **Step 5: Route deletion only through the CMS**

Remove `r2KeyFromUrl()` and `deleteFromR2()`. Await the CMS DELETE response and reload state only on success.

- [ ] **Step 6: Add health indicators and accurate completion messages**

Load `/api/health` with state. Display database status, R2 configured/reachable state, and orphan count. Completion text includes exact succeeded and failed counts; any failure keeps the modal open.

- [ ] **Step 7: Verify and commit**

```powershell
node upload-tool/tests/check_cms_script.mjs
Select-String -Path upload-tool/cms.js -Pattern "R2_UPLOAD_URL|R2_BASE_URL|bulk-import-form|deleteFromR2"
git add upload-tool/cms.html upload-tool/cms.js upload-tool/tests/check_cms_script.mjs
git commit -m "refactor: route CMS media through the local API"
```

Expected: syntax passes and the forbidden-pattern search returns no matches.

### Task 8: Full Local Verification and Deployment Readiness

**Files:**
- Modify only if tests expose a defect: files owned by Tasks 1-7
- Do not modify: `upload-tool/site_content.sqlite` except through a normal, backed-up CMS initialization
- Do not deploy until required real configuration is provided

**Interfaces:**
- Verifies all interfaces from prior tasks.

- [ ] **Step 1: Run the complete isolated suite**

```powershell
python -m unittest discover -s upload-tool/tests -p "test_*.py" -v
node upload-tool/tests/check_cms_script.mjs
node --test upload-tool/tests/test_worker.mjs
Get-Content -Raw upload-tool/r2-upload.js | node --input-type=module --check
git diff --check
```

Expected: all tests and syntax checks pass; `git diff --check` reports no whitespace errors.

- [ ] **Step 2: Back up and inspect the real database before first refactored startup**

Create a timestamped copy beside the database using `Copy-Item -LiteralPath`. Verify `PRAGMA integrity_check` on both original and backup. Record row counts and orphan counts. Do not remove the 10 known orphan rows.

- [ ] **Step 3: Start and exercise the local CMS**

Run `python upload-tool/cms_server.py`, open `http://127.0.0.1:8090`, and verify the three tabs, group detail, edit/save, drag sorting, delete confirmation, batch modal, health indicators, and export. Use a temporary local-only item or a fake Worker configuration until real Worker credentials are approved.

- [ ] **Step 4: Verify generated/static frontend behavior**

After an explicit CMS export, validate `data.js` and `commercial.js` with `node --check` through a VM-loading test, then open `index.html`, `commercial.html`, `commercial-detail.html`, `about.html`, and `videos.html` from the CMS server and confirm no console errors.

- [ ] **Step 5: Prepare but do not guess real Cloudflare values**

Request the real R2 bucket name. Generate a strong upload token locally, place the Worker URL/token only in ignored `cms_config.json`, set the same value with `npx wrangler secret put UPLOAD_TOKEN`, and populate the ignored `wrangler.jsonc` with the supplied bucket name and existing public base URL. Show the exact diff of Worker source/config without printing the token.

- [ ] **Step 6: Deploy only after explicit confirmation, then perform one reversible smoke test**

Run `npx wrangler deploy r2-upload.js` from `upload-tool/`. Upload one small test image through the CMS, verify the SQLite row and public URL, delete it through the CMS, and verify both the row and R2 object are gone.

- [ ] **Step 7: Final review and commit any verification-only fixes**

```powershell
git status --short
git diff --stat
```

Stage only files owned by this plan. Do not stage the unrelated deleted design files or `AGENTS.md`. If verification required code fixes, commit them as `fix: complete CMS and R2 verification`; otherwise create no empty commit.

## Completion Criteria

- The CMS loads with valid JavaScript and all write routes return structured JSON instead of disconnecting.
- New and edited content persists without resetting sort order.
- SQLite foreign keys protect all newly managed relationships; known pre-existing orphans remain reported and untouched.
- Browser code contains no Worker URL, public R2 URL, or secret.
- Upload success means both R2 and SQLite succeeded; DB failure triggers verified R2 compensation.
- Delete failure preserves enough database state to retry.
- Batch failures remain visible and retryable.
- Worker upload/delete require a secret and restrict keys and MIME types.
- Exports are atomic and the static site still renders all pages.
- Sanitized CMS source and tests are tracked; database, media, cache, and real configuration remain ignored.
